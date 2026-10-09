"""Independent examples for trusted catalog data and retained uncertainty."""

import asyncio
import json
from datetime import timedelta

import pytest
from conftest import condition, requirement
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from test_supabase import compare, crawl_request, field_proof, imported, repo_for, session
from test_supabase import config as config
from test_supabase import rows as rows
from test_v2 import data, form

from api.app import create_app
from api.settings import Settings
from api.store import dump
from api.v2 import state
from api.v2.models import ComparisonV2, RequirementV2
from data_access.gateway import DataGateway
from data_access.supabase.adapter import CatalogAdapter
from decision.engine import usable
from decision.semantic import evaluate
from decision.what_if import build_analysis, plan_analysis
from domain.common import AppError, now
from domain.crawl_v2 import CrawlResultV2
from domain.requirements import SetValue, Target, Tree
from domain.what_if import CreateWhatIf
from semantic_assessment.models import AssessmentBatch
from semantic_assessment.service import prepare, validate


@pytest.fixture
def trusted(config, rows):
    config.supabase_tour_trusted_domains = ["catalog-example.invalid"]
    rows[1]["destinations"] = ["Tokyo"]
    rows[1]["transport"] = "bus"
    repo, engine = repo_for(config, rows)
    sources = repo.registry()
    return repo, engine, sources


def catalog(rows, sources, config):
    p, t, o = rows
    adapter = CatalogAdapter(
        "catalog_test", registry=sources, trusted_domains=config.supabase_tour_trusted_domains
    )
    tour = adapter.add_tour(t, p)
    offer = adapter.add_offer(o)
    adapter.payload["source_results"] = [
        {
            "source_id": sources[0].source_id,
            "status": "ok",
            "tour_snapshot_ids": [tour["snapshot_id"]],
            "offer_snapshot_ids": [offer["snapshot_id"]],
        }
    ]
    return adapter.finish()


def test_opt_in_evaluates_origin_and_preserves_database_provenance(trusted, rows, config):
    _, _, sources = trusted
    crawl = catalog(rows, sources, config)
    tour = crawl.tours[0]
    fact = tour.fields["departure_origin"]
    assert fact.verification == "catalog_validated" and fact.completeness == "complete"
    ev = next(e for e in crawl.evidence if e.id in fact.evidence_ids)
    assert ev.method == "database_record" and ev.raw_quote == "Hồ Chí Minh"
    assert ev.catalog_validation.source_id == sources[0].source_id
    assert ev.record_ref.record_key == rows[1]["record_key"]
    for expected, status in [("city:vn:hcmc", "pass"), ("city:vn:hanoi", "fail")]:
        c = condition("departure_origin", SetValue(items=[expected]), operator="in")
        result = evaluate(c, tour, None, requirement().party, sources[0], now().isoformat())
        assert result["status"] == status


def test_record_verified_label_without_opt_in_stays_unverified(rows):
    assert imported(rows).tours[0].fields["departure_origin"].verification == "unverified"


@pytest.mark.parametrize("change", ["allowlist", "capability", "pause", "domain", "supplier"])
def test_trust_requires_every_source_binding(trusted, rows, config, change):
    _, _, sources = trusted
    if change == "allowlist":
        config.supabase_tour_trusted_domains = []
    elif change == "capability":
        sources[0].limits.pop("catalog_validated")
    elif change == "pause":
        sources[0].access_status = "blocked"
    elif change == "domain":
        rows[1]["url"] = "https://other.invalid/tour-one"
    else:
        sources[0].supplier_id = "supplier_other"
    crawl = catalog(rows, sources, config)
    assert crawl.tours[0].fields["departure_origin"].verification == "unverified"


@pytest.mark.parametrize("bad", [None, {}, {"value": "fake"}])
def test_invalid_optional_proof_never_falls_back(trusted, rows, config, bad):
    rows[1]["evidence"]["fields"] = {"departure_city": bad}
    crawl = catalog(rows, trusted[2], config)
    assert crawl.tours[0].fields["departure_origin"].verification == "unverified"
    assert crawl.tours[0].fields["duration_days"].verification == "catalog_validated"
    assert any(i.code == "CATALOG_FIELD_PROOF_INVALID" for i in crawl.issues)


