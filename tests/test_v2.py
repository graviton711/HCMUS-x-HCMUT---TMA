import asyncio
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from api.app import create_app
from api.store import Store, dump, jobs, revisions, schema_info
from api.v2 import state
from api.v2.admin import digest
from api.v2.models import Interpretation
from domain.common import AppError, now
from requirements.extraction import Extraction, Operation, RawCondition


class Nim:
    async def extract(self, message, previous=None, *, feedback=None):
        if "timeout" in message.text:
            raise AppError("LLM_TIMEOUT", "Synthetic timeout", 504)
        if previous:
            conditions = [
                RawCondition(
                    id="budget",
                    field="estimated_cost",
                    operator="lte",
                    strength="hard",
                    raw_values=["32 triệu đồng mỗi người lớn"],
                    quote="32 triệu đồng mỗi người lớn",
                ),
                RawCondition(
                    id="duration",
                    field="duration_days",
                    operator="near",
                    strength="soft",
                    raw_values=["6"],
                    quote="6 ngày",
                ),
            ]
            return Extraction(
                operations=[
                    Operation(op="replace", target_id=c.id, condition=c, quote=c.quote) for c in conditions
                ]
            ), {}
        return Extraction(
            conditions=[
                RawCondition(
                    id="destination",
                    field="destinations",
                    operator="contains",
                    strength="hard",
                    raw_values=["Nhật"],
                    quote="Nhật",
                )
            ]
        ), {}

    async def interpret(self, message, context):
        if "sửa" in message.text:
            return Interpretation(intent="edit", requested_action="search")
        if "tiếp" in message.text:
            return Interpretation(intent="next_group")
        return Interpretation(intent="answer", metric_ids=[m["id"] for m in context["metrics"][:1]])


@pytest.fixture
def app(settings):
    return create_app(settings, nim=Nim())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        session = c.post("/v2/sessions").json()["data"]
        c.headers["Authorization"] = f"Bearer {session['token']}"
        yield c


def data(response, status=200):
    assert response.status_code == status, response.text
    assert response.json()["schema_version"] == "2.0-draft"
    assert response.json()["request_id"]
    return response.json()["data"]


def form(urls=None, *, country="country:jp", date="2026-11-10"):
    return {
        "input": {
            "kind": "structured",
            "form": {
                "conditions": [
                    {
                        "id": "destination",
                        "field": "destinations",
                        "operator": "contains",
                        "strength": "hard",
                        "value": {"kind": "set", "items": [country]},
                    },
                    {
                        "id": "origin",
                        "field": "departure_origin",
                        "operator": "in",
                        "strength": "hard",
                        "value": {"kind": "set", "items": ["city:vn:hcmc"]},
                    },
                    {
                        "id": "date",
                        "field": "departure_date",
                        "operator": "eq",
                        "strength": "hard",
                        "value": {"kind": "date", "value": date},
                    },
                    {
                        "id": "budget",
                        "field": "estimated_cost",
                        "operator": "lte",
                        "strength": "hard",
                        "value": {
                            "kind": "budget",
                            "amount": 35000000,
                            "currency": "VND",
                            "basis": "per_adult",
                        },
                    },
                    {
                        "id": "duration",
                        "field": "duration_days",
                        "operator": "near",
                        "strength": "soft",
                        "value": {"kind": "number", "amount": 5},
                    },
                ],
                "party": {"adults": 2},
            },
        },
        "reference_urls": urls or [],
    }


def finish(app, count=1):
    for _ in range(count):
        assert asyncio.run(app.state.worker.run_once())


def value(r, cid):
    return next(c["value"] for c in r["conditions"] if c["id"] == cid)


def propose(client, r, edits, **kwargs):
    return data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={
                "expected_revision": r["revision"],
                "input": {"kind": "structured", "edits": edits},
                **kwargs,
            },
        )
    )


def budget_edit(amount):
    return {
        "op": "replace_condition_value",
        "condition_id": "budget",
        "value": {
            "kind": "budget",
            "amount": amount,
            "currency": "VND",
            "basis": "per_adult",
            "coverage": "tour_price",
        },
    }


def confirm(client, p, key=None):
    return client.post(
        f"/v2/proposals/{p['id']}/confirm",
        json={"expected_revision": p["base_revision"], "expected_proposal_version": p["version"]},
        headers={"Idempotency-Key": key} if key else {},
    )


