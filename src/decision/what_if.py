"""Conditional analysis on one acquired universe, with proof-bound deltas."""

import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from itertools import combinations

from decision.candidates import assess_options, evaluate_candidates
from decision.v2 import LABELS, RANK_POLICY, rank_candidates
from domain.crawl import money_wire
from domain.requirements import Budget, DateValue, Tree
from domain.what_if import WhatIfAnalysis
from requirements.service import prune


def digest(value, prefix):
    return (
        prefix
        + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    )


def leaves(tree):
    return (
        {tree.condition_id} if tree.kind == "predicate" else set().union(*(leaves(c) for c in tree.children))
    )


def condition_groups(r):
    groups = []
    for soft, tree in [(False, r.hard_tree), (True, r.preference_tree)]:
        conditions = [c for c in r.conditions if (c.strength == "soft") == soft]
        sets = [{c.id} for c in conditions]
        fields = {}
        for c in conditions:
            field = "travel_dates" if c.field in {"departure_date", "return_date"} else c.field
            fields.setdefault(field, set()).add(c.id)
        sets.extend(fields.values())

        def alternatives(node, sets=sets):
            if node.kind == "any":
                sets.append(leaves(node))
            for child in node.children:
                alternatives(child)

        alternatives(tree)
        merged = []
        for group in sets:
            overlap = [s for s in merged if s & group]
            merged = [s for s in merged if not s & group]
            merged.append(group.union(*overlap))
        by_id = {c.id: c for c in conditions}
        for group in merged:
            names = sorted({by_id[cid].field for cid in group})
            groups.append(
                dict(
                    id=digest(sorted(group), "group_"),
                    strength="soft" if soft else "hard",
                    condition_ids=sorted(group),
                    fields=names,
                    label=" / ".join(
                        "Ngân sách" if f == "estimated_cost" else LABELS.get(f, f) for f in names
                    ),
                )
            )
    return sorted(groups, key=lambda g: (g["strength"] == "soft", g["fields"], g["id"]))


def scenario_requirement(r, removed=(), replacements=()):
    removed = set(removed)
    replacements = {c.id: c for c in replacements}
    return r.model_copy(
        update={
            "conditions": [replacements.get(c.id, c) for c in r.conditions if c.id not in removed],
            "hard_tree": prune(r.hard_tree, removed) or Tree(kind="all"),
            "preference_tree": prune(r.preference_tree, removed) or Tree(kind="all"),
        }
    )


def reevaluate(r, universe, at, synthetic, cache):
    records = []
    for candidate in universe:
        assessed = assess_options(
            r,
            candidate["tour"],
            candidate["options"],
            candidate["item"]["source"],
            at,
            synthetic,
            complete=candidate["offers_complete"],
            evaluation_cache=cache,
        )
        records.append({**candidate, **assessed})
    return records


def passing(records):
    return {c["id"] for c in records if c["hard_status"] in {"pass", None}}


def population(r, records):
    return dict(
        eligible=len(passing(records)),
        ineligible=sum(c["hard_status"] == "fail" for c in records),
        unknown=sum(c["hard_status"] == "unknown" for c in records),
        eligible_candidate_ids=sorted(passing(records)),
        has_hard_constraints=bool(leaves(r.hard_tree)),
    )


def removal(groups, kind):
    ids = sorted({cid for g in groups for cid in g["condition_ids"]})
    return dict(
        id=digest([kind, ids], "scenario_"),
        kind=kind,
        group_ids=[g["id"] for g in groups],
        condition_ids=ids,
        label="Tạm bỏ: " + " + ".join(g["label"] for g in groups),
        removed=ids,
        replacements=[],
        edits=[dict(op="remove_condition", condition_id=cid) for cid in ids],
    )


