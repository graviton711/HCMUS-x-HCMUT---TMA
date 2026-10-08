"""Normalization, backend issues and targeted v2 clarification answers."""

import hashlib
import json
import re

from domain.common import AppError
from domain.requirements import (
    FIELDS,
    Condition,
    DateValue,
    Readiness,
    RequirementState,
    SetValue,
    UnresolvedValue,
)
from domain.semantic import (
    ENTITY_FIELDS,
    QUALITATIVE_FIELDS,
    SEMANTIC_POLICY,
    ConditionV2,
    EntitySetValue,
    QualitativeValue,
    ResolutionTrace,
    SemanticIssue,
    TemporalValue,
)
from requirements.catalog import CATALOG_VERSION, resolve_entities
from requirements.normalize import fold, ground, normalize
from requirements.service import finalize
from requirements.signals import qualitative_polarities, signal_spans
from requirements.temporal import lunar_context, normalize_temporal, resolve_temporal


def explicit_hard(text):
    return bool(re.search(r"\b(?:bat buoc|phai(?!\s+chang)|nhat thiet|chi chap nhan)\b", fold(text)))


def qualitative_strength(field, message, source):
    choices = set()
    for _start, end in signal_spans(field, source.quote):
        context = re.split(r"[,.;\n]|\bnhưng\b", message.text[: source.start + end])[-1]
        choices.add("hard" if explicit_hard(context) else "soft")
    return next(iter(choices)) if len(choices) == 1 else "unresolved"


def tour_type_problem(raw):
    if raw.field != "tour_type":
        return None
    if not raw.raw_values or all(fold(v) in {"tour", "du lich"} for v in raw.raw_values):
        return "'tour/du lịch' chung không phải yêu cầu loại tour. Bỏ object tour_type nếu user chưa nói loại; nếu có ghép đoàn/đoàn riêng/loại cụ thể, giữ raw_values nguyên văn trong quote. Không tạo tour_type với raw_values rỗng."
    if all(m.status == "resolved" for m in resolve_entities("destinations", raw.raw_values).members):
        return "Raw values của tour_type là địa danh đã có trong catalog, không phải loại tour. Dùng field destinations với raw names/quotes hiện tại; chỉ tạo tour_type khi user nói ghép đoàn/đoàn riêng/loại cụ thể. Không bỏ điểm đến để né lỗi."
    return None


