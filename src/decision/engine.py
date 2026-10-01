from decimal import Decimal
from itertools import combinations

from domain.common import AppError, instant
from domain.crawl import CrawlResult, Fact, OfferSnapshot, SourceCapability, money_wire
from domain.requirements import (
    Budget,
    Condition,
    DateValue,
    NumberValue,
    Requirement,
    SetValue,
    Tree,
    UnresolvedValue,
)
from requirements.normalize import PLACE_PARENTS

POLICY_VERSION = "decision-v1"
VOLATILE = {"departure_date", "return_date", "availability", "price"}


def freshness(fact: Fact, field: str, source: SourceCapability | None, evaluated_at: str) -> str:
    age = (instant(evaluated_at) - instant(fact.observed_at)).total_seconds()
    if age < -300:
        return "unknown"
    ttl = source.freshness_seconds.get(field) if source else None
    if ttl is None:
        return "unknown"
    return "fresh" if age <= ttl else "stale"


def usable(fact: Fact | None, field: str, source, at, synthetic=False) -> tuple[bool, str]:
    if fact is None:
        return False, "FIELD_MISSING"
    if fact.data_state != "present":
        return False, f"FIELD_{fact.data_state.upper()}"
    if fact.verification == "unverified" and not synthetic:
        return False, "FIELD_UNVERIFIED"
    if field in VOLATILE and freshness(fact, field, source, at) != "fresh":
        return False, "FIELD_STALE_OR_FRESHNESS_UNKNOWN"
    return True, "OK"


def applicable(conditions, party):
    for condition in conditions:
        if condition.field == "unresolved":
            return False
        actual = {"adults": party.adults, "children_count": len(party.children), "rooming": party.rooming}.get(condition.field)
        if actual is None or actual != condition.value:
            return False
    return True


def estimate_cost(budget: Budget, party, offer: OfferSnapshot | None, source, at, synthetic=False) -> dict:
    result = {"lower": None, "upper": None, "currency": budget.currency, "basis": budget.basis,
              "coverage": budget.coverage, "evidence_ids": [], "reasons": [], "components": []}

    def unknown(reason):
        result["reasons"].append(reason)
        return result

    if not budget.currency or not budget.basis:
        return unknown("BUDGET_UNRESOLVED")
    if not offer:
        return unknown("OFFER_REQUIRED")
    ok, reason = usable(offer.pricing_complete, "price", source, at, synthetic)
    if not ok or offer.pricing_complete.value is not True:
        return unknown("PRICE_COVERAGE_UNCONFIRMED")
    result["evidence_ids"].extend(offer.pricing_complete.evidence_ids)
    if budget.basis in {"group_total", "per_person"} and party.adults is None:
        return unknown("PARTY_REQUIRED")
    if budget.basis == "per_person" and party.children:
        return unknown("PER_PERSON_PRICE_AMBIGUOUS")
    quotes = []
    for fact in offer.price_quotes:
        ok, _ = usable(fact, "price", source, at, synthetic)
        if ok and fact.value.currency == budget.currency and fact.value.coverage == budget.coverage:
            if applicable(fact.value.applicability, party):
                quotes.append(fact)
    counts = [("per_adult", 1, None)]
    group_quotes = [f for f in quotes if f.value.basis == "per_group"]
    if budget.basis == "group_total":
        if group_quotes:
            counts = [("per_group", 1, None)]
        else:
            if any(child.age is None for child in party.children):
                return unknown("CHILD_AGE_REQUIRED")
            counts = [("per_adult", party.adults, None)] + [("child", 1, child.age) for child in party.children]
    lower, upper = Decimal(0), Decimal(0)
    for basis, count, age in counts:
        matches = [f for f in quotes if (f.value.basis == basis if basis != "child" else (
            f.value.basis in {"per_child", "per_infant"} and f.value.age_min is not None
            and f.value.age_min <= age < f.value.age_max_exclusive))]
        if len(matches) != 1:
            return unknown("PRICE_MISSING_OR_AMBIGUOUS")
        fact = matches[0]
        quote = fact.value
        lo = Decimal(quote.amount) * count
        hi = None if quote.kind == "from" else Decimal(quote.upper_amount if quote.kind == "range" else quote.amount) * count
        lower += lo
        upper = upper + hi if upper is not None and hi is not None else None
        result["components"].append({"quote_id": quote.quote_id, "count": count,
                                      "lower": money_wire(lo, budget.currency), "upper": money_wire(hi, budget.currency)})
        result["evidence_ids"].extend(fact.evidence_ids)
    for fact in offer.extra_charges:
        ok, _ = usable(fact, "price", source, at, synthetic)
        if not ok:
            return unknown("CHARGE_UNKNOWN")
        charge = fact.value
        if charge.required is False:
            continue
        if charge.required is None or charge.currency != budget.currency or not applicable(charge.applicability, party):
            return unknown("CHARGE_APPLICABILITY_UNKNOWN")
        if budget.basis == "group_total":
            count = {"per_adult": party.adults, "per_child": len(party.children),
                     "per_person": party.adults + len(party.children), "per_group": 1}.get(charge.basis)
        else:
            count = 1 if charge.basis in {"per_adult", "per_person"} else None
        if count is None:
            return unknown("CHARGE_ALLOCATION_UNKNOWN")
        amount = Decimal(charge.amount) * count
        lower += amount
        upper = upper + amount if upper is not None else None
        result["components"].append({"charge_id": charge.charge_id, "count": count, "amount": money_wire(amount, budget.currency)})
        result["evidence_ids"].extend(fact.evidence_ids)
    result.update(lower=money_wire(lower, budget.currency), upper=money_wire(upper, budget.currency),
                  evidence_ids=list(dict.fromkeys(result["evidence_ids"])))
    return result