def bounded_replacements(r, group, records, options):
    if len(group["condition_ids"]) != 1:
        return []
    condition = next(c for c in r.conditions if c.id == group["condition_ids"][0])
    values = set()
    if isinstance(condition.value, Budget) and condition.operator == "lte":
        cap = Decimal(condition.value.amount)
        ceiling = cap * (1 + Decimal(str(options.max_budget_increase_ratio)))
        for candidate in records:
            for assessment in candidate["offer_assessments"]:
                evaluation = next(e for e in assessment["evaluations"] if e["condition_id"] == condition.id)
                cost = evaluation["actual"]
                if (
                    evaluation["status"] == "fail"
                    and isinstance(cost, dict)
                    and cost.get("upper") is not None
                ):
                    amount = Decimal(str(cost["upper"]))
                    if cap < amount <= ceiling:
                        values.add(amount)
        return [
            condition.model_copy(
                update={
                    "value": condition.value.model_copy(
                        update={"amount": money_wire(v, condition.value.currency)}
                    )
                }
            )
            for v in sorted(values)[:3]
        ]
    if (
        isinstance(condition.value, DateValue)
        and condition.operator == "eq"
        and condition.field == "departure_date"
    ):
        original = date.fromisoformat(condition.value.value)
        for candidate in records:
            for assessment in candidate["offer_assessments"]:
                evaluation = next(e for e in assessment["evaluations"] if e["condition_id"] == condition.id)
                actual = evaluation["actual"]
                if evaluation["status"] == "fail" and isinstance(actual, str):
                    changed = date.fromisoformat(actual)
                    if 0 < abs((changed - original).days) <= options.max_date_shift_days:
                        values.add(changed)
        return [
            condition.model_copy(
                update={
                    "operator": "between",
                    "value": DateValue(
                        value=min(v, original).isoformat(), upper=max(v, original).isoformat()
                    ),
                }
            )
            for v in sorted(values, key=lambda d: (abs((d - original).days), d))[:3]
        ]
    return []


def plan_analysis(r, crawl, registry, at, options, *, exclusions=(), check=None):
    """Prepare bounded scenarios and the union for one soft assessment call."""
    cache = {}
    universe = evaluate_candidates(r, crawl, registry, at, exclusions=exclusions, evaluation_cache=cache)
    universe = [c for c in universe if c["id"] not in exclusions]
    groups = condition_groups(r)
    selected = [
        g
        for g in groups
        if (not options.condition_ids or set(g["condition_ids"]) & set(options.condition_ids))
        and (options.include_soft or g["strength"] == "hard")
    ]
    hard = [g for g in selected if g["strength"] == "hard"]
    specs = [removal([g], "remove_hard_group") for g in hard]
    for group in hard:
        for replacement in bounded_replacements(r, group, universe, options):
            raw = replacement.model_dump(mode="json", exclude={"sources", "trace"})
            if isinstance(replacement.value, Budget):
                original = next(c for c in r.conditions if c.id == replacement.id)
                old = (
                    f"{original.value.amount:,}".replace(",", ".")
                    if replacement.value.currency == "VND"
                    else str(original.value.amount)
                )
                new = (
                    f"{replacement.value.amount:,}".replace(",", ".")
                    if replacement.value.currency == "VND"
                    else str(replacement.value.amount)
                )
                basis = {"per_adult": "người lớn", "per_person": "người", "group_total": "cả nhóm"}.get(
                    replacement.value.basis, "chưa rõ"
                )
                label = f"Nới trần giá: {old} → {new} {replacement.value.currency}/{basis}"
            else:
                label = f"Mở ngày khởi hành: {replacement.value.value} đến {replacement.value.upper}"
            specs.append(
                dict(
                    id=digest(["bound", raw], "scenario_"),
                    kind="relax_bound",
                    group_ids=[group["id"]],
                    condition_ids=group["condition_ids"],
                    label=label,
                    removed=[],
                    replacements=[replacement],
                    edits=[dict(op="upsert_condition", condition=raw)],
                )
            )
    specs.extend(removal([g], "remove_soft_group") for g in selected if g["strength"] == "soft")
    if options.include_pairs:
        specs.extend(removal([a, b], "remove_hard_pair") for a, b in combinations(hard, 2))
    total = len(specs)
    planned, singles, pair_skipped, attempted = [], {}, 0, 0
    base_pass = passing(universe)
    for spec in specs:
        if check:
            check()
        if attempted >= options.max_scenarios:
            break
        attempted += 1
        changed = scenario_requirement(r, spec["removed"], spec["replacements"])
        records = reevaluate(changed, universe, at, crawl.origin == "synthetic", cache)
        added = passing(records) - base_pass
        if spec["kind"] == "remove_hard_group":
            singles[spec["group_ids"][0]] = added
        if spec["kind"] == "remove_hard_pair":
            individual = set().union(*(singles.get(gid, set()) for gid in spec["group_ids"]))
            if not added - individual:
                pair_skipped += 1
                continue
            spec["joint_only_candidate_ids"] = sorted(added - individual)
        planned.append((spec, changed, records))
    union_ids = base_pass | set().union(*(passing(records) for _, _, records in planned))
    union = [{**c, "hard_status": "pass"} for c in universe if c["id"] in union_ids]
    limits = dict(
        candidate_limit=options.candidate_limit,
        max_scenarios=options.max_scenarios,
        scenario_count=len(planned),
        scenario_space=total,
        attempted_scenarios=attempted,
        redundant_pairs_skipped=pair_skipped,
        scenarios_truncated=attempted < total,
        max_witnesses_per_scenario=3,
        max_budget_increase_ratio=options.max_budget_increase_ratio,
        max_date_shift_days=options.max_date_shift_days,
        max_joint_groups=2,
        scope_of_minimality="tested_single_and_pair_group_removals",
    )
    return universe, groups, planned, union, limits