def test_website_proof_keeps_supplier_published_path(trusted, rows, config):
    rows[1]["evidence"]["fields"] = {"departure_city": field_proof(rows[1])}
    crawl = catalog(rows, trusted[2], config)
    fact = crawl.tours[0].fields["departure_origin"]
    assert fact.verification == "supplier_published"
    ev = next(e for e in crawl.evidence if e.id in fact.evidence_ids)
    assert ev.method == "html" and ev.catalog_validation is None


def test_metadata_time_mismatch_not_trusted(trusted, rows, config):
    rows[1]["evidence"]["observed_at"] = (now() - timedelta(days=1)).isoformat()
    crawl = catalog(rows, trusted[2], config)
    assert crawl.tours[0].fields["departure_origin"].verification == "unverified"
    assert any(i.code == "CATALOG_METADATA_INVALID" for i in crawl.issues)


def test_canonical_url_cannot_hide_foreign_record_source(trusted, rows, config):
    rows[1]["canonical_url"] = rows[1]["url"]
    rows[1]["url"] = "https://foreign.invalid/tour-one"
    crawl = catalog(rows, trusted[2], config)
    assert crawl.tours[0].fields["departure_origin"].verification == "unverified"
    assert crawl.offers[0].fields["departure_date"].verification == "unverified"


def test_malformed_record_metadata_is_not_catalog_validated(trusted, rows, config):
    rows[1]["evidence"] = "verified"
    crawl = catalog(rows, trusted[2], config)
    assert crawl.tours[0].fields["departure_origin"].verification == "unverified"


def test_partial_places_do_not_prove_absence(trusted, rows, config):
    rows[1]["destinations"] = ["Tokyo", "Unknown Place"]
    crawl = catalog(rows, trusted[2], config)
    fact = crawl.tours[0].fields["destinations"]
    assert fact.verification == "catalog_validated" and fact.completeness == "partial"
    for expected, status in [("country:jp", "pass"), ("country:fr", "unknown")]:
        c = condition("destinations", SetValue(items=[expected]), operator="contains")
        assert (
            evaluate(c, crawl.tours[0], None, requirement().party, trusted[2][0], now().isoformat())["status"]
            == status
        )


def test_mixed_and_main_journey_are_not_inferred(trusted, rows, config):
    rows[1]["transport"] = "mixed"
    crawl = catalog(rows, trusted[2], config)
    assert crawl.tours[0].fields["transport"].data_state == "unsupported"
    assert "return_date" not in crawl.offers[0].fields
    assert "tour_type" not in crawl.tours[0].semantic_fields
    rows[1]["transport"] = "bus"
    assert catalog(rows, trusted[2], config).tours[0].fields["transport"].scope is None


def test_price_from_keeps_qualifiers_unknown(trusted, rows, config):
    crawl = catalog(rows, trusted[2], config)
    q = crawl.offers[0].price_quotes[0]
    assert q.value.kind == "from" and q.value.coverage == "unspecified"
    assert q.verification == "unverified" and crawl.offers[0].pricing_complete is None


def test_date_requires_ttl_and_rechecks_trust(trusted, rows, config):
    sources = trusted[2]
    crawl = catalog(rows, sources, config)
    fact = crawl.offers[0].fields["departure_date"]
    assert fact.verification == "catalog_validated"
    assert (
        usable(fact, "departure_date", sources[0], now().isoformat())[1] == "FIELD_FRESHNESS_POLICY_MISSING"
    )
    sources[0].freshness_seconds["departure_date"] = 3600  # Explicit test policy, not a production default.
    assert usable(fact, "departure_date", sources[0], now().isoformat())[0]
    assert not usable(fact, "departure_date", sources[0], (now() + timedelta(hours=2)).isoformat())[0]
    sources[0].limits.pop("catalog_validated")
    assert usable(fact, "departure_date", sources[0], now().isoformat())[1] == "CATALOG_TRUST_NOT_APPROVED"


