import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, update
from test_v2 import Nim, budget_edit, comparison, confirm, data, finish, form, propose

from api.app import create_app
from api.store import Store, dump, sessions
from api.v2 import state
from api.v2.admin import digest
from api.v2.models import RequirementV2
from data_access.fixtures import fixture_registry, fixture_result
from data_access.gateway import DataGateway
from data_access.v2 import core_requirement, registry_from_records
from decision.v2 import build_comparison
from domain.common import AppError, now
from domain.crawl import CrawlRequest, CrawlResult
from domain.requirements import Message, QuerySpec, RequirementState
from requirements.nim import NimGateway, parse_validated
from requirements.v2 import InitialExtractionV2, RawPreference, SlotExtractor, UpdateExtractionV2


@pytest.fixture
def app(settings):
    return create_app(settings, nim=Nim())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        token = data(c.post("/v2/sessions"), 201)["token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


def fixture(r):
    request = CrawlRequest(
        request_id="test_crawl",
        mode="compare_urls" if r.targets else "discover",
        source_ids=["demo"],
        query=QuerySpec.from_requirement(
            core_requirement(r, "compare_urls" if r.targets else "discover", r.targets)
        ),
        targets=r.targets,
        deadline_at=(now() + timedelta(minutes=3)).isoformat(),
    )
    crawl = fixture_result(request)
    if not r.targets:
        crawl.source_results = [
            crawl.source_results[0].model_copy(
                update={
                    "tour_snapshot_ids": [t.snapshot_id for t in crawl.tours],
                    "offer_snapshot_ids": [o.snapshot_id for o in crawl.offers],
                }
            )
        ]
    return CrawlResult.model_validate(crawl.model_dump())


def result(r, crawl):
    return build_comparison("comparison_test", r, crawl, fixture_registry(), now().isoformat())


def test_unknown_hard_condition_is_not_recommended(client):
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=form()), 201))
    crawl = fixture(r)
    for offer in crawl.offers:
        del offer.fields["departure_date"]
    output = result(r, crawl)
    assert not output["recommendations"]["candidate_ids"]
    assert len(output["recommendations"]["needs_verification"]) == 2
    assert output["empty_reason"] == "ONLY_UNVERIFIED"


@pytest.mark.parametrize("kind", ["from", "unverified", "foreign", "stale"])
def test_price_metric_rejects_incomparable_or_unusable_quotes(client, kind):
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=form()), 201))
    crawl = fixture(r)
    quote = crawl.offers[-1].price_quotes[0]
    if kind == "from":
        quote.value.kind = "from"
    elif kind == "foreign":
        quote.value = quote.value.model_copy(update={"currency": "USD", "amount": "120"})
    elif kind == "stale":
        quote.observed_at = (now() - timedelta(days=2)).isoformat()
    else:
        payload = crawl.model_dump(mode="json")
        payload["origin"] = "source"
        for ev in payload["evidence"]:
            ev["method"] = "html"
        for snapshot in [*payload["tours"], *payload["offers"]]:
            for fact in snapshot["fields"].values():
                fact["verification"] = "supplier_published"
        crawl = CrawlResult.model_validate(payload)
    output = result(r, crawl)
    differences = [m for m in output["analysis"]["metrics"] if m["operation"] == "subtract"]
    if kind == "foreign":
        assert differences and all(m["result"] is None for m in differences)
        ids = {m["id"] for m in differences}
        assert all(not ids.intersection(c["metric_ids"]) for c in output["analysis"]["claims"])
    else:
        assert not differences
        unusable_offer = crawl.offers[-1].snapshot_id
        assert all(
            op.get("snapshot_id") != unusable_offer
            for m in output["analysis"]["metrics"]
            for op in m["operands"]
        )


