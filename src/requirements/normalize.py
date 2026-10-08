import calendar
import json
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from domain.common import AppError, instant, uid
from domain.requirements import (
    FIELDS,
    SET_FIELDS,
    Budget,
    Child,
    Condition,
    DateValue,
    Message,
    NumberValue,
    Party,
    SetValue,
    SourceReference,
    UnresolvedValue,
)
from requirements.extraction import RawCondition, RawParty


def fold(text: str) -> str:
    value = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in value if unicodedata.category(c) != "Mn").strip()


ALIASES = {
    "nhat": "country:jp",
    "nhat ban": "country:jp",
    "japan": "country:jp",
    "han": "country:kr",
    "han quoc": "country:kr",
    "korea": "country:kr",
    "viet nam": "country:vn",
    "vietnam": "country:vn",
    "thai lan": "country:th",
    "thailand": "country:th",
    "singapore": "country:sg",
    "dai loan": "country:tw",
    "trung quoc": "country:cn",
    "sai gon": "city:vn:hcmc",
    "tp.hcm": "city:vn:hcmc",
    "tphcm": "city:vn:hcmc",
    "ho chi minh": "city:vn:hcmc",
    "tp ho chi minh": "city:vn:hcmc",
    "hcm": "city:vn:hcmc",
    "ha noi": "city:vn:hanoi",
    "hanoi": "city:vn:hanoi",
    "da nang": "city:vn:danang",
    "tokyo": "city:jp:tokyo",
    "kyoto": "city:jp:kyoto",
    "osaka": "city:jp:osaka",
    "seoul": "city:kr:seoul",
    "busan": "city:kr:busan",
    "mien trung": "region:vn:central",
    "may bay": "flight",
    "bay": "flight",
    "xe khach": "coach",
    "xe bus": "coach",
    "tau hoa": "train",
    "ve may bay": "airfare",
    "visa": "visa",
    "bao hiem": "insurance",
}
PLACE_PARENTS = {
    "city:jp:tokyo": "country:jp",
    "city:jp:kyoto": "country:jp",
    "city:jp:osaka": "country:jp",
    "city:kr:seoul": "country:kr",
    "city:kr:busan": "country:kr",
    "city:vn:hcmc": "country:vn",
    "city:vn:hanoi": "country:vn",
    "city:vn:danang": "region:vn:central",
    "region:vn:central": "country:vn",
}


def ground(message: Message, quote: str) -> SourceReference:
    positions = [m.start() for m in re.finditer(re.escape(quote), message.text)]
    if len(positions) != 1:
        error = AppError("LLM_INVALID_OUTPUT", "Quote thiếu hoặc không xác định duy nhất trong câu gốc.", 502)
        error.repair_hint = f"Quote {json.dumps(quote, ensure_ascii=False)} xuất hiện {len(positions)} lần. Sao chép đúng nguyên văn cả dấu/chữ hoa; nếu lặp thì mở rộng quote với ngữ cảnh để unique. Không đổi raw intent."
        raise error
    return SourceReference(
        kind="text", message_id=message.id, quote=quote, start=positions[0], end=positions[0] + len(quote)
    )


def money(raw: str) -> Decimal:
    text = fold(raw).replace(" ", "")
    m = re.fullmatch(r"([0-9][0-9.,]*)(trieu|tr|k|nghin|ngan|ty)?(?:vnd|dong|d|usd|eur)?", text)
    if not m:
        raise ValueError("Unrecognized amount")
    number, suffix = m.groups()
    # Vietnamese grouping: 1.250.000; decimal comma: 2,5 triệu.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", number):
        number = number.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", number):
        number = number.replace(",", "")
    else:
        number = number.replace(",", ".")
    try:
        value = Decimal(number)
    except InvalidOperation as exc:
        raise ValueError("Ambiguous amount") from exc
    scale = {"trieu": 10**6, "tr": 10**6, "k": 1000, "nghin": 1000, "ngan": 1000, "ty": 10**9}.get(suffix, 1)
    return value * scale


def amount_from_quote(raw: str, quote: str) -> Decimal:
    """Retain a unit attached to the raw number even if the model omitted it."""
    if re.fullmatch(r"[\d.,]+", raw.strip()):
        matches = list(
            re.finditer(
                r"(?<!\d)" + re.escape(raw.strip()) + r"(?![\d.,])\s*(triệu|tr|nghìn|ngàn|k|tỷ)\b",
                quote,
                re.I,
            )
        )
        if len(matches) == 1:
            return money(matches[0].group())
        if len(matches) > 1:
            raise ValueError("AMBIGUOUS_AMOUNT_UNIT")
    try:
        return money(raw)
    except ValueError:
        # The raw slot may include its quoted basis (e.g. "30tr VND cả nhóm").
        # Accept exactly one explicit monetary expression, not other head counts.
        tokens = list(
            re.finditer(
                r"(?<!\d)[0-9][0-9.,]*\s*(?:(?:trieu|tr|nghin|ngan|k|ty)(?:\s*(?:vnd|dong|d|usd|eur))?|vnd|dong|d|usd|eur)\b",
                fold(raw),
            )
        )
        if len(tokens) != 1:
            raise ValueError("AMBIGUOUS_AMOUNT") from None
        return money(tokens[0].group())


