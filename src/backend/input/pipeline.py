"""Form/text → Requirement. Form wins conflicts; the rest is `missing`."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.errors import AppError
from backend.input.lunar import resolve_lunar as _resolve_lunar
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

def _strip_vi(text: str) -> str:
    """De-accent Vietnamese so undiacritized input still matches."""
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn").lower()


def _money_pattern(units: dict[str, int]) -> re.Pattern[str]:
    alts = sorted({_strip_vi(k) for k in units}, key=len, reverse=True)
    return re.compile(r"(\d[\d.,]*)\s*(" + "|".join(alts) + r")?", re.IGNORECASE)


def _money_to_vnd(raw: str, units: dict[str, int]) -> int | None:
    match = _money_pattern(units).search(raw)
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
    if cfg is None:
        raise AppError("CONFIG_MISSING", "Thiếu InputCfg.", 500)
    low = _strip_vi(text)
    hard: list[dict[str, Any]] = []
    for place in known_places or []:
        key = _strip_vi(place)
        if key not in low:
            continue
        before = low.split(key)[0][-cfg.window_before:]
        words = before.split()
        markers = [_strip_vi(m) for m in cfg.departure_markers]
        # Single-syllable markers match whole words only ("tu" must not hit "tuoi"/"tour");
        # multi-word markers match substrings.
        hit = any((m in words) if " " not in m else (m in before) for m in markers)
        field = "departure_city" if hit else "destination"
        hard.append({"field": field, "operator": "contains", "value": place})
    budget_at = -1
    for w in [_strip_vi(b) for b in cfg.budget_words]:
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
        if field in ("date_from", "date_to") and isinstance(value, dict):
            if value.get("calendar") != "lunar":
                continue
            value = _resolve_lunar(value)
            if value is None:
                continue
        if value is None or value == "":
            continue
        operator = str(item.get("operator", "eq"))
        if operator == "contains" and isinstance(value, list):
            # Shape normalization: single-element lists unwrap, multi becomes any.
            if len(value) == 1:
                value = value[0]
            elif value:
                operator = "any"
            else:
                continue
        if operator == "any":
            vals = [v for v in (value if isinstance(value, list) else [value])
                    if v not in (None, "")]
            if not vals:
                continue
            if len(vals) == 1:
                operator, value = "contains", vals[0]
            else:
                value = vals
        out.append(Condition(id=f"h{i+1}", field=field,
                             operator=operator,
                             value=value, strength="hard", quote=quote[:cfg.quote_chars]))
    return out


def build_requirement(text: str = "", form: dict[str, Any] | None = None,
                      nim: NimClient | None = None, cfg: InputCfg | None = None,
                      known_places: list[str] | None = None, ref_date: str = "") -> Requirement:
    form = form or {}
    if cfg is None:
        raise AppError("CONFIG_MISSING", "Thiếu InputCfg.", 500)
    conditions: list[Condition] = []
    seen = set()

    for form_key, field in _FORM_MAP.items():
        value = form.get(form_key)
        if value is None or value == "" or value == []:
            continue
        if field == "destination" and isinstance(value, list):
            places = list(dict.fromkeys(str(place) for place in value if str(place).strip()))
            if places:
                conditions.append(Condition(
                    id=f"h{len(conditions)+1}", field=field,
                    operator="contains" if len(places) == 1 else "any",
                    value=places[0] if len(places) == 1 else places,
                    strength="hard",
                ))
        else:
            conditions.append(Condition(id=f"h{len(conditions)+1}", field=field,
                                        operator="eq", value=value, strength="hard"))
        seen.add(field)

    travelers = form.get("travelers", 1)
    travelers = travelers if isinstance(travelers, int) and travelers > 0 else 1

    soft: list[Condition] = []
    if text.strip():
        if nim is not None and nim.configured():
            parsed = nim.extract(text, ref_date)
        else:
            parsed = keyword_extract(text, cfg, known_places)
        items = [item for item in parsed.get("hard", [])
                 if isinstance(item, dict) and item.get("field") not in seen]
        # Budgets must be grounded in an explicit number in the text.
        # Form budgets bypass this (explicit user data, trusted).
        if nim is not None and nim.configured() and not re.search(r"\d", text):
            items = [it for it in items if it.get("field") != "budget_max"]
        conditions.extend(_clean_hard(items, text, cfg))
        raw_soft = parsed.get("soft", [])
        if isinstance(raw_soft, list):
            for i, s in enumerate(raw_soft):
                pref = s.get("text") if isinstance(s, dict) else s
                if isinstance(pref, str) and pref.strip():
                    soft.append(Condition(id=f"s{i+1}", field="preference",
                                          operator="contains", value=pref.strip(),
                                          strength="soft", quote=pref[:cfg.quote_chars]))
        if isinstance(parsed.get("travelers"), int) and parsed["travelers"] > 0 and "travelers" not in form:
            travelers = parsed["travelers"]

    conditions.extend(soft)
    have = {c.field for c in conditions if c.strength == "hard"}
    missing = [f for f in cfg.required_slots if f not in have]
    return Requirement(id=uid("req"), conditions=conditions, missing=missing,
                       raw_text=text, travelers=travelers)
