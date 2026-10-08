import asyncio
import copy
import json
from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import condition, requirement
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from api.app import create_app
from api.settings import Settings
from api.store import dump
from api.v2 import state
from data_access.gateway import DataGateway
from data_access.supabase.adapter import CatalogAdapter, candidate_id, lookup_url, source_id
from data_access.supabase.reader import REQUIRED, SupabaseRepository, database_error
from decision.semantic import evaluate
from decision.v2 import tour_identity
from domain.common import AppError, now
from domain.crawl import CrawlRequest, SourceCapability
from domain.crawl_v2 import CrawlResultV2
from domain.requirements import Party, QuerySpec, Requirement, SetValue, Target


@pytest.fixture
def rows():
    at = now()
    p = {
        "id": 1,
        "source_key": "a" * 64,
        "display_name": "Test provider",
        "website": "https://catalog-example.invalid",
        "observed_at": at,
    }
    t = {
        "id": 1,
        "record_key": "b" * 64,
        "provider_id": 1,
        "url": "https://catalog-example.invalid/tour-one",
        "canonical_url": "",
        "observed_at": at,
        "tour_name": "Test Japan tour",
        "departure_city": "Hồ Chí Minh",
        "destinations": ["Tokyo", "Unknown Place"],
        "route": ["Tokyo"],
        "transport": "mixed",
        "duration_days": 5,
        "duration_nights": 5,
        "price": Decimal("10000000"),
        "currency": "VND",
        "price_type": "from",
        "itinerary": "Test itinerary",
        "inclusions": "Test inclusions",
        "exclusions": "",
        "cancellation_policy": "Test cancellation",
        "surcharges": "",
        "child_policy": "",
        "evidence": {"observed_at": at.isoformat(), "record_evidence": "verified"},
    }
    o = {
        "id": 1,
        "record_key": "c" * 64,
        "tour_id": 1,
        "observed_at": at,
        "departure_date": (at + timedelta(days=30)).date(),
        "price": Decimal("10000000"),
        "price_by_age": {"adult": 10000000, "child": 9000000, "infant": 2000000},
        "single_supplement": Decimal("0"),
        "availability": "available",
        "evidence": {"observed_at": at.isoformat()},
    }
    return p, t, o


@pytest.fixture
def config(tmp_path):
    return Settings(
        _env_file=None,
        data_provider="supabase",
        supabase_tour_db_url="postgresql://test:secret@localhost/catalog",
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        worker_enabled=False,
    )


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def one(self):
        return self.rows[0]

    def scalar_one(self):
        return next(iter(self.rows[0].values()))


class Engine:
    def __init__(self, rows):
        p, t, o = rows
        self.providers, self.tours, self.offers = [p], [t], [o]
        self.calls, self.closed, self.failure = [], False, None
        self.schema = [
            {"table_name": table, "column_name": column}
            for table, columns in REQUIRED.items()
            for column in columns
        ]

    def connect(self):
        if self.failure:
            raise self.failure
        return nullcontext(self)

    def begin(self):
        return nullcontext()

    def dispose(self):
        self.closed = True

    def execute(self, statement, params=None):
        sql, params = str(statement), params or {}
        self.calls.append((sql, copy.deepcopy(params)))
        if "information_schema" in sql:
            return Result(self.schema)
        if "set_config" in sql:
            return Result([{"set_config": params["ms"]}])
        if "SHOW transaction_read_only" in sql:
            return Result([{"read_only": "on"}])
        if sql.startswith("SELECT (SELECT count(*)"):
            return Result(
                [{"providers": len(self.providers), "tours": len(self.tours), "offers": len(self.offers)}]
            )
        if "public.providers" in sql:
            return Result(copy.deepcopy(self.providers))
        if "public.tours" in sql:
            if "provider_id IN" not in sql:
                return Result(copy.deepcopy([t for t in self.tours if t["id"] in params["ids"]]))
            return Result(
                copy.deepcopy([t for t in self.tours if t["provider_id"] in params["ids"]][: params["lim"]])
            )
        if "public.offers" in sql:
            groups = {tid: [] for tid in params["ids"]}
            for o in sorted(self.offers, key=lambda x: (x["departure_date"], x["id"])):
                if o["tour_id"] in groups:
                    groups[o["tour_id"]].append(o)
            ranked = [
                dict(o, catalog_order=i + 1, catalog_total=len(group))
                for group in groups.values()
                for i, o in enumerate(group)
            ]
            ranked.sort(key=lambda o: (o["catalog_order"], o["tour_id"]))
            return Result(copy.deepcopy(ranked[: params["lim"]]))
        raise AssertionError(sql)


