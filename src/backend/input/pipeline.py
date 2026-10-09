"""Form/text → Requirement. Form wins conflicts; the rest is `missing`."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.input.nim import NimClient
from backend.models import Condition, Requirement, uid
from backend.settings import InputCfg

_HARD_FIELDS = {
    "destination", "departure_city", "date_from", "date_to",
    "budget_max", "duration_days", "transport", "accommodation",
}
_FORM_MAP = {
    "destinations": "destination",
    "departure_city": "departure_city",
    "date_from": "date_from",
    "date_to": "date_to",
    "budget_max": "budget_max",
    "duration_days": "duration_days",
    "transport": "transport",
    "accommodation": "accommodation",
}

_MONEY = re.compile(r"(\d[\d.,]*)\s*(triệu|tr|tỷ|tỉ|nghìn|k|đ|vnd|trieu|ty|ti|nghin)?", re.IGNORECASE)
_BUDGET_WORDS = ("toi da", "duoi", "khong qua", "ngan sach")


def _strip_vi(text: str) -> str:
    """De-accent Vietnamese so undiacritized input still matches."""
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn").lower()


def _money_to_vnd(raw: str, units: dict[str, int]) -> int | None:
    match = _MONEY.search(raw)
    if not match:
        return None
    num_raw, unit = match.group(1), _strip_vi(match.group(2) or "")
    table = {_strip_vi(k): v for k, v in units.items()}
    if unit in table:
        return int(float(num_raw.replace(",", ".")) * table[unit])
    digits = re.sub(r"\D", "", num_raw)
    return int(digits) if digits else None


def keyword_extract(text: str, cfg: InputCfg | None = None,
                    known_places: list[str] | None = None) -> dict[str, Any]:
    """Offline fallback: destinations + budget only. Everything else is missing.

    Place names come from the catalog being searched, not from configs.
    """
    cfg = cfg or InputCfg()
    low = _strip_vi(text)
    hard: list[dict[str, Any]] = []
    for place in known_places or []:
        key = _strip_vi(place)
        if key not in low:
            continue
        before = low.split(key)[0][-cfg.window_before:]
        field = "departure_city" if ("tu" in before.split() or "xuat phat" in before) else "destination"
        hard.append({"field": field, "operator": "contains", "value": place})
    budget_at = -1
    for w in _BUDGET_WORDS:
        at = low.find(w)
        if at != -1 and (budget_at == -1 or at < budget_at):
            budget_at = at
    if budget_at != -1:
        amount = _money_to_vnd(low[budget_at:budget_at + cfg.window_budget], cfg.money_units)
        if amount is not None:
            hard.append({"field": "budget_max", "operator": "lte", "value": amount})
    return {"hard": hard, "soft": [], "travelers": 1}


def _clean_hard(items: list[dict[str, Any]], quote: str, cfg: InputCfg) -> list[Condition]:
    out: list[Condition] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", ""))
        if field not in _HARD_FIELDS:
            continue
        value = item.get("value")
        if field == "budget_max":
            value = value if isinstance(value, int) else _money_to_vnd(str(value or ""), cfg.money_units)
            if value is None:
                continue
        if value is None or value == "":
            continue
        out.append(Condition(id=f"h{i+1}", field=field,
                             operator=str(item.get("operator", "eq")),
                             value=value, strength="hard", quote=quote[:cfg.quote_chars]))
    return out


def build_requirement(text: str = "", form: dict[str, Any] | None = None,
                      nim: NimClient | None = None, cfg: InputCfg | None = None,
                      known_places: list[str] | None = None) -> Requirement:
    form = form or {}
    cfg = cfg or InputCfg()
    conditions: list[Condition] = []
    seen = set()

    for form_key, field in _FORM_MAP.items():
        value = form.get(form_key)
        if value is None or value == "" or value == []:
            continue
        if field == "destination" and isinstance(value, list):
            for place in value:
                conditions.append(Condition(id=f"h{len(conditions)+1}", field=field,
                                            operator="contains", value=str(place), strength="hard"))
        else:
            conditions.append(Condition(id=f"h{len(conditions)+1}", field=field,
                                        operator="eq", value=value, strength="hard"))
        seen.add(field)

    travelers = form.get("travelers", 1)
    travelers = travelers if isinstance(travelers, int) and travelers > 0 else 1

    soft: list[Condition] = []
    if text.strip():
        if nim is not None and nim.configured():
            parsed = nim.extract(text)
        else:
            parsed = keyword_extract(text, cfg, known_places)
        items = [item for item in parsed.get("hard", [])
                 if isinstance(item, dict) and item.get("field") not in seen]
        conditions.extend(_clean_hard(items, text, cfg))
        raw_soft = parsed.get("soft", [])
        if isinstance(raw_soft, list):
            for i, s in enumerate(raw_soft):
                if isinstance(s, dict) and s.get("text"):
                    soft.append(Condition(id=f"s{i+1}", field="preference",
                                          operator="contains", value=str(s["text"]),
                                          strength="soft", quote=text[:cfg.quote_chars]))
        if isinstance(parsed.get("travelers"), int) and parsed["travelers"] > 0 and "travelers" not in form:
            travelers = parsed["travelers"]

    conditions.extend(soft)
    missing = [f for f in ("destination", "date_from", "budget_max")
               if f not in {c.field for c in conditions if c.strength == "hard"}]
    return Requirement(id=uid("req"), conditions=conditions, missing=missing,
                       raw_text=text, travelers=travelers)
