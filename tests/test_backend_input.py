"""Structured requirement validation. No keyword or model extraction fallback."""

import pytest

from backend.errors import AppError
from backend.input.lunar import resolve_lunar
from backend.input.pipeline import requirement_from_form, validate_requirement


def condition(field, value, quote, operator="contains", strength="hard", condition_id="h1"):
    return {
        "id": condition_id,
        "field": field,
        "operator": operator,
        "value": value,
        "strength": strength,
        "quote": quote,
    }


def test_validates_strict_requirement_with_exact_quotes():
    raw = "Đà Lạt đi từ TP.HCM, ngân sách 8000000"
    req = validate_requirement(raw, [
        condition("destination", "Đà Lạt", "Đà Lạt"),
        condition("departure_city", "TP.HCM", "TP.HCM", condition_id="h2"),
        condition("budget_max", 8_000_000, "8000000", operator="lte", condition_id="h3"),
    ], travelers=2)
    assert req.travelers == 2
    assert [item.field for item in req.conditions] == ["destination", "departure_city", "budget_max"]
    assert req.missing == []


@pytest.mark.parametrize(
    ("field", "value", "quote", "operator"),
    [
        ("budget_max", "8 triệu", "8 triệu", "lte"),
        ("budget_max", 8_000_000, "8000000", "contains"),
        ("date_from", "27/12/2026", "27/12/2026", "eq"),
        ("date_from", "2026-02-30", "2026-02-30", "eq"),
        ("duration_days", True, "3", "eq"),
        ("transport", "xe khách", "xe khách", "eq"),
    ],
)
def test_rejects_values_that_need_guessing(field, value, quote, operator):
    with pytest.raises(AppError) as exc:
        validate_requirement(quote, [condition(field, value, quote, operator)])
    assert exc.value.code == "REQUIREMENT_INVALID"


def test_rejects_quote_not_present_verbatim():
    with pytest.raises(AppError, match="exact quote"):
        validate_requirement("Đà Lạt 3 ngày", [condition("destination", "Đà Lạt", "Da Lat")])


def test_structured_destination_choices_use_any_operator():
    raw = "Đà Lạt hoặc Hạ Long"
    req = validate_requirement(raw, [condition(
        "destination", ["Đà Lạt", "Hạ Long"], raw, operator="any"
    )])
    assert req.conditions[0].value == ["Đà Lạt", "Hạ Long"]


def test_shared_date_assumption_links_branches_with_same_range():
    raw = "cuối tháng 11 hoặc tháng 12, Cần Thơ hoặc Ninh Chữ"
    req = validate_requirement(
        raw,
        [],
        alternatives=[
            {
                "id": "a1",
                "label": "Can Tho late Nov",
                "conditions": [
                    condition("destination", "Cần Thơ", "Cần Thơ", condition_id="c1"),
                    condition("date_from", "2026-11-21", "cuối tháng 11", operator="eq", condition_id="c2"),
                    condition("date_to", "2026-11-30", "cuối tháng 11", operator="eq", condition_id="c3"),
                ],
            },
            {
                "id": "a2",
                "label": "Ninh Chu late Nov",
                "conditions": [
                    condition("destination", "Ninh Chữ", "Ninh Chữ", condition_id="c4"),
                    condition("date_from", "2026-11-21", "cuối tháng 11", operator="eq", condition_id="c5"),
                    condition("date_to", "2026-11-30", "cuối tháng 11", operator="eq", condition_id="c6"),
                ],
            },
        ],
        assumptions=[
            {
                "id": "d1",
                "kind": "date_window",
                "label": "late Nov",
                "quote": "cuối tháng 11",
                "date_from": "2026-11-21",
                "date_to": "2026-11-30",
                "condition_ids": ["c2", "c3", "c5", "c6"],
                "timezone": "Asia/Ho_Chi_Minh",
            }
        ],
    )
    assert req.assumptions[0].condition_ids == ["c2", "c3", "c5", "c6"]