def test_preference_weights_change_rank_with_public_contributions(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    hotel = {
        "id": "hotel",
        "field": "hotel_stars_min",
        "operator": "prefer_high",
        "strength": "soft",
        "value": {"kind": "number", "amount": 4},
    }
    p = propose(
        client,
        r,
        [
            {"op": "upsert_condition", "condition": hotel},
            {
                "op": "upsert_condition",
                "condition": {
                    "id": "price_preference",
                    "field": "estimated_cost",
                    "operator": "prefer_low",
                    "strength": "soft",
                    "value": {"kind": "budget", "amount": 35000000, "currency": "VND", "basis": "per_adult"},
                },
            },
            {"op": "set_preference_level", "dimension": "comfort", "level": 5},
            {"op": "set_preference_level", "dimension": "cost", "level": 0},
        ],
    )
    r2 = data(confirm(client, p))
    _, job, output = comparison(client, app, r2)
    assert job["status"] == "succeeded"
    rec = output["result"]["recommendations"]
    first = next(c for c in output["result"]["columns"] if c["id"] == rec["candidate_ids"][0])
    assert first["title"] == "[Mô phỏng] Nhật Bản 6 ngày"
    assert next(x for x in rec["items"][0]["contributions"] if x["dimension"] == "cost")["weight"] == 0


def test_or_tree_discard_and_atomic_invalid_edits(client):
    body = form()
    body["input"]["form"]["conditions"].append(
        {
            "id": "korea",
            "field": "destinations",
            "operator": "contains",
            "strength": "hard",
            "value": {"kind": "set", "items": ["country:kr"]},
        }
    )
    body["input"]["form"]["hard_tree"] = {
        "kind": "all",
        "children": [
            {
                "kind": "any",
                "children": [
                    {"kind": "predicate", "condition_id": "destination"},
                    {"kind": "predicate", "condition_id": "korea"},
                ],
            },
            {"kind": "predicate", "condition_id": "origin"},
            {"kind": "predicate", "condition_id": "date"},
            {"kind": "predicate", "condition_id": "budget"},
        ],
    }
    r = data(client.post("/v2/requirements", json=body), 201)
    invalid = client.post(
        f"/v2/requirements/{r['id']}/proposals",
        json={
            "expected_revision": 1,
            "input": {
                "kind": "structured",
                "edits": [
                    budget_edit(31000000),
                    {
                        "op": "replace_tree",
                        "tree_kind": "hard_tree",
                        "tree": {"kind": "predicate", "condition_id": "missing"},
                    },
                ],
            },
        },
    )
    assert invalid.status_code == 422
    assert data(client.get(f"/v2/requirements/{r['id']}"))["active_proposal"] is None
    p = propose(client, r, [{"op": "remove_condition", "condition_id": "korea"}])
    change = next(c for c in p["changes"] if c["condition_id"] == "korea")
    p2 = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [change["id"]],
            },
        )
    )
    assert p2["preview"]["hard_tree"] == r["hard_tree"] and not p2["changes"]


def test_duplicate_urls_and_single_pending_proposal(client):
    accepted = data(
        client.post(
            "/v2/requirements",
            json={
                "input": {"kind": "urls"},
                "reference_urls": [
                    "https://tour-demo.invalid/tour-a#price",
                    "https://tour-demo.invalid/tour-a",
                ],
            },
        ),
        201,
    )
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    assert len(p["preview"]["reference_urls"]) == 1
    response = client.post(
        f"/v2/requirements/{accepted['requirement_id']}/proposals",
        json={
            "expected_revision": 0,
            "input": {"kind": "structured", "edits": [{"op": "set_notes", "notes": "hello"}]},
        },
    )
    assert response.status_code == 409


