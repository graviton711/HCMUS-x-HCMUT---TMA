import pytest
from conftest import condition, requirement
from pydantic import ValidationError

from api.dto import Edit
from domain.common import AppError
from domain.requirements import Budget, DateValue, Message, NumberValue, SetValue, Tree
from requirements.edits import apply_edits
from requirements.extraction import Extraction, Operation, RawCondition
from requirements.normalize import date_value, money, normalize
from requirements.service import finalize, from_extraction


def message(text):
    return Message(id="m1", text=text, received_at="2026-10-01T03:00:00+00:00")


def raw_budget(text, values, op="lte"):
    return normalize(RawCondition(id="budget", field="estimated_cost", operator=op, strength="hard",
                                   quote=text, raw_values=values), message(text), "Asia/Ho_Chi_Minh")


@pytest.mark.parametrize("text,value", [("2,5 triệu", 2500000), ("1.250.000đ", 1250000), ("30tr", 30000000), ("2000USD", 2000)])
def test_money(text, value):
    assert money(text) == value


def test_tour_price_default_is_visible():
    c = raw_budget("Tối đa 30tr VND cho cả nhà", ["30tr"])
    assert c.value == Budget(amount=30000000, currency="VND", basis="group_total")
    assert c.sources[-1].kind == "system_default"
    r = requirement([c], messages=[message("Tối đa 30tr VND cho cả nhà")])
    assert not any("coverage" in q.field_path for q in r.clarifications)


def test_explicit_total_overrides_default():
    c = raw_budget("Tổng chi phí chuyến đi tối đa 2000 USD cho cả hai", ["2000"])
    assert c.value.coverage == "trip_total"
    assert c.value.coverage_origin == "explicit"
    assert c.value.amount == "2000"


def test_no_currency_or_basis_invented():
    c = raw_budget("Ngân sách 30 triệu", ["30 triệu"])
    assert c.value.currency is None and c.value.basis is None
    assert {q.reason_code for q in requirement([c], messages=[message("Ngân sách 30 triệu")]).clarifications} >= {"CURRENCY_REQUIRED", "BUDGET_BASIS_REQUIRED"}


def test_shared_range_units():
    c = raw_budget("Giá tour trong khoảng 10–15 triệu đồng/người lớn", ["10", "15 triệu"], "between")
    assert c.value.amount == 10000000 and c.value.upper == 15000000
    assert c.value.basis == "per_adult"


def test_quote_grounding_rejects_invented_values():
    with pytest.raises(AppError):
        raw_budget("Ngân sách 30 triệu", ["40 triệu"])


def test_missing_year_remains_unresolved():
    c = normalize(RawCondition(id="date", field="departure_date", operator="eq", strength="hard",
                              quote="Đi ngày 10/11", raw_values=["10/11"]), message("Đi ngày 10/11"), "Asia/Ho_Chi_Minh")
    assert c.value.kind == "unresolved"


def test_relative_month_and_no_inferred_nights():
    assert date_value("tháng sau", message("tháng sau"), "Asia/Ho_Chi_Minh") == DateValue(value="2026-11-01", upper="2026-11-30")
    raw = RawCondition(id="days", field="duration_days", operator="eq", strength="hard", quote="5 ngày", raw_values=["5"])
    r = from_extraction(extraction=Extraction(conditions=[raw]), message=message("5 ngày"), requirement_id="req",
                        mode="discover", timezone="Asia/Ho_Chi_Minh", targets=[])
    assert [c.field for c in r.conditions] == ["duration_days"]


def test_or_and_soft_tree_preserved():
    m = message("Nhật hoặc Hàn, ưu tiên khách sạn 4 sao")
    extraction = Extraction(conditions=[
        RawCondition(id="dest", field="destinations", operator="contains_any", strength="hard", quote="Nhật hoặc Hàn", raw_values=["Nhật", "Hàn"]),
        RawCondition(id="hotel", field="hotel_stars_min", operator="gte", strength="soft", quote="ưu tiên khách sạn 4 sao", raw_values=["4"]),
    ])
    r = from_extraction(extraction=extraction, message=m, requirement_id="req", mode="discover", timezone="Asia/Ho_Chi_Minh", targets=[])
    assert r.conditions[0].value.items == ["country:jp", "country:kr"]
    assert r.conditions[0].operator == "contains_any"
    assert r.hard_tree.children[0].condition_id == "dest"
    assert r.preference_tree.children[0].condition_id == "hotel"


def test_remove_and_increment_preserve_other_conditions():
    initial = requirement([
        condition("destinations", SetValue(items=["country:jp"]), "contains", cid="dest"),
        condition("hotel_stars_min", NumberValue(amount=4), "gte", cid="hotel"),
        condition("estimated_cost", Budget(amount=30000000, currency="VND", basis="group_total"), "lte", cid="budget"),
    ])
    m = message("Bỏ khách sạn, tăng thêm 5tr")
    extraction = Extraction(operations=[Operation(op="remove", target_id="hotel", quote="Bỏ khách sạn"),
        Operation(op="increment_budget", target_id="budget", quote="tăng thêm 5tr", delta_raw="5tr")])
    r = from_extraction(extraction=extraction, message=m, requirement_id=initial.id, mode=initial.mode,
                        timezone=initial.timezone, targets=[], previous=initial)
    assert r.revision == 2
    assert r.conditions[0] == initial.conditions[0]
    assert {c.id for c in r.conditions} == {"dest", "budget"}
    assert next(c for c in r.conditions if c.id == "budget").value.amount == 35000000


def test_contradictory_bounds_but_not_alternatives():
    conditions = [condition("duration_days", NumberValue(amount=5), "lte", cid="c1"),
                  condition("duration_days", NumberValue(amount=7), "gte", cid="c2")]
    r = requirement(conditions)
    assert "CONTRADICTORY_CONDITIONS" in r.readiness.reasons
    data = r.model_dump()
    data["hard_tree"] = Tree(kind="any", children=r.hard_tree.children)
    r = finalize(type(r).model_validate(data))
    assert "CONTRADICTORY_CONDITIONS" not in r.readiness.reasons


def test_return_before_departure_detected():
    r = requirement([condition("departure_date", DateValue(value="2026-11-15"), "eq", cid="d"),
                     condition("return_date", DateValue(value="2026-11-10"), "lt", cid="r")])
    assert "CONTRADICTORY_CONDITIONS" in r.readiness.reasons


@pytest.mark.parametrize("value", [True, "5", -1])
def test_strict_numeric(value):
    with pytest.raises(ValidationError):
        NumberValue(amount=value)


def test_tree_cannot_drop_mandatory_condition():
    r = requirement([condition("duration_days", NumberValue(amount=5))])
    with pytest.raises(ValidationError):
        type(r).model_validate({**r.model_dump(), "hard_tree": {"kind": "all", "children": []}})


def test_typed_edit_changes_strength_and_removes_tree_leaf():
    r = requirement([condition("hotel_stars_min", NumberValue(amount=4), "gte")])
    r2 = apply_edits(r, [Edit(op="replace", target="conditions.c1.strength", value="soft")])
    assert not r2.hard_tree.children
    assert r2.preference_tree.children[-1].condition_id == "c1"
    r3 = apply_edits(r2, [Edit(op="remove", target="conditions.c1")])
    assert not r3.conditions and not r3.preference_tree.children