def repo_for(config, rows):
    engine = Engine(rows)
    return SupabaseRepository(config, engine=engine), engine


def crawl_request(repo, mode="discover", urls=()):
    sources = repo.registry()
    r = requirement([condition("destinations", SetValue(items=["country:jp"]), operator="contains")])
    return CrawlRequest(
        request_id="crawl_catalog",
        mode=mode,
        source_ids=[s.source_id for s in sources],
        query=QuerySpec.from_requirement(r),
        targets=[Target(target_id=f"target_{i}", url=u) for i, u in enumerate(urls)],
        deadline_at=(now() + timedelta(seconds=30)).isoformat(),
    ), r


def imported(rows):
    p, t, o = rows
    a = CatalogAdapter("crawl_test")
    tour = a.add_tour(t, p)
    offer = a.add_offer(o)
    a.payload["source_results"] = [
        {
            "source_id": source_id(p),
            "status": "partial",
            "tour_snapshot_ids": [tour["snapshot_id"]],
            "offer_snapshot_ids": [offer["snapshot_id"]],
        }
    ]
    return a.finish()


def field_proof(t):
    return {
        "record_key": t["record_key"],
        "field": "departure_city",
        "value": "Hồ Chí Minh",
        "url": t["url"],
        "raw_value": "Hồ Chí Minh",
        "raw_quote": "Khởi hành từ Hồ Chí Minh",
        "locator": "#origin",
        "method": "html",
        "observed_at": t["observed_at"].isoformat(),
    }


def test_config_requires_postgres_and_hides_credentials():
    with pytest.raises(ValidationError) as e:
        Settings(_env_file=None, data_provider="supabase", supabase_tour_db_url="https://super-secret@host")
    assert "super-secret" not in str(e.value)


def test_probe_schema_and_catalog_scope(rows, config):
    repo, engine = repo_for(config, rows)
    p = repo.probe()
    assert p["counts"] == {"providers": 1, "tours": 1, "offers": 1} and p["transaction_read_only"] == "on"
    assert repo.registry()[0].limits == {"catalog_read_only": 1, "live_refresh": 0}
    assert not repo.registry()[0].freshness_seconds
    assert all(sql.startswith(("SELECT", "SHOW")) for sql, _ in engine.calls)
    engine.schema = [
        r for r in engine.schema if not (r["table_name"] == "offers" and r["column_name"] == "price")
    ]
    with pytest.raises(AppError) as e:
        repo.registry()
    assert e.value.code == "SUPABASE_SCHEMA_MISMATCH" and e.value.details["missing_columns"] == {
        "offers": ["price"]
    }
    repo.close()
    assert engine.closed


def test_import_does_not_promote_verified_or_invent_values(rows):
    out = imported(rows)
    t, o = out.tours[0], out.offers[0]
    assert t.fields["departure_origin"].value == "city:vn:hcmc"
    assert (
        t.fields["destinations"].value == ["city:jp:tokyo"]
        and t.fields["destinations"].completeness == "partial"
    )
    assert t.fields["transport"].data_state == "unsupported" and t.fields["transport"].raw_value == "mixed"
    assert "return_date" not in o.fields and "availability" not in o.fields
    assert o.catalog_fields["availability_status"].value == "available"
    assert o.catalog_fields["unclassified_prices"].value["child"] == 9000000
    assert len(o.price_quotes) == 1 and o.price_quotes[0].value.kind == "from"
    assert o.price_quotes[0].value.coverage == "unspecified"
    assert all(e.method == "database_record" and e.record_ref for e in out.evidence)
    c = condition("departure_origin", SetValue(items=["city:vn:hcmc"]), operator="in")
    ev = evaluate(c, t, o, Party(), None, now().isoformat())
    assert ev["status"] == "unknown" and ev["reason_code"] == "FIELD_UNVERIFIED"


def test_valid_proof_is_field_bound(rows):
    _, t, _ = rows
    t["evidence"]["fields"] = {"departure_city": field_proof(t)}
    out = imported(rows)
    fact = out.tours[0].fields["departure_origin"]
    assert fact.verification == "supplier_published"
    ev = next(e for e in out.evidence if e.id in fact.evidence_ids)
    assert ev.method == "html" and ev.record_ref is None
    c = condition("departure_origin", SetValue(items=["city:vn:hcmc"]), operator="in")
    assert evaluate(c, out.tours[0], None, Party(), None, now().isoformat())["status"] == "pass"


