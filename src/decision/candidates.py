"""Pure per-offer eligibility. Never combine constraints from different offers."""

import hashlib
import json

from decision.engine import fold_tree, freshness
from decision.semantic import evaluate
from domain.common import AppError


def tour_identity(tour):
    return "tour_" + hashlib.sha256(json.dumps([tour.supplier_id, tour.tour_id]).encode()).hexdigest()[:32]


def hard_status(r, evaluations):
    if not any(c.strength != "soft" for c in r.conditions):
        return None
    return fold_tree(r.hard_tree, {e["condition_id"]: e["status"] for e in evaluations})


def assess_options(
    r, tour, options, source, at, synthetic=False, *, selected_id=None, complete=True, evaluation_cache=None
):
    key = tour_identity(tour)

    def evaluations(offer, reason=None, *, per_offer=False):
        def cached(condition):
            # Cache lifetime is one immutable universe/time. Object identities include condition/party changes.
            cache_key = (id(condition), id(tour), id(offer), id(r.party), id(source), at, synthetic, reason)
            if evaluation_cache is None:
                return evaluate(condition, tour, offer, r.party, source, at, synthetic, reason)
            if cache_key not in evaluation_cache:
                evaluation_cache[cache_key] = evaluate(
                    condition, tour, offer, r.party, source, at, synthetic, reason
                )
            return evaluation_cache[cache_key]

        return [
            dict(
                cached(c),
                id="eval_"
                + hashlib.sha256(
                    json.dumps([key, offer.snapshot_id if per_offer else "candidate", c.id]).encode()
                ).hexdigest()[:32],
                candidate_id=key,
                offer_snapshot_id=offer.snapshot_id if offer else None,
                expected=c.value.model_dump(mode="json"),
            )
            for c in r.conditions
        ]

    assessed = []
    for option in sorted(options, key=lambda o: o.snapshot_id):
        es = evaluations(option, per_offer=True)
        status = hard_status(r, es)
        if status == "pass" and not r.readiness.can_evaluate_hard_constraints:
            status = "unknown"
        assessed.append({"offer_snapshot_id": option.snapshot_id, "hard_status": status, "evaluations": es})
    passing = [a["offer_snapshot_id"] for a in assessed if a["hard_status"] == "pass"]
    selected = None
    if selected_id:
        selected = next((o for o in options if o.snapshot_id == selected_id), None)
        if selected is None or any(
            freshness(f, name, source, at) == "stale" for name, f in selected.fields.items()
        ):
            raise AppError("OFFER_SELECTION_INVALID", "Offer sai binding hoặc đã cũ.", 409)
    elif len(options) == 1 and complete:
        selected = options[0]
    elif len(passing) == 1 and complete:
        selected = next(o for o in options if o.snapshot_id == passing[0])
    reason = None if selected else "MULTIPLE_OFFERS_UNSELECTED" if options else "OFFER_MISSING"
    es = evaluations(selected, reason)
    status = hard_status(r, es)
    if not selected and assessed and status != "fail":
        statuses = [a["hard_status"] for a in assessed]
        status = (
            "pass"
            if passing
            else "fail"
            if complete and all(s == "fail" for s in statuses)
            else "unknown"
            if status is not None
            else None
        )
        # The whole tree above is folded per offer. Aggregate display predicates cannot establish eligibility.
        for e in es:
            if e["strength"] == "soft" or e["status"] != "unknown":
                continue
            parts = [p for a in assessed for p in a["evaluations"] if p["condition_id"] == e["condition_id"]]
            if parts and all(p["status"] == "pass" for p in parts):
                e.update(
                    status="pass",
                    actual=None,
                    reason_code="ALL_RETURNED_OFFERS_MATCH",
                    evidence_ids=sorted({eid for p in parts for eid in p["evidence_ids"]}),
                )
            elif complete and parts and all(p["status"] == "fail" for p in parts):
                e.update(
                    status="fail",
                    actual=None,
                    reason_code="ALL_OFFERS_FAIL",
                    evidence_ids=sorted({eid for p in parts for eid in p["evidence_ids"]}),
                )
    if status == "pass" and not r.readiness.can_evaluate_hard_constraints:
        status = "unknown"
    return dict(
        selected=selected,
        evaluations=es,
        hard_status=status,
        offer_reason=reason,
        offer_assessments=assessed,
        eligible_offer_snapshot_ids=passing,
        offers_complete=complete,
    )