def test_shared_date_assumption_rejects_mixed_ranges():
    raw = "cuối tháng 11 hoặc tháng 12"
    with pytest.raises(AppError, match="must match"):
        validate_requirement(
            raw,
            [],
            alternatives=[
                {
                    "id": "a1",
                    "label": "late Nov",
                    "conditions": [
                        condition("date_from", "2026-11-21", "cuối tháng 11", operator="eq", condition_id="c1"),
                        condition("date_to", "2026-11-30", "cuối tháng 11", operator="eq", condition_id="c2"),
                    ],
                },
                {
                    "id": "a2",
                    "label": "Dec",
                    "conditions": [
                        condition("date_from", "2026-12-01", "tháng 12", operator="eq", condition_id="c3"),
                        condition("date_to", "2026-12-31", "tháng 12", operator="eq", condition_id="c4"),
                    ],
                },
            ],
            assumptions=[
                {
                    "id": "d1",
                    "kind": "date_window",
                    "label": "mixed",
                    "quote": "cuối tháng 11",
                    "date_from": "2026-11-21",
                    "date_to": "2026-11-30",
                    "condition_ids": ["c1", "c2", "c3", "c4"],
                    "timezone": "Asia/Ho_Chi_Minh",
                }
            ],
        )


def test_departure_city_can_match_multiple_catalog_labels():
    raw = "Sài Gòn hoặc TP.HCM"
    req = validate_requirement(raw, [condition(
        "departure_city", ["Sài Gòn", "TP.HCM"], raw, operator="any"
    )])

    assert req.conditions[0].operator == "any"
    assert req.conditions[0].value == ["Sài Gòn", "TP.HCM"]


def test_form_adapter_uses_explicit_fields_only():
    req = requirement_from_form({"destinations": ["Đà Lạt"], "budget_max": 8_000_000})
    assert [(item.field, item.value) for item in req.conditions] == [
        ("destination", "Đà Lạt"),
        ("budget_max", 8_000_000),
    ]


def test_traveler_mix_is_validated_and_preserved():
    requirement = validate_requirement(
        "5 người lớn",
        [],
        travelers=5,
        traveler_mix={"adult": 5},
    )
    assert requirement.traveler_mix == {"adult": 5}

    with pytest.raises(AppError, match="add up"):
        validate_requirement(
            "5 người lớn",
            [],
            travelers=5,
            traveler_mix={"adult": 4, "child": 0},
        )


def test_reviewed_soft_weights_must_total_100():
    raw = "thích thiên nhiên và biển"
    conditions = [
        {**condition("preference", "thiên nhiên", "thiên nhiên", strength="soft", condition_id="s1"),
         "weight_percent": 65},
        {**condition("preference", "biển", "biển", strength="soft", condition_id="s2"),
         "weight_percent": 35},
    ]
    requirement = validate_requirement(raw, conditions, require_weights=True)
    assert sum(item.weight_percent or 0 for item in requirement.soft()) == 100

    with pytest.raises(AppError, match="exactly 100"):
        validate_requirement(raw, [
            {**conditions[0], "weight_percent": 70},
            {**conditions[1], "weight_percent": 20},
        ], require_weights=True)


def test_bundled_soft_preference_is_rejected():
    raw = "có xe, ăn uống, vé tham quan"
    with pytest.raises(AppError, match="bundles"):
        validate_requirement(raw, [
            condition("preference", "có xe, ăn uống, vé tham quan", "có xe, ăn uống, vé tham quan", strength="soft"),
        ], require_weights=True)


def test_single_clause_soft_preference_passes():
    raw = "có xe di chuyển"
    req = validate_requirement(raw, [
        {**condition("preference", "có xe di chuyển", "có xe di chuyển", strength="soft"), "weight_percent": 100},
    ], require_weights=True)
    assert len(req.soft()) == 1


def test_lunar_date_requires_valid_round_trip():
    assert resolve_lunar({"year": 2026, "month": 12, "day": 27}) == "2027-02-03"
    assert resolve_lunar({"year": 2027, "month": 1, "day": 4}) == "2027-02-09"
    assert resolve_lunar({"year": 2026, "month": 13, "day": 1}) is None
    assert resolve_lunar({"year": 2026, "month": 2, "day": 40}) is None
def test_transport_error_names_allowed_values():
    with pytest.raises(AppError, match="flight"):
        validate_requirement("đi xe khách", [condition("transport", "xe khách", "xe khách")])


def test_quote_error_names_condition_id():
    with pytest.raises(AppError, match="h9"):
        validate_requirement(
            "Đà Lạt 3 ngày", [condition("destination", "Đà Lạt", "Da Lat", condition_id="h9")]
        )
def test_generic_accommodation_cannot_be_a_hard_condition():
    with pytest.raises(AppError, match="too generic"):
        validate_requirement(
            "cần chỗ nghỉ", [condition("accommodation", "chỗ nghỉ", "chỗ nghỉ")]
        )


def test_qualified_accommodation_stays_a_hard_condition():
    req = validate_requirement(
        "khách sạn 5 sao", [condition("accommodation", "khách sạn 5 sao", "khách sạn 5 sao")]
    )
    assert req.conditions[0].field == "accommodation"