@pytest.mark.parametrize(
    "change",
    [
        {"record_key": "wrong"},
        {"field": "destinations"},
        {"value": "Hà Nội"},
        {"url": "https://catalog-example.invalid/other-tour"},
        {"url": "https://evil.invalid/tour-one"},
        {"observed_at": "2000-01-01T00:00:00Z"},
        {"raw_quote": "No matching quote"},
        {"raw_value": "Hà Nội", "raw_quote": "Khởi hành từ Hà Nội"},
        {"verification": "independently_verified"},
    ],
)
def test_bad_proof_retains_unverified(rows, change):
    _, t, _ = rows
    proof = field_proof(t)
    proof.update(change)
    t["evidence"]["fields"] = {"departure_city": proof}
    out = imported(rows)
    assert out.tours[0].fields["departure_origin"].verification == "unverified"
    assert any(i.code == "CATALOG_FIELD_PROOF_INVALID" for i in out.issues)


def test_record_provenance_cannot_be_verified(rows):
    body = imported(rows).model_dump()
    body["tours"][0]["fields"]["departure_origin"]["verification"] = "supplier_published"
    with pytest.raises(ValidationError, match="cannot verify"):
        CrawlResultV2.model_validate(body)


def test_stable_snapshots_and_catalog_update(rows):
    first = imported(rows)
    assert imported(rows) == first
    p, t, _ = rows
    assert candidate_id(t, p) == tour_identity(first.tours[0])
    t["tour_name"] = "Updated title"
    second = imported(rows)
    assert (
        first.tours[0].snapshot_id != second.tours[0].snapshot_id
        and first.tours[0].tour_id == second.tours[0].tour_id
    )
    assert first.offers[0].snapshot_id != second.offers[0].snapshot_id
    assert second.offers[0].tour_snapshot_id == second.tours[0].snapshot_id
    assert first.tours[0].title == "Test Japan tour"


def test_atomic_isolation_and_future_timestamp(rows):
    p, t, o = rows
    a = CatalogAdapter("crawl_test")
    t["duration_days"] = "broken"
    a.add_tour(t, p)
    assert a.payload["tours"][0]["fields"]["duration_days"]["data_state"] == "invalid"
    old = copy.deepcopy(a.payload)
    o["departure_date"] = "invalid-date"
    with pytest.raises(ValueError):
        a.add_offer(o)
    assert a.payload == old
    bad = copy.deepcopy(t)
    bad["observed_at"] = now() + timedelta(days=1)
    with pytest.raises(ValueError):
        a.add_tour(bad, p)
    assert a.payload == old


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://CATALOG-example.invalid/tour-one?utm_source=x#section",
            "https://catalog-example.invalid/tour-one",
        ),
        (
            "https://catalog-example.invalid/tour-one?date=2027-02-04&utm_medium=x",
            "https://catalog-example.invalid/tour-one?date=2027-02-04",
        ),
    ],
)
def test_tracking_only_url_normalization(url, expected):
    assert lookup_url(url) == expected


@pytest.mark.asyncio
async def test_budget_exclusions_and_missing_url(rows, config):
    repo, engine = repo_for(config, rows)
    other = copy.deepcopy(engine.tours[0])
    other.update(id=2, record_key="d" * 64, url="https://catalog-example.invalid/tour-two")
    engine.tours.append(other)
    req, r = crawl_request(repo)
    out = await repo.collect(req, conditions=r.conditions, candidate_limit=1)
    assert len(out.tours) == 1 and out.source_results[0].truncated
    follow = await repo.collect(
        req, conditions=r.conditions, candidate_limit=1, exclusions=[tour_identity(out.tours[0])]
    )
    assert follow.tours[0].tour_id != out.tours[0].tour_id
    req, _ = crawl_request(repo, "compare_urls", ["https://catalog-example.invalid/missing"])
    missing = await repo.collect(req)
    assert not missing.tours and missing.source_results[0].reason_code == "CATALOG_URL_NOT_FOUND"


@pytest.mark.asyncio
async def test_empty_catalog_and_expired_deadline(rows, config):
    repo, engine = repo_for(config, rows)
    req, _ = crawl_request(repo)
    engine.tours = []
    engine.offers = []
    out = await repo.collect(req)
    assert out.source_results[0].status == "ok" and out.source_results[0].reason_code == "CATALOG_NO_MATCHES"
    calls = len(engine.calls)
    req.deadline_at = (now() - timedelta(seconds=1)).isoformat()
    with pytest.raises(AppError):
        await repo.collect(req)
    assert len(engine.calls) == calls


