"""Normalize: rows → snapshots. Mechanical mapping, unknown never invented."""

from datetime import UTC, datetime

from backend.data.catalog import FixtureCatalog
from backend.models import TourRow
from backend.normalize.snapshots import rows_to_snapshots


def test_fixture_rows_normalize_to_snapshots():
    snapshots = rows_to_snapshots(FixtureCatalog().list_tours(10))
    assert len(snapshots) == 3
    dalat = next(t for t in snapshots if t.id == "dlv-dalat-3n")
    assert dalat.destinations == ["Đà Lạt"]
    assert dalat.departure_city == "Sài Gòn"
    assert len(dalat.offers) == 2
    assert all(o.price_basis == "exact" for o in dalat.offers)
    assert all(o.price is not None for o in dalat.offers)


def test_from_price_never_exact():
    snapshots = rows_to_snapshots(FixtureCatalog().list_tours(10))
    halong = next(t for t in snapshots if t.id == "sgt-halong-3n")
    assert halong.offers[0].price_basis == "from"
    assert halong.offers[0].availability == "unknown"


def test_evidence_bound_to_snapshot():
    snapshots = rows_to_snapshots(FixtureCatalog().list_tours(10))
    for tour in snapshots:
        assert tour.evidence.record_ref == tour.id
        assert tour.observed_at != ""
        for offer in tour.offers:
            assert offer.tour_id == tour.id
            assert offer.evidence.record_ref == offer.id


def test_origin_endpoints_are_removed_only_from_visit_destinations():
    row = TourRow(
        tour={
            "record_key": "foreign",
            "url": "https://example.test/foreign",
            "departure_city": "TP.HCM",
            "destinations": ["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"],
            "route": ["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"],
        },
    )
    tour = rows_to_snapshots([row])[0]
    assert tour.destinations == ["Thượng Hải", "Hàng Châu"]
    assert tour.raw_destinations == ["TP.HCM", "Thượng Hải", "Hàng Châu", "TP.HCM"]
    assert tour.route == tour.raw_destinations
    assert tour.destination_countries == ["cn"]
    assert tour.destination_country_complete


def test_destination_list_with_origin_only_becomes_unknown_not_a_domestic_match():
    row = TourRow(
        tour={
            "record_key": "origin-only",
            "departure_city": "Sài Gòn",
            "destinations": ["TP.HCM"],
        },
    )
    tour = rows_to_snapshots([row])[0]
    assert tour.destinations == []
    assert not tour.destination_country_complete


def test_structured_pricing_metadata_requires_bound_fields_and_trusted_source():
    observed = datetime.now(UTC).isoformat()
    row = TourRow(
        tour={
            "record_key": "priced",
            "url": "https://trusted.example.test/tour",
            "price_type": "fixed",
            "currency": "VND",
        },
        offers=[
            {
                "record_key": "priced-offer",
                "price": 10_000_000,
                "observed_at": observed,
                "field_meta": {
                    "source_url": "https://trusted.example.test/tour",
                    "pricing": {
                        "observed_at": observed,
                        "quotes": [
                            {
                                "quote_id": "adult",
                                "kind": "exact",
                                "amount": 10_000_000,
                                "currency": "VND",
                                "basis": "per_adult",
                                "coverage": "tour_price",
                                "applicability": [],
                            }
                        ],
                        "extra_charges": [],
                        "complete": False,
                    },
                },
            }
        ],
    )
    offer = rows_to_snapshots([row], trusted_domains=["trusted.example.test"])[0].offers[0]
    assert offer.pricing_metadata_state == "validated"
    assert offer.price_trusted
    assert offer.pricing_complete is False
    assert offer.price_basis == "exact"
    assert offer.price_quotes[0]["amount"] == "10000000"

    untrusted = rows_to_snapshots([row])[0].offers[0]
    assert untrusted.pricing_metadata_state == "untrusted"

    live_without_policy = rows_to_snapshots([row], require_trusted_pricing=True)[0].offers[0]
    assert not live_without_policy.price_trusted


def test_bad_price_metadata_is_never_used_to_change_from_price():
    row = TourRow(
        tour={"record_key": "from", "url": "https://trusted.example.test/tour", "price_type": "from", "currency": "VND"},
        offers=[{
            "record_key": "from-offer",
            "price": 10_000_000,
            "observed_at": "2026-10-10T00:00:00+00:00",
            "field_meta": {"source_url": "https://trusted.example.test/tour", "pricing": {
                "observed_at": "2026-10-09T00:00:00+00:00",
                "quotes": [{"quote_id": "adult", "kind": "exact", "amount": 10_000_000,
                            "currency": "VND", "basis": "per_adult", "coverage": "tour_price",
                            "applicability": []}],
                "extra_charges": [], "complete": True,
            }},
        }],
    )
    offer = rows_to_snapshots([row], trusted_domains=["trusted.example.test"])[0].offers[0]
    assert offer.pricing_metadata_state == "invalid"
    assert offer.pricing_issue == "CATALOG_PRICING_METADATA_INVALID"
    assert offer.price_basis == "from"


def test_stale_offer_is_not_freshened_by_normalization():
    row = TourRow(
        tour={"record_key": "old", "departure_city": "Sài Gòn", "destinations": ["Đà Lạt"]},
        offers=[{"record_key": "old-offer", "price": 1_000_000,
                 "price_type": "fixed", "departure_date": "2026-10-11",
                 "observed_at": "2026-10-01T00:00:00+00:00"}],
    )
    later = datetime.fromisoformat("2026-10-10T00:00:00+00:00")
    offer = rows_to_snapshots([row], now=later)[0].offers[0]
    assert offer.price_freshness == "stale"
    assert offer.departure_freshness == "stale"
