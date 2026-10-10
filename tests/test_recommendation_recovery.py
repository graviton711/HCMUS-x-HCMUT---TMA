"""Listed tour caps, geography and date windows without changing payable guarantees."""

import copy
from datetime import timedelta

import pytest
from conftest import condition, requirement
from pydantic import ValidationError
from test_catalog_validation import catalog
from test_catalog_validation import trusted as trusted
from test_supabase import config as config
from test_supabase import rows as rows
from test_v2 import app as app
from test_v2 import client as client
from test_v2 import data, form

from api.v2.models import RequirementV2
from data_access.supabase.adapter import destination_places
from data_access.supabase.priority import acquisition_priority, folded_sql
from decision.candidates import assess_options
from decision.semantic import evaluate
from decision.v2 import build_comparison
from domain.common import AppError, now
from domain.crawl_v2 import CrawlResultV2
from domain.requirements import Budget, DateValue, Message, Party, Tree
from domain.semantic import BudgetV2, ConditionV2
from requirements.catalog import expand_entities, resolve_entities
from requirements.extraction import RawCondition
from requirements.search_dates import future_windows, require_future_departure
from requirements.semantic import normalize_v2


def budget(measure="listed", amount=12_000_000, **kw):
    return ConditionV2.model_validate(
        {
            **condition(
                "estimated_cost",
                Budget(amount=amount, currency="VND", basis="per_adult", coverage="tour_price"),
                operator="lte",
                cid="budget",
            ).model_dump(),
            "value": BudgetV2(
                amount=amount, currency="VND", basis="per_adult", coverage="tour_price", measure=measure, **kw
            ).model_dump(),
        }
    )


def fresh_sources(trusted):
    sources = trusted[2]
    sources[0].freshness_seconds.update(price=86400, departure_date=86400)
    return sources


@pytest.mark.parametrize(
    "measure,cap,status",
    [("listed", 12_000_000, "pass"), ("listed", 9_000_000, "fail"), ("payable", 12_000_000, "unknown")],
)
def test_from_is_listed_amount_but_never_payable_upper(trusted, rows, config, measure, cap, status):
    sources = fresh_sources(trusted)
    crawl = catalog(rows, sources, config)
    out = evaluate(
        budget(measure, cap), crawl.tours[0], crawl.offers[0], Party(adults=1), sources[0], now().isoformat()
    )
    assert out["status"] == status
    if measure == "listed":
        assert out["actual"]["measure"] == "listed"
        assert out["actual"]["price_kind"] == "from"
        assert out["actual"]["payable_upper"] is None


@pytest.mark.parametrize(
    "change", ["stale", "untrusted", "missing", "zero", "contact", "invalid_metadata", "invalid_proof"]
)
def test_listed_missing_or_stale_never_pass(trusted, rows, config, change):
    sources = fresh_sources(trusted)
    at = now().isoformat()
    if change == "stale":
        older = now() - timedelta(days=2)
        rows[2]["observed_at"] = older
        rows[2]["evidence"]["observed_at"] = older.isoformat()
    elif change == "untrusted":
        config.supabase_tour_trusted_domains = []
    elif change == "missing":
        rows[2]["price_by_age"].pop("adult")
    elif change == "zero":
        rows[2]["price_by_age"]["adult"] = 0
    elif change == "contact":
        rows[1]["price_type"] = "contact"
    elif change == "invalid_metadata":
        rows[2]["field_meta"] = {"pricing": {"complete": True}}
    else:
        rows[2]["evidence"]["fields"] = {"price_by_age.adult": {}}
    crawl = catalog(rows, sources, config)
    out = evaluate(budget(), crawl.tours[0], crawl.offers[0], Party(adults=1), sources[0], at)
    assert out["status"] == "unknown"