def comparison(client, app, r, **extra):
    accepted = data(
        client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": r["revision"], **extra}),
        202,
    )
    finish(app)
    job = data(client.get(f"/v2/jobs/{accepted['job_id']}"))
    result = data(client.get(f"/v2/comparisons/{accepted['comparison_id']}"))
    return accepted, job, result


def test_structured_hybrid_prices_evidence_and_distinct_rank(client, app):
    r = data(client.post("/v2/requirements", json=form(["https://tour-demo.invalid/tour-a"])), 201)
    assert r["mode"] == "hybrid" and r["revision"] == 1
    accepted, job, published = comparison(client, app, r)
    assert job["status"] == "succeeded", job
    result = published["result"]
    assert len(result["recommendations"]["candidate_ids"]) == 2
    assert len({c["tour_id"] for c in result["columns"]}) == len(result["columns"])
    assert any(c["origin"] == "both" for c in result["columns"])
    assert "price_quotes" in {row["id"] for row in result["rows"]}
    assert result["analysis"]["metrics"]
    eid = result["analysis"]["metrics"][0]["evidence_ids"][0]
    evidence = data(client.get(f"/v2/evidence/{eid}"))
    assert evidence["quality"]["origin"] == "synthetic"
    assert evidence["deep_link"]["status"] == "best_effort"
    with app.state.store.engine.connect() as c:
        assert c.execute(select(state.snapshots.c.id)).first()
    first = data(client.get(f"/v2/jobs/{accepted['job_id']}/events?limit=2"))
    assert first["has_more"] and first["next_seq"] == 2
    tail = data(client.get(f"/v2/jobs/{accepted['job_id']}/events?after_seq=2"))
    assert tail["items"][-1]["stage"] == "publication"
    assert [e["seq"] for e in first["items"] + tail["items"]] == list(range(1, tail["next_seq"] + 1))


def test_url_only_requires_confirm_and_has_price_without_budget(client, app):
    accepted = data(
        client.post(
            "/v2/requirements",
            json={"input": {"kind": "urls"}, "reference_urls": ["https://tour-demo.invalid/tour-a"]},
        ),
        201,
    )
    current = data(client.get(f"/v2/requirements/{accepted['requirement_id']}"))
    assert (
        current["revision"] == 0
        and current["party"]["adults"] is None
        and current["preference_levels"] is None
    )
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    r = data(confirm(client, p))
    _, job, published = comparison(client, app, r)
    assert job["status"] == "succeeded", job
    result = published["result"]
    assert result["recommendations"]["kind"] == "similar" and not result["evaluations"]
    assert any(
        cell["row_id"] == "price_quotes" and cell["value"][0]["amount"] == 10000000
        for cell in result["cells"]
    )


def test_multifield_preview_merge_discard_atomic_confirm_and_no_search(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    p = propose(
        client,
        r,
        [
            budget_edit(32000000),
            {
                "op": "replace_condition_value",
                "condition_id": "duration",
                "value": {"kind": "number", "amount": 6},
            },
        ],
    )
    assert len(p["changes"]) == 2
    assert value(data(client.get(f"/v2/requirements/{r['id']}")), "budget")["amount"] == 35000000
    p = propose(
        client, r, [budget_edit(30000000)], proposal_id=p["id"], expected_proposal_version=p["version"]
    )
    change = next(c for c in p["changes"] if c["condition_id"] == "budget")
    assert change["before"]["value"]["amount"] == 35000000 and change["after"]["value"]["amount"] == 30000000
    p = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [change["id"]],
            },
        )
    )
    assert value(p["preview"], "budget")["amount"] == 35000000
    r2 = data(confirm(client, p, "confirm-batch"))
    assert r2["revision"] == 2 and value(r2, "duration")["amount"] == 6
    assert data(confirm(client, p, "confirm-batch"))["revision"] == 2
    assert confirm(client, p).status_code == 409
    with app.state.store.engine.connect() as c:
        assert len(c.execute(select(revisions).where(revisions.c.resource_id == r["id"])).all()) == 2
        assert not c.execute(select(jobs.c.id)).first()