@pytest.mark.parametrize("tamper", ["receipt", "checks", "publisher", "key", "time", "field", "raw"])
def test_receipt_tampering_rejected(trusted, rows, config, tamper):
    payload = catalog(rows, trusted[2], config).model_dump(mode="json")
    ev = payload["evidence"][0]
    if tamper == "receipt":
        ev["catalog_validation"] = None
    elif tamper == "checks":
        ev["catalog_validation"]["checks"] = ["schema"]
    elif tamper == "publisher":
        ev["catalog_validation"]["source_id"] = "catalog_other"
    elif tamper == "key":
        ev["record_ref"]["record_key"] = "wrong"
    elif tamper == "field":
        ev["record_ref"]["field"] = "destinations"
    elif tamper == "raw":
        ev["raw_quote"] = "Hà Nội"
    else:
        ev["observed_at"] = (now() - timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        CrawlResultV2.model_validate(payload)


@pytest.mark.parametrize("provider", ["http", "fixture"])
def test_other_transports_cannot_self_attest_catalog(trusted, rows, config, provider):
    repo, _, sources = trusted
    crawl = catalog(rows, sources, config)
    request, _ = crawl_request(repo)
    config.data_provider = provider
    gateway = DataGateway(config, registry=sources, result_model=CrawlResultV2)
    crawl.request_id = request.request_id
    with pytest.raises(AppError) as exc:
        gateway.validate_binding(crawl, request)
    assert exc.value.code == "CRAWLER_INVALID_OUTPUT"


@pytest.mark.parametrize(
    "domains", [["*.example.com"], ["https://example.com"], ["Example.com"], ["example.com", "example.com"]]
)
def test_domains_require_exact_hosts(domains):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_tour_trusted_domains=domains)


@pytest.mark.parametrize(
    "ttls", [{"price": 0}, {"itinerary": 3600}, {"price": -1}, {"price": True}, {"price": 1.5}]
)
def test_freshness_config_has_no_implicit_or_invalid_ttl(ttls):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_tour_freshness_seconds=ttls)


def test_persisted_registry_uses_current_config_and_keeps_pause(trusted, config):
    repo, _, _ = trusted
    app = create_app(config, gateway=DataGateway(config, catalog_repository=repo))
    service = app.state.worker.v2
    assert service.registry()[0].limits["catalog_validated"] == 1
    config.supabase_tour_trusted_domains = []
    assert "catalog_validated" not in service.registry()[0].limits
    config.supabase_tour_trusted_domains = ["catalog-example.invalid"]
    config.supabase_tour_freshness_seconds = {"departure_date": 7200}
    assert service.registry()[0].freshness_seconds["departure_date"] == 7200
    with app.state.store.transaction() as c:
        record = json.loads(c.execute(select(state.source_registry.c.payload)).scalar_one())
        record["state"] = "paused"
        c.execute(update(state.source_registry).values(payload=dump(record)))
    assert service.registry()[0].access_status == "blocked"


def test_catalog_text_supports_positive_soft_claim_but_not_absence(trusted, rows, config):
    crawl = catalog(rows, trusted[2], config)
    r = RequirementV2(
        id="req_soft",
        revision=1,
        mode="compare_urls",
        input_kind="urls",
        reference_urls=[rows[1]["url"]],
        targets=[Target(target_id="t1", url=rows[1]["url"])],
    )
    from domain.requirements import SourceReference
    from domain.semantic import ConditionV2, QualitativeValue

    soft_conditions = [
        ConditionV2(
            id="nature",
            field="nature",
            operator="prefer",
            strength="soft",
            value=QualitativeValue(
                raw="thiên nhiên", concept="nature", metric_policy="nature-itinerary-tags-v1"
            ),
            sources=[SourceReference(kind="form", field_path="nature")],
        )
    ]
    r = RequirementV2.model_validate(
        {
            **r.model_dump(),
            "conditions": soft_conditions,
            "preference_tree": Tree(kind="predicate", condition_id="nature"),
        }
    )
    candidates = [
        {
            "id": "tour_test",
            "tour": crawl.tours[0],
            "hard_status": "pass",
            "evaluations": [{"condition_id": "nature", "status": "unknown"}],
        }
    ]
    payload, excerpts, _ = prepare(r, candidates, crawl, config)
    excerpt = next(iter(excerpts.values()))
    assert excerpt["verification"] == "catalog_validated" and not excerpt["complete"]
    batch = AssessmentBatch.model_validate(
        {
            "items": [
                {
                    "candidate_id": "tour_test",
                    "condition_id": "nature",
                    "status": "matched",
                    "citations": [{"excerpt_id": excerpt["id"], "quote": excerpt["text"]}],
                }
            ]
        }
    )
    assert validate(batch, payload, excerpts)[0].usable_for_ranking
    batch.items[0].status = "not_matched"
    with pytest.raises(ValueError, match="Incomplete"):
        validate(batch, payload, excerpts)


