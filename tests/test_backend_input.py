"""Input: text/form → conditions. Offline, no NIM. Places come from the catalog."""

import json

import httpx

from backend.data.catalog import FixtureCatalog
from backend.input.lunar import resolve_lunar as _resolve_lunar
from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement, keyword_extract
from backend.settings import PromptCfg

PLACES = ["Đà Lạt", "Phú Quốc", "Hạ Long", "Sài Gòn", "Hà Nội"]


def _mock_nim(payload: dict) -> NimClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    return NimClient("key", "model", 9.0,
                     prompt=PromptCfg(system="s", max_tokens=64, temperature=0, timeout_s=5),
                     transport=httpx.MockTransport(handler))


def test_keyword_extract_destination_and_departure(input_cfg):
    parsed = keyword_extract("Đà Lạt 3 ngày, đi từ Sài Gòn", input_cfg, known_places=PLACES)
    fields = {h["field"]: h["value"] for h in parsed["hard"]}
    assert fields["destination"] == "Đà Lạt"
    assert fields["departure_city"] == "Sài Gòn"


def test_keyword_extract_budget_near_keyword_only(input_cfg):
    parsed = keyword_extract("Đà Lạt 3 ngày, tối đa 8 triệu/người", input_cfg, known_places=PLACES)
    budget = next(h for h in parsed["hard"] if h["field"] == "budget_max")
    assert budget["value"] == 8_000_000


def test_keyword_extract_ignores_dates_as_budget(input_cfg):
    parsed = keyword_extract("Đi ngày 2026-12-25, Đà Lạt", input_cfg, known_places=PLACES)
    assert "budget_max" not in {h["field"] for h in parsed["hard"]}


def test_catalog_destinations_feed_fallback(input_cfg):
    places = FixtureCatalog().list_destinations()
    assert set(places) == {"Đà Lạt", "Phú Quốc", "Hạ Long"}
    parsed = keyword_extract("Tour Hạ Long 3 ngày", input_cfg, known_places=places)
    assert parsed["hard"][0] == {"field": "destination", "operator": "contains",
                                 "value": "Hạ Long"}


def test_form_wins_over_text(input_cfg):
    req = build_requirement("Phú Quốc 20 triệu", {"budget_max": 8_000_000}, cfg=input_cfg,
                            known_places=PLACES)
    budgets = [c for c in req.conditions if c.field == "budget_max"]
    assert len(budgets) == 1
    assert budgets[0].value == 8_000_000


def test_missing_slots_reported_not_guessed(input_cfg):
    req = build_requirement("Đà Lạt", cfg=input_cfg, known_places=PLACES)
    assert "budget_max" in req.missing
    assert "date_from" in req.missing
    assert all(c.value not in (None, "") for c in req.conditions)


def test_keyword_extract_undiacritized(input_cfg):
    req = build_requirement("Da Lat 3 ngay, di tu Sai Gon, toi da 8 trieu/nguoi",
                            cfg=input_cfg, known_places=["Đà Lạt", "Sài Gòn"])
    fields = {c.field: c.value for c in req.conditions}
    assert fields["destination"] == "Đà Lạt"
    assert fields["departure_city"] == "Sài Gòn"
    assert fields["budget_max"] == 8_000_000


def test_condition_ids_unique(input_cfg):
    req = build_requirement("Đà Lạt 3 ngày, tối đa 8 triệu", cfg=input_cfg, known_places=PLACES)
    ids = [c.id for c in req.conditions]
    assert len(ids) == len(set(ids)) > 1


def test_nim_invented_budget_without_digits_dropped(input_cfg):
    nim = _mock_nim({"hard": [{"field": "budget_max", "operator": "lte", "value": 5000000}],
                     "soft": [], "travelers": 1})
    req = build_requirement("tour giá hợp lý", nim=nim, cfg=input_cfg)
    assert "budget_max" not in {c.field for c in req.conditions}
    assert "budget_max" in req.missing


def test_nim_grounded_budget_kept(input_cfg):
    nim = _mock_nim({"hard": [{"field": "budget_max", "operator": "lte", "value": 8000000}],
                     "soft": [], "travelers": 1})
    req = build_requirement("tour tối đa 8 triệu", nim=nim, cfg=input_cfg)
    assert [c.value for c in req.conditions if c.field == "budget_max"] == [8000000]


def test_form_only_requirement(input_cfg):
    req = build_requirement("", {"destinations": ["Đà Lạt"], "budget_max": 8_000_000,
                                 "departure_city": "Sài Gòn", "travelers": 2}, cfg=input_cfg)
    assert req.travelers == 2
    assert "destination" not in req.missing
    assert "budget_max" not in req.missing


def test_drop_fields_relaxes_form_text_and_missing(input_cfg):
    req = build_requirement("Da Lat 3 ngay, di tu Sai Gon, toi da 8 trieu/nguoi",
                            {"budget_max": 8_000_000},
                            cfg=input_cfg, known_places=["Đà Lạt", "Sài Gòn"],
                            drop_fields=["departure_city", "budget_max", "not_a_field"])
    fields = {c.field for c in req.conditions}
    assert "departure_city" not in fields
    assert "budget_max" not in fields
    assert "destination" in fields
    assert "departure_city" not in req.missing
    assert "budget_max" not in req.missing