def test_cancel_preserves_committed_revision_and_idempotency(client):
    r = data(client.post("/v2/requirements", json=form()), 201)
    p = propose(client, r, [budget_edit(32000000)])
    cancelled = data(
        client.post(f"/v2/proposals/{p['id']}/cancel", json={"expected_proposal_version": p["version"]})
    )
    assert cancelled["committed_requirement"]["revision"] == 1
    assert value(cancelled["committed_requirement"], "budget")["amount"] == 35000000
    assert confirm(client, p).status_code == 409


def test_text_initial_proposal_and_chat_edits_are_not_committed(client, app):
    accepted = data(client.post("/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}}), 202)
    assert data(client.get(f"/v2/requirements/{accepted['requirement_id']}"))["revision"] == 0
    finish(app)
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    assert p["preview"]["conditions"] and p["version"] == 2
    assert data(client.get(f"/v2/requirements/{accepted['requirement_id']}"))["conditions"] == []
    assert confirm(client, p).status_code == 409
    assert not p["preview"]["completeness"]["is_complete"]
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted = data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={
                "expected_revision": 1,
                "input": {"kind": "message", "text": "Đổi 32 triệu đồng mỗi người lớn và 6 ngày"},
            },
        ),
        202,
    )
    assert confirm(client, data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))).status_code == 409
    finish(app)
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    assert (
        value(p["preview"], "budget")["amount"] == 32000000 and value(p["preview"], "duration")["amount"] == 6
    )
    assert value(data(client.get(f"/v2/requirements/{r['id']}")), "budget")["amount"] == 35000000


