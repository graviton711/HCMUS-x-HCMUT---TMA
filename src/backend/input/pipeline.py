"""Form/text → Requirement. Form wins conflicts; the rest is `missing`."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.input.nim import NimClient
from backend.models import Condition, Requirement, uid

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
_KNOWN_PLACES = ["đà lạt", "phú quốc", "hạ long", "sài gòn", "hà nội", "đà nẵng", "nha trang", "huế"]


def _strip_vi(text: str) -> str:
    """De-accent Vietnamese so undiacritized input still matches."""
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn").lower()


def _money_to_vnd(raw: str) -> int | None:
    match = _MONEY.search(raw)
    if not match:
        return None
    num_raw, unit = match.group(1), (match.group(2) or "").lower()
    if unit in ("tỷ", "tỉ", "triệu", "tr", "nghìn", "k", "ty", "ti", "trieu", "nghin"):
        num = float(num_raw.replace(",", "."))
        factor = {"tỷ": 1_000_000_000, "tỉ": 1_000_000_000, "ty": 1_000_000_000, "ti": 1_000_000_000,
                  "triệu": 1_000_000, "tr": 1_000_000, "trieu": 1_000_000,
                  "nghìn": 1_000, "k": 1_000, "nghin": 1_000}[unit]
        return int(num * factor)
    digits = re.sub(r"\D", "", num_raw)
    return int(digits) if digits else None


def keyword_extract(text: str) -> dict[str, Any]:
    """Offline fallback: destinations + budget only. Everything else is missing."""
    low = _strip_vi(text)
    hard: list[dict[str, Any]] = []
    for place in _KNOWN_PLACES:
        key = _strip_vi(place)
        if key not in low:
            continue
        before = low.split(key)[0][-16:]
        field = "departure_city" if ("tu" in before.split() or "xuat phat" in before) else "destination"
        hard.append({"field": field, "operator": "contains", "value": place})
    budget_at = -1
    for w in ("toi da", "duoi", "khong qua", "ngan sach"):
        at = low.find(w)
        if at != -1 and (budget_at == -1 or at < budget_at):
            budget_at = at
    if budget_at != -1:
        amount = _money_to_vnd(low[budget_at:budget_at + 40])
        if amount is not None:
            hard.append({"field": "budget_max", "operator": "lte", "value": amount})
    return {"hard": hard, "soft": [], "travelers": 1}


def _clean_hard(items: list[dict[str, Any]], quote: str) -> list[Condition]:
    out: list[Condition] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", ""))
        if field not in _HARD_FIELDS:
            continue
        value = item.get("value")
        if field == "budget_max":
            value = value if isinstance(value, int) else _money_to_vnd(str(value or ""))
            if value is None:
                continue
        if value is None or value == "":
            continue
        out.append(Condition(id=f"h{i+1}", field=field,
                             operator=str(item.get("operator", "eq")),
                             value=value, strength="hard", quote=quote[:200]))
    return out


def build_requirement(text: str = "", form: dict[str, Any] | None = None,
                      nim: NimClient | None = None) -> Requirement:
    form = form or {}
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
            parsed = keyword_extract(text)
        for item in parsed.get("hard", []):
            if isinstance(item, dict) and item.get("field") not in seen:
                conditions.extend(_clean_hard([item], text))
        raw_soft = parsed.get("soft", [])
        if isinstance(raw_soft, list):
            for i, s in enumerate(raw_soft):
                if isinstance(s, dict) and s.get("text"):
                    soft.append(Condition(id=f"s{i+1}", field="preference",
                                          operator="contains", value=str(s["text"]),
                                          strength="soft", quote=text[:200]))
        if isinstance(parsed.get("travelers"), int) and parsed["travelers"] > 0 and "travelers" not in form:
            travelers = parsed["travelers"]

    conditions.extend(soft)
    missing = [f for f in ("destination", "date_from", "budget_max")
               if f not in {c.field for c in conditions if c.strength == "hard"}]
    return Requirement(id=uid("req"), conditions=conditions, missing=missing,
                       raw_text=text, travelers=travelers)
