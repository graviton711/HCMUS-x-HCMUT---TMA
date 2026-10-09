"""Regression cases for real catalog route endpoints and price/date eligibility."""

import asyncio
import copy
from datetime import timedelta

import pytest
from conftest import condition, requirement
from sqlalchemy import update
from test_auth_history import identity as identity
from test_auth_history import payload
from test_catalog_validation import catalog
from test_catalog_validation import trusted as trusted
from test_supabase import config as config
from test_supabase import rows as rows
from test_v2 import form

from api.store import dump, resources
from data_access.supabase.adapter import destination_places
from decision.candidates import assess_options
from decision.engine import usable
from decision.semantic import evaluate
from domain.common import now
from domain.crawl import CrawlRequest
from domain.requirements import Budget, DateValue, Party, QuerySpec, SetValue
from domain.semantic import ConditionV2
from requirements.catalog import resolve_entities


@pytest.mark.parametrize(
    "names,expected",
    [
        (["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"], ["city:cn:shanghai", "city:cn:hangzhou"]),
        (["Hồ Chí Minh", "Đài Bắc", "Nam Đầu", "TP.HCM"], ["city:tw:taipei", "region:tw:nantou"]),
        (["Hồ Chí Minh", "Đà Nẵng", "TP.HCM"], ["city:vn:danang"]),
    ],
)
def test_origin_endpoints_not_a_destination(names, expected):
    found, partial = destination_places(names, "city:vn:hcmc")
    assert found == expected and not partial
    assert destination_places(["Hồ Chí Minh"], "city:vn:hcmc") == ([], True)
    assert destination_places(["Tokyo", "TP.HCM", "Kyoto"], "city:vn:hcmc")[0] == [
        "city:jp:tokyo",
        "city:vn:hcmc",
        "city:jp:kyoto",
    ]


@pytest.mark.parametrize("semantic", [False, True])
@pytest.mark.parametrize(
    "names,status",
    [
        (["TP.HCM", "Thượng Hải", "Ô Trấn", "TP.HCM"], "fail"),
        (["TP.HCM", "Đài Bắc", "Đài Trung", "Cao Hùng", "TP.HCM"], "fail"),
        (["TP.HCM", "Brunei Darussalam", "TP.HCM"], "fail"),
        (["TP.HCM", "Đà Lạt", "TP.HCM"], "pass"),
        (["TP.HCM", "Unknown destination", "TP.HCM"], "unknown"),
    ],
)
def test_country_filter_uses_visit_destinations_and_shared_hierarchy(
    trusted, rows, config, names, status, semantic
):
    rows[1]["destinations"] = names
    rows[1]["route"] = names.copy()
    crawl = catalog(rows, trusted[2], config)
    v = resolve_entities("destinations", ["Việt Nam"]) if semantic else SetValue(items=["country:vn"])
    c = ConditionV2.model_validate(
        {
            **condition("destinations", SetValue(items=["country:vn"]), operator="contains").model_dump(),
            "value": v.model_dump(),
        }
    )
    assert (
        evaluate(c, crawl.tours[0], None, requirement().party, trusted[2][0], now().isoformat())["status"]
        == status
    )
    assert crawl.tours[0].fields["destinations"].raw_value
    assert rows[1]["destinations"] == names
    if status != "unknown":
        assert "city:vn:hcmc" in crawl.tours[0].semantic_fields["route"].value


def test_date_mismatch_fails_only_when_fresh_and_unknown_offer_can_be_selected(trusted, rows, config):
    sources = trusted[2]
    crawl = catalog(rows, sources, config)
    tour, offer = crawl.tours[0], crawl.offers[0]
    c = condition("departure_date", DateValue(value=rows[2]["departure_date"].isoformat()), operator="eq")
    r = requirement([c])
    assert (
        evaluate(c, tour, offer, r.party, sources[0], now().isoformat())["reason_code"]
        == "FIELD_FRESHNESS_POLICY_MISSING"
    )
    selected = assess_options(r, tour, [offer], sources[0], now().isoformat(), selected_id=offer.snapshot_id)
    assert selected["selected"] == offer and selected["hard_status"] == "unknown"
    sources[0].freshness_seconds["departure_date"] = 86400
    assert evaluate(c, tour, offer, r.party, sources[0], now().isoformat())["status"] == "pass"
    other = c.model_copy(
        update={"value": DateValue(value=(rows[2]["departure_date"] + timedelta(days=1)).isoformat())}
    )
    assert evaluate(other, tour, offer, r.party, sources[0], now().isoformat())["status"] == "fail"
    assert (
        evaluate(c, tour, offer, r.party, sources[0], (now() + timedelta(days=2)).isoformat())["reason_code"]
        == "FIELD_STALE"
    )


def pricing(rows, kind="exact", amount=10000000):
    rows[1]["price_type"] = kind
    rows[2]["price_by_age"]["adult"] = amount
    rows[2]["field_meta"] = {
        "pricing": {
            "observed_at": rows[2]["observed_at"].isoformat(),
            "quotes": [
                {
                    "quote_id": "adult",
                    "amount": amount,
                    "currency": "VND",
                    "kind": kind,
                    "basis": "per_adult",
                    "coverage": "tour_price",
                }
            ],
            "extra_charges": [],
            "complete": True,
        }
    }