def test_old_budget_and_v1_keep_payable_semantics():
    value = budget().value.model_dump(exclude={"measure"})
    assert BudgetV2.model_validate(value).measure == "payable"
    assert "measure" not in Budget.model_fields
    with pytest.raises(ValidationError):
        BudgetV2(amount=1, currency="VND", coverage="trip_total", measure="listed")


@pytest.mark.parametrize(
    "state,reason", [("fresh", "usable"), ("stale", "FIELD_STALE"), ("untrusted", "FIELD_UNVERIFIED")]
)
def test_audit_reports_listed_quality_separately_from_payable(trusted, rows, config, state, reason):
    from data_access.supabase.audit import summarize

    sources = fresh_sources(trusted)
    if state == "stale":
        older = now() - timedelta(days=2)
        rows[2]["observed_at"] = older
        rows[2]["evidence"]["observed_at"] = older.isoformat()
    elif state == "untrusted":
        config.supabase_tour_trusted_domains = []
    report = summarize(catalog(rows, sources, config), sources)
    assert report["listed_prices"]["count"] == 1
    assert report["listed_prices"]["eligibility_reasons"] == {reason: 1}
    assert report["listed_prices"]["kinds"] == {"from": 1}
    assert report["listed_prices"]["payable_total_status"] == "not_calculated"
    assert report["prices"]["pricing_complete"] == 0


def test_binding_rejects_foreign_listed_evidence(trusted, rows, config):
    crawl = catalog(rows, fresh_sources(trusted), config).model_dump()
    fact = crawl["offers"][0]["listed_price_quotes"][0]
    fact["verification"] = "unverified"
    fact["evidence_ids"] = crawl["tours"][0]["fields"]["departure_origin"]["evidence_ids"]
    with pytest.raises(ValidationError, match="Listed price/evidence"):
        CrawlResultV2.model_validate(crawl)


@pytest.mark.parametrize(
    "names,expected",
    [
        (["TP.HCM – Pháp – Thụy Sĩ – Ý – Vatican"], {"country:fr", "country:ch", "country:it", "country:va"}),
        (
            ["Paris", "Lille", "Brussels", "Amsterdam"],
            {"city:fr:paris", "city:fr:lille", "city:be:brussels", "city:nl:amsterdam"},
        ),
    ],
)
def test_places_split_chain_keep_city_and_country_hierarchy(names, expected):
    found, partial = destination_places(names, "city:vn:hcmc")
    assert set(found) == expected and not partial
    assert "country:fr" in expand_entities(found, "place")
    assert "city:fr:paris" not in expand_entities(["country:fr"], "place")


def test_unknown_names_and_compound_names_not_invented():
    assert resolve_entities("destinations", ["Foo-Bar"]).members[0].entity_id is None
    assert resolve_entities("destinations", ["Bali"]).members[0].entity_id == "region:id:bali"


def date_requirement(months):
    cs = [
        condition(
            "departure_date", DateValue(value=f"{m}-01", upper=f"{m}-28"), operator="between", cid=f"d{i}"
        )
        for i, m in enumerate(months)
    ]
    r = requirement(cs)
    return r.model_copy(
        update={
            "hard_tree": Tree(kind="any", children=[Tree(kind="predicate", condition_id=c.id) for c in cs])
        }
    )


def test_nonadjacent_months_or_keeps_gap_out():
    r = date_requirement(["2026-11", "2027-01"])
    _, windows = future_windows(r, "2026-10-10T00:00:00+07:00")
    assert [lo.month for lo, _ in windows] == [11, 1]
    sql, offers, params = acquisition_priority(r, r.conditions)
    assert " OR " in offers and "EXISTS" in sql
    assert set(v for k, v in params.items() if k.startswith("date_")) == {
        "2026-11-01",
        "2026-11-28",
        "2027-01-01",
        "2027-01-28",
    }


