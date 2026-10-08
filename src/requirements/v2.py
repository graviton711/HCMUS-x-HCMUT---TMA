"""Grounded non-condition slots for the v2 proposal parser."""

import re
from functools import reduce
from operator import or_
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, create_model, model_validator

from domain.common import AppError, Identifier, Model
from domain.semantic import FIELDS_V2, QUALITATIVE_FIELDS, TemporalValue
from requirements.extraction import InitialExtraction, Operation, RawCondition, UpdateExtraction
from requirements.normalize import fold, ground
from requirements.prompts_v2 import extraction_prompt_v2
from requirements.signals import (
    SIGNALS,
    coverage_manifest,
    has_positive,
    qualitative_polarities,
    quote_candidates,
)

V2_PROMPT_VERSION = "vi-semantic-v2.8"
V2_PROMPT = extraction_prompt_v2()


class RawTemporal(Model):
    calendar: Literal["gregorian", "vietnamese_lunar", "unresolved"]
    semantics: Literal["availability", "exact", "departure_window", "ambiguous", "single"]
    group_id: Identifier | None = None
    year_raw: str | None = None
    year_quote: str | None = None
    holiday_year_raw: str | None = None
    holiday_year_quote: str | None = None


class RawConditionV2(RawCondition):
    field: Literal[
        "destinations",
        "departure_origin",
        "departure_date",
        "return_date",
        "duration_days",
        "duration_nights",
        "estimated_cost",
        "transport",
        "flight_stops",
        "hotel_stars_min",
        "shopping_stops",
        "included_services",
        "supplier",
        "unsupported",
        "tour_type",
        "route",
        "supplier_reputation",
        "service_quality",
        "price_value",
        "nature",
    ]
    scope: Literal["main_journey", "itinerary"] | None = None
    temporal: RawTemporal | None = None
    operator: Literal[
        "contains",
        "contains_any",
        "contains_all",
        "excludes",
        "in",
        "not_in",
        "eq",
        "lt",
        "lte",
        "gt",
        "gte",
        "between",
        "near",
        "prefer_low",
        "prefer_high",
        "unresolved",
        "prefer",
        "requires",
    ]

    @model_validator(mode="after")
    def compatible_operator(self):
        if self.operator not in FIELDS_V2[self.field]:
            raise ValueError(
                f"Invalid operator {self.operator} for {self.field}. Allowed: {sorted(FIELDS_V2[self.field])}"
            )
        if self.temporal and self.field not in {"departure_date", "return_date"}:
            raise ValueError("Temporal slot belongs only to a date")
        return self


# Keep the common constructor for normalization/tests, but constrain provider generation by field.
RawPredicateV2 = Annotated[
    reduce(
        or_,
        (
            create_model(
                "Raw" + "".join(part.title() for part in name.split("_")) + "V2",
                __base__=RawConditionV2,
                field=(Literal[name], ...),
                operator=(Literal[tuple(sorted(operators))], ...),
            )
            for name, operators in FIELDS_V2.items()
        ),
    ),
    Field(discriminator="field"),
    BeforeValidator(lambda v: v.model_dump() if isinstance(v, RawConditionV2) else v),
]


class OperationV2(Operation):
    condition: RawPredicateV2 | None = None


class RawAnswer(Model):
    clarification_id: Identifier
    value_raw: str = Field(min_length=1, max_length=800)
    quote: str = Field(min_length=1, max_length=8000)


class RawPreference(Model):
    dimension: Literal["cost", "comfort", "pace", "culture"]
    level: int = Field(ge=0, le=5)
    quote: str = Field(min_length=1, max_length=8000)


class RawURLs(Model):
    urls: list[str] = Field(max_length=5)
    quote: str = Field(min_length=1, max_length=8000)


class RawNotes(Model):
    text: str = Field(max_length=8000)
    quote: str = Field(min_length=1, max_length=8000)


class ExtraSlots(Model):
    preference_updates: list[RawPreference] = Field(default_factory=list, max_length=4)
    reference_urls_update: RawURLs | None = None
    notes_update: RawNotes | None = None
    answers: list[RawAnswer] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def no_duplicate_dimensions(self):
        if len({x.dimension for x in self.preference_updates}) != len(self.preference_updates):
            raise ValueError("Duplicate preference update")
        return self