def evaluate_candidates(r, crawl, registry, at, *, exclusions=(), selections=(), evaluation_cache=None):
    """Evaluate the whole acquired universe; no eligibility filtering or display limit."""
    sources = {s.source_id: s for s in registry}
    tours = {t.snapshot_id: t for t in crawl.tours}
    offers = {o.snapshot_id: o for o in crawl.offers}
    by_entity = {}
    for sr in crawl.source_results:
        for tid in sr.tour_snapshot_ids:
            tour = tours[tid]
            item = by_entity.setdefault(
                tour_identity(tour),
                dict(
                    tour=tour,
                    source_ids=set(),
                    target_ids=set(),
                    discovered=False,
                    offers={},
                    source=sources.get(sr.source_id),
                ),
            )
            item["source_ids"].add(sr.source_id)
            if sr.target_id:
                item["target_ids"].add(sr.target_id)
                item["tour"] = tour
            else:
                item["discovered"] = True
            for oid in sr.offer_snapshot_ids:
                if offers[oid].tour_snapshot_id == tid:
                    item["offers"][oid] = offers[oid]
    selection = {s["tour_id"]: s["offer_snapshot_id"] for s in selections}
    if set(selection) - by_entity.keys():
        raise AppError("OFFER_SELECTION_INVALID", "Tour không thuộc kết quả đã thu thập.", 409)
    evaluated = []
    for key, item in sorted(by_entity.items()):
        if key in exclusions and not item["target_ids"]:
            continue
        tour = item["tour"]
        options = [o for o in item["offers"].values() if o.tour_snapshot_id == tour.snapshot_id]
        complete = getattr(crawl, "offer_coverage", {}).get(
            tour.snapshot_id,
            not any(s.truncated for s in crawl.source_results if tour.snapshot_id in s.tour_snapshot_ids),
        )
        assessed = assess_options(
            r,
            tour,
            options,
            item["source"],
            at,
            crawl.origin == "synthetic",
            selected_id=selection.get(key),
            complete=complete,
            evaluation_cache=evaluation_cache,
        )
        evaluated.append(dict(id=key, item=item, tour=tour, options=options, **assessed))
    return evaluated


def prepare_candidates(r, crawl, registry, at, *, exclusions=(), selections=(), candidate_limit=20):
    evaluated = evaluate_candidates(r, crawl, registry, at, exclusions=exclusions, selections=selections)
    discovery = [
        c
        for c in evaluated
        if c["item"]["discovered"] and c["hard_status"] != "fail" and c["id"] not in exclusions
    ]
    discovery.sort(key=lambda c: (0 if c["hard_status"] in {"pass", None} else 1, c["id"]))
    retained = {c["id"] for c in discovery[:candidate_limit]} | {
        c["id"] for c in evaluated if c["item"]["target_ids"]
    }
    return [c for c in evaluated if c["id"] in retained], len(discovery) > candidate_limit or any(
        s.truncated for s in crawl.source_results
    )


def refresh_candidates(r, prepared, at, *, synthetic=False, selections=()):
    """Recheck expiry without replacing the pool whose text the model has assessed."""
    selected = {s["tour_id"]: s["offer_snapshot_id"] for s in selections}
    refreshed = []
    for candidate in prepared[0]:
        updated = assess_options(
            r,
            candidate["tour"],
            candidate["options"],
            candidate["item"]["source"],
            at,
            synthetic,
            selected_id=selected.get(candidate["id"]),
            complete=candidate["offers_complete"],
        )
        refreshed.append({**candidate, **updated})
    return refreshed, prepared[1]
