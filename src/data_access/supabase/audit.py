"""Bounded, read-only quality audit through the production catalog adapter."""

from collections import Counter
from datetime import timedelta

from domain.common import now, uid
from domain.crawl import CrawlRequest
from domain.requirements import QuerySpec, RequirementState

FIELDS = {
    "tour.departure_origin": ("tours", "fields", "departure_origin"),
    "tour.destinations": ("tours", "fields", "destinations"),
    "tour.transport": ("tours", "fields", "transport"),
    "tour.duration_days": ("tours", "fields", "duration_days"),
    "tour.itinerary": ("tours", "catalog_fields", "itinerary"),
    "tour.route": ("tours", "semantic_fields", "route"),
    "offer.departure_date": ("offers", "fields", "departure_date"),
    "offer.return_date": ("offers", "fields", "return_date"),
    "offer.availability_capacity": ("offers", "fields", "availability"),
}


def summarize(crawl, registry=()):
    fields = {}
    for label, (collection, group, name) in FIELDS.items():
        snapshots = getattr(crawl, collection)
        facts = [getattr(s, group).get(name) for s in snapshots]
        fields[label] = {
            "sample_size": len(snapshots),
            "states": dict(Counter(f.data_state if f else "missing" for f in facts)),
            "verification": dict(Counter(f.verification for f in facts if f)),
            "complete_facts": sum(f is not None and f.completeness == "complete" for f in facts),
        }
    quotes = [q for o in crawl.offers for q in o.price_quotes]
    return {
        "policy_version": "catalog-quality-audit-v2",
        "catalog_policy": "catalog-validation-v1",
        "trusted_sources": [s.source_id for s in registry if s.limits.get("catalog_validated") == 1],
        "evaluated_at": now().isoformat(),
        "sample": {"tours": len(crawl.tours), "offers": len(crawl.offers), "price_quotes": len(quotes)},
        "retrieval": crawl.retrieval,
        "offer_coverage": {
            "complete_tours": sum(crawl.offer_coverage.values()),
            "incomplete_tours": sum(not v for v in crawl.offer_coverage.values()),
        },
        "fields": fields,
        "prices": {
            "verification": dict(Counter(q.verification for q in quotes)),
            "kinds": dict(Counter(q.value.kind for q in quotes if q.value)),
            "coverage": dict(Counter(q.value.coverage for q in quotes if q.value)),
            "missing_quotes": sum(not o.price_quotes for o in crawl.offers),
            "pricing_complete": sum(
                o.pricing_complete is not None and o.pricing_complete.value is True for o in crawl.offers
            ),
            "unclassified_age_price_records": sum(
                "unclassified_prices" in o.catalog_fields for o in crawl.offers
            ),
        },
        "issue_counts": dict(Counter(i.code for i in crawl.issues)),
        "freshness": {
            "registry_origin": "catalog_bootstrap_only",
            "configured_volatile_ttls": {
                s.source_id: s.freshness_seconds for s in registry if s.freshness_seconds
            },
            "required_for_fields": ["price", "departure_date", "return_date", "availability"],
        },
        "adapter_limitations": [
            "Qualified price coverage/applicability is not imported from catalog evidence yet.",
            "Child price amounts without age brackets cannot price the group.",
            "Return date, tour type and numeric seat capacity are not inferred from other columns.",
        ],
        "limitations": [
            "Counts describe the bounded normalized sample, not every database record.",
            "Scan/pool/offer truncation and quarantined records may hide additional quality gaps.",
            "Supplier proof is not independent verification; freshness is a separate prerequisite.",
            "Catalog validation checks imported data; it does not independently verify supplier claims.",
            "Audit bootstrap TTLs do not describe the application's persisted source registry.",
        ],
    }


async def audit_catalog(repository, settings, *, candidate_limit=100):
    registry = repository.registry()
    inventory = RequirementState(id="catalog_inventory", revision=1, mode="discover")
    request = CrawlRequest(
        request_id=uid("audit"),
        mode="discover",
        source_ids=[s.source_id for s in registry],
        query=QuerySpec.from_requirement(inventory),
        targets=[],
        deadline_at=(now() + timedelta(seconds=settings.job_timeout_seconds)).isoformat(),
    )
    crawl = await repository.collect(request, candidate_limit=candidate_limit, registry=registry)
    return summarize(crawl, registry)
