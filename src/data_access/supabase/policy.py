"""Explicit trust for the team's catalog; never infer trust from a row label."""

from urllib.parse import urlsplit

from domain.crawl_v2 import CATALOG_CHECKS, CATALOG_POLICY

CATALOG_FIELDS = {
    "departure_city",
    "destinations",
    "duration_days",
    "duration_nights",
    "transport",
    "departure_date",
    "price_by_age.adult",
    "route",
    "itinerary",
    "inclusions",
    "exclusions",
    "cancellation_policy",
    "surcharges",
    "child_policy",
}
TEXT_FIELDS = {"itinerary", "inclusions", "exclusions", "cancellation_policy", "surcharges", "child_policy"}


def trusted_source(source, provider, url, domains):
    host = (urlsplit(url).hostname or "").lower()
    provider_host = (urlsplit(provider["website"]).hostname or "").lower()
    return bool(
        source is not None
        and source.source_id == "catalog_" + provider["source_key"].strip()
        and source.supplier_id == "supplier_" + provider["source_key"].strip()
        and source.access_status == "approved"
        and source.limits.get("catalog_read_only") == 1
        and source.limits.get("catalog_validated") == 1
        and host == provider_host
        and host in domains
        and host in source.approved_domains
    )


def receipt(source):
    return {"policy_version": CATALOG_POLICY, "source_id": source.source_id, "checks": sorted(CATALOG_CHECKS)}
