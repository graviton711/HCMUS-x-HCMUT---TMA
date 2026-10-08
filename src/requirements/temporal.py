"""Grounded temporal intents and checked Vietnamese UTC+7 conversion."""

import re
from datetime import date

from vi_lunaire import lunar_to_solar, solar_to_lunar

from domain.common import AppError
from domain.semantic import TemporalValue
from requirements.normalize import fold, ground

CONVERTER_VERSION = "vi-lunaire-2026.4.11-vn-utc7-roundtrip-v1"


def lunar_date(year, month, day, leap=False):
    if (
        any(type(n) is not int for n in (year, month, day))
        or type(leap) is not bool
        or not 1 <= month <= 12
        or not 1 <= day <= 30
    ):
        raise ValueError("INVALID_LUNAR_DATE")
    if not 2000 <= year <= 2099:
        raise ValueError("DATE_YEAR_OUT_OF_RANGE")
    solar = lunar_to_solar(year, month, day, leap=leap)
    check = solar_to_lunar(solar.year, solar.month, solar.day)
    if (check.year, check.month, check.day, check.leap) != (year, month, day, leap):
        raise ValueError("INVALID_LUNAR_DATE")
    return solar


def lunar_context(text):
    return bool(re.search(r"\bam(?: lich)?\b|\btet\b", fold(text)))


def availability_cue(text):
    text = fold(text)
    return bool(
        re.search(
            r"khoang[^.\n]{0,65}co the di|(?:toi|minh|tui) ranh|co the khoi hanh bat ky|khong bat buoc khoi hanh dung",
            text,
        )
    )


def exact_cue(text):
    return bool(re.search(r"(?:khoi hanh|ngay di|ngay ve|ve)\s+(?:co dinh|dung (?:ngay|mung))", fold(text)))


def tet_window(text):
    matches = list(
        re.finditer(
            r"\btu\s+(\d{1,2}/\d{1,2}\s+am)[^.\n]{0,30}?den\s+((?:mung|mong)\s+\d{1,2}\s+tet)", fold(text)
        )
    )
    return matches[0] if len(matches) == 1 else None


def resolve_temporal(value):
    data = value.model_dump()
    data.update(resolved_date=None, converter_version=None)
    if value.semantics == "departure_window":
        data["reason"] = "TEMPORAL_SEMANTICS_UNSUPPORTED"
    elif value.semantics == "ambiguous":
        data["reason"] = "TEMPORAL_SEMANTICS_REQUIRED"
    elif value.calendar == "unresolved":
        data["reason"] = "CALENDAR_REQUIRED"
    elif value.day is None or value.month is None:
        data["reason"] = "DATE_NEEDS_CLARIFICATION"
    else:
        year = value.year
        if value.holiday == "tet" and value.holiday_year is not None:
            year = value.holiday_year - (value.month >= 11)
            if value.year_origin == "explicit" and value.year is not None and value.year != year:
                data["reason"] = "TEMPORAL_YEAR_CONFLICT"
                return TemporalValue.model_validate(data)
            data["year_origin"] = "holiday_anchor"
        if year is None:
            data["reason"] = "DATE_YEAR_REQUIRED"
        else:
            data["year"] = year
            try:
                if value.calendar == "vietnamese_lunar":
                    leap = value.leap
                    if leap is None:
                        try:
                            lunar_date(year, value.month, 1, True)
                        except ValueError:
                            leap = False
                        else:
                            data["reason"] = "LUNAR_LEAP_REQUIRED"
                            return TemporalValue.model_validate(data)
                    solar = lunar_date(year, value.month, value.day, leap)
                    data.update(leap=leap, converter_version=CONVERTER_VERSION)
                else:
                    solar = date(year, value.month, value.day)
                    data["converter_version"] = "gregorian-date-v1"
                data.update(resolved_date=solar.isoformat(), reason=None)
            except ValueError:
                data["reason"] = (
                    "INVALID_LUNAR_DATE" if value.calendar == "vietnamese_lunar" else "INVALID_DATE"
                )
    return TemporalValue.model_validate(data)