class InitialExtractionV2(InitialExtraction, ExtraSlots):
    conditions: list[RawPredicateV2] = Field(default_factory=list, max_length=50)
    operations: list[OperationV2] = Field(default_factory=list, max_length=0)
    answers: list[RawAnswer] = Field(default_factory=list, max_length=0)
    preference_updates: list[RawPreference] = Field(max_length=4)
    reference_urls_update: RawURLs | None
    notes_update: RawNotes | None


class UpdateExtractionV2(UpdateExtraction, ExtraSlots):
    operations: list[OperationV2] = Field(default_factory=list, max_length=30)
    preference_updates: list[RawPreference] = Field(max_length=4)
    reference_urls_update: RawURLs | None
    notes_update: RawNotes | None


def generation_schema(extraction_type, message, previous=None):
    schema = extraction_type.model_json_schema()
    for definition in schema["$defs"].values():
        props = definition.get("properties", {})
        field = props.get("field", {}).get("const")
        if field == "tour_type":
            props["raw_values"]["minItems"] = 1
        pattern = SIGNALS.get(field)
        if field in {"departure_date", "return_date"}:
            pattern = r"\b(?:\d{1,2}/\d{1,2}|20\d{2}-\d{2}-\d{2}|(?:mung|mong)\s+\d+|thang\s+(?:nay|sau))\b"
        if pattern:
            candidates = [q for q in quote_candidates(message.text) if re.search(pattern, fold(q))]
            if candidates:
                props["quote"] = {"type": "string", "enum": candidates}
    if previous is None:
        positive = {row["field"] for row in coverage_manifest(message.text) if row["polarity"] == "positive"}
        if positive:
            schema["properties"]["conditions"]["minItems"] = len(positive)
    else:
        condition_ids = [c.id for c in previous.conditions]
        schema["$defs"]["OperationV2"]["properties"]["target_id"] = {
            "anyOf": [
                *([{"type": "string", "enum": condition_ids}] if condition_ids else []),
                {"type": "null"},
            ],
            "description": "Existing condition ID for replace/remove/increment_budget; null for add. Never a clarification ID.",
        }
        supported = {
            "DATE_YEAR_REQUIRED",
            "TEMPORAL_SEMANTICS_REQUIRED",
            "CONDITION_STRENGTH_REQUIRED",
            "LUNAR_LEAP_REQUIRED",
        }
        answer_ids = [q.id for q in previous.clarifications if q.reason_code in supported]
        if answer_ids:
            schema["$defs"]["RawAnswer"]["properties"]["clarification_id"] = {
                "type": "string",
                "enum": answer_ids,
            }
            schema["properties"]["answers"]["minItems"] = len(clarification_targets(message, previous))
        else:
            schema["properties"]["answers"]["maxItems"] = 0
        if clarification_only(message, previous):
            schema["properties"]["operations"]["maxItems"] = 0
    return schema


def clarification_only(message, previous):
    if previous is None or not previous.clarifications:
        return False
    clauses = [c.strip() for c in re.split(r"[.!?;\n]", fold(message.text)) if c.strip()]
    grammar = r"(?:tet\s*(?:nam\s*)?20\d{2}|20\d{2}|(?:day la\s+)?khoang\s+(?:thoi gian\s+)?(?:(?:toi|minh|tui)\s+)?co the di|(?:di doc\s+)?(?:mien trung|tay nguyen)\s+(?:chi la\s+)?(?:uu tien|bat buoc))"
    return bool(clauses) and all(
        re.fullmatch(grammar, c) and clarification_targets(message.model_copy(update={"text": c}), previous)
        for c in clauses
    )


def route_answer_grounded(condition, text):
    members = getattr(condition.value, "members", [])
    names = [m.raw for m in members] or (condition.trace.raw_values if condition.trace else [])
    folded = fold(text)
    return bool(names) and all(fold(name) in folded for name in names)


