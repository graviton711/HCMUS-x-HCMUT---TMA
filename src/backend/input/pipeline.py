"""Validate structured requirements. Free text belongs to the travel agent."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from backend.errors import AppError
from backend.models import Condition, Requirement, uid

_HARD_FIELDS = {
    "destination",
    "departure_city",
    "date_from",
    "date_to",
    "budget_max",
    "duration_days",
    "transport",
    "accommodation",
}
_TRANSPORTS = {"flight", "bus", "train", "cruise", "mixed"}


def _invalid(message: str) -> AppError:
    return AppError("REQUIREMENT_INVALID", message, 422)


def validate_requirement(
    raw_text: str,
    conditions: Any,
    travelers: Any = 1,
    requirement_id: str | None = None,
) -> Requirement:
    """Validate agent-produced conditions without guessing or coercing values."""
    if not isinstance(raw_text, str) or not raw_text.strip() or len(raw_text) > 8000:
        raise _invalid("Requirement context is empty or too long.")
    if not isinstance(conditions, list):
        raise _invalid("Conditions must be a list.")
    if not isinstance(travelers, int) or isinstance(travelers, bool) or travelers < 1:
        raise _invalid("Travelers must be a positive integer.")

    cleaned: list[Condition] = []
    seen_ids: set[str] = set()
    for item in conditions:
        if not isinstance(item, dict):
            raise _invalid("Each condition must be an object.")
        try:
            condition = Condition.model_validate(item)
        except ValidationError as exc:
            raise _invalid("A condition has an invalid shape.") from exc
        if condition.id in seen_ids:
            raise _invalid("Condition IDs must be unique.")
        seen_ids.add(condition.id)
        if not condition.quote or condition.quote not in raw_text:
            raise _invalid("Every condition needs an exact quote from the conversation.")

        if condition.strength == "soft":
            if condition.field != "preference" or condition.operator != "contains":
                raise _invalid("Soft conditions must use the preference field.")
            if not isinstance(condition.value, str) or not condition.value.strip():
                raise _invalid("A soft preference must be non-empty text.")
        else:
            _validate_hard(condition)
        cleaned.append(condition)

    return Requirement(
        id=requirement_id or uid("req"),
        conditions=cleaned,
        missing=[],
        raw_text=raw_text,
        travelers=travelers,
    )


def requirement_from_form(form: Any) -> Requirement:
    """Build conditions only from explicit UI fields; never inspect the text draft."""
    if not isinstance(form, dict):
        raise _invalid("A structured form is required.")
    mapping = (
        ("destinations", "destination"),
        ("departure_city", "departure_city"),
        ("date_from", "date_from"),
        ("date_to", "date_to"),
        ("budget_max", "budget_max"),
        ("duration_days", "duration_days"),
        ("transport", "transport"),
        ("accommodation", "accommodation"),
    )
    raw_parts: list[str] = []
    conditions: list[dict[str, Any]] = []
    for form_key, field in mapping:
        value = form.get(form_key)
        if value is None or value == "" or value == []:
            continue
        if field == "destination" and isinstance(value, list):
            values = list(dict.fromkeys(str(part).strip() for part in value if str(part).strip()))
            if not values:
                continue
            condition_value = values[0] if len(values) == 1 else values
            operator = "contains" if len(values) == 1 else "any"
            quote = " or ".join(values)
        else:
            condition_value = value
            operator = (
                "lte" if field == "budget_max" else
                "contains" if field in {"departure_city", "accommodation"} else "eq"
            )
            quote = str(value)
        raw_parts.append(quote)
        conditions.append({
            "id": f"h{len(conditions) + 1}",
            "field": field,
            "operator": operator,
            "value": condition_value,
            "strength": "hard",
            "quote": quote,
        })
    raw_text = " · ".join(raw_parts) or "Structured travel request"
    return validate_requirement(raw_text, conditions, form.get("travelers", 1))


def _validate_hard(condition: Condition) -> None:
    field, operator, value = condition.field, condition.operator, condition.value
    if field not in _HARD_FIELDS:
        raise _invalid("Unsupported hard condition field.")

    if field == "budget_max":
        if operator != "lte" or not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _invalid("Budget must be a positive integer in VND.")
        return
    if field in {"date_from", "date_to"}:
        if operator != "eq" or not isinstance(value, str):
            raise _invalid("Travel dates must be ISO dates.")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise _invalid("Travel dates must be valid ISO dates.") from exc
        return
    if field == "duration_days":
        if operator != "eq" or not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _invalid("Duration must be a positive integer in days.")
        return
    if field == "destination":
        values = value if operator == "any" else [value]
        if operator not in {"contains", "any"} or not isinstance(values, list):
            raise _invalid("Destination must be text or a list of choices.")
        if not values or any(not isinstance(part, str) or not part.strip() for part in values):
            raise _invalid("Destination values must be non-empty text.")
        if operator == "any" and len(values) < 2:
            raise _invalid("Use a single destination with the contains operator.")
        return
    if field == "departure_city":
        if operator != "contains" or not isinstance(value, str) or not value.strip():
            raise _invalid("Departure city must be non-empty text.")
        return
    if field == "transport":
        if operator != "eq" or not isinstance(value, str) or value not in _TRANSPORTS:
            raise _invalid("Transport must use a supported transport value.")
        return
    if field == "accommodation" and (
        operator != "contains" or not isinstance(value, str) or not value.strip()
    ):
        raise _invalid("Accommodation must be non-empty text.")
