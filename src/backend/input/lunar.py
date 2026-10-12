"""Lunar helpers. Deterministic calendar math lives here, never in prompts."""

from __future__ import annotations


def resolve_lunar(value: dict) -> str | None:
    """Lunar {year, month, day} ref to ISO date. Roundtrip-checked, else None."""
    try:
        year, month, day = int(value["year"]), int(value["month"]), int(value["day"])
        leap = bool(value.get("leap", False))
        if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 30):
            return None
        from vi_lunaire import lunar_to_solar, solar_to_lunar

        solar = lunar_to_solar(year, month, day, leap=leap)
        back = solar_to_lunar(solar.year, solar.month, solar.day)
        if (back.year, back.month, back.day, back.leap) != (year, month, day, leap):
            return None
        return solar.isoformat()
    except (KeyError, TypeError, ValueError):
        return None