def normalize_v2(raw, message, timezone):
    source = ground(message, raw.quote)
    problem = tour_type_problem(raw)
    if problem:
        error = AppError("LLM_INVALID_OUTPUT", "Loại tour cần giá trị được người dùng nói rõ.", 502)
        error.repair_hint = problem
        raise error
    for slot in raw.raw_values:
        if not slot or fold(slot) not in fold(raw.quote):
            # Legacy explicit-zero derivations still use their existing validator.
            if raw.field not in {"shopping_stops", "flight_stops"}:
                error = AppError("LLM_INVALID_OUTPUT", "Raw slot thiếu căn cứ trong quote.", 502)
                error.repair_hint = f"Field {raw.field}: raw value {json.dumps(slot, ensure_ascii=False)} is not contained in quote {json.dumps(raw.quote, ensure_ascii=False)}. Pick a sufficient exact quote from THIS message and keep verbatim raw entity/amount/date values."
                raise error
    scope = getattr(raw, "scope", None)
    if raw.field == "route":
        scope = "itinerary"
    sources, operator = [source], raw.operator
    strength = raw.strength
    if raw.field in {"departure_date", "return_date"}:
        anchor = re.search(re.escape(raw.raw_values[0]), raw.quote, re.I) if raw.raw_values else None
        end = source.start + anchor.end() if anchor else source.end
        context = re.split(r"[,.;\n]|\bnhưng\b", message.text[:end])[-1]
        strength = (
            "soft"
            if not explicit_hard(context) and re.search(r"\b(?:uu tien|thich|neu duoc)\b", fold(context))
            else "hard"
        )
        policy_source = ground(message, message.text)
        policy_source.rule = "date_bound_strength_v1"
        sources.append(policy_source)
    if raw.field == "route":
        context = re.split(r"[,.;\n]", message.text[: source.end])[-1]
        strength = (
            "hard"
            if explicit_hard(context)
            else "soft"
            if re.search(r"\b(?:uu tien|thich|neu duoc)\b", fold(context))
            else "unresolved"
        )
        policy_source = ground(message, message.text)
        policy_source.rule = "route_strength_review_v1"
        sources.append(policy_source)
    trace = ResolutionTrace(raw_values=raw.raw_values, rule="semantic-normalization", version=SEMANTIC_POLICY)
    if raw.field in ENTITY_FIELDS:
        if raw.field in {"destinations", "departure_origin", "transport", "tour_type"} and raw.raw_values:
            anchor = re.search(re.escape(raw.raw_values[0]), raw.quote, re.I)
            end = source.start + anchor.end() if anchor else source.end
            context = re.split(r"[,.;\n]|\bnhưng\b", message.text[:end])[-1]
            strength = "soft" if re.search(r"\b(?:uu tien|thich|neu duoc)\b", fold(context)) else "hard"
            policy_source = ground(message, message.text)
            policy_source.rule = "entity_scope_strength_v1"
            sources.append(policy_source)
        if raw.raw_values:
            value = resolve_entities(raw.field, raw.raw_values)
            trace.rule, trace.version = "typed-catalog-lookup", CATALOG_VERSION
        else:
            value = UnresolvedValue(raw=raw.quote, reason="ENTITY_VALUE_REQUIRED")
        if raw.field == "transport" and "o to" in fold(raw.quote):
            if scope == "main_journey" and re.search(r"dua don|trung chuyen", fold(raw.quote)):
                raise AppError(
                    "LLM_INVALID_OUTPUT",
                    "Xe đưa đón/trung chuyển không chứng minh phương tiện hành trình chính.",
                    502,
                )
            main_cue = re.search(
                r"(?:xe )?o to\s+tu\s+|tu\s+[^.\n]{1,45}\s+(?:bang|di)\s+(?:xe )?o to", fold(message.text)
            )
            if main_cue and not re.search(r"dua don|trung chuyen", fold(raw.quote)):
                scope = "main_journey"
                link = ground(message, message.text)
                link.rule = "main_journey_origin_link_v1"
                sources.append(link)
    elif raw.field in QUALITATIVE_FIELDS:
        polarities = qualitative_polarities(raw.field, message, source)
        expected = "negative" if raw.operator == "excludes" else "positive"
        if polarities != {expected}:
            error = AppError(
                "LLM_INVALID_OUTPUT",
                "Quote chưa chứng minh concept/polarity định tính; không cắt mất phủ định.",
                502,
            )
            error.repair_hint = f"Field {raw.field}, quote {json.dumps(raw.quote, ensure_ascii=False)}, polarity={sorted(polarities)}, expected={expected}. Quote phải chứa đúng concept. 'Không cần/không quan tâm' nghĩa bỏ preference, không excludes; 'không thích/tránh' dùng excludes; câu positive dùng prefer soft. Sao chép quote đủ ngữ cảnh để không cắt mất phủ định."
            raise error
        strength = qualitative_strength(raw.field, message, source)
        if strength == "unresolved":
            raise AppError(
                "LLM_INVALID_OUTPUT",
                "Quote định tính gồm các strength mâu thuẫn; tách theo ý cuối hoặc giữ ambiguity.",
                502,
            )
        if operator != "excludes":
            operator = "requires" if strength == "hard" else "prefer"
        policy_source = ground(message, message.text)
        policy_source.rule = "qualitative_strength_default_v1"
        sources.append(policy_source)
        value = QualitativeValue(
            concept=raw.field,
            raw=raw.quote,
            metric_policy="nature-itinerary-tags-v1" if raw.field == "nature" else None,
        )
        if raw.field == "nature":
            scope = "itinerary"
    elif raw.field in {"departure_date", "return_date"} and (
        lunar_context(raw.quote) or getattr(raw, "temporal", None) is not None
    ):
        try:
            value, extra = normalize_temporal(raw, message)
            sources.extend(extra)
            if value.semantics == "availability":
                operator = "gte" if raw.field == "departure_date" else "lte"
            elif value.semantics == "exact":
                operator = "eq"
            trace.rule = "grounded-calendar-intent"
        except ValueError as exc:
            value = UnresolvedValue(raw=raw.quote, reason=str(exc) if str(exc).isupper() else "INVALID_DATE")
    else:
        old = normalize(raw, message, timezone)
        if raw.field in {"departure_date", "return_date"}:
            old = old.model_copy(update={"strength": strength, "sources": [*old.sources, *sources[1:]]})
        return ConditionV2.model_validate({**old.model_dump(), "scope": scope, "trace": trace.model_dump()})
    return ConditionV2(
        id=raw.id,
        field=raw.field,
        operator=operator,
        value=value,
        strength=strength,
        scope=scope,
        trace=trace,
        sources=sources,
    )


