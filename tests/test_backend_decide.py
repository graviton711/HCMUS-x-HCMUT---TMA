"""Decide: hard filter → rank → analyze. Offline, soft stays unknown without LLM."""

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import compare
from backend.input.pipeline import build_requirement
from backend.normalize.snapshots import rows_to_snapshots


def _snapshots():
    return rows_to_snapshots(FixtureCatalog().list_tours())


def test_budget_hard_filter_per_offer():
    req = build_requirement("", {"destinations": ["Đà Lạt"], "budget_max": 7_000_000})
    comp = compare(req, _snapshots())
    kept = {(c.tour_id, c.offer_id) for c in comp.ranked}
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20270109") in kept
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20261225") not in kept


def test_from_price_is_unknown_never_filtered_nor_trusted():
    req = build_requirement("", {"destinations": ["Hạ Long"], "budget_max": 1_000_000})
    comp = compare(req, _snapshots())
    states = {(e.offer_id, e.condition_id): e.state for e in comp.evaluations}
    budget_id = next(c.id for c in req.conditions if c.field == "budget_max")
    assert states[("sgt-halong-3n-20261227", budget_id)] == "unknown"
    assert ("sgt-halong-3n", "sgt-halong-3n-20261227") in {
        (c.tour_id, c.offer_id) for c in comp.ranked}


def test_destination_mismatch_fails():
    req = build_requirement("", {"destinations": ["Đà Lạt"]})
    comp = compare(req, _snapshots())
    tours = {c.tour_id for c in comp.ranked}
    assert tours == {"dlv-dalat-3n"}


def test_rank_prefers_cheaper_on_tie():
    req = build_requirement("", {"destinations": ["Đà Lạt"]})
    comp = compare(req, _snapshots())
    assert comp.ranked[0].offer_id == "dlv-dalat-3n-20270109"


def test_analysis_surfaces_costs_risks_benefits():
    req = build_requirement("", {"destinations": ["Phú Quốc"]})
    comp = compare(req, _snapshots())
    text = " ".join(comp.analysis.hidden_costs + comp.analysis.conditions
                    + comp.analysis.risks + comp.analysis.benefits)
    assert "Phụ thu" in text or "phụ thu" in text.lower()
    assert comp.analysis.benefits, "inclusions should surface as benefits"
    assert comp.candidates_considered == 3
