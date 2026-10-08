"""Explicit live catalog/API smoke; isolated app state and separately labeled NIM probe."""

import argparse
import asyncio
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.settings import Settings
from domain.common import now
from domain.what_if import WhatIfAnalysis
from requirements.catalog import CATALOG_VERSION
from semantic_assessment.what_if import NimWhatIfGateway, WhatIfExplainer


def condition(cid, field, operator, value, strength="hard", **extra):
    return dict(id=cid, field=field, operator=operator, value=value, strength=strength, **extra)


def entities(kind, *values):
    return dict(
        kind="entities",
        members=[dict(raw=raw, entity_type=kind, entity_id=eid, status="resolved") for raw, eid in values],
        catalog_version=CATALOG_VERSION,
    )


def request_for(name):
    japan = name in {"japan", "nim-synthetic"}
    constraints = [
        condition(
            "destination",
            "destinations",
            "contains" if japan else "contains_any",
            dict(
                kind="set",
                items=["country:jp"] if japan else ["city:vn:danang", "region:vn:central_highlands"],
            ),
        ),
        condition(
            "origin",
            "departure_origin",
            "in",
            dict(kind="set", items=["city:vn:hcmc"] if japan else ["city:vn:haiphong"]),
        ),
        condition(
            "date",
            "departure_date",
            "eq" if japan else "gte",
            dict(
                kind="date",
                value="2026-11-10" if name == "nim-synthetic" else "2026-11-03" if japan else "2027-02-03",
            ),
        ),
        condition(
            "budget",
            "estimated_cost",
            "lte",
            dict(
                kind="budget",
                amount=11000000 if name == "nim-synthetic" else 30000000 if japan else 10000000,
                currency="VND",
                basis="per_adult",
                coverage="tour_price",
            ),
        ),
    ]
    if not japan:
        constraints.extend(
            [
                condition("return", "return_date", "lte", dict(kind="date", value="2027-02-09")),
                condition("type", "tour_type", "in", entities("tour_type", ("ghép đoàn", "join_group"))),
                condition(
                    "transport",
                    "transport",
                    "in",
                    entities("transport", ("xe ô tô", "motor_vehicle")),
                    scope="main_journey",
                ),
                condition(
                    "route",
                    "route",
                    "contains_any",
                    entities("place", ("miền Trung", "region:vn:central")),
                    "soft",
                    scope="itinerary",
                ),
                *[
                    condition(
                        field, field, "prefer", dict(kind="qualitative", concept=field, raw=raw), "soft"
                    )
                    for field, raw in [
                        ("supplier_reputation", "uy tín"),
                        ("service_quality", "dịch vụ tốt"),
                        ("price_value", "giá hợp lý"),
                        ("nature", "gần gũi thiên nhiên"),
                    ]
                ],
            ]
        )
    if name == "nim-synthetic":
        constraints.append(
            condition("duration", "duration_days", "near", dict(kind="number", amount=5), "soft")
        )
    return dict(
        input=dict(
            kind="structured", form=dict(conditions=constraints, party=dict(adults=1 if japan else 2))
        ),
        timezone="Asia/Ho_Chi_Minh",
    )


def data(response, expected=200):
    if response.status_code != expected:
        code = response.json().get("error", {}).get("code", "UNEXPECTED_STATUS")
        raise RuntimeError(f"HTTP {response.status_code}: {code}")
    return response.json()["data"]


def finish(app, client, accepted):
    assert asyncio.run(app.state.worker.run_once()), "No queued job"
    return data(client.get(f"/v2/jobs/{accepted['job_id']}"))