def test_stale_parse_cannot_overwrite_new_direct_edit(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted = data(
        client.post(
            f"/v2/requirements/{r['id']}/proposals",
            json={
                "expected_revision": 1,
                "input": {"kind": "message", "text": "Đổi 32 triệu đồng mỗi người lớn và 6 ngày"},
            },
        ),
        202,
    )
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    p = propose(
        client, r, [budget_edit(28000000)], proposal_id=p["id"], expected_proposal_version=p["version"]
    )
    finish(app)
    job = data(client.get(f"/v2/jobs/{accepted['job_id']}"))
    assert job["status"] == "failed" and job["error"]["code"] == "PROPOSAL_CONFLICT"
    latest = data(client.get(f"/v2/proposals/{p['id']}"))
    assert latest["version"] == p["version"] and value(latest["preview"], "budget")["amount"] == 28000000
    assert data(confirm(client, latest))["revision"] == 2


def test_expiry_owner_isolation_and_contract_errors(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    p = propose(client, r, [budget_edit(32000000)])
    with app.state.store.transaction() as c:
        payload = state.proposal(
            c, app.state.store.authenticate(client.headers["Authorization"].split()[1]), p["id"]
        ).model_dump()
        payload["expires_at"] = (now() - timedelta(seconds=1)).isoformat()
        c.execute(
            update(state.proposals).where(state.proposals.c.id == p["id"]).values(payload=dump(payload))
        )
    assert confirm(client, p).status_code == 410
    token = data(client.post("/v2/sessions"), 201)["token"]
    for path in (f"/v2/requirements/{r['id']}", f"/v2/proposals/{p['id']}"):
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404 and response.json()["schema_version"] == "2.0-draft"
    assert (
        client.post(
            "/v2/requirements", json={"input": {"kind": "urls"}, "reference_urls": ["javascript:alert(1)"]}
        ).status_code
        == 422
    )
    assert client.get("/v2/catalog").json()["data"]["preference_dimensions"][2]["supported"] is False


def test_next_group_excludes_previous_and_old_comparison_is_immutable(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted, job, old = comparison(client, app, r)
    assert job["status"] == "succeeded"
    _, next_job, next_result = comparison(
        client, app, r, round_intent="next_group", previous_comparison_id=accepted["comparison_id"]
    )
    assert next_job["status"] == "succeeded"
    assert not next_result["result"]["recommendations"]["candidate_ids"]
    p = propose(client, r, [budget_edit(32000000)])
    data(confirm(client, p))
    assert data(client.get(f"/v2/comparisons/{accepted['comparison_id']}")) == old


def test_exact_date_does_not_silently_widen(client, app):
    r = data(client.post("/v2/requirements", json=form(date="2026-11-11")), 201)
    _, job, result = comparison(client, app, r)
    assert job["status"] == "succeeded"
    assert result["result"]["empty_reason"] == "ALL_INELIGIBLE"
    assert not result["result"]["recommendations"]["candidate_ids"]


def test_unsupported_url_keeps_column(client, app):
    accepted = data(
        client.post(
            "/v2/requirements",
            json={"input": {"kind": "urls"}, "reference_urls": ["https://unsupported.invalid/tour"]},
        ),
        201,
    )
    p = data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    r = data(confirm(client, p))
    _, job, published = comparison(client, app, r)
    assert job["status"] == "succeeded"
    assert (
        len(published["result"]["columns"]) == 1
        and published["result"]["columns"][0]["offer_reason"] == "SOURCE_NOT_APPROVED"
    )


def test_cancelled_job_replay_restart_and_late_publish_gate(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted = data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)
    row = app.state.store.claim(app.state.worker.id)
    assert data(client.post(f"/v2/jobs/{accepted['job_id']}/cancel"))["status"] == "cancelled"
    with app.state.store.transaction() as c:
        assert not state.running(c, row, app.state.worker.id)
    events = data(client.get(f"/v2/jobs/{accepted['job_id']}/events"))
    assert events["items"][-1]["status"] == "cancelled"
    assert data(client.get(f"/v2/comparisons/{accepted['comparison_id']}"))["result"] is None
    second = data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)
    app.state.store.claim(app.state.worker.id)
    app.state.store.recover()
    assert data(client.get(f"/v2/jobs/{second['job_id']}"))["error"]["code"] == "JOB_INTERRUPTED"


def test_conversation_edit_and_answer_have_snapshot_refs(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    accepted, job, published = comparison(client, app, r)
    assert job["status"] == "succeeded"
    message = {
        "text": "Giá chênh lệch sao?",
        "client_message_id": "answer1",
        "context": {
            "requirement_revision": 1,
            "comparison_id": accepted["comparison_id"],
            "result_revision": 1,
        },
    }
    chat = data(client.post(f"/v2/conversations/{r['id']}/messages", json=message), 202)
    assert (
        data(client.post(f"/v2/conversations/{r['id']}/messages", json=message), 202)["job_id"]
        == chat["job_id"]
    )
    finish(app)
    response = data(client.get(f"/v2/conversations/{r['id']}/messages/answer1"))["result"]
    assert response["intent"] == "answer" and response["answer"]["revision"] == 1
    assert response["answer"]["metrics"] == published["result"]["analysis"]["metrics"][:1]
    message = {
        "text": "sửa 32 triệu đồng mỗi người lớn và 6 ngày rồi tìm",
        "client_message_id": "edit1",
        "context": {"requirement_revision": 1},
    }
    data(client.post(f"/v2/conversations/{r['id']}/messages", json=message), 202)
    finish(app, 2)
    response = data(client.get(f"/v2/conversations/{r['id']}/messages/edit1"))["result"]
    p = data(client.get(f"/v2/proposals/{response['proposal_id']}"))
    assert p["requested_action"] == "search" and len(p["changes"]) == 2
    assert data(client.get(f"/v2/requirements/{r['id']}"))["revision"] == 1


def test_additive_migration_keeps_existing_v1_rows(settings):
    store = Store(settings)
    session = store.new_session()
    with store.transaction() as c:
        c.execute(update(schema_info).values(version=1))
    store.engine.dispose()
    upgraded = Store(settings)
    assert upgraded.authenticate(session["token"]) == session["session_id"]
    with upgraded.engine.connect() as c:
        assert c.execute(select(schema_info.c.version)).scalar() == 2
    upgraded.engine.dispose()


def test_admin_roles_contact_audit_pause_and_metrics(settings):
    settings.admin_token = "A" * 32
    settings.admin_operator_token = "O" * 32
    settings.admin_viewer_token = "V" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        session = data(c.post("/v2/sessions"), 201)
        user = {"Authorization": f"Bearer {session['token']}"}
        admin = {"Authorization": "Bearer " + "A" * 32}
        operator = {"Authorization": "Bearer " + "O" * 32}
        viewer = {"Authorization": "Bearer " + "V" * 32}
        assert c.get("/v2/admin/sources", headers=user).status_code == 403
        contact = {
            "category": "support",
            "message": "Xin hỗ trợ",
            "reply_to": "user@example.com",
            "client_submission_id": "ticket1",
        }
        ticket = data(c.post("/v2/contacts", json=contact, headers=user), 201)
        assert (
            data(c.post("/v2/contacts", json=contact, headers=user), 201)["ticket_id"] == ticket["ticket_id"]
        )
        assert (
            c.patch(
                f"/v2/admin/contacts/{ticket['ticket_id']}",
                json={"expected_version": 1, "status": "in_progress"},
                headers=viewer,
            ).status_code
            == 403
        )
        redacted = data(c.get("/v2/admin/contacts", headers=viewer))["items"][0]
        assert "reply_to" not in redacted and "message" not in redacted
        updated = data(
            c.patch(
                f"/v2/admin/contacts/{ticket['ticket_id']}",
                json={"expected_version": 1, "status": "in_progress", "internal_note": "private note"},
                headers=operator,
            )
        )
        assert updated["version"] == 2
        assert (
            c.patch(
                f"/v2/admin/contacts/{ticket['ticket_id']}",
                json={"expected_version": 1, "status": "resolved"},
                headers=operator,
            ).status_code
            == 409
        )
        paused = data(
            c.patch(
                "/v2/admin/sources/demo", json={"expected_version": 1, "state": "paused"}, headers=operator
            )
        )
        assert paused["version"] == 2
        assert (
            c.patch(
                "/v2/admin/sources/demo", json={"expected_version": 2, "state": "active"}, headers=operator
            ).status_code
            == 403
        )
        data(
            c.patch("/v2/admin/sources/demo", json={"expected_version": 2, "state": "active"}, headers=admin)
        )
        audit_records = data(c.get("/v2/admin/audit", headers=viewer))["items"]
        assert (
            audit_records
            and "user@example.com" not in json.dumps(audit_records)
            and "private note" not in json.dumps(audit_records)
        )
        interval = {
            "from": (now() - timedelta(hours=1)).isoformat(),
            "to": (now() + timedelta(hours=1)).isoformat(),
        }
        metrics = data(c.get("/v2/admin/overview", params=interval, headers=admin))
        assert metrics["distinct_sessions"] == 1 and metrics["comparison_runs"] == 0


def test_source_checks_fail_closed_and_approval_binding(settings):
    settings.admin_token = "A" * 32

    async def checker(record):
        return {
            "access_status": "approved",
            "checked_at": (now() - timedelta(seconds=1)).isoformat(),
            "valid_until": (now() + timedelta(hours=1)).isoformat(),
            "policy_ref": record["policy_ref"],
            "profile_ref": record["profile_ref"],
            "capability_digest": digest(record),
        }

    app = create_app(settings, nim=Nim(), access_checker=checker)
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + "A" * 32
        source = data(c.get("/v2/admin/sources/demo"))
        check = data(
            c.post("/v2/admin/sources/demo/checks", json={"expected_version": source["version"]}), 202
        )
        finish(app)
        record = data(c.get("/v2/admin/sources/demo"))
        assert record["version"] == 2
        approved = data(
            c.post(
                "/v2/admin/sources/demo/approvals",
                json={"expected_version": 2, "check_job_id": check["job_id"]},
            )
        )
        assert approved["state"] == "paused" and approved["version"] == 3
        assert (
            c.post(
                "/v2/admin/sources/demo/approvals", json={"expected_version": 3, "check_job_id": "wrong"}
            ).status_code
            == 409
        )
        data(c.patch("/v2/admin/sources/demo", json={"expected_version": 3, "state": "active"}))
        refresh = data(c.post("/v2/admin/sources/demo/refreshes", json={"expected_version": 4}), 202)
        finish(app)
        assert data(c.get(f"/v2/admin/jobs/{refresh['job_id']}"))["status"] == "succeeded"


def test_no_checker_never_approves(settings):
    settings.admin_token = "A" * 32
    app = create_app(settings, nim=Nim())
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + "A" * 32
        accepted = data(c.post("/v2/admin/sources/demo/checks", json={"expected_version": 1}), 202)
        finish(app)
        assert (
            data(c.get(f"/v2/admin/jobs/{accepted['job_id']}"))["error"]["code"]
            == "ACCESS_CHECKER_NOT_CONFIGURED"
        )
