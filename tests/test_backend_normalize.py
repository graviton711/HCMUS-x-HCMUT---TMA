"""Normalize: rows → snapshots. Mechanical mapping, unknown never invented."""

from backend.data.catalog import FixtureCatalog
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
