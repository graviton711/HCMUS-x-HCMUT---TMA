"""Explicit live smoke: real NIM/catalog, isolated application state, public artifacts only."""

import asyncio
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.settings import Settings
from domain.common import now

JAPAN = "Tôi muốn tìm tour Nhật Bản khởi hành từ Hồ Chí Minh ngày 03/11/2026, đi 1 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour."
TET = (
    "Tết Nguyên đán năm nay e dự định đi du lịch ghép đoàn bằng xe ô tô từ Hải Phòng đi dọc miền trung vào Đà Nẵng hoặc Tây Nguyên.\n"
    "Cty nào uy tín và dv tốt, giá hợp lý, tour có các điểm đẹp gần gũi thiên nhiên e tham khảo ạ.\n"
    "Từ 27/12 âm đến mùng 4 Tết ạ."
)
FOLLOW_UP = (
    "Nhóm có 2 người lớn. Giá tour tối đa 10 triệu VND mỗi người lớn. Đi dịp Tết 2027. "
    "Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên."
)


def response_data(response, expected=200):
    if response.status_code != expected:
        code = response.json().get("error", {}).get("code", "UNEXPECTED_STATUS")
        raise RuntimeError(f"HTTP {response.status_code}: {code}")
    return response.json()["data"]


def summary_of(proposal):
    preview = proposal["preview"]
    return {
        "conditions": [{"field": c["field"], "strength": c["strength"]} for c in preview["conditions"]],
        "adults": preview["party"]["adults"],
        "core": {f["field_path"]: f["status"] for f in preview["completeness"]["fields"]},
        "can_confirm": preview["readiness"]["can_confirm"],
        "clarification_reasons": [q["reason_code"] for q in preview["clarifications"]],
    }


def core_values(proposal):
    return {
        c["field"]: c["value"]
        for c in proposal["preview"]["conditions"]
        if c["field"]
        in {"destinations", "departure_origin", "departure_date", "return_date", "estimated_cost"}
    }


def entities(value):
    return set(value.get("items", [])) or {
        m["entity_id"] for m in value.get("members", []) if m["status"] == "resolved"
    }


def finish(app, client, accepted, steps):
    assert asyncio.run(app.state.worker.run_once()), "No queued job"
    job = response_data(client.get(f"/v2/jobs/{accepted['job_id']}"))
    steps["job"] = job
    proposal = response_data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))
    steps["proposal"] = proposal
    return job, proposal


