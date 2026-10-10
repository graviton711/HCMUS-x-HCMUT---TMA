"""Lunar helpers. Deterministic calendar math lives here, never in prompts."""

from __future__ import annotations

from datetime import date


def tet_frame(ref_iso: str) -> str:
    """Upcoming-Tet facts for `ref_iso` (YYYY-MM-DD), computed with vi_lunaire.

    Gives the model a year frame so it never does lunar arithmetic itself.
    """
    try:
        ref = date.fromisoformat(ref_iso)
    except ValueError:
        return ""
    for lunar_year in (ref.year - 1, ref.year, ref.year + 1, ref.year + 2):
        try:
            from vi_lunaire import lunar_to_solar

            tet = lunar_to_solar(lunar_year, 1, 1)
        except (ValueError, OverflowError):
            continue
        if tet > ref:
            return (
                f"Tết sắp tới sau {ref_iso}: mùng 1 = {tet.isoformat()}"
                f" (tháng Giêng năm âm {lunar_year});"
                f" tháng Chạp trước đó thuộc năm âm {lunar_year - 1}."
            )
    return ""


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
