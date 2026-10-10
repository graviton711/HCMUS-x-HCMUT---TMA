"""Reject provably expired discovery windows without altering historical requirements."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from domain.common import AppError, instant, now
from domain.requirements import DateValue


def future_windows(requirement, at=None):
    today = (
        instant(at).astimezone(ZoneInfo(requirement.timezone)).date()
        if at
        else now().astimezone(ZoneInfo(requirement.timezone)).date()
    )
    full = [(today, date.max)]
    conditions = {c.id: c for c in requirement.conditions}

    def visit(tree):
        if tree.kind == "predicate":
            c = conditions[tree.condition_id]
            if c.field != "departure_date":
                return full
            value = c.value
            resolved = getattr(value, "resolved_date", None)
            if resolved:
                value = DateValue(value=resolved)
            if not isinstance(value, DateValue):
                return full
            lo = date.fromisoformat(value.value)
            hi = date.fromisoformat(value.upper) if value.upper else date.max
            if c.operator == "eq":
                hi = lo
            elif c.operator in {"lt", "lte"}:
                hi, lo = lo, date.min
                if c.operator == "lt":
                    if hi == date.min:
                        return []
                    hi -= timedelta(days=1)
            elif c.operator == "gt":
                if lo == date.max:
                    return []
                lo += timedelta(days=1)
            elif c.operator not in {"between", "gte"}:
                return full
            lo = max(lo, today)
            return [(lo, hi)] if lo <= hi else []
        if tree.kind == "any":
            return [interval for child in tree.children for interval in visit(child)]
        intervals = full
        for child in tree.children:
            other = visit(child)
            intervals = [
                (max(a, c), min(b, d)) for a, b in intervals for c, d in other if max(a, c) <= min(b, d)
            ]
            if not intervals:
                break
            if len(intervals) > 500:
                return full  # Ambiguous/complex trees must not create a false rejection.
        return intervals

    return today, visit(requirement.hard_tree)


def require_future_departure(requirement, at=None):
    if requirement.mode not in {"discover", "hybrid"}:
        return
    today, windows = future_windows(requirement, at)
    if not windows:
        raise AppError(
            "DEPARTURE_WINDOW_PAST",
            "Khoảng khởi hành đã qua. Chọn lại tháng/năm hoặc ngày cho chuyến đi sắp tới.",
            422,
            details={
                "field_path": "departure_date",
                "today": today.isoformat(),
                "timezone": requirement.timezone,
            },
        )