@pytest.mark.parametrize(
    "kind,amount,status",
    [
        ("exact", 10000000, "pass"),
        ("exact", 40000000, "fail"),
        ("from", 10000000, "unknown"),
        ("from", 40000000, "fail"),
    ],
)
def test_explicit_catalog_prices_preserve_bounds(trusted, rows, config, kind, amount, status):
    pricing(rows, kind, amount)
    sources = trusted[2]
    sources[0].freshness_seconds["price"] = 86400
    crawl = catalog(rows, sources, config)
    offer = crawl.offers[0]
    assert offer.price_quotes[0].verification == "catalog_validated"
    c = condition(
        "estimated_cost",
        Budget(amount=30000000, currency="VND", basis="per_adult", coverage="tour_price"),
        operator="lte",
    )
    e = evaluate(c, crawl.tours[0], offer, requirement().party, sources[0], now().isoformat())
    assert e["status"] == status
    if kind == "from":
        assert e["actual"]["upper"] is None
    assert not usable(offer.price_quotes[0], "price", sources[0], (now() + timedelta(days=2)).isoformat())[0]


@pytest.mark.parametrize("tamper", ["amount", "kind", "currency", "time", "complete", "boolean", "untrusted"])
def test_price_metadata_cannot_overwrite_or_self_verify(trusted, rows, config, tamper):
    pricing(rows)
    m = rows[2]["field_meta"]["pricing"]
    if tamper == "amount":
        m["quotes"][0]["amount"] = 1
    elif tamper == "kind":
        rows[1]["price_type"] = "from"
    elif tamper == "currency":
        m["quotes"][0]["currency"] = "USD"
    elif tamper == "time":
        m["observed_at"] = (now() - timedelta(days=1)).isoformat()
    elif tamper == "complete":
        m["complete"] = "true"
    elif tamper == "boolean":
        m["quotes"][0]["amount"] = True
    else:
        config.supabase_tour_trusted_domains = []
    crawl = catalog(rows, trusted[2], config)
    assert crawl.offers[0].price_quotes[0].verification == "unverified"
    if tamper != "untrusted":
        assert any(i.code == "CATALOG_PRICING_METADATA_INVALID" for i in crawl.issues)


def test_completed_history_refs_resume_wrapped_comparison_and_analysis(identity):
    client, app, _ = identity
    r = payload(client.post("/v2/requirements", json=form()), 201)
    accepted = payload(
        client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": r["revision"]}), 202
    )
    asyncio.run(app.state.worker.run_once())
    output = payload(client.get("/v2/comparisons/" + accepted["comparison_id"]))
    assert output["status"] in {"succeeded", "partial"}, output
    a = payload(
        client.post(
            "/v2/comparisons/" + accepted["comparison_id"] + "/what-if",
            json={"expected_revision": r["revision"]},
        ),
        202,
    )
    # Emulate the persisted terminal wrapper from process_what_if without calling an upstream model.
    with app.state.store.transaction() as c:
        c.execute(
            update(resources)
            .where(resources.c.id == a["analysis_id"])
            .values(status="succeeded", payload=dump({"result": {"requirement_id": r["id"]}}))
        )
    detail = payload(client.get("/v2/history/" + r["id"]))
    assert detail["comparison_id"] == accepted["comparison_id"]
    assert detail["runs"][0]["id"] == accepted["comparison_id"]
    assert detail["analysis_id"] == a["analysis_id"]


def test_retrieval_filters_fresh_wrong_date_before_pool(trusted, rows, config):
    repo, engine, sources = trusted
    pricing(rows)
    sources[0].freshness_seconds.update(departure_date=86400, price=86400)
    second_tour, second_offer = copy.deepcopy(rows[1]), copy.deepcopy(rows[2])
    second_tour.update(id=2, record_key="d" * 64, url="https://catalog-example.invalid/second")
    second_offer.update(
        id=2, record_key="e" * 64, tour_id=2, departure_date=rows[2]["departure_date"] + timedelta(days=1)
    )
    engine.tours.append(second_tour)
    engine.offers.append(second_offer)
    r = requirement(
        [
            condition("destinations", SetValue(items=["country:jp"]), operator="contains", cid="place"),
            condition(
                "departure_date",
                DateValue(value=rows[2]["departure_date"].isoformat()),
                operator="eq",
                cid="date",
            ),
            condition(
                "estimated_cost",
                Budget(amount=30000000, currency="VND", basis="per_adult", coverage="tour_price"),
                operator="lte",
                cid="cost",
            ),
        ],
        party=Party(adults=1),
    )
    req = CrawlRequest(
        request_id="fresh_schedule",
        mode="discover",
        source_ids=[s.source_id for s in sources],
        targets=[],
        query=QuerySpec.from_requirement(r),
        deadline_at=(now() + timedelta(seconds=30)).isoformat(),
    )
    crawl = asyncio.run(repo.collect(req, conditions=r.conditions, requirement=r, registry=sources))
    assert len(crawl.tours) == 1 and crawl.retrieval["offer_rejected"] == 1
    assert crawl.retrieval["pass_count"] == 1 and crawl.retrieval["unknown_count"] == 0


def test_explicit_mandatory_charge_is_counted_and_incomplete_price_never_passes(trusted, rows, config):
    pricing(rows, amount=29000000)
    terms = rows[2]["field_meta"]["pricing"]
    terms["extra_charges"] = [
        {"charge_id": "fee", "amount": 2000000, "currency": "VND", "basis": "per_adult", "required": True}
    ]
    trusted[2][0].freshness_seconds["price"] = 86400
    c = condition(
        "estimated_cost",
        Budget(amount=30000000, currency="VND", basis="per_adult", coverage="tour_price"),
        operator="lte",
    )
    crawl = catalog(rows, trusted[2], config)
    e = evaluate(c, crawl.tours[0], crawl.offers[0], requirement().party, trusted[2][0], now().isoformat())
    assert e["status"] == "fail" and e["actual"]["lower"] == 31000000
    terms["complete"] = False
    crawl = catalog(rows, trusted[2], config)
    assert (
        evaluate(c, crawl.tours[0], crawl.offers[0], requirement().party, trusted[2][0], now().isoformat())[
            "status"
        ]
        == "unknown"
    )
