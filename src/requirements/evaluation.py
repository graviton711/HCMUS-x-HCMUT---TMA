"""Explicitly invoked live smoke evaluation; never part of offline pytest."""

import asyncio
import json
from pathlib import Path

from domain.common import AppError
from domain.requirements import Message
from requirements.nim import NimGateway, parse_validated


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and contains(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and sorted(actual) == sorted(expected)
    return actual == expected


async def evaluate_smoke(settings, cases_path: Path, output: Path):
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        row = {"id": case["id"], "passed": False}
        try:
            message = Message(
                id=f"m_{case['id']}", text=case["text"], received_at="2026-10-01T03:00:00+00:00"
            )
            async with asyncio.timeout(settings.job_timeout_seconds):
                r, metrics = await parse_validated(
                    NimGateway(settings),
                    message,
                    requirement_id=f"r_{case['id']}",
                    mode="discover",
                    timezone="Asia/Ho_Chi_Minh",
                    targets=[],
                )
                actual = [c.model_dump() for c in r.conditions]
                matches = len(actual) == len(case["conditions"]) and all(
                    any(contains(c, wanted) for c in actual) for wanted in case["conditions"]
                )
                matches &= set(case["reasons"]) == set(r.readiness.reasons)
                row.update(metrics=metrics, conditions=actual, reasons=r.readiness.reasons)
                if case.get("patch"):
                    patch = Message(
                        id=f"patch_{case['id']}", text=case["patch"], received_at="2026-10-02T03:00:00+00:00"
                    )
                    updated, patch_metrics = await parse_validated(
                        NimGateway(settings),
                        patch,
                        r,
                        requirement_id=r.id,
                        mode=r.mode,
                        timezone=r.timezone,
                        targets=[],
                    )
                    removed = set(case.get("removed_fields", []))
                    preserved = [
                        c
                        for c in r.conditions
                        if c.field not in removed
                        and not (case.get("updated_budget") and c.field == "estimated_cost")
                    ]
                    matches &= all(c in updated.conditions for c in preserved)
                    matches &= not any(c.field in removed for c in updated.conditions)
                    if case.get("updated_budget"):
                        matches &= any(
                            c.field == "estimated_cost" and c.value.amount == case["updated_budget"]
                            for c in updated.conditions
                        )
                    row.update(
                        patch_metrics=patch_metrics,
                        patch_conditions=[c.model_dump() for c in updated.conditions],
                    )
                row["passed"] = matches
        except (AppError, TimeoutError, ValueError) as exc:
            row["error"] = exc.code if isinstance(exc, AppError) else type(exc).__name__
            row["validation_hint"] = getattr(exc, "repair_hint", None)
        results.append(row)
        # Synthetic fixture cases only; do not print user messages or upstream raw content.
        print(f"{case['id']}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "scope": "curated_smoke_not_full_gold",
            "passed": sum(r["passed"] for r in results),
            "total": len(results),
            "results": results,
        }
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