@pytest.mark.parametrize(
    "months,reject", [(["2026-02"], True), (["2026-02", "2027-02"], False), (["2026-10"], False)]
)
def test_search_guard_only_rejects_provably_past(months, reject):
    r = date_requirement(months)
    if reject:
        with pytest.raises(AppError) as e:
            require_future_departure(r, "2026-10-10T00:00:00+07:00")
        assert e.value.code == "DEPARTURE_WINDOW_PAST"
    else:
        require_future_departure(r, "2026-10-10T00:00:00+07:00")
    require_future_departure(r.model_copy(update={"mode": "compare_urls"}), "2026-10-10T00:00:00+07:00")


def test_query_priority_binds_same_offer_date_price_and_never_filters_analysis():
    r = date_requirement(["2026-11"])
    c = budget()
    r = r.model_copy(
        update={
            "conditions": [*r.conditions, c],
            "hard_tree": Tree(kind="all", children=[r.hard_tree, Tree(kind="predicate", condition_id=c.id)]),
        }
    )
    priority, offers, params = acquisition_priority(r, r.conditions)
    assert "offers.price_by_age" in offers and "offers.departure_date" in offers
    assert "EXISTS (SELECT 1 FROM public.offers" in priority
    assert 12_000_000 in params.values()
    assert acquisition_priority(r, r.conditions, analysis=True) == ("0", "TRUE", {})
    assert "translate" in folded_sql("tours.departure_city")


def test_api_form_defaults_listed_and_preserves_value_edit(client):
    r = data(client.post("/v2/requirements", json=form()), 201)
    assert next(c for c in r["conditions"] if c["id"] == "budget")["value"]["measure"] == "listed"
    body = {
        "expected_revision": r["revision"],
        "input": {
            "kind": "structured",
            "edits": [
                {
                    "op": "replace_condition_value",
                    "condition_id": "budget",
                    "value": {
                        "kind": "budget",
                        "amount": 40_000_000,
                        "currency": "VND",
                        "basis": "per_adult",
                        "coverage": "tour_price",
                    },
                }
            ],
        },
    }
    p = data(client.post(f"/v2/requirements/{r['id']}/proposals", json=body))
    assert next(c for c in p["preview"]["conditions"] if c["id"] == "budget")["value"]["measure"] == "listed"
    older = copy.deepcopy(r)
    for c in older["conditions"]:
        if c["value"]["kind"] == "budget":
            c["value"].pop("measure")
    assert (
        next(c for c in RequirementV2.model_validate(older).conditions if c.id == "budget").value.measure
        == "payable"
    )


def test_positive_recommendation_has_listed_and_separate_raw_cost_terms(trusted, rows, config, client):
    sources = fresh_sources(trusted)
    rows[1]["surcharges"] = "Phụ thu phòng đơn: liên hệ nhà cung cấp."
    crawl = catalog(rows, sources, config)
    body = form(date=rows[2]["departure_date"].isoformat())
    body["input"]["form"]["conditions"] = [
        c for c in body["input"]["form"]["conditions"] if c["field"] != "duration_days"
    ]
    body["input"]["form"]["conditions"][3]["value"]["amount"] = 12_000_000
    body["input"]["form"]["party"]["adults"] = 1
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=body), 201))
    result = build_comparison("comparison_recovery", r, crawl, sources, now().isoformat())
    assert len(result["recommendations"]["candidate_ids"]) == 1
    assert any(row["field"] == "listed_price_quotes" for row in result["rows"])
    disclosure = result["analysis"]["cost_disclosures"][0]
    assert any(p["text"] == rows[1]["surcharges"] for p in disclosure["policies"])
    assert disclosure["offers"][0]["payable_total_status"] == "not_calculated"


