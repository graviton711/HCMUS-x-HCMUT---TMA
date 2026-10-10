"""Emit actual FastAPI responses for frontend contract tests. Never call real NIM/network."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from fastapi.testclient import TestClient  # noqa: E402
from test_v2 import Nim, form  # noqa: E402

from api.app import create_app  # noqa: E402
from api.settings import Settings  # noqa: E402


def collect():
    app = create_app(
        Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            data_provider="fixture",
            worker_enabled=False,
            nvidia_nim_api="test-only-no-network",
        ),
        nim=Nim(),
    )
    captured = []

    def save(name, validator, response, status=200):
        assert response.status_code == status, response.text
        payload = response.json()
        captured.append({"name": name, "validator": validator, "response": payload})
        return payload.get("data", payload)

    def work():
        assert asyncio.run(app.state.worker.run_once())

    with TestClient(app) as client:
        save("health", "health", client.get("/health"))
        session = save("session", "session", client.post("/v2/sessions"), 201)
        client.headers["Authorization"] = f"Bearer {session['token']}"
        save("catalog", "catalog", client.get("/v2/catalog"))

        created = save(
            "URL requirement acceptance",
            "createRequirement",
            client.post(
                "/v2/requirements",
                json={"input": {"kind": "urls"}, "reference_urls": ["https://tour-demo.invalid/tour-a", "https://tour-demo.invalid/tour-b", "https://tour-demo.invalid/tour-c"]},
            ),
            201,
        )
        rid, pid = created["requirement_id"], created["proposal_id"]
        save("draft current", "requirement", client.get(f"/v2/requirements/{rid}"))
        proposal = save("URL proposal", "proposal", client.get(f"/v2/proposals/{pid}"))
        confirmed = save(
            "URL confirm",
            "requirement",
            client.post(f"/v2/proposals/{pid}/confirm", json={"expected_revision": 0, "expected_proposal_version": proposal["version"]}),
        )
        accepted = save(
            "comparison acceptance",
            "acceptedComparison",
            client.post("/v2/comparisons", json={"requirement_id": rid, "revision": confirmed["revision"]}),
            202,
        )
        save("queued comparison job", "job", client.get(f"/v2/jobs/{accepted['job_id']}"))
        work()
        save("terminal comparison job", "job", client.get(f"/v2/jobs/{accepted['job_id']}"))
        first = save("event cursor page", "events", client.get(f"/v2/jobs/{accepted['job_id']}/events?limit=2"))
        save("events terminal drain", "events", client.get(f"/v2/jobs/{accepted['job_id']}/events?after_seq={first['next_seq']}&limit=100"))
        published = save("published comparison", "comparison", client.get(f"/v2/comparisons/{accepted['comparison_id']}"))
        comparison = published["result"]
        save("restored current refs", "requirement", client.get(f"/v2/requirements/{rid}"))
        save("immutable revision", "requirement", client.get(f"/v2/requirements/{rid}/revisions/1"))
        evidence_id = next(eid for cell in comparison["cells"] for eid in cell["evidence_ids"])
        save("evidence deep link", "evidence", client.get(f"/v2/evidence/{evidence_id}"))

        save("chat acceptance", "acceptedMessage", client.post(f"/v2/conversations/{rid}/messages", json={"text": "Giá khác nhau thế nào?", "client_message_id": "answer_contract", "context": {"requirement_revision": 1, "comparison_id": comparison["id"], "result_revision": 1}}), 202)
        work()
        save("chat answer", "message", client.get(f"/v2/conversations/{rid}/messages/answer_contract"))

        analysis = save("what-if acceptance", "acceptedWhatIf", client.post(f"/v2/comparisons/{comparison['id']}/what-if", json={"expected_revision": 1}), 202)
        work()
        save("what-if result", "whatIf", client.get(f"/v2/what-if/{analysis['analysis_id']}"))
        save("history index", "history", client.get("/v2/history"))
        save("history detail", "historyDetail", client.get(f"/v2/history/{rid}"))
        save("history metadata", "historyMetadata", client.patch(f"/v2/history/{rid}", json={"expected_version": 0, "title": "Contract"}))

        structured = save("structured form", "createRequirement", client.post("/v2/requirements", json=form()), 201)
        structured_id = structured["id"]
        hard_comparison = save("hard comparison acceptance", "acceptedComparison", client.post("/v2/comparisons", json={"requirement_id": structured_id, "revision": 1}), 202)
        work()
        hard_result = save("hard comparison", "comparison", client.get(f"/v2/comparisons/{hard_comparison['comparison_id']}"))
        hard_analysis = save("hard what-if acceptance", "acceptedWhatIf", client.post(f"/v2/comparisons/{hard_result['id']}/what-if", json={"expected_revision": 1}), 202)
        work()
        hard_analysis_result = save("hard what-if result", "whatIf", client.get(f"/v2/what-if/{hard_analysis['analysis_id']}"))
        scenarios = hard_analysis_result["result"]["scenarios"]
        scenario = next(s for s in scenarios if s["edits"])
        applied = save("what-if review proposal", "proposal", client.post(f"/v2/what-if/{hard_analysis['analysis_id']}/scenarios/{scenario['id']}/proposals", json={"expected_revision": 1}))
        save("what-if proposal cancel", "cancelProposal", client.post(f"/v2/proposals/{applied['id']}/cancel", json={"expected_proposal_version": applied['version']}))
        body = {"expected_revision": 1, "input": {"kind": "structured", "edits": [{"op": "replace_condition_value", "condition_id": "duration", "value": {"kind": "number", "amount": 6}}]}}
        proposal = save("direct edit", "createProposal", client.post(f"/v2/requirements/{structured_id}/proposals", json=body))
        proposal = save("discard individual change", "proposal", client.post(f"/v2/proposals/{proposal['id']}/discard-changes", json={"expected_revision": 1, "expected_proposal_version": proposal["version"], "change_ids": [proposal["changes"][0]["id"]]}))
        save("cancel proposal", "cancelProposal", client.post(f"/v2/proposals/{proposal['id']}/cancel", json={"expected_proposal_version": proposal["version"]}))
        proposal = save("new direct edit", "createProposal", client.post(f"/v2/requirements/{structured_id}/proposals", json=body))
        save("structured edit confirm", "requirement", client.post(f"/v2/proposals/{proposal['id']}/confirm", json={"expected_revision": 1, "expected_proposal_version": proposal["version"]}))

        text = save("text acceptance", "createRequirement", client.post("/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}}), 202)
        work()
        save("text parse proposal", "proposal", client.get(f"/v2/proposals/{text['proposal_id']}"))
        save("text parse job", "job", client.get(f"/v2/jobs/{text['job_id']}"))

        save("contact", "contact", client.post("/v2/contacts", json={"category": "data_issue", "message": "Kiểm tra contract trong test.", "client_submission_id": "contact_contract", "context": {"session_id": session["id"], "comparison_id": comparison["id"]}}), 201)
        cancelled = save("comparison to cancel", "acceptedComparison", client.post("/v2/comparisons", json={"requirement_id": rid, "revision": 1}), 202)
        save("cancel job", "cancelJob", client.post(f"/v2/jobs/{cancelled['job_id']}/cancel"))
        save("cancelled events", "events", client.get(f"/v2/jobs/{cancelled['job_id']}/events"))
        error = client.post("/v2/requirements", json={"input": {"kind": "urls"}, "reference_urls": ["javascript:alert(1)"]})
        assert error.status_code == 422
        captured.append({"name": "validation error", "validator": "errorPayload", "response": error.json()["error"]})
    return captured


if __name__ == "__main__":
    print(json.dumps(collect(), ensure_ascii=True))
