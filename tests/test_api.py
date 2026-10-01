import asyncio

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.store import jobs
from domain.common import AppError
from requirements.extraction import Extraction, Operation, RawCondition


class FakeNim:
    async def extract(self, message, previous=None, *, feedback=None):
        if "timeout" in message.text:
            raise AppError("LLM_TIMEOUT", "Synthetic timeout", 504)
        if previous:
            return Extraction(operations=[Operation(op="remove", target_id="hotel", quote=message.text)]), {"synthetic": True}
        return Extraction(conditions=[RawCondition(id="dest", field="destinations", operator="contains",
            raw_values=["Nhật"], quote="Nhật", strength="hard")]), {"synthetic": True}


@pytest.fixture
def app(settings):
    return create_app(settings, nim=FakeNim())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        token = c.post("/v1/sessions").json()["token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


def discovery_form():
    return {"mode": "discover", "form": {"conditions": [
        {"id": "dest", "field": "destinations", "operator": "contains_any", "value": {"kind": "set", "items": ["country:jp", "country:kr"]}},
        {"id": "budget", "field": "estimated_cost", "operator": "lte", "value": {"kind": "budget", "amount": 30000000, "currency": "VND", "basis": "group_total"}},
        {"id": "hotel", "field": "hotel_stars_min", "operator": "gte", "strength": "soft", "value": {"kind": "number", "amount": 4}},
    ], "party": {"adults": 2, "children": [{"id": "kid", "age": 8}]}}}


def complete(app):
    assert asyncio.run(app.state.worker.run_once()) is True


def test_discover_full_flow_and_evidence(client, app):
    response = client.post("/v1/requirements", json=discovery_form())
    assert response.status_code == 201, response.text
    requirement = response.json()
    assert requirement["readiness"]["can_collect_data"]
    response = client.post("/v1/comparisons", json={"requirement_id": requirement["id"], "revision": 1})
    assert response.status_code == 202, response.text
    job = response.json()
    complete(app)
    assert client.get(f"/v1/jobs/{job['job_id']}").json()["status"] == "succeeded"
    result = client.get(f"/v1/comparisons/{job['comparison_id']}").json()["result"]
    assert result["origin"] == "synthetic"
    assert len(result["groups"]["eligible"]) == 1
    assert len(result["groups"]["needs_verification"]) == 1
    assert len(result["groups"]["ineligible"]) == 1
    evidence_id = result["evidence_refs"][0]
    assert client.get(f"/v1/evidence/{evidence_id}").status_code == 200
    token = client.post("/v1/sessions").json()["token"]
    other = {"Authorization": f"Bearer {token}"}
    for url in (f"/v1/requirements/{requirement['id']}", f"/v1/comparisons/{job['comparison_id']}", f"/v1/jobs/{job['job_id']}", f"/v1/evidence/{evidence_id}"):
        assert client.get(url, headers=other).status_code == 404


def test_compare_urls_keeps_unapproved_target(client, app):
    created = client.post("/v1/requirements", json={"mode": "compare_urls", "urls": [
        "https://tour-demo.invalid/tour-a", "http://127.0.0.1/private"]})
    assert created.status_code == 201
    r = created.json()
    assert r["readiness"]["can_collect_data"]
    job = client.post("/v1/comparisons", json={"requirement_id": r["id"], "revision": 1}).json()
    complete(app)
    result = client.get(f"/v1/comparisons/{job['comparison_id']}").json()["result"]
    assert [t["url"] for t in result["targets"]] == ["https://tour-demo.invalid/tour-a", "http://127.0.0.1/private"]
    assert result["targets"][1]["reason_code"] == "SOURCE_NOT_APPROVED"
    assert not result["filter_applied"]


def test_text_parsing_job(client, app):
    response = client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"})
    assert response.status_code == 202
    created = response.json()
    assert client.get(f"/v1/requirements/{created['requirement_id']}").json()["revision"] == 0
    complete(app)
    result = client.get(f"/v1/requirements/{created['requirement_id']}").json()
    assert result["revision"] == 1 and result["conditions"][0]["value"]["items"] == ["country:jp"]


def test_idempotency_and_revision_conflict(client):
    body = discovery_form()
    first = client.post("/v1/requirements", json=body, headers={"Idempotency-Key": "key1"})
    again = client.post("/v1/requirements", json=body, headers={"Idempotency-Key": "key1"})
    assert first.json() == again.json()
    assert client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"}, headers={"Idempotency-Key": "key1"}).status_code == 409
    rid = first.json()["id"]
    patch = {"expected_revision": 1, "edits": [{"op": "replace", "target": "conditions.budget.value.amount", "value": 35000000}]}
    assert client.patch(f"/v1/requirements/{rid}", json=patch).status_code == 200
    assert client.patch(f"/v1/requirements/{rid}", json=patch).status_code == 409


def test_queued_patch_cannot_overwrite_newer_revision(client, app):
    rid = client.post("/v1/requirements", json=discovery_form()).json()["id"]
    queued = client.patch(f"/v1/requirements/{rid}", json={"expected_revision": 1, "text": "Bỏ khách sạn"}).json()
    updated = client.patch(f"/v1/requirements/{rid}", json={"expected_revision": 1, "edits": [
        {"op": "replace", "target": "conditions.budget.value.amount", "value": 35000000}]}).json()
    assert updated["revision"] == 2
    complete(app)
    job = client.get(f"/v1/jobs/{queued['job_id']}").json()
    assert job["status"] == "failed" and job["error"]["code"] == "REVISION_CONFLICT"
    latest = client.get(f"/v1/requirements/{rid}").json()
    assert latest["revision"] == 2
    assert any(c["id"] == "hotel" for c in latest["conditions"])


def test_failed_patch_preserves_revision(client, app):
    rid = client.post("/v1/requirements", json=discovery_form()).json()["id"]
    queued = client.patch(f"/v1/requirements/{rid}", json={"expected_revision": 1, "text": "timeout"}).json()
    complete(app)
    job = client.get(f"/v1/jobs/{queued['job_id']}").json()
    assert job["error"]["code"] == "LLM_TIMEOUT"
    assert client.get(f"/v1/requirements/{rid}").json()["revision"] == 1


def test_cancelled_job_is_terminal(client, app):
    queued = client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"}).json()
    url = f"/v1/jobs/{queued['job_id']}"
    assert client.post(f"{url}/cancel").json()["status"] == "cancelled"
    assert asyncio.run(app.state.worker.run_once()) is False
    assert client.get(url).json()["status"] == "cancelled"


def test_restart_fails_running_job_explicitly(client, app):
    created = client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"}).json()
    claimed = app.state.store.claim("old_worker")
    assert claimed is not None
    app.state.store.recover()
    job = client.get(f"/v1/jobs/{created['job_id']}").json()
    assert job["status"] == "failed" and job["error"]["code"] == "JOB_INTERRUPTED"


def test_late_result_cannot_revive_cancelled_job(client, app):
    created = client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"}).json()
    row = app.state.store.claim("old_worker")
    client.post(f"/v1/jobs/{created['job_id']}/cancel")
    app.state.store.commit_job(row, "old_worker", comparison={"job_status": "succeeded", "result": {}})
    assert client.get(f"/v1/jobs/{created['job_id']}").json()["status"] == "cancelled"


def test_field_failure_vs_acquisition_failure(client, app):
    r = client.post("/v1/requirements", json={"mode": "compare_urls", "urls": [
        "https://tour-demo.invalid/tour-a", "https://tour-demo.invalid/no-tour"]}).json()
    created = client.post("/v1/comparisons", json={"requirement_id": r["id"], "revision": 1}).json()
    complete(app)
    assert client.get(f"/v1/jobs/{created['job_id']}").json()["status"] == "partial"
    r2 = client.post("/v1/requirements", json={"mode": "compare_urls", "urls": [
        "https://tour-demo.invalid/no-a", "https://tour-demo.invalid/no-b"]}).json()
    second = client.post("/v1/comparisons", json={"requirement_id": r2["id"], "revision": 1}).json()
    complete(app)
    assert client.get(f"/v1/jobs/{second['job_id']}").json()["error"]["code"] == "SOURCES_UNAVAILABLE"


def test_invalid_input_no_sensitive_echo(client):
    response = client.post("/v1/requirements", json={"mode": "discover", "text": "private", "extra": "secret"})
    assert response.status_code == 422
    assert "secret" not in response.text and "private" not in response.text
    assert client.post("/v1/requirements", content="a" * 66000).status_code == 413


def test_request_limits_and_auth(client):
    assert client.get("/v1/sources", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/health").json()["data_origin"] == "synthetic"
    assert client.get("/openapi.json").status_code == 200


def test_clarification_answer_and_stale_answer(client):
    body = discovery_form()
    body["form"]["conditions"][1]["value"].pop("currency")
    r = client.post("/v1/requirements", json=body).json()
    q = next(q for q in r["clarifications"] if q["reason_code"] == "CURRENCY_REQUIRED")
    url = f"/v1/requirements/{r['id']}"
    answer = {"expected_revision": 1, "answers": [{"clarification_id": q["id"], "value": "VND"}]}
    response = client.patch(url, json=answer)
    assert response.status_code == 200, response.text
    assert response.json()["readiness"]["status"] == "ready"
    answer["expected_revision"] = 2
    assert client.patch(url, json=answer).status_code == 409


def test_queued_deadline_becomes_failed(client, app):
    created = client.post("/v1/requirements", json={"mode": "discover", "text": "Đi Nhật"}).json()
    with app.state.store.transaction() as c:
        c.execute(jobs.update().where(jobs.c.id == created["job_id"]).values(deadline_at="2000-01-01T00:00:00+00:00"))
    assert asyncio.run(app.state.worker.run_once()) is False
    assert client.get(f"/v1/jobs/{created['job_id']}").json()["error"]["code"] == "JOB_DEADLINE_EXCEEDED"