@pytest.mark.asyncio
async def test_invalid_catalog_url_isolated_from_valid_target(rows, config):
    repo, engine = repo_for(config, rows)
    broken = copy.deepcopy(engine.tours[0])
    broken.update(id=2, record_key="d" * 64, url="https://[invalid-host/tour")
    engine.tours.append(broken)
    req, _ = crawl_request(repo, "compare_urls", [rows[1]["url"]])
    out = await repo.collect(req)
    assert len(out.tours) == 1
    assert any(i.code == "CATALOG_RECORD_INVALID" for i in out.issues)


@pytest.mark.asyncio
async def test_offer_budget_is_fair_and_truncation_public(rows, config):
    config.supabase_tour_max_offers = 2
    repo, engine = repo_for(config, rows)
    other = copy.deepcopy(engine.tours[0])
    other.update(id=2, record_key="d" * 64, url="https://catalog-example.invalid/tour-two")
    engine.tours.append(other)
    for identifier, tour_id in [(2, 1), (3, 2)]:
        o = copy.deepcopy(engine.offers[0])
        o.update(id=identifier, record_key=str(identifier) * 64, tour_id=tour_id)
        engine.offers.append(o)
    req, _ = crawl_request(repo)
    out = await repo.collect(req)
    assert len(out.offers) == 2 and len({o.tour_snapshot_id for o in out.offers}) == 2
    assert out.source_results[0].truncated


@pytest.mark.asyncio
async def test_provider_domain_change_requires_registry_review(rows, config):
    repo, engine = repo_for(config, rows)
    req, _ = crawl_request(repo)
    engine.providers[0]["website"] = "https://changed.example.invalid"
    with pytest.raises(AppError) as error:
        await repo.collect(req)
    assert error.value.code == "CATALOG_PROVIDER_CHANGED"


def test_connection_error_is_redacted(rows, config):
    repo, engine = repo_for(config, rows)
    engine.failure = OperationalError("SQL", {}, Exception("postgresql://test:super-secret@host/catalog"))
    with pytest.raises(AppError) as e:
        repo.registry()
    assert e.value.code == "SUPABASE_UNAVAILABLE" and "super-secret" not in str(e.value.payload())


@pytest.mark.parametrize(
    "code,expected",
    [
        ("57014", "SOURCE_TIMEOUT"),
        ("42501", "SUPABASE_PERMISSION_DENIED"),
        ("42P01", "SUPABASE_SCHEMA_MISMATCH"),
        ("42703", "SUPABASE_SCHEMA_MISMATCH"),
    ],
)
def test_upstream_error_codes(code, expected):
    class Upstream(Exception):
        pass

    error = Upstream("private details")
    error.sqlstate = code
    assert database_error(error).code == expected


def test_catalog_approval_cannot_enable_live_http(rows):
    p, _, _ = rows
    s = Settings(_env_file=None, data_provider="http")
    source = SourceCapability(
        source_id=source_id(p),
        supplier_id="supplier_test",
        approved_domains=["catalog-example.invalid"],
        access_status="approved",
        checked_at=now().isoformat(),
        modes=["compare_urls"],
        limits={"catalog_read_only": 1},
    )
    g = DataGateway(s, registry=[source])
    r = Requirement(
        id="req_http",
        revision=1,
        mode="compare_urls",
        targets=[
            Target(target_id="target_one", url="https://catalog-example.invalid/tour-one"),
            Target(target_id="target_two", url="https://catalog-example.invalid/tour-two"),
        ],
    )
    out = asyncio.run(g.collect(r, (now() + timedelta(seconds=10)).isoformat()))
    assert out.source_results[0].reason_code == "SOURCE_UNSUPPORTED"


def test_supabase_v1_returns_actionable_error(rows, config):
    repo, _ = repo_for(config, rows)
    g = DataGateway(config, catalog_repository=repo)
    with pytest.raises(AppError) as e:
        asyncio.run(g.collect(requirement(), (now() + timedelta(seconds=10)).isoformat()))
    assert e.value.code == "SUPABASE_V2_REQUIRED"


