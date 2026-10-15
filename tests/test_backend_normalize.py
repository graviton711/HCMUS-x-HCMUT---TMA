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
    assert not hasattr(tour, "destination_countries")
    assert not hasattr(tour, "destination_country_complete")


def test_origin_endpoint_with_different_label_is_not_removed_by_alias():
    row = TourRow(
        tour={
            "record_key": "origin-only",
            "departure_city": "Sài Gòn",
            "destinations": ["TP.HCM"],
        },
    )
    tour = rows_to_snapshots([row])[0]
    assert tour.destinations == ["TP.HCM"]
    assert not hasattr(tour, "destination_country_complete")


def test_origin_endpoint_alias_is_not_removed_without_an_alias_registry():
    row = TourRow(
        tour={
            "record_key": "origin-alias",
            "departure_city": "TP.HCM",
            "destinations": ["Sài Gòn", "Đà Lạt"],
        },
    )
    tour = rows_to_snapshots([row])[0]
    assert tour.destinations == ["Sài Gòn", "Đà Lạt"]


def test_offer_price_basis_is_not_inherited_from_tour_or_metadata():
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
                                "kind": "from",
                                "amount": 99_000_000,
                                "currency": "USD",
                                "basis": "per_group",
                                "coverage": "trip_total",
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
    offer = rows_to_snapshots([row])[0].offers[0]
    assert offer.price == 10_000_000
    assert offer.price_basis == "unknown"
    assert offer.pricing_complete is False
    assert offer.price_quotes[0]["amount"] == 99_000_000


def test_optional_quote_metadata_never_changes_canonical_from_price():
    row = TourRow(
        tour={"record_key": "from", "url": "https://trusted.example.test/tour", "price_type": "from", "currency": "VND"},
        offers=[{
            "record_key": "from-offer",
            "price": 10_000_000,
            "price_type": "from",
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
    offer = rows_to_snapshots([row])[0].offers[0]
    assert offer.price == 10_000_000
    assert offer.price_basis == "from"


def test_offer_age_prices_and_supplements_are_preserved():
    row = TourRow(
        tour={"record_key": "age-prices", "price_type": "fixed", "currency": "VND"},
        offers=[{
            "record_key": "age-offer",
            "price": 2_000_000,
            "price_type": "fixed",
            "price_by_age": {"adult": 2_000_000, "child": 1_000_000, "infant": None},
            "single_supplement": 500_000,
            "supplements": "Lễ Tết: 300.000đ/khách",
        }],
    )

    offer = rows_to_snapshots([row])[0].offers[0]
    assert offer.price_by_age == {"adult": 2_000_000, "child": 1_000_000, "infant": None}
    assert offer.single_supplement == 500_000
    assert offer.supplements == "Lễ Tết: 300.000đ/khách"


def test_stale_departure_date_is_retained_without_price_freshness_state():
    row = TourRow(
        tour={"record_key": "old", "departure_city": "Sài Gòn", "destinations": ["Đà Lạt"]},
        offers=[{"record_key": "old-offer", "price": 1_000_000,
                 "price_type": "fixed", "departure_date": "2026-10-11",
                 "observed_at": "2026-10-01T00:00:00+00:00"}],
    )
    later = datetime.fromisoformat("2026-10-10T00:00:00+00:00")
    offer = rows_to_snapshots([row], now=later)[0].offers[0]
    assert offer.departure_freshness == "stale"
    assert not hasattr(offer, "price_freshness")