def test_structured_destination_options_are_or(input_cfg):
    req = build_requirement("", {"destinations": ["Đà Nẵng", "Đà Lạt"]}, cfg=input_cfg)
    destinations = [condition for condition in req.conditions if condition.field == "destination"]
    assert len(destinations) == 1
    assert destinations[0].operator == "any"
    assert destinations[0].value == ["Đà Nẵng", "Đà Lạt"]


def test_nim_or_splits_into_any_condition(input_cfg):
    nim = _mock_nim({"hard": [{"field": "destination", "operator": "any",
                               "value": ["Đà Nẵng", "Tây Nguyên"]}],
                     "soft": [], "travelers": 1})
    req = build_requirement("Đà Nẵng hoặc Tây Nguyên", nim=nim, cfg=input_cfg)
    dests = [c for c in req.conditions if c.field == "destination"]
    assert len(dests) == 1
    assert dests[0].operator == "any"
    assert dests[0].value == ["Đà Nẵng", "Tây Nguyên"]


def test_nim_single_any_unwraps_to_contains(input_cfg):
    nim = _mock_nim({"hard": [{"field": "destination", "operator": "any",
                               "value": ["Đà Lạt"]}],
                     "soft": [], "travelers": 1})
    req = build_requirement("Đà Lạt", nim=nim, cfg=input_cfg)
    dests = [c for c in req.conditions if c.field == "destination"]
    assert len(dests) == 1
    assert dests[0].operator == "contains"
    assert dests[0].value == "Đà Lạt"


def test_nim_transport_passes_through_enum(input_cfg):
    nim = _mock_nim({"hard": [{"field": "transport", "operator": "eq", "value": "bus"}],
                     "soft": [], "travelers": 1})
    req = build_requirement("đi xe ô tô", nim=nim, cfg=input_cfg)
    assert req.conditions[0].value == "bus"


def test_nim_raw_transport_kept_for_eval(input_cfg, decide_cfg):
    from backend.decide.engine import eval_hard
    from backend.normalize.snapshots import rows_to_snapshots

    nim = _mock_nim({"hard": [{"field": "transport", "operator": "eq", "value": "xe ô tô"}],
                     "soft": [], "travelers": 1})
    req = build_requirement("đi xe ô tô", nim=nim, cfg=input_cfg)
    assert req.conditions[0].value == "xe ô tô"
    tour = rows_to_snapshots(FixtureCatalog().list_tours(10))[0]
    offer = tour.offers[0]
    assert eval_hard(req.conditions[0], tour, offer) == ("unknown", "UNSUPPORTED_TRANSPORT")


def test_nim_soft_preferences_extracted(input_cfg):
    nim = _mock_nim({"hard": [], "soft": [{"text": "gần gũi thiên nhiên"},
                                          {"text": "dịch vụ tốt"}], "travelers": 2})
    req = build_requirement("tour thiên nhiên, dịch vụ tốt", nim=nim, cfg=input_cfg)
    assert req.travelers == 2
    assert [(c.id, str(c.value)) for c in req.soft()] == [
        ("s1", "gần gũi thiên nhiên"), ("s2", "dịch vụ tốt")]


def test_nim_soft_strings_accepted(input_cfg):
    nim = _mock_nim({"hard": [], "soft": ["uy tín", "dịch vụ tốt"], "travelers": 1})
    req = build_requirement("cty uy tín, dịch vụ tốt", nim=nim, cfg=input_cfg)
    assert [str(c.value) for c in req.soft()] == ["uy tín", "dịch vụ tốt"]


def test_resolve_lunar_ground_truth():
    assert _resolve_lunar({"calendar": "lunar", "year": 2026, "month": 12, "day": 27}) == "2027-02-03"
    assert _resolve_lunar({"calendar": "lunar", "year": 2027, "month": 1, "day": 4}) == "2027-02-09"
    assert _resolve_lunar({"calendar": "lunar", "year": 2026, "month": 1, "day": 1}) == "2026-02-17"
    assert _resolve_lunar({"calendar": "lunar", "year": 2026, "month": 13, "day": 1}) is None
    assert _resolve_lunar({"calendar": "lunar", "year": 2026, "month": 2, "day": 40}) is None
    assert _resolve_lunar({"calendar": "solar"}) is None


def test_tet_frame_upcoming():
    from backend.input.lunar import tet_frame

    frame = tet_frame("2026-10-09")
    assert "2027-02-06" in frame
    assert "2026" in frame
    assert tet_frame("not-a-date") == ""


def test_nim_lunar_ref_resolves_to_iso(input_cfg):
    nim = _mock_nim({"hard": [
        {"field": "date_from", "operator": "eq",
         "value": {"calendar": "lunar", "year": 2026, "month": 12, "day": 27}},
        {"field": "date_to", "operator": "eq",
         "value": {"calendar": "lunar", "year": 2027, "month": 1, "day": 4}}],
        "soft": [], "travelers": 1})
    req = build_requirement("từ 27/12 âm đến mùng 4 Tết", nim=nim, cfg=input_cfg)
    dates = {c.field: c.value for c in req.conditions}
    assert dates["date_from"] == "2027-02-03"
    assert dates["date_to"] == "2027-02-09"
    assert "date_from" not in req.missing