def compare_interval(operator: str, lo, hi, target, target_hi=None) -> str:
    if lo is None:
        return "unknown"
    if operator == "lte":
        return "pass" if hi is not None and hi <= target else "fail" if lo > target else "unknown"
    if operator == "lt":
        return "pass" if hi is not None and hi < target else "fail" if lo >= target else "unknown"
    if operator == "gte":
        return "pass" if lo >= target else "fail" if hi is not None and hi < target else "unknown"
    if operator == "gt":
        return "pass" if lo > target else "fail" if hi is not None and hi <= target else "unknown"
    if operator in {"eq", "between"}:
        end = target if operator == "eq" else target_hi
        if hi is not None and target <= lo and hi <= end:
            return "pass"
        if lo > end or (hi is not None and hi < target):
            return "fail"
    return "unknown"


def expand_places(items):
    expanded = set(items)
    for item in list(expanded):
        while item in PLACE_PARENTS:
            item = PLACE_PARENTS[item]
            expanded.add(item)
    return expanded


def evaluate(c: Condition, tour, offer, party, source, at, synthetic=False, offer_reason=None) -> dict:
    out = {"condition_id": c.id, "field": c.field, "strength": c.strength, "status": "unknown",
           "actual": None, "reason_code": "FIELD_MISSING", "evidence_ids": [], "data_quality": {}}
    if isinstance(c.value, UnresolvedValue):
        out["reason_code"] = c.value.reason
        return out
    if isinstance(c.value, Budget):
        cost = estimate_cost(c.value, party, offer, source, at, synthetic)
        out.update(actual=cost, evidence_ids=cost["evidence_ids"], reason_code=offer_reason or (cost["reasons"][0] if cost["reasons"] else "BUDGET_BOUNDS"))
        lo = Decimal(cost["lower"]) if cost["lower"] is not None else None
        hi = Decimal(cost["upper"]) if cost["upper"] is not None else None
        out["status"] = compare_interval(c.operator, lo, hi, Decimal(c.value.amount),
                                           Decimal(c.value.upper) if c.value.upper is not None else None)
        return out
    fact = (offer.fields.get(c.field) if offer else None) if c.field in {"departure_date", "return_date"} else tour.fields.get(c.field)
    ok, reason = usable(fact, c.field, source, at, synthetic)
    out["reason_code"] = offer_reason if fact is None and offer_reason and c.field in VOLATILE else reason
    if fact:
        out.update(actual=fact.value, evidence_ids=fact.evidence_ids,
                   data_quality={"state": fact.data_state, "verification": fact.verification,
                                 "completeness": fact.completeness, "freshness": freshness(fact, c.field, source, at)})
    if not ok:
        return out
    actual = fact.value
    if isinstance(c.value, SetValue):
        found = set(actual if isinstance(actual, list) else [actual])
        if c.field == "destinations":
            found = expand_places(found)
        wanted = set(c.value.items)
        if c.operator in {"contains", "contains_all"}:
            state = "pass" if wanted <= found else "fail" if fact.completeness == "complete" else "unknown"
        elif c.operator in {"contains_any", "in"}:
            state = "pass" if wanted & found else "fail" if fact.completeness == "complete" else "unknown"
        else:
            state = "fail" if wanted & found else "pass" if fact.completeness == "complete" else "unknown"
    else:
        # A minimum/all-stops claim requires coverage of the whole itinerary.
        if fact.completeness != "complete":
            out["reason_code"] = "FIELD_SCOPE_INCOMPLETE"
            return out
        target = c.value.value if isinstance(c.value, DateValue) else c.value.amount
        state = compare_interval(c.operator, actual, actual, target, c.value.upper)
    out.update(status=state, reason_code="PREFERENCE_VALUE" if c.operator in {"near", "prefer_low", "prefer_high"} else "CONDITION_EVALUATED")
    return out