def confirm_and_compare(app, client, proposal, steps):
    confirmed = client.post(
        f"/v2/proposals/{proposal['id']}/confirm",
        json={
            "expected_revision": proposal["base_revision"],
            "expected_proposal_version": proposal["version"],
        },
    )
    steps["confirm"] = confirmed.json()
    result_summary = {"confirm_http_status": confirmed.status_code}
    if confirmed.status_code != 200:
        return result_summary
    r = response_data(confirmed)
    accepted = response_data(
        client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": r["revision"]}), 202
    )
    assert asyncio.run(app.state.worker.run_once()), "No comparison job"
    job = response_data(client.get(f"/v2/jobs/{accepted['job_id']}"))
    comparison = response_data(client.get(f"/v2/comparisons/{accepted['comparison_id']}"))
    steps.update(comparison_job=job, comparison=comparison)
    result_summary["comparison_status"] = job["status"]
    result = comparison.get("result")
    if result:
        result_summary.update(
            columns=len(result["columns"]),
            recommendations=len(result["recommendations"]["items"]),
            empty_reason=result["empty_reason"],
            retrieval=result["analysis"]["retrieval"],
            semantic_state=result["analysis"]["semantic_assessment"]["state"],
        )
    return result_summary


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = Settings(database_url="sqlite:///:memory:", worker_enabled=False)
    if settings.data_provider != "supabase":
        raise RuntimeError("Live smoke requires DATA_PROVIDER=supabase")
    output = Path("data/live-tests") / ("personalized-" + now().strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(parents=True, exist_ok=False)
    summaries, checks = [], {}

    def save(name, request, steps, summary):
        summaries.append({"case": name, **summary})
        (output / f"{name}.json").write_text(
            json.dumps(
                {"request": request, "steps": steps, "summary": summary}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(json.dumps({"case": name, **summary}, ensure_ascii=False), flush=True)

    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        session = response_data(client.post("/v2/sessions"), 201)
        client.headers["Authorization"] = "Bearer " + session["token"]
        for name, text in [("japan", JAPAN), ("tet", TET)]:
            request = {"input": {"kind": "text", "text": text}, "timezone": "Asia/Ho_Chi_Minh"}
            steps = {}
            started = time.monotonic()
            accepted = response_data(client.post("/v2/requirements", json=request), 202)
            job, proposal = finish(app, client, accepted, steps)
            summary = {"parse_status": job["status"], "seconds": round(time.monotonic() - started, 2)}
            checks[name + "_parse"] = job["status"] == "succeeded"
            if checks[name + "_parse"]:
                summary.update(summary_of(proposal))
                summary.update(confirm_and_compare(app, client, proposal, steps))
                checks[name + "_gate"] = summary["confirm_http_status"] == (200 if name == "japan" else 409)
                if name == "japan":
                    checks["japan_party"] = summary["adults"] == 1
                    checks["japan_conditions"] = len(summary["conditions"]) == 4 and all(
                        c["strength"] == "hard" for c in summary["conditions"]
                    )
                    values = core_values(proposal)
                    budget = values.get("estimated_cost", {})
                    checks["japan_values"] = (
                        entities(values.get("destinations", {})) == {"country:jp"}
                        and entities(values.get("departure_origin", {})) == {"city:vn:hcmc"}
                        and values.get("departure_date", {}).get("value") == "2026-11-03"
                        and all(
                            budget.get(key) == expected
                            for key, expected in {
                                "amount": 30000000,
                                "currency": "VND",
                                "basis": "per_adult",
                                "coverage": "tour_price",
                            }.items()
                        )
                    )
                else:
                    checks["tet_no_invented_core"] = summary["adults"] is None and not any(
                        c["field"] == "estimated_cost" for c in summary["conditions"]
                    )
            save(name, request, steps, summary)
            if name != "tet" or not checks[name + "_parse"]:
                continue
            # These answers are synthetic test data, never inferred from the original user message.
            follow_request = {
                "expected_revision": proposal["base_revision"],
                "proposal_id": proposal["id"],
                "expected_proposal_version": proposal["version"],
                "input": {"kind": "message", "text": FOLLOW_UP},
            }
            follow_steps = {}
            accepted = response_data(
                client.post(f"/v2/requirements/{proposal['requirement_id']}/proposals", json=follow_request),
                202,
            )
            follow_job, updated = finish(app, client, accepted, follow_steps)
            follow_summary = {"parse_status": follow_job["status"], "answers_origin": "synthetic_test_input"}
            checks["tet_follow_up_parse"] = follow_job["status"] == "succeeded"
            if checks["tet_follow_up_parse"]:
                follow_summary.update(summary_of(updated))
                follow_summary.update(confirm_and_compare(app, client, updated, follow_steps))
                checks["tet_follow_up_gate"] = follow_summary["confirm_http_status"] == 200
                checks["tet_follow_up_party"] = follow_summary["adults"] == 2
                before, after = core_values(proposal), core_values(updated)
                checks["tet_preserved_locations"] = before.get("destinations") == after.get(
                    "destinations"
                ) and before.get("departure_origin") == after.get("departure_origin")
                checks["tet_window"] = (
                    after.get("departure_date", {}).get("resolved_date") == "2027-02-03"
                    and after.get("return_date", {}).get("resolved_date") == "2027-02-09"
                )
                checks["tet_budget"] = all(
                    after.get("estimated_cost", {}).get(key) == expected
                    for key, expected in {
                        "amount": 10000000,
                        "currency": "VND",
                        "basis": "per_adult",
                        "coverage": "tour_price",
                    }.items()
                )
                qualitative = {"supplier_reputation", "service_quality", "price_value", "nature"}
                old = {c["id"]: c for c in proposal["preview"]["conditions"] if c["field"] in qualitative}
                new = {c["id"]: c for c in updated["preview"]["conditions"] if c["field"] in qualitative}
                checks["tet_preserved_priorities"] = len(old) == 4 and old == new
            save("tet-follow-up", follow_request, follow_steps, follow_summary)
    (output / "summary.json").write_text(
        json.dumps({"cases": summaries, "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"checks": checks, "artifacts": str(output.resolve())}, ensure_ascii=False), flush=True)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
