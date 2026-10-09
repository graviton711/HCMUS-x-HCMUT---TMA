"""Product prerequisites, separate from extraction semantics and tour evidence."""

import hashlib
from decimal import Decimal
from typing import Literal

from pydantic import ValidationError

from domain.common import AppError, Identifier, Model
from domain.requirements import Budget, Clarification, DateValue, SetValue, Tree, UnresolvedValue
from domain.semantic import (
    CORE_FIELDS,
    CompletenessReport,
    ConditionV2,
    CoreFieldState,
    EntitySetValue,
    TemporalValue,
    ValueV2,
)
from requirements.catalog import TYPE_BY_FIELD, known_entity_ids

QUESTIONS = {
    "destinations": "Bạn muốn tìm tour đến đâu?",
    "departure_origin": "Bạn muốn tour khởi hành từ đâu?",
    "departure_date": "Bạn dự định đi ngày nào hoặc trong khoảng thời gian nào?",
    "party.adults": "Nhóm có bao nhiêu người lớn?",
    "estimated_cost": "Trần giá tour là bao nhiêu, dùng tiền tệ nào và tính cho mỗi người lớn hay cả nhóm?",
}
CORE_REASONS = {"CORE_FIELD_REQUIRED", "BUDGET_CAP_REQUIRED", "CORE_FIELD_BRANCH_REQUIRED", "PARTY_REQUIRED"}


def guaranteed(tree, condition_ids):
    """Every OR branch must contain a qualifying predicate; empty AND proves none."""
    if tree.kind == "predicate":
        return tree.condition_id in condition_ids
    if tree.kind == "all":
        return any(guaranteed(child, condition_ids) for child in tree.children)
    return all(guaranteed(child, condition_ids) for child in tree.children)


def positive(c):
    return c.operator not in {"excludes", "not_in"}


def resolved(c):
    if c.strength == "unresolved" or isinstance(c.value, UnresolvedValue):
        return False
    if isinstance(c.value, EntitySetValue):
        known = known_entity_ids(TYPE_BY_FIELD[c.field])
        # Preserve the usable branch of a partial OR; the semantic issue exposes missing catalog members.
        if c.operator == "contains_any":
            return any(m.status == "resolved" and m.entity_id in known for m in c.value.members)
        return all(m.status == "resolved" and m.entity_id in known for m in c.value.members)
    if isinstance(c.value, TemporalValue):
        return c.value.resolved_date is not None
    if isinstance(c.value, Budget):
        return c.value.currency is not None and c.value.basis is not None
    if isinstance(c.value, SetValue):
        return set(c.value.items) <= known_entity_ids(TYPE_BY_FIELD[c.field])
    return isinstance(c.value, DateValue)


def cap(c):
    return (
        c.strength == "hard"
        and c.operator in {"lt", "lte", "between"}
        and isinstance(c.value, Budget)
        and Decimal(c.value.upper if c.operator == "between" else c.value.amount) > 0
    )


def matches_question(q, conditions, field):
    if field == "party.adults":
        return q.field_path == field
    for c in conditions:
        if q.field_path.startswith(f"conditions.{c.id}."):
            return True
        if isinstance(c.value, TemporalValue) and q.field_path.startswith(
            f"temporal_groups.{c.value.group_id}."
        ):
            return True
    return False