def test_what_if_distinguishes_catalog_fail_from_unknown_price(trusted, rows, config):
    crawl = catalog(rows, trusted[2], config)
    r = RequirementV2(
        id="req_what_if",
        revision=1,
        mode="compare_urls",
        input_kind="urls",
        reference_urls=[rows[1]["url"]],
        targets=[Target(target_id="t1", url=rows[1]["url"])],
    )
    from domain.semantic import ConditionV2

    r = RequirementV2.model_validate(
        {
            **r.model_dump(),
            "conditions": [
                ConditionV2.model_validate(
                    condition(
                        "departure_origin", SetValue(items=["city:vn:hanoi"]), operator="in", cid="origin"
                    ).model_dump()
                )
            ],
            "hard_tree": Tree(kind="predicate", condition_id="origin"),
        }
    )
    at = now().isoformat()
    plan = plan_analysis(r, crawl, trusted[2], at, CreateWhatIf(expected_revision=1))
    result = build_analysis("analysis_test", "comparison_test", r, crawl, at, plan)
    removal = next(s for s in result.scenarios if s.kind == "remove_hard_group")
    assert result.baseline.ineligible == 1 and result.baseline.unknown == 0
    assert len(removal.proven_blocked_candidate_ids) == 1 and not removal.previously_unknown_candidate_ids
    assert removal.restriction_ratio.percent == 100


def test_api_cells_evidence_and_history_keep_catalog_status(trusted, rows, config):
    repo, _, _ = trusted
    app = create_app(config, gateway=DataGateway(config, catalog_repository=repo))
    with TestClient(app) as c:
        session(c)
        r = data(c.post("/v2/requirements", json=form()), 201)
        job, result = compare(c, app, r)
        assert job["status"] == "succeeded"
        result = result["result"]
        ComparisonV2.model_validate(result)
        cell = next(x for x in result["cells"] if x["row_id"] == "departure_origin")
        assert cell["verification"] == "catalog_validated"
        ev = data(c.get(f"/v2/evidence/{cell['evidence_ids'][0]}"))
        assert ev["quality"]["verification"] == "catalog_validated"
        assert ev["deep_link"]["method"] == "page" and ev["locator"]["text_quote"]["exact"] is None
        assert not ev["quality"]["independently_verified"]
        assert result["policy_versions"]["catalog_validation"] == "catalog-validation-v1"
        assert all(
            e["reason_code"] != "FIELD_UNVERIFIED"
            for e in result["evaluations"]
            if e["field"] == "departure_origin"
        )


def test_reader_uses_catalog_validation_before_static_filter(trusted, rows, config):
    repo, _, sources = trusted
    request, _ = crawl_request(repo)
    c = condition("departure_origin", SetValue(items=["city:vn:hanoi"]), operator="in")
    r = requirement([c])
    request.query = request.query.model_copy(update={"hard_tree": r.hard_tree})
    crawl = asyncio.run(repo.collect(request, conditions=[c], requirement=r, registry=sources))
    assert not crawl.tours and crawl.retrieval["static_rejected"] == 1


def test_comparison_rechecks_policy_after_async_assessment(trusted, config, monkeypatch):
    repo, _, _ = trusted
    app = create_app(config, gateway=DataGateway(config, catalog_repository=repo))
    original = app.state.worker.v2.assessor.run

    async def revoke(*args, **kwargs):
        report = await original(*args, **kwargs)
        config.supabase_tour_trusted_domains = []
        return report

    monkeypatch.setattr(app.state.worker.v2.assessor, "run", revoke)
    with TestClient(app) as c:
        session(c)
        r = data(c.post("/v2/requirements", json=form()), 201)
        job, comparison = compare(c, app, r)
        assert job["status"] == "failed" and job["error"]["code"] == "SOURCE_POLICY_CHANGED"
        assert comparison["status"] == "failed" and comparison.get("result") is None
        with app.state.store.engine.connect() as conn:
            assert conn.execute(select(state.snapshots.c.id)).first() is None