def ranked(r, records, semantic_report):
    ordered = rank_candidates(r, records, semantic_report=semantic_report)
    keys = [(c["score_lower"], c["score_upper"], c["coverage"]) for c in ordered]
    return [
        dict(
            candidate_id=c["id"],
            rank=i + 1,
            score_lower=c["score_lower"],
            score_upper=c["score_upper"],
            coverage=c["coverage"],
            tied=keys.count(keys[i]) > 1,
        )
        for i, c in enumerate(ordered)
    ]


def build_analysis(aid, cid, r, crawl, at, plan, *, semantic_report=None, exclusions=()):
    universe, groups, planned, _, limits = plan
    baseline = population(r, universe)
    before = ranked(r, universe, semantic_report)
    before_map = {x["candidate_id"]: x for x in before}
    base = {c["id"]: c for c in universe}
    scenarios = []
    for spec, changed, records in planned:
        after = ranked(changed, records, semantic_report)
        after_map = {x["candidate_id"]: x for x in after}
        ids = sorted(passing(records) - passing(universe))
        proven = [cid for cid in ids if base[cid]["hard_status"] == "fail"]
        uncertain = [cid for cid in ids if base[cid]["hard_status"] == "unknown"]
        soft = spec["kind"] == "remove_soft_group"
        denominator = len(after)
        reason = (
            "SOFT_RANK_SENSITIVITY"
            if soft
            else "ORIGINAL_ELIGIBILITY_UNKNOWN"
            if uncertain
            else "EMPTY_ELIGIBLE_COHORT"
            if not denominator
            else "UNVERIFIED_CANDIDATES"
            if not ids and baseline["unknown"]
            else None
        )
        ratio = dict(
            state="not_applicable" if soft else "blocked" if reason else "computed",
            numerator=len(proven),
            denominator=denominator,
            percent=None if reason else 100 * len(proven) / denominator,
            reason_code=reason,
        )
        changes = [
            dict(
                candidate_id=cid,
                before=before_map[cid],
                after=after_map[cid],
                rank_delta=before_map[cid]["rank"] - after_map[cid]["rank"],
                evidence_ids=sorted(
                    {
                        e
                        for c in records
                        if c["id"] == cid
                        for part in [*base[cid]["contributions"], *c["contributions"]]
                        for e in part["evidence_ids"]
                    }
                ),
            )
            for cid in sorted(before_map.keys() & after_map.keys())
            if before_map[cid] != after_map[cid]
        ]
        witnesses = []
        for candidate in records:
            if candidate["id"] not in ids[:3]:
                continue
            passing_offer = next(
                (a for a in candidate["offer_assessments"] if a["hard_status"] in {"pass", None}), None
            )
            original = next(
                (
                    a
                    for a in base[candidate["id"]]["offer_assessments"]
                    if passing_offer and a["offer_snapshot_id"] == passing_offer["offer_snapshot_id"]
                ),
                None,
            )
            original_es = original["evaluations"] if original else base[candidate["id"]]["evaluations"]
            scenario_es = passing_offer["evaluations"] if passing_offer else candidate["evaluations"]
            witnesses.append(
                dict(
                    candidate_id=candidate["id"],
                    title=candidate["tour"].title,
                    canonical_url=candidate["tour"].canonical_url,
                    tour_snapshot_id=candidate["tour"].snapshot_id,
                    offer_snapshot_id=passing_offer["offer_snapshot_id"] if passing_offer else None,
                    original_status=base[candidate["id"]]["hard_status"] or "pass",
                    original_evaluations=[
                        e for e in original_es if e["condition_id"] in spec["condition_ids"]
                    ],
                    scenario_evaluations=[e for e in scenario_es if e["strength"] != "soft"],
                    evidence_ids=sorted(
                        {eid for e in [*original_es, *scenario_es] for eid in e["evidence_ids"]}
                    ),
                )
            )
        top_changed = [x["candidate_id"] for x in before[:3]] != [x["candidate_id"] for x in after[:3]]
        known_soft = any(
            part["utility"] is not None and part["weight"] > 0
            for c in universe
            if c["id"] in before_map
            for part in c["contributions"]
            if part["condition_id"] in spec["condition_ids"]
        )
        state = (
            "insufficient_data"
            if (soft and not known_soft) or (not ids and (baseline["unknown"] or not universe))
            else "measured"
        )
        if soft:
            insight = f"{spec['label']}: tập đủ hard giữ {baseline['eligible']} tour; nhóm đầu {'thay đổi' if top_changed else 'giữ nguyên'} theo policy."
            if not known_soft:
                insight = f"{spec['label']}: chưa đủ dữ liệu để đo ảnh hưởng của ưu tiên này."
        else:
            insight = f"{spec['label']}: số tour đạt các điều kiện còn lại {baseline['eligible']} → {denominator}; thêm {len(proven)} tour đã bị yêu cầu gốc loại có bằng chứng."
            if uncertain:
                insight += f" {len(uncertain)} tour thêm vào có trạng thái yêu cầu gốc chưa xác minh."
            if state == "insufficient_data":
                insight += " Chưa đủ dữ liệu để kết luận mức hạn chế lựa chọn."
        tradeoffs = [
            dict(
                condition_id=cid,
                before=next(c for c in r.conditions if c.id == cid).model_dump(
                    mode="json", exclude={"sources"}
                ),
                after=next(
                    (
                        c.model_dump(mode="json", exclude={"sources"})
                        for c in spec["replacements"]
                        if c.id == cid
                    ),
                    None,
                ),
            )
            for cid in spec["condition_ids"]
        ]
        scenarios.append(
            dict(
                **{k: spec[k] for k in ("id", "kind", "group_ids", "condition_ids", "label", "edits")},
                state=state,
                population=population(changed, records),
                additional_candidate_ids=ids,
                proven_blocked_candidate_ids=proven,
                previously_unknown_candidate_ids=uncertain,
                joint_only_candidate_ids=spec.get("joint_only_candidate_ids", []),
                restriction_ratio=ratio,
                top_before=before[:3],
                top_after=after[:3],
                top_changed=top_changed,
                rank_changes=changes[:10],
                rank_changes_truncated=len(changes) > 10,
                witnesses=witnesses,
                witnesses_truncated=len(ids) > 3,
                tradeoffs=tradeoffs,
                minimal_within_tested_subsets=spec["kind"] == "remove_hard_pair",
                limitations=[
                    "Kịch bản giả định; cần review proposal trước khi đổi nhu cầu.",
                    "Thứ tự theo policy bảo thủ; ties/khoảng chồng nhau không chứng minh ưu thế.",
                    "Bỏ field core có thể tạo proposal cần bổ sung; không tự bỏ business gate.",
                ],
                insight=insight,
            )
        )
    fingerprint = digest(crawl.model_dump(mode="json"), "snapshot_")
    return WhatIfAnalysis.model_validate(
        dict(
            id=aid,
            comparison_id=cid,
            requirement_id=r.id,
            revision=r.revision,
            origin=crawl.origin,
            evaluated_at=at,
            scope=dict(
                baseline="recomputed_on_analysis_snapshot",
                snapshot_id=fingerprint,
                ranking_policy=RANK_POLICY,
                catalog_validation_policy="catalog-validation-v1",
                candidate_count=len(universe),
                exclusions=list(exclusions),
                retrieval=crawl.retrieval,
                source_coverage=[s.model_dump(mode="json") for s in crawl.source_results],
                offer_coverage=crawl.offer_coverage,
                all_offers_complete=all(c["offers_complete"] for c in universe),
                condition_diagnostics=[
                    dict(
                        condition_id=condition.id,
                        field=condition.field,
                        strength=condition.strength,
                        counts=dict(
                            Counter(
                                e["status"]
                                for c in universe
                                for e in c["evaluations"]
                                if e["condition_id"] == condition.id
                            )
                        ),
                        unknown_reason_counts=dict(
                            Counter(
                                e["reason_code"] or "UNKNOWN"
                                for c in universe
                                for e in c["evaluations"]
                                if e["condition_id"] == condition.id and e["status"] == "unknown"
                            )
                        ),
                        aggregation="candidate_condition_summary_not_full_tree_eligibility",
                        offer_counts=dict(
                            Counter(
                                e["status"]
                                for c in universe
                                for a in c["offer_assessments"]
                                for e in a["evaluations"]
                                if e["condition_id"] == condition.id
                            )
                        ),
                        offer_unknown_reason_counts=dict(
                            Counter(
                                e["reason_code"] or "UNKNOWN"
                                for c in universe
                                for a in c["offer_assessments"]
                                for e in a["evaluations"]
                                if e["condition_id"] == condition.id and e["status"] == "unknown"
                            )
                        ),
                    )
                    for condition in r.conditions
                ],
            ),
            baseline=baseline,
            baseline_top=before[:3],
            groups=groups,
            scenarios=scenarios,
            candidates=[
                dict(
                    candidate_id=c["id"],
                    title=c["tour"].title,
                    canonical_url=c["tour"].canonical_url,
                    tour_snapshot_id=c["tour"].snapshot_id,
                    hard_status=c["hard_status"],
                    eligible_offer_snapshot_ids=c["eligible_offer_snapshot_ids"],
                )
                for c in universe
            ],
            semantic_assessment=semantic_report or dict(state="skipped", items=[]),
            explanation=dict(state="pending", insight_ids=[], text=[]),
            limits=limits,
            limitations=[
                "Phân tích trên snapshot mới; baseline không lấy từ pool của comparison cũ.",
                "Số lượng/% chỉ áp dụng cho universe đã đọc; không đại diện toàn thị trường.",
                "Tỷ lệ hạn chế lựa chọn không là trọng số, contribution% tổng điểm hoặc xác suất nhân quả.",
                "Không tự giảm số người, đổi giá/ngày, nâng verification hoặc coi unknown là fail.",
                "Giới hạn nới giá/ngày là budget tìm kịch bản, không là sự đồng ý của người dùng.",
            ],
        )
    )