def clarification_targets(message, previous):
    """Targets explicitly answered by a bounded grammar; never generate answers."""
    from requirements.temporal import availability_cue

    if previous is None:
        return []
    text = fold(message.text)
    targets = []
    for q in previous.clarifications:
        clear = False
        if q.reason_code == "DATE_YEAR_REQUIRED":
            tet_group = any(
                isinstance(c.value, TemporalValue)
                and c.value.holiday == "tet"
                and q.field_path.startswith(f"temporal_groups.{c.value.group_id}.")
                for c in previous.conditions
            )
            clear = bool(
                tet_group
                and re.search(r"\btet\s*(?:nam\s*)?20\d{2}\b", text)
                or sum(other.reason_code == "DATE_YEAR_REQUIRED" for other in previous.clarifications) == 1
                and re.fullmatch(r"20\d{2}[.!]?", text)
            )
        elif q.reason_code == "TEMPORAL_SEMANTICS_REQUIRED":
            clear = availability_cue(message.text) or bool(
                re.search(r"\b(?:ngay di|ngay ve|khoi hanh)\b[^.;\n]{0,25}\bco dinh\b", text)
            )
        elif q.reason_code == "CONDITION_STRENGTH_REQUIRED":
            c = next((c for c in previous.conditions if q.field_path == f"conditions.{c.id}.strength"), None)
            clear = bool(
                c
                and c.field == "route"
                and route_answer_grounded(c, message.text)
                and re.search(SIGNALS["route"], text)
                and re.search(r"\b(?:uu tien|bat buoc)\b", text)
            )
        if clear:
            targets.append(q)
    return targets