def test_cancel_during_nim_await_prevents_late_preview(client, app):
    class DelayedNim(Nim):
        async def extract(self, message, previous=None, *, feedback=None):
            await started.put(True)
            await resume.wait()
            return await super().extract(message, previous, feedback=feedback)

    accepted = data(client.post("/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}}), 202)

    async def scenario():
        nonlocal started, resume
        started, resume = asyncio.Queue(), asyncio.Event()
        app.state.worker.v2.nim = DelayedNim()
        task = asyncio.create_task(app.state.worker.run_once())
        await started.get()
        owner = app.state.store.authenticate(client.headers["Authorization"].split()[1])
        with app.state.store.transaction() as c:
            app.state.store.cancel(c, owner, accepted["job_id"])
        resume.set()
        assert await task

    started, resume = None, None
    asyncio.run(scenario())
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    assert p["version"] == 1 and not p["preview"]["conditions"]
    assert data(client.get(f"/v2/jobs/{accepted['job_id']}"))["status"] == "cancelled"


def test_grounded_preference_chat_and_individual_discard(client, app):
    class SlotNim(Nim):
        async def extract_v2(self, message, previous=None, *, feedback=None):
            return UpdateExtractionV2(
                reference_urls_update=None,
                notes_update=None,
                preference_updates=[
                    RawPreference(dimension="cost", level=4, quote="tiết kiệm mức 4"),
                    RawPreference(dimension="comfort", level=5, quote="thoải mái mức 5"),
                ],
            ), {}

    app.state.worker.v2.nim = SlotNim()
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted = data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={
                "expected_revision": 1,
                "input": {"kind": "message", "text": "Đổi tiết kiệm mức 4 và thoải mái mức 5"},
            },
        ),
        202,
    )
    finish(app)
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    assert (
        len(p["changes"]) == 2
        and p["preview"]["provenance"]["preference_levels.cost"]["quote"] == "tiết kiệm mức 4"
    )
    cost = next(c for c in p["changes"] if c["path"] == "preference_levels.cost")
    updated = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [cost["id"]],
            },
        )
    )
    assert updated["preview"]["preference_levels"]["cost"]["level"] == 3
    assert updated["preview"]["preference_levels"]["comfort"]["level"] == 5


def test_route_scoped_idempotency_and_conflict(client):
    r = data(client.post("/v2/requirements", json=form(), headers={"Idempotency-Key": "shared"}), 201)
    assert (
        data(client.post("/v2/requirements", json=form(), headers={"Idempotency-Key": "shared"}), 201)["id"]
        == r["id"]
    )
    assert (
        client.post(
            "/v2/requirements", json=form(country="country:kr"), headers={"Idempotency-Key": "shared"}
        ).status_code
        == 409
    )
    p = data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={"expected_revision": 1, "input": {"kind": "structured", "edits": [budget_edit(30000000)]}},
            headers={"Idempotency-Key": "shared"},
        )
    )
    assert p["base_revision"] == 1


def test_partial_acquisition_keeps_reference(settings):
    settings.data_provider = "http"
    settings.crawler_url = "http://crawler.test/crawl"

    async def handler(request):
        req = CrawlRequest.model_validate(json.loads(request.content))
        if req.mode == "discover":
            raise httpx.ReadError("synthetic connection failure")
        result = fixture_result(req).model_dump(mode="json")
        result["origin"] = "source"
        for e in result["evidence"]:
            e["method"] = "html"
        for snapshot in [*result["tours"], *result["offers"]]:
            facts = list(snapshot["fields"].values()) + snapshot.get("price_quotes", [])
            if snapshot.get("pricing_complete"):
                facts.append(snapshot["pricing_complete"])
            for fact in facts:
                fact["verification"] = "supplier_published"
        return httpx.Response(200, json=result)

    gateway = DataGateway(settings, registry=fixture_registry(), transport=httpx.MockTransport(handler))
    app = create_app(settings, nim=Nim(), gateway=gateway)
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + data(c.post("/v2/sessions"), 201)["token"]
        r = data(c.post("/v2/requirements", json=form(["https://tour-demo.invalid/tour-a"])), 201)
        _, job, published = comparison(c, app, r)
        assert job["status"] == "partial", job
        assert len(published["result"]["columns"]) == 1
        assert any(sr["status"] == "error" for sr in published["result"]["source_coverage"])


def test_pause_blocks_snapshot_reuse(settings):
    settings.admin_token = "A" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + data(c.post("/v2/sessions"), 201)["token"]
        r = data(c.post("/v2/requirements", json=form(["https://tour-demo.invalid/tour-a"])), 201)
        accepted, _, _ = comparison(c, app, r)
        data(
            c.patch(
                "/v2/admin/sources/demo",
                json={"expected_version": 1, "state": "paused"},
                headers={"Authorization": "Bearer " + "A" * 32},
            )
        )
        _, job, _ = comparison(
            c, app, r, round_intent="offer_change", previous_comparison_id=accepted["comparison_id"]
        )
        assert job["status"] == "failed" and job["error"]["code"] == "SOURCE_BLOCKED"