def date_value(raw: str, message: Message, timezone: str) -> DateValue:
    text = fold(raw)
    reference = instant(message.received_at).astimezone(ZoneInfo(timezone)).date()
    if text in {"thang sau", "thang nay"}:
        month = reference.month + (text == "thang sau")
        year = reference.year + (month == 13)
        month = 1 if month == 13 else month
        return DateValue(
            value=date(year, month, 1).isoformat(),
            upper=date(year, month, calendar.monthrange(year, month)[1]).isoformat(),
        )
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return DateValue(value=date.fromisoformat(text).isoformat())
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        day, month, year = map(int, m.groups())
        return DateValue(value=date(year, month, day).isoformat())
    raise ValueError("DATE_NEEDS_CLARIFICATION")


def normalize(raw: RawCondition, message: Message, timezone: str) -> Condition:
    source = ground(message, raw.quote)
    source.rule = "vi_quoted_value_v1"
    q = fold(raw.quote)
    implicit_zero = (
        raw.field in {"shopping_stops", "flight_stops"}
        and raw.raw_values == ["0"]
        and ("khong shopping" in q or "khong mua sam" in q or "khong dung" in q or "bay thang" in q)
    )
    for value in raw.raw_values:
        if not value or (fold(value) not in q and not implicit_zero):
            raise AppError("LLM_INVALID_OUTPUT", "Raw value không có căn cứ trong quote.", 502)
    if raw.field not in FIELDS or raw.operator not in FIELDS[raw.field]:
        error = AppError("LLM_INVALID_OUTPUT", "Field/operator không nằm trong contract.", 502)
        error.repair_hint = f"Invalid operator {raw.operator} for {raw.field}. Allowed: {sorted(FIELDS.get(raw.field, []))}. Keep the user's comparison meaning."
        raise error
    strength, operator = raw.strength, raw.operator
    if operator in {"near", "prefer_low", "prefer_high"}:
        strength = "soft"
    if "khong can" in q and raw.field != "unsupported":
        raise AppError("LLM_INVALID_OUTPUT", "Không cần không phải điều kiện phủ định mới.", 502)
    sources = [source]
    try:
        if raw.field == "unsupported":
            raise ValueError("UNSUPPORTED_CONDITION")
        if raw.field in SET_FIELDS:
            items = [ALIASES.get(fold(v)) for v in raw.raw_values]
            if not items or any(v is None for v in items):
                raise ValueError("UNKNOWN_ENTITY")
            value = SetValue(items=list(dict.fromkeys(items)))
            source.rule = "catalog_aliases_v1"
        elif raw.field == "estimated_cost":
            source.rule = "vi_money_v1"
            if not 1 <= len(raw.raw_values) <= 2:
                raise ValueError("BUDGET_NEEDS_CLARIFICATION")
            amounts = [amount_from_quote(v, raw.quote) for v in raw.raw_values]
            if (
                len(amounts) == 2
                and re.fullmatch(r"[\d.,]+", raw.raw_values[0])
                and re.search(r"tr|triệu|nghìn|ty|tỷ", raw.raw_values[1], re.I)
            ):
                unit = re.sub(r"^[\d.,\s]+", "", raw.raw_values[1])
                amounts[0] = money(raw.raw_values[0] + unit)
                source.rule = "shared_range_unit_v1"
            currency = "VND" if re.search(r"\bvnd\b|\bdong\b|\d\s*d\b", q) else None
            if re.search(r"\busd\b|\beur\b", q):
                currency = "USD" if "usd" in q else "EUR"
            basis = None
            if re.search(r"ca (nha|nhom|hai)|cho nhom|tong nhom", q):
                basis = "group_total"
            elif re.search(r"(/|moi |cho mot )nguoi lon|/adult", q):
                basis = "per_adult"
            elif re.search(r"(/|moi |cho mot )nguoi\b", q):
                basis = "per_person"
            explicit = "gia tour" in q or "chi phi chuyen di" in q or "toan bo chuyen di" in q
            coverage = "trip_total" if "chi phi chuyen di" in q or "toan bo chuyen di" in q else "tour_price"
            if not explicit:
                sources.append(
                    SourceReference(
                        kind="system_default",
                        field_path="value.coverage",
                        submitted_value="tour_price",
                        rule="budget_tour_price_v1",
                    )
                )

            def wire(a):
                if currency in (None, "VND") and a == a.to_integral():
                    return int(a)
                return format(a, "f")

            value = Budget(
                amount=wire(amounts[0]),
                upper=wire(amounts[1]) if len(amounts) == 2 else None,
                currency=currency,
                basis=basis,
                coverage=coverage,
                coverage_origin="explicit" if explicit else "system_default",
            )
        elif raw.field in {"departure_date", "return_date"}:
            if not raw.raw_values:
                raise ValueError("DATE_NEEDS_CLARIFICATION")
            value = date_value(raw.raw_values[0], message, timezone)
            source.rule = "vi_calendar_v1"
            if len(raw.raw_values) == 2:
                upper = date_value(raw.raw_values[1], message, timezone)
                value = DateValue(value=value.value, upper=upper.upper or upper.value)
            flexible = re.search(r"linh hoat\s+(\d+)\s+ngay\s+moi phia", q)
            if flexible and value.upper is None:
                days = int(flexible.group(1))
                if days > 31:
                    raise ValueError("DATE_FLEXIBILITY_TOO_LARGE")
                day = date.fromisoformat(value.value)
                value = DateValue(
                    value=(day - timedelta(days=days)).isoformat(),
                    upper=(day + timedelta(days=days)).isoformat(),
                )
                source.rule = "vi_date_flexibility_v1"
            if value.upper is not None:
                operator = "between"
        else:
            if implicit_zero:
                values = [0]
                source.rule = "explicit_no_stops_v1"
            elif operator in {"prefer_low", "prefer_high"} and not raw.raw_values:
                values = [1 if raw.field == "hotel_stars_min" else 0]
                source.rule = "direction_only_placeholder_v1"
            else:
                values = []
                for token in raw.raw_values:
                    m = re.fullmatch(r"\s*(\d+)\s*(?:ngày|đêm|sao|ngay|dem)?\s*", token, re.I)
                    if not m:
                        raise ValueError("NUMBER_NEEDS_CLARIFICATION")
                    values.append(int(m.group(1)))
                if not 1 <= len(values) <= 2:
                    raise ValueError("NUMBER_NEEDS_CLARIFICATION")
            value = NumberValue(amount=values[0], upper=values[1] if len(values) == 2 else None)
    except ValueError as exc:
        reason = str(exc)
        value = UnresolvedValue(
            raw=raw.quote,
            reason=reason if re.fullmatch(r"[A-Z][A-Z_]{1,80}", reason) else "VALUE_NEEDS_CLARIFICATION",
        )
    return Condition(
        id=raw.id, field=raw.field, operator=operator, value=value, strength=strength, sources=sources
    )