class SlotExtractor:
    def __init__(self, nim):
        self.nim = nim
        self.slots = ExtraSlots()
        self.sources = {}

    async def extract(self, message, previous=None, *, feedback=None):
        method = getattr(self.nim, "extract_v2", self.nim.extract)
        extraction, metrics = await method(message, previous, feedback=feedback)
        self.slots = ExtraSlots.model_validate(
            {k: getattr(extraction, k) for k in ExtraSlots.model_fields if hasattr(extraction, k)}
        )
        self.extraction = extraction
        if clarification_only(message, previous) and extraction.operations:
            error = AppError(
                "LLM_INVALID_OUTPUT", "Reply clarification thuần không được trích lại conditions cũ.", 502
            )
            error.repair_hint = "reply_mode=answers_only: set operations=[]; return answers for actual previous.clarifications IDs, quote/value from CURRENT message only. Do NOT replace dates or route from previous. Backend applies the answers to existing values atomically."
            raise error
        coverage_guard(extraction, message, previous)
        # Completeness guard for explicit UI control grammar; never infer a condition here.
        dimensions = {
            "tiet kiem": "cost",
            "chi phi": "cost",
            "thoai mai": "comfort",
            "nhip di": "pace",
            "van hoa": "culture",
        }
        supplied = {p.dimension: p.level for p in self.slots.preference_updates}
        text = fold(message.text)
        for clause in re.split(r"[.;\n]", text):
            if re.search(r"\b(khong|giu nguyen|truoc|cu)\b", clause):
                continue
            matches = list(
                re.finditer(
                    r"(tiet kiem|chi phi|thoai mai|nhip di|van hoa)\s*(?:len\s*)?muc\s*([0-5])\b", clause
                )
            )
            if len({m.group(1) for m in matches}) != len(matches):
                continue
            for match in matches:
                dimension, level = dimensions[match.group(1)], int(match.group(2))
                if supplied.get(dimension) != level:
                    error = AppError("LLM_INVALID_OUTPUT", "Thiếu preference slot user nêu tường minh.", 502)
                    error.repair_hint = f"Bắt buộc giữ preference_updates dimension={dimension}, level={level}, quote nguyên văn duy nhất; không tạo unsupported hoặc bỏ slot."
                    raise error
        self.sources = {}
        for pref in self.slots.preference_updates:
            self.sources[f"preference_levels.{pref.dimension}"] = ground(message, pref.quote).model_dump(
                mode="json"
            )
        urls = self.slots.reference_urls_update
        if urls:
            if any(u not in urls.quote for u in urls.urls):
                raise AppError("LLM_INVALID_OUTPUT", "URL phải có trong quote gốc.", 502)
            self.sources["reference_urls"] = ground(message, urls.quote).model_dump(mode="json")
        notes = self.slots.notes_update
        if notes:
            if notes.text and notes.text not in notes.quote:
                raise AppError("LLM_INVALID_OUTPUT", "Notes phải có trong quote gốc.", 502)
            self.sources["notes"] = ground(message, notes.quote).model_dump(mode="json")
        return extraction, metrics

    def finish_requirement(self, parsed, message, previous):
        from domain.semantic import SemanticRequirement
        from requirements.semantic import answer_clarification, finalize_v2

        if not isinstance(parsed, SemanticRequirement):
            return parsed
        if self.slots.answers and previous is None:
            raise AppError("LLM_INVALID_OUTPUT", "Answer cần context trước.", 502)
        questions = {q.id: q for q in previous.clarifications} if previous else {}
        seen = set()
        for raw in self.slots.answers:
            if raw.clarification_id not in questions or raw.clarification_id in seen:
                raise AppError("LLM_INVALID_OUTPUT", "Answer stale hoặc trùng clarification ID.", 502)
            seen.add(raw.clarification_id)
            q = questions[raw.clarification_id]
            target_ids = (
                {q.field_path.split(".")[1]}
                if q.field_path.startswith("conditions.")
                else {
                    c.id
                    for c in previous.conditions
                    if isinstance(c.value, TemporalValue)
                    and q.field_path.startswith(f"temporal_groups.{c.value.group_id}.")
                }
            )
            if any(
                op.target_id in target_ids
                or op.condition
                and op.condition.id in target_ids
                or op.op == "replace_tree"
                for op in self.extraction.operations
            ):
                raise AppError(
                    "LLM_INVALID_OUTPUT", "Answer và operation đụng cùng target trong một lượt.", 502
                )
            source = ground(message, raw.quote)
            if raw.value_raw not in raw.quote:
                raise AppError("LLM_INVALID_OUTPUT", "Answer value không có trong quote.", 502)
            if q.reason_code == "DATE_YEAR_REQUIRED":
                if not re.fullmatch(r"20\d{2}", raw.value_raw):
                    raise AppError("LLM_INVALID_OUTPUT", "Năm trả lời không rõ.", 502)
                group = [
                    c
                    for c in previous.conditions
                    if isinstance(c.value, TemporalValue) and c.value.group_id == q.field_path.split(".")[1]
                ]
                key = "holiday_year" if group and group[0].value.holiday == "tet" else "year"
                answer = {key: int(raw.value_raw)}
            elif q.reason_code == "TEMPORAL_SEMANTICS_REQUIRED":
                from requirements.temporal import availability_cue

                if availability_cue(raw.quote):
                    answer = {"semantics": "availability"}
                elif re.search(r"\b(co dinh|dung ngay)\b", fold(raw.quote)):
                    answer = {"semantics": "exact"}
                else:
                    raise AppError("LLM_INVALID_OUTPUT", "Semantics answer chưa có căn cứ.", 502)
            elif q.reason_code == "CONDITION_STRENGTH_REQUIRED":
                condition = next(
                    (c for c in previous.conditions if q.field_path == f"conditions.{c.id}.strength"), None
                )
                if (
                    condition
                    and condition.field == "route"
                    and not route_answer_grounded(condition, raw.quote)
                ):
                    error = AppError(
                        "LLM_INVALID_OUTPUT", "Strength answer chưa nhắc đúng route đang được hỏi.", 502
                    )
                    error.repair_hint = "Quote phải nhắc route của condition đang được hỏi và strength cue từ CURRENT message. Không trả lời câu hỏi miền Trung bằng câu ưu tiên Tây Nguyên; dùng operation sửa route nếu user thay đổi route."
                    raise error
                text = fold(raw.value_raw)
                if text in {"bat buoc", "hard"}:
                    answer = "hard"
                elif text in {"uu tien", "soft"}:
                    answer = "soft"
                else:
                    raise AppError("LLM_INVALID_OUTPUT", "Strength answer chưa rõ.", 502)
            elif q.reason_code == "LUNAR_LEAP_REQUIRED":
                text = fold(raw.value_raw)
                if text not in {"thang nhuan", "nhuan", "thang thuong", "khong nhuan"}:
                    raise AppError("LLM_INVALID_OUTPUT", "Leap answer chưa rõ.", 502)
                answer = text in {"thang nhuan", "nhuan"}
            else:
                raise AppError("LLM_INVALID_OUTPUT", "Answer reason chưa được hỗ trợ.", 502)
            try:
                parsed = answer_clarification(parsed, q, answer, source)
            except AppError as exc:
                raise AppError("LLM_INVALID_OUTPUT", exc.message, 502) from exc
        return finalize_v2(parsed)