def test_malformed_slot_quote_never_creates_diff(client, app):
    class InvalidNim(Nim):
        async def extract_v2(self, message, previous=None, *, feedback=None):
            return UpdateExtractionV2(
                reference_urls_update=None,
                notes_update=None,
                preference_updates=[RawPreference(dimension="cost", level=4, quote="not present")],
            ), {}

    app.state.worker.v2.nim = InvalidNim()
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted = data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={"expected_revision": 1, "input": {"kind": "message", "text": "ưu tiên tiết kiệm"}},
        ),
        202,
    )
    finish(app)
    assert data(client.get(f"/v2/jobs/{accepted['job_id']}"))["error"]["code"] == "LLM_INVALID_OUTPUT"
    assert data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))["changes"] == []


def test_contact_context_and_resolved_retention(client, app):
    owner = app.state.store.authenticate(client.headers["Authorization"].split()[1])
    assert (
        client.post(
            "/v2/contacts",
            json={"category": "support", "message": "hello", "context": {"session_id": "other"}},
        ).status_code
        == 404
    )
    ticket = data(
        client.post(
            "/v2/contacts", json={"category": "support", "message": "hello", "context": {"session_id": owner}}
        ),
        201,
    )
    with app.state.store.transaction() as c:
        record = json.loads(
            c.execute(
                select(state.contacts.c.payload).where(state.contacts.c.id == ticket["ticket_id"])
            ).scalar()
        )
        record.update(status="resolved", resolved_at=(now() - timedelta(days=31)).isoformat())
        c.execute(
            update(state.contacts)
            .where(state.contacts.c.id == ticket["ticket_id"])
            .values(status="resolved", payload=dump(record))
        )
    app.state.store.purge()
    with app.state.store.engine.connect() as c:
        assert not c.execute(
            select(state.contacts.c.id).where(state.contacts.c.id == ticket["ticket_id"])
        ).first()


def test_adult_subtotal_has_party_revision_and_offer_operands(client):
    r = RequirementV2.model_validate(data(client.post("/v2/requirements", json=form()), 201))
    crawl = fixture(r)
    metrics = result(r, crawl)["analysis"]["metrics"]
    subtotals = [m for m in metrics if m["operation"] == "multiply"]
    assert len(subtotals) == 2
    for metric in subtotals:
        quote, party = metric["operands"]
        assert party["requirement_id"] == r.id and party["revision"] == r.revision and party["value"] == 2
        assert metric["result"] == quote["value"] * 2
        assert metric["evidence_ids"] == quote["evidence_ids"] and metric["limitations"]
    for offer in crawl.offers:
        offer.price_quotes[0].value = offer.price_quotes[0].value.model_copy(
            update={"age_min": 18, "age_max_exclusive": 65}
        )
    assert not result(r, crawl)["analysis"]["metrics"]


def test_discard_value_preserves_explicit_tree_and_membership_dependency(client):
    r = data(client.post("/v2/requirements", json=form()), 201)
    tree = {"kind": "any", "children": r["hard_tree"]["children"]}
    p = propose(
        client, r, [budget_edit(31000000), {"op": "replace_tree", "tree_kind": "hard_tree", "tree": tree}]
    )
    budget_change = next(ch for ch in p["changes"] if ch["condition_id"] == "budget")
    updated = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [budget_change["id"]],
            },
        )
    )
    assert updated["preview"]["hard_tree"] == p["preview"]["hard_tree"]
    data(
        client.post(f"/v2/proposals/{p['id']}/cancel", json={"expected_proposal_version": updated["version"]})
    )
    p = propose(
        client,
        r,
        [
            {"op": "remove_condition", "condition_id": "date"},
            {
                "op": "replace_tree",
                "tree_kind": "hard_tree",
                "tree": {
                    "kind": "any",
                    "children": [
                        {"kind": "predicate", "condition_id": "destination"},
                        {"kind": "predicate", "condition_id": "origin"},
                        {"kind": "predicate", "condition_id": "budget"},
                    ],
                },
            },
        ],
    )
    removed = next(ch for ch in p["changes"] if ch["condition_id"] == "date")
    rejected = client.post(
        f"/v2/proposals/{p['id']}/discard-changes",
        json={
            "expected_revision": 1,
            "expected_proposal_version": p["version"],
            "change_ids": [removed["id"]],
        },
    )
    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "DISCARD_DEPENDENCY"
    assert data(client.get(f"/v2/proposals/{p['id']}"))["version"] == p["version"]
    restored = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [ch["id"] for ch in p["changes"]],
            },
        )
    )
    assert restored["preview"]["hard_tree"] == r["hard_tree"] and not restored["changes"]


