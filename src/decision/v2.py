"""Deterministic, evidence-bound public matrix and preference policy."""

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from itertools import combinations

from decision.engine import evaluate, fold_tree, freshness, usable
from domain.common import AppError, instant
from domain.crawl import money_wire
from domain.requirements import DateValue, NumberValue

RANK_POLICY = "rank-v2.1"
DIMENSIONS = {"estimated_cost": "cost", "hotel_stars_min": "comfort", "included_services": "comfort"}
LABELS = {
    "duration_days": "Thời lượng",
    "duration_nights": "Số đêm",
    "hotel_stars_min": "Khách sạn",
    "shopping_stops": "Điểm mua sắm",
    "flight_stops": "Chặng dừng",
    "destinations": "Điểm đến",
    "departure_origin": "Nơi khởi hành",
    "departure_date": "Ngày khởi hành",
    "return_date": "Ngày về",
    "availability": "Số chỗ công bố",
    "transport": "Phương tiện",
    "included_services": "Dịch vụ bao gồm",
    "supplier": "Nhà cung cấp",
}


def tour_identity(tour):
    return "tour_" + hashlib.sha256(json.dumps([tour.supplier_id, tour.tour_id]).encode()).hexdigest()[:32]


def preference_utility(condition, evaluation, domain):
    if evaluation["status"] in {"pass", "fail"}:
        return 1.0 if evaluation["status"] == "pass" else 0.0
    if evaluation["reason_code"] != "PREFERENCE_VALUE":
        return None
    actual = evaluation["actual"]
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        return None
    target = condition.value.amount if isinstance(condition.value, NumberValue) else None
    if condition.operator == "near" and target is not None:
        return 1 / (1 + abs(actual - target) / max(target, 1))
    lo, hi = min(domain), max(domain)
    if hi == lo:
        return 1.0
    return (hi - actual) / (hi - lo) if condition.operator == "prefer_low" else (actual - lo) / (hi - lo)


def score_tree(tree, contributions):
    if tree.kind == "predicate":
        part = contributions[tree.condition_id]
        return part["utility"] or 0.0, part["weight"], part["weight"] if part["utility"] is not None else 0.0
    parts = [score_tree(child, contributions) for child in tree.children]
    parts = [p for p in parts if p[1] > 0]
    if not parts:
        return 0.0, 0.0, 0.0
    if tree.kind == "any":
        return max(parts, key=lambda p: (p[0], p[2] / p[1]))
    weight = sum(p[1] for p in parts)
    return sum(p[0] * p[1] for p in parts) / weight, weight, sum(p[2] for p in parts)