def normalize_temporal(raw, message):
    if len(raw.raw_values) != 1:
        raise ValueError("DATE_NEEDS_CLARIFICATION")
    slot = raw.raw_values[0]
    text, quote = fold(slot), fold(raw.quote)
    metadata = getattr(raw, "temporal", None)
    window = tet_window(message.text)
    paired = window is not None and text.removeprefix("tu ").removeprefix("den ") in {window[1], window[2]}
    gregorian = bool(re.search(r"\bduong(?: lich)?\b", text)) and not lunar_context(slot)
    lunar = not gregorian and (lunar_context(raw.quote) or paired)
    calendar = metadata.calendar if metadata else "vietnamese_lunar" if lunar else "gregorian"
    if lunar and calendar != "vietnamese_lunar":
        raise AppError("LLM_INVALID_OUTPUT", "Lịch âm/Tết không được trích thành ngày dương.", 502)
    if calendar == "vietnamese_lunar" and not lunar:
        raise AppError("LLM_INVALID_OUTPUT", "Calendar lịch âm cần quote có căn cứ.", 502)
    m = re.fullmatch(
        r"(?:tu\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?(?:\s+(?:am(?: lich)?|duong(?: lich)?|nhuan))*",
        text,
    )
    holiday_day = re.fullmatch(r"(?:den\s+)?(?:mung|mong)\s*(\d{1,2})\s*(?:tet)?", text)
    if m:
        day, month = int(m[1]), int(m[2])
        year = int(m[3]) if m[3] else None
    elif holiday_day and "tet" in quote:
        day, month, year = int(holiday_day[1]), 1, None
    else:
        raise ValueError("DATE_NEEDS_CLARIFICATION")
    sources = []
    holiday = "tet" if calendar == "vietnamese_lunar" and "tet" in fold(message.text) else None
    holiday_year = None
    if metadata:
        for name, quote_name in (("year_raw", "year_quote"), ("holiday_year_raw", "holiday_year_quote")):
            supplied = getattr(metadata, name)
            if supplied is not None:
                supplied_quote = getattr(metadata, quote_name)
                if (
                    not supplied_quote
                    or not re.fullmatch(r"20\d{2}", supplied)
                    or supplied not in supplied_quote
                ):
                    raise AppError("LLM_INVALID_OUTPUT", "Năm phải được giữ nguyên từ quote.", 502)
                sources.append(ground(message, supplied_quote))
                if name == "holiday_year_raw":
                    if not re.search(r"tet\s*(?:nam\s*)?" + supplied, fold(supplied_quote)):
                        raise AppError("LLM_INVALID_OUTPUT", "Năm Tết cần anchor Tết rõ ràng.", 502)
                    holiday_year = int(supplied)
                else:
                    year = int(supplied)
    # Exact explicit Tet anchor can be normalized without guessing a relative year.
    anchors = set(re.findall(r"tet\s*(?:nam\s*)?(20\d{2})\b", fold(message.text)))
    if holiday and holiday_year is None and len(anchors) == 1:
        holiday_year = int(next(iter(anchors)))
        match = re.search(r"Tết\s*(?:năm\s*)?20\d{2}", message.text, re.I)
        if match:
            sources.append(ground(message, match[0] if message.text.count(match[0]) == 1 else message.text))
    group_id = metadata.group_id if metadata and metadata.group_id else raw.id
    semantics = metadata.semantics if metadata else "single"
    if metadata is None and holiday and re.search(r"tu[^.\n]{0,45}den[^.\n]{0,20}tet", fold(message.text)):
        group_id = "tet_window"
        semantics = "availability" if availability_cue(message.text) else "ambiguous"
    if paired:
        group_id = "tet_window"
        semantics = (
            "availability"
            if availability_cue(message.text)
            else "exact"
            if exact_cue(message.text)
            else "ambiguous"
        )
        derivation = ground(message, message.text)
        derivation.rule = "tet_interval_semantics_v1"
        sources.append(derivation)
    if semantics == "availability" and not availability_cue(message.text):
        raise AppError(
            "LLM_INVALID_OUTPUT", "Khoảng mơ hồ cần hỏi semantics thay vì tự ép availability.", 502
        )
    role = "end" if raw.field == "return_date" else "start" if semantics != "single" else "single"
    leap = (
        True
        if re.search(r"\bnhuan\b", quote) and "khong nhuan" not in quote
        else False
        if "khong nhuan" in quote
        else None
    )
    value = TemporalValue(
        raw=slot,
        calendar=calendar,
        group_id=group_id,
        role=role,
        semantics=semantics,
        day=day,
        month=month,
        year=year,
        year_origin="explicit" if year is not None else None,
        holiday=holiday,
        holiday_year=holiday_year,
        leap=leap,
        reason="DATE_YEAR_REQUIRED",
    )
    return resolve_temporal(value), sources
