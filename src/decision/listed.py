"""Listed offer amounts are a separate measure, never a payable upper bound."""

from decimal import Decimal

from decision.engine import applicable, usable
from domain.crawl import money_wire


def listed_price(budget, party, offer, source, at, synthetic=False):
    result = dict(
        lower=None,
        upper=None,
        currency=budget.currency,
        basis=budget.basis,
        coverage=budget.coverage,
        measure="listed",
        price_kind=None,
        payable_upper=None,
        evidence_ids=[],
        reasons=[],
        components=[],
        warnings=["PAYABLE_TOTAL_UNCONFIRMED"],
    )

    def unknown(reason):
        result["reasons"].append(reason)
        return result

    if not offer:
        return unknown("OFFER_REQUIRED")
    if budget.basis not in {"per_adult", "per_person"}:
        return unknown("LISTED_PRICE_BASIS_UNSUPPORTED")
    if budget.basis == "per_person" and party.children:
        return unknown("PER_PERSON_PRICE_AMBIGUOUS")
    if not budget.currency:
        return unknown("BUDGET_UNRESOLVED")
    facts = getattr(offer, "listed_price_quotes", []) or offer.price_quotes
    matches, reasons = [], []
    for fact in facts:
        ok, reason = usable(fact, "price", source, at, synthetic)
        if not ok:
            reasons.append(reason)
            continue
        q = fact.value
        if q.basis != "per_adult" or q.currency != budget.currency or q.coverage != "tour_price":
            continue
        if q.kind not in {"from", "exact"} or not applicable(q.applicability, party):
            continue
        matches.append(fact)
    if len(matches) != 1:
        return unknown(reasons[0] if not matches and reasons else "LISTED_PRICE_MISSING_OR_AMBIGUOUS")
    fact = matches[0]
    q = fact.value
    amount = money_wire(Decimal(q.amount), q.currency)
    result.update(
        lower=amount,
        upper=amount,
        price_kind=q.kind,
        evidence_ids=fact.evidence_ids,
        components=[dict(quote_id=q.quote_id, amount=amount, kind=q.kind, measure="listed")],
    )
    return result


def cost_disclosure(candidate, at, synthetic=False):
    """Keep published terms with their citations; never infer a surcharge amount."""
    source = candidate["item"]["source"]
    tour = candidate["tour"]
    policies = []
    for name in ("inclusions", "exclusions", "surcharges", "child_policy"):
        fact = tour.policies.get(name)
        if fact is not None:
            ok, reason = usable(fact, name, source, at, synthetic)
            policies.append(
                dict(
                    field=name, text=fact.value, evidence_ids=fact.evidence_ids, usable=ok, reason_code=reason
                )
            )
    options = []
    for offer in candidate["options"]:
        facts = getattr(offer, "listed_price_quotes", [])
        quotes = []
        for fact in facts:
            ok, reason = usable(fact, "price", source, at, synthetic)
            quotes.append(
                dict(
                    value=fact.value.model_dump(mode="json") if fact.value else None,
                    usable=ok,
                    reason_code=reason,
                    evidence_ids=fact.evidence_ids,
                )
            )
        options.append(
            dict(
                offer_snapshot_id=offer.snapshot_id,
                listed_quotes=quotes,
                extra_charges=[f.model_dump(mode="json") for f in offer.extra_charges],
                pricing_complete=offer.pricing_complete.model_dump(mode="json")
                if offer.pricing_complete
                else None,
                payable_total_status="not_calculated",
            )
        )
    return dict(
        candidate_id=candidate["id"], policies=policies, offers=options, warning="PAYABLE_TOTAL_UNCONFIRMED"
    )