def test_current_refs_survive_publication_and_job_cancel_after_crawl_await(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted, _, _ = comparison(client, app, r)
    current = data(client.get(f"/v2/requirements/{r['id']}"))
    assert current["latest_comparison_id"] == accepted["comparison_id"]
    assert current["latest_comparison_job_id"] == accepted["job_id"]
    pending = data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)
    from data_access.v2 import GatewayV2

    original = GatewayV2.collect

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(self, requirement, deadline_at):
            result = await original(self, requirement, deadline_at)
            entered.set()
            await release.wait()
            return result

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(GatewayV2, "collect", delayed)
            task = asyncio.create_task(app.state.worker.run_once())
            await asyncio.wait_for(entered.wait(), 2)
            owner = app.state.store.authenticate(client.headers["Authorization"].split()[1])
            with app.state.store.transaction() as c:
                app.state.store.cancel(c, owner, pending["job_id"])
            release.set()
            await task

    asyncio.run(scenario())
    published = data(client.get(f"/v2/comparisons/{pending['comparison_id']}"))
    assert published["status"] == "cancelled" and published["result"] is None
    with app.state.store.engine.connect() as c:
        assert not c.execute(
            select(state.snapshots.c.id).where(state.snapshots.c.comparison_id == pending["comparison_id"])
        ).first()


def test_future_schema_rejected_without_additive_ddl(tmp_path, settings):
    path = tmp_path / "future.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE schema_info (version INTEGER PRIMARY KEY)")
        c.exec_driver_sql("INSERT INTO schema_info VALUES (999)")
    settings.database_url = f"sqlite:///{path}"
    with pytest.raises(RuntimeError, match="migration required"):
        Store(settings)
    assert inspect(engine).get_table_names() == ["schema_info"]
    engine.dispose()


def test_v2_error_envelope_and_limits(client):
    for response, status in [
        (client.get("/v2/missing"), 404),
        (client.post("/v2/contacts", content="x" * 65537), 413),
        (client.post("/v2/requirements", json={"input": {"kind": "text", "text": "x" * 2001}}), 422),
    ]:
        assert response.status_code == status
        assert response.json()["schema_version"] == "2.0-draft" and response.json()["request_id"]


@pytest.mark.parametrize("repair_success", [True, False])
def test_v2_nim_schema_and_missing_preference_bounded_repair(settings, repair_success):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        required = body["response_format"]["json_schema"]["schema"]["required"]
        assert {"preference_updates", "reference_urls_update", "notes_update"} <= set(required)
        calls.append(body)
        slots = (
            [RawPreference(dimension="cost", level=4, quote="Ưu tiên tiết kiệm mức 4")]
            if len(calls) == 2 and repair_success
            else []
        )
        extraction = InitialExtractionV2(
            preference_updates=slots, reference_urls_update=None, notes_update=None
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": extraction.model_dump_json()}}]
            },
        )

    nim = NimGateway(settings, transport=httpx.MockTransport(handler))
    extractor = SlotExtractor(nim)
    message = Message(id="msg_test", text="Ưu tiên tiết kiệm mức 4.", received_at=now().isoformat())

    async def parse():
        return await parse_validated(
            extractor,
            message,
            requirement_id="req",
            mode="discover",
            timezone="Asia/Ho_Chi_Minh",
            targets=[],
            requirement_model=RequirementState,
        )

    if repair_success:
        _, metrics = asyncio.run(parse())
        assert metrics["repair_used"] and extractor.slots.preference_updates[0].level == 4
        assert extractor.sources["preference_levels.cost"]["quote"] == "Ưu tiên tiết kiệm mức 4"
    else:
        with pytest.raises(AppError) as exc:
            asyncio.run(parse())
        assert exc.value.code == "LLM_INVALID_OUTPUT"
    assert len(calls) == 2


