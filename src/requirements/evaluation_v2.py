"""Explicit live semantic evaluation through the production v2 parser, without a DB."""

import asyncio
import json
import time
from pathlib import Path

from domain.common import AppError
from domain.requirements import Message
from domain.semantic import ConditionV2, SemanticRequirement
from requirements.nim import NimGateway, parse_validated
from requirements.semantic import finalize_v2, normalize_v2
from requirements.v2 import SlotExtractor


def matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and matches(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                sum(matches(a, e) for a in actual) >= sum(e == other for other in expected) for e in expected
            )
        )
    return actual == expected


def assertions(requirement, expected):
    conditions = [c.model_dump(mode="json") for c in requirement.conditions]
    checks = {}
    for wanted in expected.get("conditions", []):
        field = wanted["field"]
        checks[f"condition:{field}"] = any(matches(c, wanted) for c in conditions)
    if "fields" in expected:
        checks["exact_fields"] = sorted(c["field"] for c in conditions) == sorted(expected["fields"])
    for field in expected.get("absent_fields", []):
        checks[f"absent:{field}"] = not any(c["field"] == field for c in conditions)
    if "reasons" in expected:
        checks["blocking_reasons"] = set(requirement.readiness.reasons) == set(expected["reasons"])
    for key in ("readiness", "party"):
        if key in expected:
            checks[key] = matches(getattr(requirement, key).model_dump(mode="json"), expected[key])
    for reason in expected.get("absent_questions", []):
        checks[f"no_question:{reason}"] = all(q.reason_code != reason for q in requirement.clarifications)
    checks["provenance"] = all(
        c.sources and all(s.kind != "text" or s.quote for s in c.sources) for c in requirement.conditions
    )
    return checks


async def parse(settings, text, rid, previous=None):
    message = Message(
        id=f"msg_{rid}_{'patch' if previous else 'initial'}",
        text=text,
        received_at="2026-10-07T14:00:00+00:00",
    )
    wrapper = SlotExtractor(NimGateway(settings))
    try:
        async with asyncio.timeout(settings.job_timeout_seconds):
            return await parse_validated(
                wrapper,
                message,
                previous,
                requirement_id=rid,
                mode="discover",
                timezone="Asia/Ho_Chi_Minh",
                targets=[],
                requirement_model=SemanticRequirement,
                condition_model=ConditionV2,
                normalizer=normalize_v2,
                finalizer=finalize_v2,
                batch_validation=True,
            )
    except AppError as exc:
        if hasattr(wrapper, "extraction"):
            exc.validation_snapshot = wrapper.extraction.model_dump(mode="json")
        raise


async def evaluate_semantic(settings, cases_path: Path, output: Path, repeat=1):
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    report = {
        "scope": "curated_semantic_smoke_not_general_accuracy",
        "model": settings.nvidia_nim_model,
        "passed": 0,
        "total": 0,
        "results": results,
    }
    for run in range(repeat):
        for case in cases:
            row = {"id": case["id"], "run": run + 1, "passed": False}
            stage = "initial"
            started = time.monotonic()
            try:
                r, metrics = await parse(settings, case["text"], f"eval_{case['id']}_{run}")
                checks = assertions(r, case["expected"])
                row.update(checks=checks, metrics=metrics, requirement=r.model_dump(mode="json"))
                if case.get("patch"):
                    stage = "patch"
                    updated, patch_metrics = await parse(settings, case["patch"], r.id, r)
                    checks.update(
                        {f"patch:{k}": v for k, v in assertions(updated, case["patch_expected"]).items()}
                    )
                    updated_by_id = {c.id: c for c in updated.conditions}
                    changed = set(case.get("patch_changed_fields", []))
                    checks["patch:preserves_others"] = all(
                        updated_by_id.get(c.id) == c for c in r.conditions if c.field not in changed
                    )
                    row.update(patch_metrics=patch_metrics, updated=updated.model_dump(mode="json"))
                row["passed"] = all(checks.values())
            except (AppError, TimeoutError, ValueError) as exc:
                row["error_stage"] = stage
                row["error"] = exc.code if isinstance(exc, AppError) else type(exc).__name__
                row["message"] = exc.message if isinstance(exc, AppError) else str(exc)[:1000]
                row["validation_hint"] = getattr(exc, "repair_hint", None)
                row["diagnostic_extraction"] = getattr(exc, "validation_snapshot", None)
            row["latency_seconds"] = round(time.monotonic() - started, 3)
            results.append(row)
            failed = [k for k, value in row.get("checks", {}).items() if not value]
            print(
                f"{case['id']} run {run + 1}: {'PASS' if row['passed'] else 'FAIL'} {row.get('error', '')} {', '.join(failed)}",
                flush=True,
            )
            report.update(passed=sum(r["passed"] for r in results), total=len(results))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
