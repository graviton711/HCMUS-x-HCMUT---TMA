"""Validate structured requirements. Free text belongs to the travel agent."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from backend.errors import AppError
from backend.models import (
    Condition,
    RankingKey,
    RankingSpec,
    Requirement,
    RequirementAlternative,
    RequirementAssumption,
    uid,
)
from shared.text import fold_vi

_GENERIC_ACCOMMODATION = {
    # Bare lodging words with no type or standard cannot discriminate between tours.
    "chonghi",
    "choo",
    "noio",
    "noinghi",
    "luutru",
    "choluutru",
    "khachsan",
    "hotel",
    "resort",
    "nhanghi",
    "motel",
}

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
    ranking: Any = None,
    require_weights: bool = False,
    traveler_mix: Any = None,
    alternatives: Any = None,
    assumptions: Any = None,
) -> Requirement:
    """Validate agent-produced conditions without guessing or coercing values."""
    if not isinstance(raw_text, str) or not raw_text.strip() or len(raw_text) > 8000:
        raise _invalid("Requirement context is empty or too long.")
    if not isinstance(conditions, list):
        raise _invalid("Conditions must be a list.")
    if not isinstance(travelers, int) or isinstance(travelers, bool) or travelers < 1:
        raise _invalid("Travelers must be a positive integer.")
    if traveler_mix is None:
        traveler_mix = {}
    if not isinstance(traveler_mix, dict):
        raise _invalid("Traveler mix must be an object.")
    allowed_ages = {"adult", "child", "small_child", "infant"}
    if any(key not in allowed_ages for key in traveler_mix):
        raise _invalid("Traveler mix contains an unsupported age group.")
    if any(
        not isinstance(count, int) or isinstance(count, bool) or count < 0
        for count in traveler_mix.values()
    ):
        raise _invalid("Traveler counts must be non-negative integers.")
    if traveler_mix and sum(traveler_mix.values()) != travelers:
        raise _invalid("Traveler mix must add up to the total number of travelers.")

    cleaned: list[Condition] = []
    seen_ids: set[str] = set()
    def parse_conditions(items: Any, *, alternative: bool = False) -> list[Condition]:
        if not isinstance(items, list):
            raise _invalid("Conditions must be a list.")
        parsed: list[Condition] = []
        for item in items:
            if not isinstance(item, dict):
                raise _invalid("Each condition must be an object.")
            try:
                condition = Condition.model_validate(item)
            except ValidationError as exc:
                detail = "; ".join(
                    f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
                    for err in exc.errors()[:3]
                )
                raise _invalid(f"A condition has an invalid shape ({detail}).") from exc
            if condition.id in seen_ids:
                raise _invalid("Condition IDs must be unique across the requirement.")
            seen_ids.add(condition.id)
            if not condition.quote or condition.quote not in raw_text:
                raise _invalid(
                    f"Condition '{condition.id}' needs an exact quote from the conversation "
                    "(raw_text holds the full user-side history)."
                )

            if alternative and condition.strength != "hard":
                raise _invalid("Alternative branches may contain hard conditions only.")
            if condition.strength == "soft":
                if condition.field != "preference" or condition.operator != "contains":
                    raise _invalid(
                        "Soft conditions must use field 'preference' with operator 'contains'."
                    )
                if not isinstance(condition.value, str) or not condition.value.strip():
                    raise _invalid("A soft preference must be non-empty text.")
                # Bundled soft preferences ("Xe, an uong, ve, tron goi") cannot be
                # evidenced reliably — each item needs its own condition + quote.
                clauses = [part.strip() for part in re.split(r"[,;]", condition.value) if part.strip()]
                if len(clauses) > 1:
                    raise _invalid(
                        f"Soft preference '{condition.id}' bundles {len(clauses)} items. "
                        "Split into one condition per verifiable item (xe / cho nghi / an uong / ve / tron goi)."
                    )
            elif condition.weight_percent is not None:
                raise _invalid("Only soft preferences can have a weight.")
            else:
                _validate_hard(condition)
            parsed.append(condition)
        return parsed

    cleaned = parse_conditions(conditions)

    if alternatives is None:
        alternatives = []
    if not isinstance(alternatives, list) or len(alternatives) > 20:
        raise _invalid("Alternatives must be a list of at most 20 branches.")
    parsed_alternatives: list[RequirementAlternative] = []
    seen_alternative_ids: set[str] = set()
    for item in alternatives:
        if not isinstance(item, dict):
            raise _invalid("Each alternative must be an object.")
        alternative_id = item.get("id")
        label = item.get("label")
        if not isinstance(alternative_id, str) or not alternative_id.strip():
            raise _invalid("Each alternative needs an ID.")
        if alternative_id in seen_alternative_ids:
            raise _invalid("Alternative IDs must be unique.")
        if alternative_id == "common":
            raise _invalid("Alternative ID 'common' is reserved for shared conditions.")
        seen_alternative_ids.add(alternative_id)
        if not isinstance(label, str) or not label.strip() or len(label) > 160:
            raise _invalid("Each alternative needs a short label.")
        branch_conditions = parse_conditions(item.get("conditions"), alternative=True)
        if not branch_conditions:
            raise _invalid("Each alternative needs at least one hard condition.")
        parsed_alternatives.append(RequirementAlternative(
            id=alternative_id,
            label=label.strip(),
            conditions=branch_conditions,
        ))

    if assumptions is None:
        assumptions = []
    if not isinstance(assumptions, list) or len(assumptions) > 20:
        raise _invalid("Assumptions must be a list of at most 20 items.")
    parsed_assumptions: list[RequirementAssumption] = []
    condition_by_id = {
        condition.id: condition
        for condition in [*cleaned, *(c for a in parsed_alternatives for c in a.conditions)]
    }
    alternative_by_condition = {
        condition.id: alternative.id
        for alternative in parsed_alternatives
        for condition in alternative.conditions
    }
    assumption_ids: set[str] = set()
    for item in assumptions:
        if not isinstance(item, dict):
            raise _invalid("Each assumption must be an object.")
        try:
            assumption = RequirementAssumption.model_validate(item)
            start = date.fromisoformat(assumption.date_from)
            end = date.fromisoformat(assumption.date_to)
        except (ValidationError, ValueError) as exc:
            raise _invalid("A date assumption has an invalid shape or date range.") from exc
        if assumption.id in assumption_ids:
            raise _invalid("Assumption IDs must be unique.")
        assumption_ids.add(assumption.id)
        if start > end or not assumption.quote or assumption.quote not in raw_text:
            raise _invalid(
                f"Date assumption '{assumption.id}' needs an ordered range and an exact "
                "user quote from the conversation."
            )
        linked = [condition_by_id.get(condition_id) for condition_id in assumption.condition_ids]
        if len(linked) < 2 or len(linked) % 2 != 0 or any(condition is None for condition in linked):
            raise _invalid("A date assumption must link date conditions in from/to pairs.")
        linked_conditions = [condition for condition in linked if condition is not None]
        if {condition.field for condition in linked_conditions} != {"date_from", "date_to"}:
            raise _invalid("A date assumption must link both date conditions.")
        pairs: dict[str, dict[str, Any]] = {}
        for condition in linked_conditions:
            group = alternative_by_condition.get(condition.id, "common")
            slot = pairs.setdefault(group, {})
            if condition.field in slot:
                raise _invalid("A date assumption must pair dates within the same scope or branch.")
            slot[condition.field] = condition.value
        for slot in pairs.values():
            if set(slot) != {"date_from", "date_to"}:
                raise _invalid("A date assumption must pair dates within the same scope or branch.")
            if (slot["date_from"], slot["date_to"]) != (assumption.date_from, assumption.date_to):
                raise _invalid("A date assumption must match its linked date conditions.")
        parsed_assumptions.append(assumption)

    soft_conditions = [condition for condition in cleaned if condition.strength == "soft"]
    if require_weights and soft_conditions:
        weights = [condition.weight_percent for condition in soft_conditions]
        if any(weight is None for weight in weights) or sum(weight or 0 for weight in weights) != 100:
            raise _invalid("Soft preference weights must add up to exactly 100.")

    ranking_spec = None
    if ranking is not None:
        try:
            ranking_spec = RankingSpec.model_validate(ranking)
        except ValidationError as exc:
            raise _invalid("Ranking must contain supported ordered fields and directions.") from exc
        ranking_fields = [key.field for key in ranking_spec.order_by]
        if len(ranking_fields) != len(set(ranking_fields)):
            raise _invalid("Ranking fields must not be repeated.")
        if any(condition.strength == "soft" for condition in cleaned) and "soft_fit" not in ranking_fields:
            if len(ranking_fields) == 5:
                raise _invalid("Leave one ranking position for soft_fit when soft preferences are present.")
            ranking_spec = RankingSpec(order_by=[
                *ranking_spec.order_by,
                RankingKey(field="soft_fit", direction="desc"),
            ])

    return Requirement(
        id=requirement_id or uid("req"),
        conditions=cleaned,
        alternatives=parsed_alternatives,
        assumptions=parsed_assumptions,
        missing=[],
        raw_text=raw_text,
        travelers=travelers,
        traveler_mix=traveler_mix,
        ranking=ranking_spec,
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
    return validate_requirement(
        raw_text, conditions, form.get("travelers", 1), traveler_mix=form.get("traveler_mix")
    )


def _validate_hard(condition: Condition) -> None:
    field, operator, value = condition.field, condition.operator, condition.value
    if field not in _HARD_FIELDS:
        raise _invalid(
            f"Unsupported hard condition field '{field}'. Use one of {sorted(_HARD_FIELDS)}."
        )

    if field == "budget_max":
        if operator != "lte" or not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _invalid("Budget must use operator 'lte' with a positive integer in VND.")
        return
    if field in {"date_from", "date_to"}:
        if operator != "eq" or not isinstance(value, str):
            raise _invalid("Travel dates must use operator 'eq' with an ISO date value.")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise _invalid("Travel dates must be valid ISO dates.") from exc
        return
    if field == "duration_days":
        if operator != "eq" or not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _invalid("Duration must use operator 'eq' with a positive integer in days.")
        return
    if field == "destination":
        values = value if operator == "any" else [value]
        if operator not in {"contains", "any"} or not isinstance(values, list):
            raise _invalid("Destination must use operator 'contains' with text or 'any' with choices.")
        if not values or any(not isinstance(part, str) or not part.strip() for part in values):
            raise _invalid("Destination values must be non-empty text.")
        if operator == "any" and len(values) < 2:
            raise _invalid("Use a single destination with the contains operator.")
        return
    if field == "departure_city":
        if operator == "contains" and isinstance(value, str) and value.strip():
            return
        if (
            operator == "any"
            and isinstance(value, list)
            and len(value) >= 2
            and all(isinstance(part, str) and part.strip() for part in value)
        ):
            return
        raise _invalid(
            "Departure city must use operator 'contains' with text or 'any' with catalog labels."
        )
    if field == "transport":
        if operator != "eq" or not isinstance(value, str) or value not in _TRANSPORTS:
            raise _invalid(
                f"Transport must use operator 'eq' with one of {sorted(_TRANSPORTS)}."
            )
        return
    if field == "accommodation":
        if operator != "contains" or not isinstance(value, str) or not value.strip():
            raise _invalid("Accommodation must use operator 'contains' with non-empty text.")
        if fold_vi(value) in _GENERIC_ACCOMMODATION:
            raise _invalid(
                f"Accommodation '{value.strip()}' is too generic to filter tours; use the stated "
                "type or standard, or drop it to a soft preference."
            )
        return