def data(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def session(c):
    c.headers["Authorization"] = "Bearer " + c.post("/v2/sessions").json()["data"]["token"]


def compare(c, app, r):
    accepted = data(
        c.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": r["revision"]}), 202
    )
    assert asyncio.run(app.state.worker.run_once())
    return data(c.get(f"/v2/jobs/{accepted['job_id']}")), data(
        c.get(f"/v2/comparisons/{accepted['comparison_id']}")
    )


def test_api_url_confirm_evidence_and_snapshot_ownership(rows, config):
    repo, engine = repo_for(config, rows)
    app = create_app(config, gateway=DataGateway(config, catalog_repository=repo))
    with TestClient(app) as c:
        session(c)
        assert c.get("/health").json()["data_provider"] == "supabase"
        a = data(
            c.post("/v2/requirements", json={"input": {"kind": "urls"}, "reference_urls": [rows[1]["url"]]}),
            201,
        )
        p = data(c.get(f"/v2/proposals/{a['proposal_id']}"))
        r = data(
            c.post(
                f"/v2/proposals/{p['id']}/confirm",
                json={"expected_revision": p["base_revision"], "expected_proposal_version": p["version"]},
            )
        )
        job, pub = compare(c, app, r)
        assert job["status"] == "succeeded", job
        result = pub["result"]
        assert result["origin"] == "source" and len(result["columns"]) == 1
        price = next(x for x in result["cells"] if x["row_id"] == "published_price")
        assert (
            price["value"][0]["kind"] == "from"
            and price["verification"] == "unverified"
            and price["freshness"]["state"] == "unknown"
        )
        assert not result["analysis"]["metrics"]
        ev = data(c.get(f"/v2/evidence/{price['evidence_ids'][0]}"))
        assert ev["record_ref"]["table"] == "tours" and ev["quality"]["provenance_kind"] == "database_record"
        assert ev["deep_link"]["method"] == "page" and "#:~:text=" not in ev["deep_link"]["url"]
        assert ev["locator"]["text_quote"]["exact"] is None
        with app.state.store.engine.connect() as conn:
            assert conn.execute(select(state.snapshots.c.id)).first()
        engine.tours[0]["price"] = Decimal("20000000")
        assert price["value"][0]["amount"] == 10000000
        session(c)
        assert c.get(f"/v2/evidence/{price['evidence_ids'][0]}").status_code == 404
    assert engine.closed


def test_api_hybrid_unknown_and_source_pause(rows, config):
    repo, _ = repo_for(config, rows)
    app = create_app(config, gateway=DataGateway(config, catalog_repository=repo))
    with TestClient(app) as c:
        session(c)
        r = data(
            c.post(
                "/v2/requirements",
                json={
                    "input": {
                        "kind": "structured",
                        "form": {
                            "conditions": [
                                {
                                    "id": "origin",
                                    "field": "departure_origin",
                                    "operator": "in",
                                    "strength": "hard",
                                    "value": {"kind": "set", "items": ["city:vn:hcmc"]},
                                },
                                {
                                    "id": "dest",
                                    "field": "destinations",
                                    "operator": "contains",
                                    "strength": "hard",
                                    "value": {"kind": "set", "items": ["country:jp"]},
                                },
                                {
                                    "id": "date",
                                    "field": "departure_date",
                                    "operator": "eq",
                                    "strength": "hard",
                                    "value": {"kind": "date", "value": rows[2]["departure_date"].isoformat()},
                                },
                                {
                                    "id": "budget",
                                    "field": "estimated_cost",
                                    "operator": "lte",
                                    "strength": "hard",
                                    "value": {
                                        "kind": "budget",
                                        "amount": 20000000,
                                        "currency": "VND",
                                        "basis": "per_adult",
                                        "coverage": "tour_price",
                                    },
                                },
                            ],
                            "party": {"adults": 1},
                        },
                    },
                    "reference_urls": [rows[1]["url"]],
                },
            ),
            201,
        )
        job, pub = compare(c, app, r)
        assert job["status"] == "succeeded", job
        result = pub["result"]
        assert result["empty_reason"] == "ONLY_UNVERIFIED" and not result["recommendations"]["candidate_ids"]
        assert result["columns"][0]["origin"] == "both" and all(
            e["status"] == "unknown" for e in result["evaluations"]
        )
        with app.state.store.transaction() as conn:
            record = json.loads(conn.execute(select(state.source_registry.c.payload)).scalar_one())
            record["state"] = "paused"
            conn.execute(update(state.source_registry).values(payload=dump(record)))
        _, paused = compare(c, app, r)
        assert not paused["result"]["columns"][0]["tour_snapshot_id"]
        assert paused["result"]["source_coverage"][0]["reason_code"] == "SOURCE_BLOCKED"
