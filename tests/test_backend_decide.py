"""Decide: hard filter → rank → analyze. Offline, soft stays unknown without LLM."""

import json

import httpx

from backend.data.catalog import FixtureCatalog
from backend.decide.engine import assess_soft_llm, compare
from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement
from backend.models import Condition
from backend.normalize.snapshots import rows_to_snapshots
from backend.settings import PromptCfg


def _snapshots():
    return rows_to_snapshots(FixtureCatalog().list_tours(10))


def _mock_nim(payload: dict) -> NimClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    return NimClient("key", "model", 9.0,
                     prompt=PromptCfg(system="s", max_tokens=64, temperature=0),
                     transport=httpx.MockTransport(handler))


def test_assess_goes_through_shared_gateway(input_cfg, decide_cfg):
    from backend.models import Condition

    nim = _mock_nim({"scores": [{"tour_id": "dlv-dalat-3n", "condition_id": "s1",
                                 "score": 0.9, "quote": "Langbiang"}]})
    soft = [Condition(id="s1", field="preference", value="thích núi", strength="soft")]
    scores = assess_soft_llm(_snapshots(), soft, nim,
                             prompt=nim.prompt,
                             excerpt_chars=decide_cfg.excerpt_chars,
                             quote_chars=decide_cfg.quote_chars,
                             soft_fields=decide_cfg.soft_fields)
    assert scores[("dlv-dalat-3n", "s1")][0] == 0.9
    assert "Langbiang" in scores[("dlv-dalat-3n", "s1")][1]


def test_compare_uses_soft_scores_in_rank(input_cfg, decide_cfg):
    nim = _mock_nim({"scores": [{"tour_id": "vtr-phuquoc-4n", "condition_id": "s1",
                                 "score": 1.0, "quote": "VinWonders"}]})
    req = build_requirement("", {}, cfg=input_cfg)
    req.conditions.append(Condition(
        id="s1", field="preference", value="thích công viên", strength="soft"))
    comp = compare(req, _snapshots(),
                   lambda ts, soft: assess_soft_llm(ts, soft, nim, nim.prompt, 6000, 300,
                                                    decide_cfg.soft_fields),
                   decide_cfg)
    assert comp.ranked[0].tour_id == "vtr-phuquoc-4n"


def _req(form, input_cfg):
    return build_requirement("", form, cfg=input_cfg)


def test_budget_hard_filter_per_offer(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"], "budget_max": 7_000_000}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    kept = {(c.tour_id, c.offer_id) for c in comp.ranked}
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20270109") in kept
    assert ("dlv-dalat-3n", "dlv-dalat-3n-20261225") not in kept


def test_from_price_is_unknown_never_filtered_nor_trusted(input_cfg, decide_cfg):
    req = _req({"destinations": ["Hạ Long"], "budget_max": 1_000_000}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    states = {(e.offer_id, e.condition_id): e.state for e in comp.evaluations}
    budget_id = next(c.id for c in req.conditions if c.field == "budget_max")
    assert states[("sgt-halong-3n-20261227", budget_id)] == "unknown"
    assert ("sgt-halong-3n", "sgt-halong-3n-20261227") in {
        (c.tour_id, c.offer_id) for c in comp.ranked}


def test_destination_mismatch_fails(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    tours = {c.tour_id for c in comp.ranked}
    assert tours == {"dlv-dalat-3n"}


def test_rank_prefers_cheaper_on_tie(input_cfg, decide_cfg):
    req = _req({"destinations": ["Đà Lạt"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    assert comp.ranked[0].offer_id == "dlv-dalat-3n-20270109"


def test_analysis_surfaces_costs_risks_benefits(input_cfg, decide_cfg):
    req = _req({"destinations": ["Phú Quốc"]}, input_cfg)
    comp = compare(req, _snapshots(), None, decide_cfg)
    text = " ".join(comp.analysis.hidden_costs + comp.analysis.conditions
                    + comp.analysis.risks + comp.analysis.benefits)
    assert "Phụ thu" in text or "phụ thu" in text.lower()
    assert comp.analysis.benefits, "inclusions should surface as benefits"
    assert comp.candidates_considered == 3