def apply_completeness(r):
    # Standalone semantic parsing and v1 retain their existing domain policy.
    if "input_kind" not in type(r).model_fields:
        return r
    exempt = r.input_kind == "urls" and r.mode == "compare_urls"
    questions = [
        q
        for q in r.clarifications
        if q.reason_code not in (CORE_REASONS - {"PARTY_REQUIRED"})
        and (exempt or q.reason_code != "PARTY_REQUIRED")
        and (exempt or q.reason_code != "SEARCH_SCOPE_REQUIRED")
    ]
    states = []
    semantic_reasons = list(
        dict.fromkeys(
            [q.reason_code for q in questions if q.blocking] + [i.reason_code for i in r.issues if i.blocking]
        )
    )
    for field in () if exempt else CORE_FIELDS:
        cs = [c for c in r.conditions if c.field == field]
        candidates = [c for c in cs if (cap(c) if field == "estimated_cost" else positive(c))]
        existing = [q for q in questions if matches_question(q, cs, field)]
        issues = [i for i in r.issues if i.blocking and set(i.condition_ids) & {c.id for c in cs}]
        usable = {c.id for c in candidates if resolved(c)}
        present = bool(candidates) if field != "party.adults" else r.party.adults is not None
        complete = (
            r.party.adults is not None
            if field == "party.adults"
            else guaranteed(r.hard_tree, usable)
            or (field != "estimated_cost" and guaranteed(r.preference_tree, usable))
        )
        if complete and not any(q.blocking for q in existing) and not issues:
            status, reasons = "resolved", []
        elif issues:
            status, reasons = "unsupported", [i.reason_code for i in issues]
        elif existing:
            status, reasons = "needs_clarification", [q.reason_code for q in existing]
        elif any(isinstance(c.value, (EntitySetValue, SetValue)) and not resolved(c) for c in candidates):
            status, reasons = "unsupported", ["CATALOG_MISSING"]
        else:
            reason = (
                "CORE_FIELD_BRANCH_REQUIRED"
                if usable and not complete
                else "BUDGET_CAP_REQUIRED"
                if field == "estimated_cost" and cs
                else "CORE_FIELD_REQUIRED"
            )
            status, reasons = ("needs_clarification" if present or cs else "missing"), [reason]
            path = field if field == "party.adults" else f"trip.{field}"
            digest = hashlib.sha256(f"{r.id}:{r.revision}:{path}:{reason}".encode()).hexdigest()[:20]
            q = Clarification(
                id=f"q_{digest}", field_path=path, reason_code=reason, question=QUESTIONS[field]
            )
            questions.append(q)
            existing.append(q)
        states.append(
            CoreFieldState(
                field_path=field,
                status=status,
                responsibility=None
                if status == "resolved"
                else "backend"
                if status == "unsupported"
                else "user",
                condition_ids=[c.id for c in cs],
                clarification_ids=[q.id for q in existing],
                reasons=list(dict.fromkeys(reasons)),
            )
        )
    report = CompletenessReport(profile="url_only" if exempt else "personalized", fields=states)
    reasons = list(dict.fromkeys([*semantic_reasons, *(reason for f in states for reason in f.reasons)]))
    can_confirm = report.is_complete and not semantic_reasons
    readiness = r.readiness.model_dump()
    readiness.update(
        status="unsupported"
        if any(f.status == "unsupported" for f in states) or any(i.blocking for i in r.issues)
        else "needs_clarification"
        if not can_confirm
        else "ready",
        reasons=reasons,
        blockers=reasons,
        can_confirm=can_confirm,
        can_search=can_confirm and r.readiness.can_collect_data,
    )
    data = r.model_dump()
    data.update(
        completeness=report.model_dump(),
        clarifications=[q.model_dump() for q in questions],
        readiness=readiness,
    )
    return type(r).model_validate(data)


class ConditionAnswer(Model):
    id: Identifier
    field: str
    operator: str
    value: ValueV2
    strength: Literal["hard", "soft", "unresolved"] = "hard"
    scope: Literal["main_journey", "itinerary"] | None = None


def answer_core(r, question, answer, source):
    """Only fill a missing slot; existing predicates require explicit typed edits."""
    field = question.field_path.removeprefix("trip.")
    if question.reason_code not in CORE_REASONS or field not in CORE_FIELDS:
        raise AppError("INVALID_ANSWER", "Target không thuộc core question.")
    data = r.model_dump()
    if field == "party.adults":
        if not isinstance(answer, dict) or set(answer) != {"adults"} or type(answer["adults"]) is not int:
            raise AppError("INVALID_ANSWER", "Số người lớn cần object adults với số nguyên 1–100.")
        if not 1 <= answer["adults"] <= 100:
            raise AppError("INVALID_ANSWER", "Số người lớn phải trong 1–100.")
        data["party"]["adults"] = answer["adults"]
        data["party"]["sources"].append(source.model_dump())
    else:
        if not isinstance(answer, dict) or set(answer) != {"condition"}:
            raise AppError("INVALID_ANSWER", "Cần object condition đúng FormConditionV2.")
        try:
            raw = ConditionAnswer.model_validate(answer["condition"])
            c = ConditionV2(**raw.model_dump(), sources=[source])
        except ValidationError as exc:
            raise AppError("INVALID_ANSWER", "Condition answer không hợp lệ.") from exc
        if c.field != field or not positive(c) or not resolved(c) or field == "estimated_cost" and not cap(c):
            raise AppError("INVALID_ANSWER", "Answer phải làm rõ đúng field; budget cần trần hard dương.")
        if c.id in {old.id for old in r.conditions}:
            raise AppError("INVALID_ANSWER", "Dùng ID mới để bổ sung; sửa condition hiện có dùng typed edit.")
        data["conditions"].append(c.model_dump())
        tree_name = "preference_tree" if c.strength == "soft" else "hard_tree"
        data[tree_name] = Tree(
            kind="all", children=[getattr(r, tree_name), Tree(kind="predicate", condition_id=c.id)]
        ).model_dump()
    return type(r).model_validate(data)