def legacy_condition(c, *, query=False):
    """Preserve all IDs/trees; unsupported pushdown remains an explicit marker."""
    data = c.model_dump(exclude={"scope", "trace"})
    if c.field not in FIELDS:
        data.update(
            field="unsupported",
            operator="unresolved",
            value=UnresolvedValue(raw="", reason="V2_EVALUATION_ONLY"),
        )
    elif query and getattr(c, "scope", None):
        data.update(
            field="unsupported",
            operator="unresolved",
            value=UnresolvedValue(raw="", reason="V2_SCOPED_EVALUATION_ONLY"),
        )
    elif isinstance(c.value, EntitySetValue):
        if all(m.entity_id for m in c.value.members):
            data["value"] = SetValue(items=[m.entity_id for m in c.value.members])
        else:
            data["value"] = UnresolvedValue(raw="", reason="ENTITY_PARTIAL")
    elif isinstance(c.value, TemporalValue):
        data["value"] = (
            DateValue(value=c.value.resolved_date)
            if c.value.resolved_date
            else UnresolvedValue(raw=c.value.raw, reason=c.value.reason)
        )
    elif isinstance(c.value, QualitativeValue):
        data.update(
            field="unsupported",
            operator="unresolved",
            value=UnresolvedValue(raw="", reason="V2_EVALUATION_ONLY"),
        )
    return Condition.model_validate(data)


def legacy_requirement(r, *, query=False, mode=None, targets=None):
    data = {k: v for k, v in r.model_dump().items() if k in RequirementState.model_fields}
    data.update(
        schema_version="1.0",
        policy_version="requirements-v1",
        revision=max(1, r.revision),
        conditions=[legacy_condition(c, query=query) for c in r.conditions],
    )
    data["readiness"] = {k: v for k, v in data["readiness"].items() if k in Readiness.model_fields}
    if mode is not None:
        data.update(mode=mode, targets=targets)
    return RequirementState.model_validate(data)