def run_case(settings, name, output):
    started = time.monotonic()
    app = create_app(settings)
    request = request_for(name)
    steps, checks = {}, {}
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers["Authorization"] = "Bearer " + data(client.post("/v2/sessions"), 201)["token"]
        r = data(client.post("/v2/requirements", json=request), 201)
        steps["requirement"] = r
        parent = data(
            client.post("/v2/comparisons", json=dict(requirement_id=r["id"], revision=r["revision"])), 202
        )
        steps["comparison_job"] = finish(app, client, parent)
        steps["comparison"] = data(client.get(f"/v2/comparisons/{parent['comparison_id']}"))
        checks["comparison_completed"] = steps["comparison_job"]["status"] in {"succeeded", "partial"}
        if not checks["comparison_completed"]:
            raise RuntimeError("Comparison failed; check live catalog configuration/availability")
        options = dict(expected_revision=r["revision"], candidate_limit=500, max_scenarios=32)
        accepted = data(client.post(f"/v2/comparisons/{parent['comparison_id']}/what-if", json=options), 202)
        steps["analysis_request"] = options
        steps["analysis_job"] = finish(app, client, accepted)
        resource = data(client.get(f"/v2/what-if/{accepted['analysis_id']}"))
        steps["analysis"] = resource
        checks["analysis_completed"] = steps["analysis_job"]["status"] in {"succeeded", "partial"}
        current = data(client.get(f"/v2/requirements/{r['id']}"))
        # GET enriches the requirement with latest comparison/job references.
        checks["requirement_unchanged"] = {key: current[key] for key in r} == r
        result = WhatIfAnalysis.model_validate(resource["result"]) if resource["result"] else None
        if result:
            checks["same_snapshot_baseline"] = result.scope["baseline"] == "recomputed_on_analysis_snapshot"
            checks["bounded_attempts"] = result.limits["attempted_scenarios"] <= 32
            checks["public_model_valid"] = True
            checks["null_unknown_ratios"] = all(
                not s.previously_unknown_candidate_ids or s.restriction_ratio.percent is None
                for s in result.scenarios
            )
            checks["grouped_travel_bounds"] = name != "tet-clarified" or any(
                set(g.condition_ids) == {"date", "return"} for g in result.groups
            )
            if name != "nim-synthetic":
                checks["catalog_read_only_snapshot"] = (
                    result.scope["retrieval"]["consistency"] == "repeatable_read"
                    and result.origin == "source"
                )
        summary = dict(
            case=name,
            input_origin="structured_equivalent"
            if name == "japan"
            else "synthetic_clarification_equivalent"
            if name == "tet-clarified"
            else "synthetic_fixture",
            seconds=round(time.monotonic() - started, 2),
            status=steps["analysis_job"]["status"],
            error=steps["analysis_job"].get("error"),
            baseline=result.baseline.model_dump(mode="json") if result else None,
            scenarios=len(result.scenarios) if result else 0,
            proven_expansion_scenarios=sum(bool(s.proven_blocked_candidate_ids) for s in result.scenarios)
            if result
            else 0,
            actionable_bounds=sum(s.kind == "relax_bound" for s in result.scenarios) if result else 0,
            limits=result.limits if result else None,
            retrieval=result.scope["retrieval"] if result else None,
            explanation=result.explanation if result else None,
            condition_diagnostics=result.scope["condition_diagnostics"] if result else None,
            checks=checks,
        )
        (output / f"{name}.json").write_text(
            json.dumps(dict(request=request, steps=steps, summary=summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        return summary, result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-nim", action="store_true")
    args = parser.parse_args()
    settings = Settings(database_url="sqlite:///:memory:", worker_enabled=False)
    if settings.data_provider != "supabase":
        raise RuntimeError("Live smoke requires DATA_PROVIDER=supabase")
    output = Path("data/live-tests") / ("what-if-" + now().strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(parents=True, exist_ok=False)
    summaries = [run_case(settings, name, output)[0] for name in ["japan", "tet-clarified"]]
    if not args.skip_nim:
        fixture_settings = Settings(
            _env_file=None, database_url="sqlite:///:memory:", worker_enabled=False, data_provider="fixture"
        )
        synthetic_summary, analysis = run_case(fixture_settings, "nim-synthetic", output)
        if not settings.nvidia_nim_api.get_secret_value():
            raise RuntimeError("NIM probe needs configured NVIDIA_NIM_API; use --skip-nim for catalog only")
        selected = asyncio.run(
            WhatIfExplainer(settings, NimWhatIfGateway(settings)).run(
                analysis, (now() + timedelta(seconds=45)).isoformat()
            )
        )
        by_id = {s.id: s.insight for s in analysis.scenarios}
        synthetic_summary["live_nim_selection"] = selected
        synthetic_summary["checks"].update(
            real_nim_completed=selected["state"] == "completed",
            generated_prose_equals_computed_templates=selected["text"]
            == [by_id[sid] for sid in selected["insight_ids"]],
        )
        (output / "nim-selection.json").write_text(
            json.dumps(synthetic_summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(dict(case="nim-selection-on-synthetic-metrics", **selected), ensure_ascii=False),
            flush=True,
        )
        summaries.append(synthetic_summary)
    result = dict(
        cases=summaries,
        passed=all(all(s["checks"].values()) for s in summaries),
        artifacts=str(output.resolve()),
    )
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(dict(passed=result["passed"], artifacts=result["artifacts"]), ensure_ascii=False),
        flush=True,
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
