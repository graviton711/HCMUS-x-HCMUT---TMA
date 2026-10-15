"""Shared group-cost math for metric profiles and what-if scenarios.

Both callers implement the same age-group and per-unit rules; only the
validation source and the returned payload differ, so those stay with the
caller. Anything changed here must keep totals byte-identical: they feed
demo-facing money numbers.
"""

from __future__ import annotations

_AGE_GROUPS = ("adult", "child", "small_child", "infant")


def age_group_total(
    price_by_age: dict[str, int | None],
    listed_price: int | None,
    mix: dict[str, int],
) -> tuple[int | None, str | None]:
    """Sum age-group prices over a validated party mix.

    Returns ``(total, None)`` on success, ``(None, missing_group)`` when a
    priced group has no price.
    """
    total = 0
    for age_group in _AGE_GROUPS:
        count = mix.get(age_group, 0)
        if not count:
            continue
        age_price = (price_by_age or {}).get(age_group)
        if age_price is None and age_group == "adult":
            age_price = listed_price
        if age_price is None:
            return None, age_group
        total += age_price * count
    return total, None


def exposure_quantity(
    unit: str,
    *,
    mix: dict[str, int],
    party: int | None,
    duration_days: int | None,
    duration_nights: int | None = None,
    nights: int | None = None,
    rooms: int | None = None,
) -> int | None:
    """Resolve a priced-exposure unit to a quantity.

    ``party`` is the validated headcount (None when the mix is unknown or
    inconsistent); scenarios pass the user-confirmed headcount, metrics pass
    it only when the mix sums to the request total. ``nights``/``rooms``
    override tour durations only when the scenario assumes them.
    """
    if unit == "per_booking":
        return 1
    if unit == "per_person":
        return party
    if unit == "per_adult":
        return mix.get("adult") if "adult" in mix else None
    if unit == "per_child":
        return mix.get("child", 0) + mix.get("small_child", 0) if mix else None
    if unit == "per_day":
        return duration_days
    if unit == "per_night":
        return nights if nights is not None else duration_nights
    if unit == "per_room":
        return rooms
    return None
