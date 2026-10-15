"""Decision verify protocol (ported from TMA verify.ts).

Locks three properties, not exact outputs:
1. Options differ when the data allows (>=2/3 distinct tours).
2. Changing the brief changes the comparison.
3. Every tradeoff sentence is grounded in numbers; no fabricated options.
"""

from __future__ import annotations

import re

from sample_rows import sample_rows

from backend.decide.engine import compare
from backend.input.pipeline import requirement_from_form
from backend.models import TourRow
from backend.normalize.snapshots import rows_to_snapshots


def _three_tour_rows() -> list[TourRow]:
    rows = sample_rows()
    extra = TourRow(
        provider={"source_key": "dulichviet", "display_name": "Du Lịch Việt"},
        tour={
            "record_key": "dlv-dalat-2n",
            "url": "https://dulichviet.com.vn/tour-da-lat-2-ngay",
            "tour_name": "Đà Lạt 2 ngày 1 đêm",
            "departure_city": "Sài Gòn",
            "destinations": ["Đà Lạt"],
            "transport": "bus",
            "duration_days": 2,
            "itinerary": "Ngày 1: đi. Ngày 2: về.",
            "observed_at": "2026-10-15T00:00:00+07:00",
        },
        offers=[{
            "record_key": "dlv-dalat-2n-20261225",
            "departure_date": "2026-12-25",
            "price": 4900000,
            "currency": "VND",
            "price_type": "fixed",
            "availability": "available",
            "observed_at": "2026-10-15T00:00:00+07:00",
        }],
    )
    return [*rows, extra]


def _req(form):
    return requirement_from_form(form)


def test_options_differ_when_data_allows(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), rows_to_snapshots(_three_tour_rows()), decide_cfg)
    distinct = {option.tour_id for option in comparison.decision_options}
    assert len(distinct) >= 2, "need >=2/3 distinct tours when data allows"


def test_input_change_changes_output(decide_cfg):
    tours = rows_to_snapshots(_three_tour_rows())
    base = compare(_req({"destinations": ["Đà Lạt"]}), tours, decide_cfg)
    changed = compare(_req({"destinations": ["Đà Lạt"], "budget_max": 5_000_000}), tours, decide_cfg)
    base_ids = [(item.tour_id, item.offer_id) for item in base.ranked]
    changed_ids = [(item.tour_id, item.offer_id) for item in changed.ranked]
    assert base_ids != changed_ids


def test_tradeoff_sentences_grounded(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), rows_to_snapshots(_three_tour_rows()), decide_cfg)
    assert comparison.decision_options
    for option in comparison.decision_options:
        assert option.tradeoffs, "options must explain themselves"
        for sentence in option.tradeoffs:
            assert re.search(r"\d", sentence), f"ungrounded tradeoff: {sentence!r}"


def test_no_fabricated_options(decide_cfg):
    comparison = compare(_req({"destinations": ["Đà Lạt"]}), rows_to_snapshots(_three_tour_rows()), decide_cfg)
    eligible = {candidate.tour_id for candidate in comparison.ranked}
    for option in comparison.decision_options:
        assert option.tour_id in eligible