def test_explicit_lower_listed_preference_is_scored_without_relaxing_cap(trusted, rows, config, client):
    sources = fresh_sources(trusted)
    crawl = catalog(rows, sources, config)
    body = form(date=rows[2]["departure_date"].isoformat())
    conditions = [c for c in body["input"]["form"]["conditions"] if c["field"] != "duration_days"]
    conditions[3]["value"]["amount"] = 12_000_000
    conditions.append(
        dict(
            id="condition_listed_price_preference",
            field="estimated_cost",
            operator="prefer_low",
            strength="soft",
            value=dict(
                kind="budget",
                measure="listed",
                amount=12_000_000,
                currency="VND",
                basis="per_adult",
                coverage="tour_price",
            ),
        )
    )
    body["input"]["form"]["conditions"] = conditions
    body["input"]["form"]["party"]["adults"] = 1
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=body), 201))
    result = build_comparison("comparison_profile_price", r, crawl, sources, now().isoformat())
    assert len(result["recommendations"]["candidate_ids"]) == 1
    item = result["recommendations"]["items"][0]
    assert item["score_interval"]["lower"] is not None
    contribution = next(
        c for c in item["contributions"] if c["condition_id"] == "condition_listed_price_preference"
    )
    assert 0 < contribution["utility"] < 1 and contribution["dimension"] == "cost"
    assert contribution["evidence_ids"]


@pytest.mark.parametrize(
    "phrase,measure",
    [
        ("ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour", "listed"),
        ("tiền thực trả tối đa 30 triệu VND mỗi người lớn cho giá tour", "payable"),
        ("tổng chi phí tối đa 30 triệu VND mỗi người lớn", "payable"),
    ],
)
def test_text_quote_determines_price_measure(phrase, measure):
    raw = RawCondition(
        id="budget",
        field="estimated_cost",
        operator="lte",
        strength="hard",
        raw_values=["30 triệu"],
        quote=phrase,
    )
    message = Message(id="m_budget", text=phrase, received_at=now().isoformat())
    assert normalize_v2(raw, message, "Asia/Ho_Chi_Minh").value.measure == measure


def test_api_rejects_new_search_in_past_but_keeps_readable_history(client):
    r = data(client.post("/v2/requirements", json=form(date="2026-02-01")), 201)
    response = client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": r["revision"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DEPARTURE_WINDOW_PAST"
    assert data(client.get(f"/v2/requirements/{r['id']}"))["conditions"] == r["conditions"]


@pytest.mark.parametrize("stale,status", [(False, "fail"), (True, "unknown")])
def test_current_month_does_not_recommend_already_departed_offer(
    trusted, rows, config, client, stale, status
):
    sources = fresh_sources(trusted)
    today = now()
    departure = (today - timedelta(days=1)).date()
    rows[2]["departure_date"] = departure
    if stale:
        rows[2]["observed_at"] = today - timedelta(days=2)
        rows[2]["evidence"]["observed_at"] = rows[2]["observed_at"].isoformat()
    crawl = catalog(rows, sources, config)
    body = form(date=departure.isoformat())
    cs = body["input"]["form"]["conditions"]
    cs[2].update(
        operator="between",
        value={
            "kind": "date",
            "value": departure.isoformat(),
            "upper": (today + timedelta(days=15)).date().isoformat(),
        },
    )
    cs[3]["value"]["amount"] = 12_000_000
    body["input"]["form"]["conditions"] = [c for c in cs if c["field"] != "duration_days"]
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=body), 201))
    result = assess_options(r, crawl.tours[0], crawl.offers, sources[0], today.isoformat())
    assert result["hard_status"] == status
    reason = next(e["reason_code"] for e in result["evaluations"] if e["field"] == "departure_date")
    assert reason == ("FIELD_STALE" if stale else "DEPARTURE_ALREADY_PASSED")


def test_priority_paging_uses_text_postgres_timeout(trusted):
    import asyncio

    from test_supabase import crawl_request

    repo, engine, sources = trusted
    request, r = crawl_request(repo)
    asyncio.run(repo.collect(request, conditions=r.conditions, requirement=r, registry=sources))
    timeouts = [params["ms"] for sql, params in engine.calls if "set_config" in sql]
    assert timeouts and all(isinstance(value, str) for value in timeouts)
