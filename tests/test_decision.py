from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import condition, requirement

from data_access.fixtures import fixture_registry, fixture_result
from decision.engine import compare, compare_interval, estimate_cost, evaluate, fold_tree
from domain.common import now
from domain.crawl import CrawlRequest, CrawlResult
from domain.requirements import Budget, Child, NumberValue, Party, QuerySpec, SetValue, Target, Tree


@pytest.fixture
def data():
    r = requirement()
    return fixture_result(CrawlRequest(request_id="crawl", mode="discover", source_ids=["demo"],
        query=QuerySpec.from_requirement(r), targets=[], deadline_at=(now() + timedelta(minutes=2)).isoformat()))


@pytest.mark.parametrize("kind,states,want", [
    ("all", ["pass", "unknown"], "unknown"), ("all", ["fail", "unknown"], "fail"),
    ("all", ["pass", "pass"], "pass"), ("any", ["pass", "unknown"], "pass"),
    ("any", ["fail", "unknown"], "unknown"), ("any", ["fail", "fail"], "fail"),
])
def test_three_valued_logic(kind, states, want):
    tree = Tree(kind=kind, children=[Tree(kind="predicate", condition_id=f"c{i}") for i in range(2)])
    assert fold_tree(tree, {f"c{i}": s for i, s in enumerate(states)}) == want


@pytest.mark.parametrize("op,lo,hi,want", [("lte", 30, 30, "pass"), ("lt", 30, 30, "fail"),
    ("lte", 20, None, "unknown"), ("lte", 31, None, "fail"), ("gte", 30, None, "pass"), ("gt", 30, 30, "fail")])
def test_budget_bounds(op, lo, hi, want):
    assert compare_interval(op, Decimal(lo), Decimal(hi) if hi is not None else None, Decimal(30)) == want


def test_party_cost_with_child(data, timestamp):
    party = Party(adults=2, children=[Child(id="child", age=8)])
    budget = Budget(amount=30000000, currency="VND", basis="group_total")
    price = estimate_cost(budget, party, data.offers[0], fixture_registry()[0], timestamp, True)
    assert price["lower"] == price["upper"] == 27000000
    assert len(price["evidence_ids"]) == 3
    missing = estimate_cost(budget, party, data.offers[1], fixture_registry()[0], timestamp, True)
    assert missing["lower"] is None and missing["upper"] is None
    assert missing["reasons"] == ["PRICE_MISSING_OR_AMBIGUOUS"]


def test_missing_price_coverage_is_not_pass(data, timestamp):
    data.offers[0].pricing_complete = None
    budget = Budget(amount=100000000, currency="VND", basis="group_total")
    result = estimate_cost(budget, Party(adults=2), data.offers[0], fixture_registry()[0], timestamp, True)
    assert result["lower"] is None
    assert result["reasons"] == ["PRICE_COVERAGE_UNCONFIRMED"]


def test_partial_itinerary_does_not_prove_absence(data, timestamp):
    tour = data.tours[0]
    tour.fields["destinations"].completeness = "partial"
    c = condition("destinations", SetValue(items=["city:jp:tokyo"]), "excludes")
    result = evaluate(c, tour, None, Party(), fixture_registry()[0], timestamp, True)
    assert result["status"] == "unknown"


def test_stale_price_not_eligible(data):
    c = condition("estimated_cost", Budget(amount=20000000, currency="VND", basis="per_adult"), "lte")
    later = (now() + timedelta(days=2)).isoformat()
    out = evaluate(c, data.tours[0], data.offers[0], Party(), fixture_registry()[0], later, True)
    assert out["status"] == "unknown"


def test_multiple_offers_do_not_mix_prices(data, timestamp):
    t = Target(target_id="a", url=data.tours[0].canonical_url)
    u = Target(target_id="missing", url="https://unapproved.example/tour")
    c = condition("estimated_cost", Budget(amount=30000000, currency="VND", basis="per_adult"), "lte")
    r = requirement([c]).model_dump()
    r.update(mode="compare_urls", targets=[t, u])
    from domain.requirements import Requirement
    from requirements.service import finalize
    r = finalize(Requirement.model_validate(r))
    duplicate = data.offers[0].model_copy(update={"snapshot_id": "second"})
    # Pure engine input already validated by gateway; focus selection behavior here.
    data.offers.append(duplicate)
    data.source_results[0].target_id = "a"
    data.source_results[0].offer_snapshot_ids.append("second")
    result = compare(r, data, fixture_registry(), timestamp)
    assert len(result["targets"]) == 2
    assert result["targets"][1]["status"] == "error"
    assert result["candidates"][0]["offer_snapshot_id"] is None
    assert result["candidates"][0]["evaluations"][0]["reason_code"] == "MULTIPLE_OFFERS_UNSELECTED"


def test_empty_conditions_dont_claim_eligible(data, timestamp):
    result = compare(requirement(), data, fixture_registry(), timestamp)
    assert result["filter_applied"] is False
    assert all(c["eligibility"] is None for c in result["candidates"])


def test_soft_preference_does_not_exclude(data, timestamp):
    c = condition("hotel_stars_min", NumberValue(amount=5), "gte", "soft")
    result = compare(requirement([c]), data, fixture_registry(), timestamp)
    assert all(c["eligibility"] is None for c in result["candidates"])
    assert result["trade_offs"]


def test_cross_offer_evidence_rejected(data):
    body = data.model_dump()
    body["offers"][0]["price_quotes"][0]["evidence_ids"] = body["offers"][1]["price_quotes"][0]["evidence_ids"]
    with pytest.raises(ValueError, match="snapshot mismatch"):
        CrawlResult.model_validate(body)