def fold_tree(tree: Tree, values: dict[str, str]) -> str:
    if tree.kind == "predicate":
        return values.get(tree.condition_id, "unknown")
    states = [fold_tree(c, values) for c in tree.children]
    if tree.kind == "all":
        return "fail" if "fail" in states else "pass" if all(s == "pass" for s in states) else "unknown"
    return "pass" if "pass" in states else "fail" if all(s == "fail" for s in states) else "unknown"


def compare(r: Requirement, crawl: CrawlResult, registry: list[SourceCapability], evaluated_at: str,
            offer_selections: list[dict] | None = None) -> dict:
    sources = {s.source_id: s for s in registry}
    selection = {s["target_id"]: s["offer_snapshot_id"] for s in offer_selections or []}
    if len(selection) != len(offer_selections or []) or set(selection) - {t.target_id for t in r.targets}:
        raise AppError("OFFER_SELECTION_INVALID", "Target lựa chọn offer không hợp lệ.", 409)
    if r.mode != "compare_urls" and selection:
        raise AppError("OFFER_SELECTION_INVALID", "Discovery không chọn offer theo target.", 409)
    candidates, targets = [], []
    synthetic = crawl.origin == "synthetic"
    filter_applied = any(c.strength != "soft" for c in r.conditions)
    tours = {t.snapshot_id: t for t in crawl.tours}
    offers = {o.snapshot_id: o for o in crawl.offers}

    def candidate(tour, offer, source, target_id=None, reason=None):
        evaluations = [evaluate(c, tour, offer, r.party, source, evaluated_at, synthetic, reason) for c in r.conditions]
        status = fold_tree(r.hard_tree, {e["condition_id"]: e["status"] for e in evaluations})
        if not r.readiness.can_evaluate_hard_constraints and status == "pass":
            status = "unknown"
        eligibility = {"pass": "eligible", "fail": "ineligible", "unknown": "needs_verification"}[status] if filter_applied else None
        cid = f"{target_id or 'discover'}:{tour.snapshot_id}:{offer.snapshot_id if offer else 'static'}"
        candidates.append({"id": cid, "target_id": target_id, "tour_snapshot_id": tour.snapshot_id,
                           "offer_snapshot_id": offer.snapshot_id if offer else None,
                           "assessment_level": "offer_specific" if offer else "tour_only", "eligibility": eligibility,
                           "evaluations": evaluations, "fields": {k: v.model_dump() for k, v in tour.fields.items()},
                           "offer_fields": {k: v.model_dump() for k, v in offer.fields.items()} if offer else {},
                           "offer_reason": reason})
        return cid

    entries = [(t, next((s for s in crawl.source_results if s.target_id == t.target_id), None)) for t in r.targets] if r.mode == "compare_urls" else [(None, s) for s in crawl.source_results]
    for target, sr in entries:
        options, ids = [], []
        if sr:
            source = sources.get(sr.source_id)
            for tid in sr.tour_snapshot_ids:
                tour = tours[tid]
                tour_offers = [offers[x] for x in sr.offer_snapshot_ids if offers[x].tour_snapshot_id == tid]
                options.extend({"offer_snapshot_id": o.snapshot_id, "offer_id": o.offer_id,
                                "fields": {k: v.model_dump() for k, v in o.fields.items()}} for o in tour_offers)
                if target:
                    chosen = selection.get(target.target_id)
                    if chosen:
                        selected = next((o for o in tour_offers if o.snapshot_id == chosen), None)
                        if selected is None:
                            raise AppError("OFFER_SELECTION_INVALID", "Offer không thuộc tour/target đã chọn.", 409)
                        for field in selected.fields.values():
                            if freshness(field, "departure_date", source, evaluated_at) != "fresh":
                                raise AppError("OFFER_SELECTION_INVALID", "Offer đã cũ; cần thu thập lại.", 409)
                    elif len(tour_offers) == 1:
                        selected = tour_offers[0]
                    else:
                        selected = None
                    reason = "MULTIPLE_OFFERS_UNSELECTED" if len(tour_offers) > 1 and selected is None else "OFFER_MISSING" if selected is None else None
                    ids.append(candidate(tour, selected, source, target.target_id, reason))
                else:
                    for offer in tour_offers or [None]:
                        ids.append(candidate(tour, offer, source))
        if target:
            if target.target_id in selection and not ids:
                raise AppError("OFFER_SELECTION_INVALID", "Target không có offer để chọn.", 409)
            targets.append({**target.model_dump(), "status": sr.status if sr else "error",
                            "reason_code": sr.reason_code if sr else "TARGET_RESULT_MISSING",
                            "candidate_ids": ids, "offer_options": options})
    groups = {k: [c["id"] for c in candidates if c["eligibility"] == k] for k in ("eligible", "ineligible", "needs_verification")}
    trade_offs = []
    for condition in r.conditions:
        if condition.strength != "soft" or not isinstance(condition.value, NumberValue):
            continue
        if condition.operator not in {"prefer_low", "prefer_high", "gte", "near"}:
            continue
        comparable = []
        for c in candidates:
            e = next(x for x in c["evaluations"] if x["condition_id"] == condition.id)
            if type(e["actual"]) is int and e["reason_code"] in {"CONDITION_EVALUATED", "PREFERENCE_VALUE"}:
                comparable.append((c["id"], e))
        for (aid, a), (bid, b) in list(combinations(comparable, 2))[:100]:
            if a["actual"] == b["actual"]:
                continue
            trade_offs.append({"condition_id": condition.id, "candidate_a": aid, "candidate_b": bid,
                               "field": condition.field, "value_a": a["actual"], "value_b": b["actual"],
                               "claim": f"{condition.field}: {a['actual']} so với {b['actual']}.",
                               "evidence_ids": list(dict.fromkeys(a["evidence_ids"] + b["evidence_ids"]))})
    failures = [s for s in crawl.source_results if s.status in {"error", "timeout"}]
    if not candidates:
        empty = "SOURCES_UNAVAILABLE" if failures else "NO_SUPPORTED_TARGETS" if not any(s.status in {"ok", "partial"} for s in crawl.source_results) else "NO_CANDIDATES"
    elif filter_applied and not groups["eligible"]:
        empty = "ONLY_UNVERIFIED" if groups["needs_verification"] else "ALL_INELIGIBLE"
    else:
        empty = None
    return {"schema_version": "1.0", "policy_version": POLICY_VERSION, "requirement_id": r.id,
            "revision": r.revision, "evaluated_at": evaluated_at, "origin": crawl.origin,
            "targets": targets, "candidates": candidates, "groups": groups,
            "filter_applied": filter_applied, "decision_blockers": r.readiness.reasons,
            "criteria": [c.model_dump() for c in r.conditions], "trade_offs": trade_offs,
            "evidence_refs": [e.id for e in crawl.evidence],
            "source_coverage": [s.model_dump() for s in crawl.source_results],
            "warnings": [i.model_dump() for i in crawl.issues], "empty_reason": empty}
