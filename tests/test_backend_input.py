"""Input: text/form → conditions. Offline, no NIM. Places come from the catalog."""

from backend.data.catalog import FixtureCatalog
from backend.input.pipeline import build_requirement, keyword_extract

PLACES = ["Đà Lạt", "Phú Quốc", "Hạ Long", "Sài Gòn", "Hà Nội"]


def test_keyword_extract_destination_and_departure():
    parsed = keyword_extract("Đà Lạt 3 ngày, đi từ Sài Gòn", known_places=PLACES)
    fields = {h["field"]: h["value"] for h in parsed["hard"]}
    assert fields["destination"] == "Đà Lạt"
    assert fields["departure_city"] == "Sài Gòn"


def test_keyword_extract_budget_near_keyword_only():
    parsed = keyword_extract("Đà Lạt 3 ngày, tối đa 8 triệu/người", known_places=PLACES)
    budget = next(h for h in parsed["hard"] if h["field"] == "budget_max")
    assert budget["value"] == 8_000_000


def test_keyword_extract_ignores_dates_as_budget():
    parsed = keyword_extract("Đi ngày 2026-12-25, Đà Lạt", known_places=PLACES)
    assert "budget_max" not in {h["field"] for h in parsed["hard"]}


def test_catalog_destinations_feed_fallback():
    places = FixtureCatalog().list_destinations()
    assert set(places) == {"Đà Lạt", "Phú Quốc", "Hạ Long"}
    parsed = keyword_extract("Tour Hạ Long 3 ngày", known_places=places)
    assert parsed["hard"][0] == {"field": "destination", "operator": "contains",
                                 "value": "Hạ Long"}


def test_form_wins_over_text():
    req = build_requirement("Phú Quốc 20 triệu", {"budget_max": 8_000_000},
                            known_places=PLACES)
    budgets = [c for c in req.conditions if c.field == "budget_max"]
    assert len(budgets) == 1
    assert budgets[0].value == 8_000_000


def test_missing_slots_reported_not_guessed():
    req = build_requirement("Đà Lạt", known_places=PLACES)
    assert "budget_max" in req.missing
    assert "date_from" in req.missing
    assert all(c.value not in (None, "") for c in req.conditions)


def test_keyword_extract_undiacritized():
    req = build_requirement("Da Lat 3 ngay, di tu Sai Gon, toi da 8 trieu/nguoi",
                            known_places=["Đà Lạt", "Sài Gòn"])
    fields = {c.field: c.value for c in req.conditions}
    assert fields["destination"] == "Đà Lạt"
    assert fields["departure_city"] == "Sài Gòn"
    assert fields["budget_max"] == 8_000_000


def test_condition_ids_unique():
    req = build_requirement("Đà Lạt 3 ngày, tối đa 8 triệu", known_places=PLACES)
    ids = [c.id for c in req.conditions]
    assert len(ids) == len(set(ids)) > 1


def test_form_only_requirement():
    req = build_requirement("", {"destinations": ["Đà Lạt"], "budget_max": 8_000_000,
                                 "departure_city": "Sài Gòn", "travelers": 2})
    assert req.travelers == 2
    assert "destination" not in req.missing
    assert "budget_max" not in req.missing