def coverage_guard(extraction, message, previous):
    """Check explicit positive signals; this is not a general NLP replacement."""
    from requirements.semantic import tour_type_problem

    raw_conditions = list(extraction.conditions) + [
        op.condition for op in extraction.operations if op.condition
    ]
    text = fold(message.text)
    missing = []
    classification_errors = [problem for c in raw_conditions if (problem := tour_type_problem(c))]
    grounding_errors = []
    for c in raw_conditions:
        try:
            source = ground(message, c.quote)
            if c.field in QUALITATIVE_FIELDS:
                expected = "negative" if c.operator == "excludes" else "positive"
                if qualitative_polarities(c.field, message, source) != {expected}:
                    grounding_errors.append(
                        f"{c.id}: quote định tính sai concept/polarity. 'Không cần/không quan tâm' => bỏ preference, không excludes; 'không thích/tránh' mới excludes; giữ đúng quote/context CURRENT message."
                    )
        except AppError as exc:
            grounding_errors.append(
                f"{c.id}: {exc.message}; quote phải unique và nguyên văn CURRENT message."
            )
        if c.field not in {"shopping_stops", "flight_stops"}:
            for slot in c.raw_values:
                if not slot or fold(slot) not in fold(c.quote):
                    grounding_errors.append(
                        f"{c.id}: raw value {slot!r} không có trong quote {c.quote!r}. Chọn quote đúng chứa mốc/giá trị này trong CURRENT message."
                    )
    dimensions = {
        "cost": r"(?:tiet kiem|chi phi)",
        "comfort": "thoai mai",
        "pace": "nhip di",
        "culture": "van hoa",
    }
    for pref in getattr(extraction, "preference_updates", []):
        pattern = r"\b" + dimensions[pref.dimension] + r"\s*(?:len\s*)?muc\s*" + str(pref.level) + r"\b"
        if not re.search(pattern, fold(pref.quote)):
            grounding_errors.append(
                f"preference_updates.{pref.dimension}: mức {pref.level} không được nêu tường minh trong quote. Không suy slider từ 'ưu tiên/giá hợp lý'; bỏ update này nếu user chưa nói mức 0–5."
            )
    for field, pattern in SIGNALS.items():
        if not has_positive(field, message.text):
            continue
        if previous and any(
            op.op == "remove" and any(c.id == op.target_id and c.field == field for c in previous.conditions)
            for op in extraction.operations
        ):
            continue
        if not any(c.field == field and re.search(pattern, fold(c.quote)) for c in raw_conditions):
            # Mentioning a preserved condition without requesting an edit is allowed.
            if previous and any(c.field == field for c in previous.conditions):
                continue
            missing.append(field)
    duplicate_ids = []
    if previous is None or any(
        q.reason_code
        in {"CORE_FIELD_REQUIRED", "BUDGET_CAP_REQUIRED", "CORE_FIELD_BRANCH_REQUIRED", "PARTY_REQUIRED"}
        for q in previous.clarifications
    ):
        seen = set()
        for condition in raw_conditions:
            key = (
                condition.field,
                condition.operator,
                condition.strength,
                getattr(condition, "scope", None),
                tuple(fold(v) for v in condition.raw_values),
            )
            if key in seen:
                duplicate_ids.append(condition.id)
            seen.add(key)
        # Bounded omission checks only: the LLM still extracts and grounds every value.
        money = re.search(
            r"\b(?:ngan sach|gia tour|chi phi)\s*(?:(?:toi da|khoang|tam|duoi|khong qua|la)\s*)?"
            r"\d+(?:[.,]\d+)*\s*(?:trieu|tr|trd|vnd|dong|usd)\b",
            text,
        )
        negated_money = money and re.search(
            r"\b(?:khong can|khong quan tam|bo qua)\s*$",
            text[: money.start()],
        )
        if money and not negated_money and not any(c.field == "estimated_cost" for c in raw_conditions):
            missing.append("estimated_cost (numeric budget)")
        adults = re.search(r"\b\d+\s+nguoi lon\b", text)
        negated_adults = adults and re.search(
            r"\b(?:khong phai|khong co)\s*$",
            text[: adults.start()],
        )
        if (
            adults
            and not negated_adults
            and (extraction.party is None or extraction.party.adults_raw is None)
        ):
            missing.append("party.adults_raw/adults_quote")
        if extraction.party and extraction.party.adults_raw is not None:
            party_quote = fold(extraction.party.adults_quote or "")
            for condition in raw_conditions:
                quote = fold(condition.quote)
                # Only a complete repeated party clause; do not drop broader unsupported requests.
                pure_party = re.fullmatch(r"(?:(?:toi|minh|tui|di|co|gom)\s+)*\d+\s+nguoi lon[.,!]?", quote)
                if condition.field == "unsupported" and pure_party and quote.strip(".,!") in party_quote:
                    duplicate_ids.append(condition.id)
    if previous:
        for op in extraction.operations:
            old = next((c for c in previous.conditions if c.id == op.target_id), None)
            if (
                op.op == "replace"
                and old
                and old.field == "estimated_cost"
                and old.strength == "hard"
                and op.condition
                and op.condition.strength == "soft"
                and not re.search(r"\b(?:uu tien|tam|khoang|thich|neu duoc|khong bat buoc)\b", fold(op.quote))
            ):
                missing.append("hard budget strength preserved on value-only update")
    if missing or duplicate_ids or classification_errors or grounding_errors:
        error = AppError("LLM_INVALID_OUTPUT", "Extraction bỏ sót nhu cầu tường minh.", 502)
        error.repair_hint = (
            "Giữ conditions/operations có quote cho các ý đang thiếu: "
            + ", ".join(missing)
            + ". Numeric budget dùng field=estimated_cost, raw_values số+đơn vị gốc, quote đủ basis/currency. "
            + "Số người lớn chỉ đặt trong party; không đặt thành date/unsupported condition. "
            + ("Loại predicates trùng ở IDs: " + ", ".join(duplicate_ids) + ". " if duplicate_ids else "")
            + "Giữ đúng một predicate cho mỗi nhu cầu, không nhân bản ngày đi thay cho budget/party. "
            + "Không tự thêm giá trị/metric/slider chưa được nói."
            + ("\n" + "\n".join(classification_errors) if classification_errors else "")
            + ("\n" + "\n".join(grounding_errors) if grounding_errors else "")
        )
        raise error
    if previous:
        answered = {a.clarification_id for a in getattr(extraction, "answers", [])}
        omitted = []
        for q in clarification_targets(message, previous):
            cid = q.field_path.split(".")[1] if q.field_path.startswith("conditions.") else None
            if cid and any(
                op.target_id == cid and op.op in {"remove", "replace"} for op in extraction.operations
            ):
                continue
            if q.id not in answered:
                omitted.append(f"{q.id} ({q.reason_code})")
        if omitted:
            error = AppError("LLM_INVALID_OUTPUT", "Bỏ sót câu trả lời clarification tường minh.", 502)
            error.repair_hint = (
                "Thêm answers cho TẤT CẢ targets đã trả lời: "
                + ", ".join(omitted)
                + ". Mỗi answer giữ clarification_id thật, value_raw nguyên văn trong quote. Không replace hai dates bằng năm mới."
            )
            raise error
    if previous is None and re.search(
        r"\btu\s+\d{1,2}/\d{1,2}\s+am[^.\n]{0,30}den\s+(?:mung|mong)\s+\d+\s+tet", text
    ):
        dates = {c.field: c for c in raw_conditions if c.field in {"departure_date", "return_date"}}
        if len(dates) != 2:
            error = AppError("LLM_INVALID_OUTPUT", "Khoảng âm lịch cần giữ hai mốc và đúng semantics.", 502)
            error.repair_hint = "Hai conditions departure_date/return_date, temporal cùng group/calendar vietnamese_lunar, raw_values tách riêng hai mốc nguyên văn từ input. Không tự suy năm/duration. Resolver quyết định semantics từ câu user."
            raise error