def test_admin_paging_filters_counts_and_expired_session_history(settings):
    settings.admin_token = "A" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        created = []
        for _ in range(3):
            session = data(c.post("/v2/sessions"), 201)
            created.append(session)
            c.headers["Authorization"] = "Bearer " + session["token"]
            data(c.post("/v2/contacts", json={"category": "support", "message": "hello"}), 201)
        expired = created[0]
        with app.state.store.transaction() as db:
            db.execute(
                update(sessions)
                .where(sessions.c.id == expired["id"])
                .values(expires_at=(now() - timedelta(seconds=1)).isoformat())
            )
        app.state.store.purge()
        assert c.get("/v2/catalog").status_code == 200
        c.headers["Authorization"] = "Bearer " + expired["token"]
        assert c.get("/v2/requirements/missing").status_code == 401
        c.headers["Authorization"] = "Bearer " + "A" * 32
        first = data(c.get("/v2/admin/sessions?limit=1"))
        next_page = data(c.get("/v2/admin/sessions", params={"limit": 1, "cursor": first["next_cursor"]}))
        assert first["items"][0]["id"] != next_page["items"][0]["id"]
        expired_items = data(c.get("/v2/admin/sessions?status=expired"))["items"]
        assert [item["id"] for item in expired_items] == [expired["id"]]
        assert expired_items[0]["user_message_count"] == 0 and expired_items[0]["comparison_count"] == 0
        assert "token_hash" not in expired_items[0]
        assert len(data(c.get(f"/v2/admin/sessions/{expired['id']}/activity"))["items"]) == 1
        assert c.get("/v2/admin/sessions?cursor=***").status_code == 422
        assert c.get("/v2/admin/sessions?from=2026-01-01").status_code == 422


def test_blocked_check_revokes_access_and_empty_draft_cannot_be_approved(settings):
    settings.admin_token = "A" * 32

    async def checker(record):
        return {
            "access_status": "blocked" if record["id"] == "demo" else "approved",
            "checked_at": (now() - timedelta(seconds=1)).isoformat(),
            "valid_until": (now() + timedelta(hours=1)).isoformat(),
            "profile_ref": record["profile_ref"],
            "policy_ref": record["policy_ref"],
            "capability_digest": digest(record),
        }

    app = create_app(settings, nim=Nim(), access_checker=checker)
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + "A" * 32
        data(c.post("/v2/admin/sources/demo/checks", json={"expected_version": 1}), 202)
        finish(app)
        blocked = data(c.get("/v2/admin/sources/demo"))
        assert blocked["state"] == "paused" and blocked["access_status"] == "blocked"
        assert app.state.worker.v2.registry()[0].access_status == "blocked"
        created = data(
            c.post(
                "/v2/admin/sources",
                json={"domain": "new.invalid", "display_name": "New", "profile_ref": "profiles/new:v1"},
            ),
            201,
        )
        jid = data(c.post(f"/v2/admin/sources/{created['id']}/checks", json={"expected_version": 1}), 202)[
            "job_id"
        ]
        finish(app)
        rejected = c.post(
            f"/v2/admin/sources/{created['id']}/approvals", json={"expected_version": 2, "check_job_id": jid}
        )
        assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "SOURCE_CAPABILITY_INVALID"