def build_comparison(
    cid, r, crawl, registry, at, *, exclusions=(), selections=(), candidate_limit=20, progress=None
):
    def stage(name, status, summary, **kwargs):
        if progress is not None:
            progress(name, status, summary, **kwargs)

    stage("evaluation", "started", "Đánh giá các điều kiện trên snapshot đã chuẩn hóa.")
    sources = {s.source_id: s for s in registry}
    suppliers = {s.supplier_id: s for s in crawl.suppliers}
    tours = {t.snapshot_id: t for t in crawl.tours}
    offers = {o.snapshot_id: o for o in crawl.offers}
    by_entity = {}
    for sr in crawl.source_results:
        for tid in sr.tour_snapshot_ids:
            t = tours[tid]
            key = tour_identity(t)
            item = by_entity.setdefault(
                key,
                {
                    "tour": t,
                    "source_ids": set(),
                    "target_ids": set(),
                    "discovered": False,
                    "offers": {},
                    "source": sources.get(sr.source_id),
                },
            )
            item["source_ids"].add(sr.source_id)
            if sr.target_id:
                item["target_ids"].add(sr.target_id)
                # Use reference snapshot for overlapping reference/discovery entities.
                item["tour"] = t
            else:
                item["discovered"] = True
            for oid in sr.offer_snapshot_ids:
                if offers[oid].tour_snapshot_id == tid:
                    item["offers"][oid] = offers[oid]
    selection = {s["tour_id"]: s["offer_snapshot_id"] for s in selections}
    if set(selection) - by_entity.keys():
        raise AppError("OFFER_SELECTION_INVALID", "Tour không thuộc kết quả đã thu thập.", 409)
    evaluated, synthetic = [], crawl.origin == "synthetic"
    excluded = set(exclusions)
    discovery_entities = sorted(k for k, v in by_entity.items() if v["discovered"] and k not in excluded)
    retained = set(discovery_entities[:candidate_limit]) | {
        k for k, v in by_entity.items() if v["target_ids"]
    }
    truncated = len(discovery_entities) > candidate_limit or any(s.truncated for s in crawl.source_results)
    for key in sorted(retained):
        item = by_entity[key]
        tour, source = item["tour"], item["source"]
        options = [o for o in item["offers"].values() if o.tour_snapshot_id == tour.snapshot_id]
        selected = None
        if key in selection:
            selected = next((o for o in options if o.snapshot_id == selection[key]), None)
            if selected is None or any(
                freshness(f, field, source, at) != "fresh" for field, f in selected.fields.items()
            ):
                raise AppError("OFFER_SELECTION_INVALID", "Offer sai binding hoặc đã cũ.", 409)
        elif len(options) == 1:
            selected = options[0]
        elif options:
            date_conditions = [
                c for c in r.conditions if c.strength == "hard" and isinstance(c.value, DateValue)
            ]
            matching = [
                o
                for o in options
                if date_conditions
                and all(
                    evaluate(c, tour, o, r.party, source, at, synthetic)["status"] == "pass"
                    for c in date_conditions
                )
            ]
            if len(matching) == 1:
                selected = matching[0]
        reason = None if selected else "MULTIPLE_OFFERS_UNSELECTED" if options else "OFFER_MISSING"
        evaluations = [
            dict(
                evaluate(c, tour, selected, r.party, source, at, synthetic, reason),
                id="eval_" + hashlib.sha256(json.dumps([key, c.id]).encode()).hexdigest()[:32],
                candidate_id=key,
                expected=c.value.model_dump(mode="json"),
            )
            for c in r.conditions
        ]
        hard = any(c.strength != "soft" for c in r.conditions)
        status = (
            fold_tree(r.hard_tree, {e["condition_id"]: e["status"] for e in evaluations}) if hard else None
        )
        if status == "pass" and not r.readiness.can_evaluate_hard_constraints:
            status = "unknown"
        evaluated.append(
            {
                "id": key,
                "item": item,
                "tour": tour,
                "selected": selected,
                "options": options,
                "evaluations": evaluations,
                "hard_status": status,
                "offer_reason": reason,
            }
        )
    stage("evaluation", "completed", "Đã đánh giá pass/fail/unknown.", counts={"candidates": len(evaluated)})
    stage("ranking", "started", "Xếp hạng theo preference tree và policy.")
    for candidate in evaluated:
        contributions = {}
        for condition in r.conditions:
            if condition.strength != "soft":
                continue
            evaluation = next(e for e in candidate["evaluations"] if e["condition_id"] == condition.id)
            domain = [
                e["actual"]
                for other in evaluated
                for e in other["evaluations"]
                if e["condition_id"] == condition.id
                and e["reason_code"] == "PREFERENCE_VALUE"
                and type(e["actual"]) is int
            ]
            dimension = DIMENSIONS.get(condition.field)
            weight = getattr(r.preference_levels, dimension).level if r.preference_levels and dimension else 3
            contributions[condition.id] = {
                "condition_id": condition.id,
                "dimension": dimension,
                "utility": preference_utility(condition, evaluation, domain or [0]),
                "weight": weight,
                "evaluation_id": evaluation["id"],
                "evidence_ids": evaluation["evidence_ids"],
            }
        score, weight, covered = score_tree(r.preference_tree, contributions)
        candidate.update(
            score=score if weight else None,
            coverage=covered / weight if weight else None,
            contributions=list(contributions.values()),
        )
    eligible = [c for c in evaluated if c["hard_status"] == "pass" and c["id"] not in excluded]
    # URL-only can expose a similar/reference group, but never personalized eligibility.
    if not any(c.strength != "soft" for c in r.conditions):
        eligible = [c for c in evaluated if c["id"] not in excluded]
    eligible.sort(key=lambda c: (-(c["score"] or 0), -(c["coverage"] or 0), c["id"]))
    recommended = eligible[:3]
    stage(
        "ranking", "completed", "Đã chọn tối đa ba tour khác nhau.", counts={"recommended": len(recommended)}
    )
    stage("comparison", "started", "Dựng bảng và kiểm tra lựa chọn offer.")
    visible_ids = {c["id"] for c in recommended} | {
        c["id"] for c in evaluated if c["item"]["target_ids"] or c["hard_status"] == "unknown"
    }
    visible = [c for c in evaluated if c["id"] in visible_ids]
    columns = []
    for c in visible:
        t, o, item = c["tour"], c["selected"], c["item"]
        columns.append(
            {
                "id": c["id"],
                "candidate_id": c["id"],
                "tour_id": c["id"],
                "tour_snapshot_id": t.snapshot_id,
                "offer_snapshot_id": o.snapshot_id if o else None,
                "selected_offer_snapshot_id": o.snapshot_id if o else None,
                "title": t.title,
                "title_reason": None if t.title else "TITLE_NOT_PROVIDED",
                "supplier": {"id": t.supplier_id, "display_name": suppliers[t.supplier_id].display_name},
                "canonical_url": t.canonical_url,
                "origin": "both"
                if item["target_ids"] and item["discovered"]
                else "reference"
                if item["target_ids"]
                else "discovery",
                "target_ids": sorted(item["target_ids"]),
                "source_ids": sorted(item["source_ids"]),
                "offer_reason": c["offer_reason"],
                "offer_options": [o.model_dump(mode="json") for o in c["options"]],
            }
        )
    # Keep inaccessible URL targets visible rather than dropping a column.
    for target in r.targets:
        if not any(target.target_id in c["target_ids"] for c in columns):
            sr = next((s for s in crawl.source_results if s.target_id == target.target_id), None)
            columns.append(
                {
                    "id": target.target_id,
                    "candidate_id": None,
                    "tour_id": None,
                    "tour_snapshot_id": None,
                    "offer_snapshot_id": None,
                    "selected_offer_snapshot_id": None,
                    "title": None,
                    "supplier": None,
                    "canonical_url": target.url,
                    "origin": "reference",
                    "target_ids": [target.target_id],
                    "source_ids": [sr.source_id] if sr else [],
                    "offer_options": [],
                    "offer_reason": sr.reason_code if sr else "TARGET_RESULT_MISSING",
                }
            )
    field_names = sorted(
        {f for c in visible for f in c["tour"].fields}
        | {f for c in visible if c["selected"] for f in c["selected"].fields}
        | {c.field for c in r.conditions if c.field not in {"estimated_cost", "unsupported"}}
    )
    policy_names = sorted({"cancellation", *[f for c in visible for f in c["tour"].policies]})
    rows = [
        {
            "id": f,
            "field": f,
            "label": LABELS.get(f, f),
            "scope": "offer" if f in {"departure_date", "return_date", "availability"} else "tour",
            "order": i,
            "condition_ids": [c.id for c in r.conditions if c.field == f],
            "value_type": "date"
            if f in {"departure_date", "return_date"}
            else "number"
            if f
            in {
                "duration_days",
                "duration_nights",
                "hotel_stars_min",
                "shopping_stops",
                "flight_stops",
                "availability",
            }
            else "set"
            if f in {"destinations", "included_services", "transport"}
            else "text",
            "unit": "days" if f == "duration_days" else "nights" if f == "duration_nights" else None,
        }
        for i, f in enumerate(field_names)
    ]
    for field, label, scope in [
        ("price_quotes", "Giá công bố", "offer"),
        ("extra_charges", "Phụ thu", "offer"),
        ("pricing_complete", "Độ đầy đủ giá", "offer"),
        *[(f"policies.{p}", p, "tour") for p in policy_names],
    ]:
        rows.append(
            {
                "id": field,
                "field": field,
                "label": label,
                "scope": scope,
                "order": len(rows),
                "condition_ids": [],
                "value_type": "boolean"
                if field == "pricing_complete"
                else "text"
                if field.startswith("policies.")
                else "price_list",
                "unit": None,
            }
        )
    cells = []
    visible_map = {c["id"]: c for c in visible}
    for row in rows:
        for column in columns:
            c = visible_map.get(column["id"])
            values = []
            if c:
                o, t = c["selected"], c["tour"]
                if row["field"] in {"price_quotes", "extra_charges"}:
                    values = getattr(o, row["field"]) if o else []
                elif row["field"] == "pricing_complete":
                    values = [o.pricing_complete] if o and o.pricing_complete else []
                else:
                    f = (
                        t.policies.get(row["field"].split(".", 1)[1])
                        if row["field"].startswith("policies.")
                        else (
                            (o.fields.get(row["field"]) if o else None)
                            if row["scope"] == "offer"
                            else t.fields.get(row["field"])
                        )
                    )
                    values = [f] if f else []
            serialized = [f.model_dump(mode="json") for f in values]
            volatile_field = (
                "price"
                if row["field"] in {"price_quotes", "extra_charges", "pricing_complete"}
                else row["field"]
            )
            states = [freshness(f, volatile_field, c["item"]["source"], at) for f in values] if c else []
            evidence_ids = sorted({eid for f in values for eid in f.evidence_ids})
            cells.append(
                {
                    "row_id": row["id"],
                    "column_id": column["id"],
                    "value": [f["value"] for f in serialized]
                    if row["field"] in {"price_quotes", "extra_charges"}
                    else serialized[0]["value"]
                    if serialized
                    else None,
                    "raw_value": [f["raw_value"] for f in serialized],
                    "data_state": "present"
                    if values and all(f.data_state == "present" for f in values)
                    else values[0].data_state
                    if values
                    else "missing",
                    "verification": serialized[0]["verification"] if serialized else "unverified",
                    "completeness": serialized[0]["completeness"] if len(serialized) == 1 else "unknown",
                    "observed_at": min((f.observed_at for f in values), default=None),
                    "freshness": {
                        "state": "stale"
                        if "stale" in states
                        else "fresh"
                        if states and all(s == "fresh" for s in states)
                        else "unknown",
                        "checked_at": at,
                        "expires_at": min(
                            (
                                (
                                    instant(f.observed_at)
                                    + timedelta(seconds=c["item"]["source"].freshness_seconds[volatile_field])
                                ).isoformat()
                                for f in values
                            ),
                            default=None,
                        )
                        if c
                        and c["item"]["source"]
                        and volatile_field in c["item"]["source"].freshness_seconds
                        else None,
                        "policy_version": "decision-v1",
                    },
                    "evidence_ids": evidence_ids,
                    "reason_code": next(
                        (
                            f.reason or f"FIELD_{f.data_state.upper()}"
                            for f in values
                            if f.data_state != "present"
                        ),
                        None,
                    )
                    if values
                    else column.get("offer_reason") or "FIELD_MISSING",
                    "evaluation_ids": [e["id"] for e in c["evaluations"] if e["field"] == row["field"]]
                    if c
                    else [],
                }
            )
    stage(
        "comparison",
        "completed",
        "Đã dựng các ô của bảng.",
        counts={"columns": len(columns), "cells": len(cells)},
    )
    stage("analysis", "started", "Tính metrics có operands và evidence.")
    metrics = []
    quotes = []
    for c in visible:
        if c["selected"]:
            exact = [
                f
                for f in c["selected"].price_quotes
                if f.value
                and f.value.kind == "exact"
                and not f.value.applicability
                and f.value.age_min is None
                and f.value.basis == "per_adult"
                and usable(f, "price", c["item"]["source"], at, synthetic)[0]
            ]
            if len(exact) == 1:
                quotes.append((c, exact[0]))
    for (a, qa), (b, qb) in list(combinations(quotes, 2))[:100]:
        comparable = (qa.value.currency, qa.value.basis, qa.value.coverage) == (
            qb.value.currency,
            qb.value.basis,
            qb.value.coverage,
        )
        value = Decimal(qa.value.amount) - Decimal(qb.value.amount) if comparable else None
        metrics.append(
            {
                "id": f"metric:{a['id']}:{b['id']}",
                "operation": "subtract",
                "operands": [
                    {
                        "candidate_id": c["id"],
                        "snapshot_id": c["selected"].snapshot_id,
                        "field": "price_quotes",
                        "quote_id": q.value.quote_id,
                        "value": q.value.amount,
                        "evidence_ids": q.evidence_ids,
                    }
                    for c, q in ((a, qa), (b, qb))
                ],
                "result": money_wire(value, qa.value.currency),
                "currency": qa.value.currency,
                "basis": qa.value.basis,
                "coverage": qa.value.coverage,
                "comparable": comparable,
                "limitations": [
                    "So sánh giá công bố theo offer; không khẳng định tổng chuyến đi hoặc phụ thu đã đủ."
                ],
                "evidence_ids": sorted(set(qa.evidence_ids + qb.evidence_ids)),
            }
        )
    recommendation_ids = [c["id"] for c in recommended]
    if r.party.adults is not None:
        for candidate, quote in quotes:
            metrics.append(
                {
                    "id": f"metric_adults:{candidate['id']}",
                    "operation": "multiply",
                    "operands": [
                        {
                            "candidate_id": candidate["id"],
                            "snapshot_id": candidate["selected"].snapshot_id,
                            "field": "price_quotes",
                            "quote_id": quote.value.quote_id,
                            "value": quote.value.amount,
                            "evidence_ids": quote.evidence_ids,
                        },
                        {
                            "requirement_id": r.id,
                            "revision": r.revision,
                            "field": "party.adults",
                            "value": r.party.adults,
                            "evidence_ids": [],
                        },
                    ],
                    "result": money_wire(Decimal(quote.value.amount) * r.party.adults, quote.value.currency),
                    "currency": quote.value.currency,
                    "basis": "group_total",
                    "coverage": quote.value.coverage,
                    "comparable": True,
                    "limitations": [
                        "Tạm tính giá công bố cho người lớn; chưa gồm trẻ em/phụ thu, không phải tổng chuyến đi cuối cùng."
                    ],
                    "evidence_ids": quote.evidence_ids,
                }
            )
    stage("analysis", "completed", "Đã tính các metrics so sánh được.", counts={"metrics": len(metrics)})
    return {
        "id": cid,
        "requirement_id": r.id,
        "revision": r.revision,
        "requirement_snapshot": r.model_dump(mode="json"),
        "origin": crawl.origin,
        "evaluated_at": at,
        "policy_versions": {"ranking": RANK_POLICY, "decision": "decision-v1"},
        "columns": columns,
        "rows": rows,
        "cells": cells,
        "evaluations": [e for c in visible for e in c["evaluations"]],
        "recommendations": {
            "kind": "personalized" if any(c.strength != "soft" for c in r.conditions) else "similar",
            "candidate_ids": recommendation_ids,
            "items": [
                {
                    "candidate_id": c["id"],
                    "rank": i + 1,
                    "score": c["score"],
                    "coverage": c["coverage"],
                    "contributions": c["contributions"],
                    "evaluation_ids": [e["id"] for e in c["evaluations"]],
                    "reason": "Đạt điều kiện bắt buộc."
                    if c["hard_status"] == "pass"
                    else "Không có điều kiện bắt buộc để kết luận phù hợp.",
                }
                for i, c in enumerate(recommended)
            ],
            "ranking_policy_version": RANK_POLICY,
            "unsupported_dimensions": ["pace", "culture"],
            "needs_verification": [c["id"] for c in evaluated if c["hard_status"] == "unknown"],
            "excluded_tour_ids": sorted(excluded),
            "candidate_limit": candidate_limit,
            "truncated": truncated,
            "evaluated_count": len(evaluated),
        },
        "analysis": {
            "metrics": metrics,
            "claims": [
                {
                    "id": "claim:" + m["id"],
                    "metric_ids": [m["id"]],
                    "text": f"{'Chênh lệch giá công bố' if m['operation'] == 'subtract' else 'Tạm tính giá công bố cho người lớn'}: {m['result']} {m['currency']} / {m['basis']}.",
                    "evidence_ids": m["evidence_ids"],
                    "limitations": m["limitations"],
                }
                for m in metrics
                if m["comparable"]
            ],
        },
        "source_coverage": [s.model_dump(mode="json") for s in crawl.source_results],
        "warnings": [i.model_dump(mode="json") for i in crawl.issues],
        "empty_reason": None
        if recommendation_ids
        else "ONLY_UNVERIFIED"
        if any(c["hard_status"] == "unknown" for c in evaluated)
        else "ALL_INELIGIBLE"
        if evaluated
        else "NO_SUPPORTED_TARGETS"
        if not any(s.status in {"ok", "partial"} for s in crawl.source_results)
        else "NO_CANDIDATES",
    }