def finalize_v2(r):
    # Recompute derived ISO values even for typed form submissions.
    temporal_conditions = [
        c.model_copy(update={"value": resolve_temporal(c.value)}) if isinstance(c.value, TemporalValue) else c
        for c in r.conditions
    ]
    r = r.model_copy(update={"conditions": temporal_conditions})
    core = finalize(legacy_requirement(r))
    by_id = {c.id: c for c in r.conditions}
    questions, issues = [], []
    for q in core.clarifications:
        if q.reason_code == "SEARCH_SCOPE_REQUIRED":
            continue
        cid = q.field_path.split(".")[1] if q.field_path.startswith("conditions.") else None
        c = by_id.get(cid)
        if c and (
            isinstance(c.value, (EntitySetValue, TemporalValue, QualitativeValue)) or c.field == "unsupported"
        ):
            if q.reason_code != "CONDITION_STRENGTH_REQUIRED":
                continue
        questions.append(q)

    def ask(path, reason, question, options=(), blocking=True):
        from domain.requirements import Clarification

        digest = hashlib.sha256(f"{r.id}:{r.revision}:{path}:{reason}".encode()).hexdigest()[:20]
        questions.append(
            Clarification(
                id=f"q_{digest}",
                field_path=path,
                reason_code=reason,
                question=question,
                options=list(options),
                blocking=blocking,
            )
        )

    scopes, groups, unassessed = [], {}, []
    for c in r.conditions:
        hard = c.strength != "soft"
        if isinstance(c.value, EntitySetValue):
            known = sum(m.entity_id is not None for m in c.value.members)
            missing = len(c.value.members) - known
            if missing:
                issues.append(
                    SemanticIssue(
                        reason_code="CATALOG_MISSING",
                        responsibility="backend",
                        condition_ids=[c.id],
                        explanation="Catalog chưa có: "
                        + ", ".join(m.raw for m in c.value.members if not m.entity_id),
                        blocking=hard and known == 0,
                    )
                )
            if c.field in {"destinations", "supplier"} and c.operator not in {"excludes", "not_in"}:
                scopes.append("partial" if missing and known else "unavailable" if missing else "complete")
        elif isinstance(c.value, TemporalValue):
            groups.setdefault(c.value.group_id, []).append(c)
        elif isinstance(c.value, QualitativeValue):
            if c.strength == "soft":
                unassessed.append(c.id)
            if c.value.metric_policy is None:
                issues.append(
                    SemanticIssue(
                        reason_code="METRIC_UNSUPPORTED",
                        responsibility="backend",
                        condition_ids=[c.id],
                        explanation="Chưa có policy/bằng chứng đánh giá ưu tiên này.",
                        blocking=hard,
                    )
                )
        elif c.field == "unsupported":
            issues.append(
                SemanticIssue(
                    reason_code=c.value.reason,
                    responsibility="backend",
                    condition_ids=[c.id],
                    explanation="Nhu cầu được giữ nhưng chưa có evaluator.",
                    blocking=hard,
                )
            )
        elif (
            isinstance(c.value, SetValue)
            and c.field in {"destinations", "supplier"}
            and c.operator not in {"excludes", "not_in"}
        ):
            scopes.append("complete")
    for gid, cs in groups.items():
        v = cs[0].value
        path = f"temporal_groups.{gid}"
        hard = any(c.strength != "soft" for c in cs)
        if v.semantics == "departure_window":
            issues.append(
                SemanticIssue(
                    reason_code="TEMPORAL_SEMANTICS_UNSUPPORTED",
                    responsibility="backend",
                    condition_ids=[c.id for c in cs],
                    explanation="Lunar departure window cần hai bounds cùng field; dùng form DateValue/between cho ngày dương đã biết.",
                    blocking=hard,
                )
            )
            continue
        if v.semantics == "ambiguous":
            ask(
                path + ".semantics",
                "TEMPORAL_SEMANTICS_REQUIRED",
                "Đây là khoảng bạn có thể đi hay ngày khởi hành/về cố định?",
                ["availability", "exact"],
                hard,
            )
        if v.calendar == "unresolved":
            ask(
                path + ".calendar",
                "CALENDAR_REQUIRED",
                "Các mốc này dùng lịch âm Việt Nam hay lịch dương?",
                ["vietnamese_lunar", "gregorian"],
                hard,
            )
        year_missing = any(c.value.year is None for c in cs)
        if v.holiday == "tet" and v.holiday_year is None or v.holiday is None and year_missing:
            ask(
                path + ".year",
                "DATE_YEAR_REQUIRED",
                "Bạn muốn đi dịp Tết năm nào?" if v.holiday else "Ngày bạn nói thuộc năm nào?",
                blocking=hard,
            )
        for c in cs:
            if c.value.reason in {
                "TEMPORAL_SEMANTICS_REQUIRED",
                "CALENDAR_REQUIRED",
                "DATE_YEAR_REQUIRED",
                None,
            }:
                continue
            if c.value.reason == "LUNAR_LEAP_REQUIRED":
                ask(
                    f"conditions.{c.id}.value.leap",
                    "LUNAR_LEAP_REQUIRED",
                    "Bạn nói tháng âm thường hay tháng nhuận?",
                    ["regular", "leap"],
                    hard,
                )
            else:
                ask(
                    f"conditions.{c.id}.value",
                    c.value.reason,
                    "Mốc ngày này chưa hợp lệ; bạn sửa lại giúp nhé.",
                    blocking=hard,
                )
    coverage = (
        "partial"
        if "partial" in scopes or "unavailable" in scopes and "complete" in scopes
        else "complete"
        if scopes and all(s == "complete" for s in scopes)
        else "unavailable"
    )
    if r.mode == "compare_urls" and not scopes and r.targets:
        coverage = "complete"
    if r.mode == "discover" and not scopes:
        ask("conditions", "SEARCH_SCOPE_REQUIRED", "Bạn muốn tìm tour đến đâu hoặc của nhà cung cấp nào?")
    blockers = list(
        dict.fromkeys(
            [q.reason_code for q in questions if q.blocking] + [i.reason_code for i in issues if i.blocking]
        )
    )
    data = r.model_dump()
    data.update(policy_version=SEMANTIC_POLICY, issues=issues, clarifications=questions)
    data["readiness"] = type(r.readiness)(
        status="unsupported"
        if any(i.blocking for i in issues)
        else "needs_clarification"
        if any(q.blocking for q in questions)
        else "ready",
        can_collect_data=bool(r.targets) or any(s != "unavailable" for s in scopes),
        can_evaluate_hard_constraints=not blockers,
        reasons=blockers,
        scope_coverage=coverage,
        unassessed_preferences=unassessed,
    )
    from requirements.completeness import apply_completeness

    return apply_completeness(type(r).model_validate(data))