def normalize_party(raw: RawParty | None, previous: Party, message: Message) -> Party:
    if raw is None:
        return previous.model_copy(deep=True)
    party = previous.model_dump()
    sources = list(previous.sources)
    if raw.adults_raw is not None:
        if not raw.adults_quote or raw.adults_raw not in raw.adults_quote or not raw.adults_raw.isdigit():
            raise AppError("LLM_INVALID_OUTPUT", "Số người lớn chưa có căn cứ.", 502)
        if not re.search(
            r"(?<!\d)" + re.escape(raw.adults_raw) + r"(?!\d)\s*(?:nguoi lon|adults?)\b",
            fold(raw.adults_quote),
        ):
            raise AppError(
                "LLM_INVALID_OUTPUT", "Không suy người lớn từ tuổi hoặc số người chưa rõ loại khách.", 502
            )
        sources.append(ground(message, raw.adults_quote))
        party["adults"] = int(raw.adults_raw)
    if raw.children is not None:
        if not raw.children and previous.children:
            raise AppError(
                "LLM_INVALID_OUTPUT",
                "Xóa toàn bộ trẻ em cần structured edit có xác nhận field; không suy từ danh sách model rỗng.",
                502,
            )
        children = []
        for quote in {child.quote for child in raw.children}:
            mentions = sum(child.quote == quote for child in raw.children)
            count = re.search(r"(?<!\d)(\d+)\s*(?:be|tre(?: em)?|con nho)\b", fold(quote))
            expected = int(count.group(1)) if count else 1
            if mentions != expected:
                raise AppError(
                    "LLM_INVALID_OUTPUT", "Số trẻ được trích xuất không khớp số trẻ trong quote.", 502
                )
        for child in raw.children:
            sources.append(ground(message, child.quote))
            if child.age_raw is not None and (
                child.age_raw not in child.quote or not child.age_raw.isdigit()
            ):
                raise AppError("LLM_INVALID_OUTPUT", "Tuổi trẻ chưa có căn cứ.", 502)
            if child.age_raw is not None and not re.search(
                r"(?<!\d)" + re.escape(child.age_raw) + r"\s*tuoi\b", fold(child.quote)
            ):
                raise AppError("LLM_INVALID_OUTPUT", "Không suy tuổi trẻ từ số lượng trẻ.", 502)
            children.append(
                Child(id=uid("child"), age=int(child.age_raw) if child.age_raw is not None else None)
            )
        party["children"] = children
    if raw.rooming_quote is not None:
        sources.append(ground(message, raw.rooming_quote))
        party["rooming"] = raw.rooming_quote
    party["sources"] = sources
    return Party.model_validate(party)