def test_expired_proof_offsets_block_registry_and_admin_refresh(settings):
    settings.admin_token = "A" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + "A" * 32
        record = data(c.get("/v2/admin/sources/demo"))
        from datetime import timezone

        record["access_valid_until"] = (
            (now() - timedelta(seconds=10)).astimezone(timezone(timedelta(hours=7))).isoformat()
        )
        assert registry_from_records([record])[0].access_status == "blocked"
        with app.state.store.transaction() as db:
            db.execute(
                update(state.source_registry)
                .where(state.source_registry.c.id == "demo")
                .values(payload=dump(record))
            )
        assert c.post("/v2/admin/sources/demo/refreshes", json={"expected_version": 1}).status_code == 409


def test_message_retry_id_deduplicates_job_and_activity_without_header(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    path = f"/v2/conversations/{r['id']}/messages"
    body = {
        "client_message_id": "retry_message",
        "text": "Cho nhóm tiếp theo",
        "context": {"requirement_revision": 1},
    }
    first, retry = data(client.post(path, json=body), 202), data(client.post(path, json=body), 202)
    assert first["job_id"] == retry["job_id"]
    with app.state.store.engine.connect() as c:
        activities = (
            c.execute(select(state.activities.c.id).where(state.activities.c.kind == "message"))
            .scalars()
            .all()
        )
    assert len(activities) == 1


def test_automatic_worker_publishes_url_flow(settings):
    import time

    settings.worker_enabled = True
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        token = data(c.post("/v2/sessions"), 201)["token"]
        c.headers["Authorization"] = "Bearer " + token
        accepted = data(
            c.post(
                "/v2/requirements",
                json={"input": {"kind": "urls"}, "reference_urls": ["https://tour-demo.invalid/tour-a"]},
            ),
            201,
        )
        p = data(c.get(f"/v2/proposals/{accepted['proposal_id']}"))
        r = data(confirm(c, p))
        search = data(c.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)
        deadline = time.monotonic() + 5
        job = data(c.get(f"/v2/jobs/{search['job_id']}"))
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.03)
            job = data(c.get(f"/v2/jobs/{search['job_id']}"))
        assert job["status"] == "succeeded", job
        assert data(c.get(f"/v2/comparisons/{search['comparison_id']}"))["result"]["columns"]


def test_schema_export_has_v2_and_keeps_v1(tmp_path, monkeypatch):
    from api.cli import main
    from data_access.supabase.pricing import CatalogPricing

    monkeypatch.setattr("sys.argv", ["tour-backend", "export-schemas", "--output", str(tmp_path)])
    main()
    assert (
        json.loads((tmp_path / "Requirement.schema.json").read_text(encoding="utf-8"))["properties"][
            "schema_version"
        ]["const"]
        == "1.0"
    )
    assert (
        json.loads((tmp_path / "v2" / "RequirementV2.schema.json").read_text(encoding="utf-8"))
        == RequirementV2.model_json_schema()
    )
    assert (
        json.loads((tmp_path / "v2" / "CatalogPricing.schema.json").read_text(encoding="utf-8"))
        == CatalogPricing.model_json_schema()
    )
    assert len(list((tmp_path / "v2").glob("*.schema.json"))) == 29
    assert (tmp_path / "v2" / "AssessmentBatch.schema.json").is_file()
    assert (tmp_path / "v2" / "SemanticReport.schema.json").is_file()


def test_paused_duplicate_domain_does_not_break_active_source_routing(settings):
    settings.admin_token = "A" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        user = data(c.post("/v2/sessions"), 201)
        c.headers["Authorization"] = "Bearer " + user["token"]
        r = data(c.post("/v2/requirements", json=form(["https://tour-demo.invalid/tour-a"])), 201)
        capability = fixture_registry()[0].model_dump(mode="json")
        capability.update(source_id="draft_same_domain", supplier_id="draft_supplier")
        data(
            c.post(
                "/v2/admin/sources",
                headers={"Authorization": "Bearer " + "A" * 32},
                json={"display_name": "Draft", "capability": capability, "profile_ref": "draft:v1"},
            ),
            201,
        )
        _, job, published = comparison(c, app, r)
        assert job["status"] == "succeeded" and any(
            col["origin"] == "both" for col in published["result"]["columns"]
        )