def answer_clarification(r, question, answer, source):
    """The caller binds the question to the current proposal/revision first."""
    from requirements.completeness import CORE_REASONS, answer_core

    if question.reason_code in CORE_REASONS:
        return finalize_v2(answer_core(r, question, answer, source))
    data = r.model_dump()
    data["issues"] = []
    cs = {c.id: c for c in r.conditions}
    path = question.field_path.split(".")
    changed = []
    if path[0] == "temporal_groups":
        group = [c for c in cs.values() if isinstance(c.value, TemporalValue) and c.value.group_id == path[1]]
        if not group:
            raise AppError("STALE_CLARIFICATION", "Khoảng thời gian đã thay đổi.", 409)
        if question.reason_code == "DATE_YEAR_REQUIRED":
            expected = "holiday_year" if group[0].value.holiday == "tet" else "year"
            if (
                not isinstance(answer, dict)
                or set(answer) != {expected}
                or type(answer[expected]) is not int
                or not 2001 <= answer[expected] <= 2099
            ):
                raise AppError("INVALID_ANSWER", "Năm phải rõ kiểu và nằm trong 2001–2099.")
            updates = answer if expected == "holiday_year" else {**answer, "year_origin": "explicit"}
        elif question.reason_code == "TEMPORAL_SEMANTICS_REQUIRED":
            if (
                not isinstance(answer, dict)
                or set(answer) != {"semantics"}
                or answer["semantics"] not in {"availability", "exact"}
            ):
                raise AppError("INVALID_ANSWER", "Chọn availability hoặc exact.")
            updates = answer
        elif question.reason_code == "CALENDAR_REQUIRED":
            if (
                not isinstance(answer, dict)
                or set(answer) != {"calendar"}
                or answer["calendar"] not in {"vietnamese_lunar", "gregorian"}
            ):
                raise AppError("INVALID_ANSWER", "Chọn calendar hợp lệ.")
            updates = answer
        else:
            raise AppError("INVALID_ANSWER", "Không hỗ trợ answer target này.")
        for c in group:
            value = resolve_temporal(c.value.model_copy(update=updates))
            op = "gte" if c.field == "departure_date" else "lte"
            if value.semantics == "exact":
                op = "eq"
            changed.append(
                c.model_copy(update={"value": value, "operator": op, "sources": [*c.sources, source]})
            )
    elif len(path) >= 3 and path[0] == "conditions" and path[1] in cs:
        c = cs[path[1]]
        if question.reason_code == "CONDITION_STRENGTH_REQUIRED" and answer in ("hard", "soft"):
            changed.append(c.model_copy(update={"strength": answer, "sources": [*c.sources, source]}))
        elif (
            question.reason_code == "LUNAR_LEAP_REQUIRED"
            and isinstance(c.value, TemporalValue)
            and type(answer) is bool
        ):
            changed.append(
                c.model_copy(
                    update={
                        "value": resolve_temporal(c.value.model_copy(update={"leap": answer})),
                        "sources": [*c.sources, source],
                    }
                )
            )
        elif (
            question.reason_code == "DATE_YEAR_REQUIRED"
            and isinstance(c.value, UnresolvedValue)
            and not lunar_context(c.value.raw)
        ):
            if (
                not isinstance(answer, dict)
                or set(answer) != {"year"}
                or type(answer["year"]) is not int
                or not 2001 <= answer["year"] <= 2099
            ):
                raise AppError("INVALID_ANSWER", "Ngày dương cần năm rõ kiểu trong 2001–2099.")
            m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?![\d/])", c.value.raw)
            if m is None:
                raise AppError("INVALID_ANSWER", "Mốc cũ chưa đủ ngày/tháng.")
            from datetime import date

            try:
                value = DateValue(value=date(answer["year"], int(m[2]), int(m[1])).isoformat())
            except ValueError as exc:
                raise AppError("INVALID_ANSWER", "Ngày dương không tồn tại.") from exc
            changed.append(c.model_copy(update={"value": value, "sources": [*c.sources, source]}))
        else:
            raise AppError("INVALID_ANSWER", "Sửa typed condition để trả lời target này.")
    else:
        raise AppError("INVALID_ANSWER", "Answer target không được hỗ trợ.")
    for c in changed:
        cs[c.id] = c
    data["conditions"] = list(cs.values())
    # A strength answer changes tree membership, with existing groups preserved.
    if question.reason_code == "CONDITION_STRENGTH_REQUIRED":
        from domain.requirements import Tree
        from requirements.service import prune

        cid = changed[0].id
        for name in ("hard_tree", "preference_tree"):
            data[name] = (prune(getattr(r, name), {cid}) or Tree(kind="all")).model_dump()
        name = "preference_tree" if changed[0].strength == "soft" else "hard_tree"
        data[name] = Tree(
            kind="all", children=[Tree.model_validate(data[name]), Tree(kind="predicate", condition_id=cid)]
        ).model_dump()
    return finalize_v2(type(r).model_validate(data))
