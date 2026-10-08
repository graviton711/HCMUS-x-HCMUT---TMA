"""Offline tests for the full-chain runner. No network, no agent, no DB."""

import ingest.run as run_mod


class _Stub:
    def __init__(self, codes):
        self.codes = list(codes or [])
        self.calls: list = []

    def main(self, argv):
        self.calls.append(list(argv))
        return self.codes.pop(0) if self.codes else 0


def _patch(monkeypatch, survey_codes=None, pipeline_codes=None):
    survey, pipeline = _Stub(survey_codes), _Stub(pipeline_codes)
    monkeypatch.setattr(run_mod, "survey_mod", survey)
    monkeypatch.setattr(run_mod, "pipeline_mod", pipeline)
    return survey, pipeline


def test_run_chain_full_order_no_audit(monkeypatch):
    survey, pipeline = _patch(monkeypatch)
    assert run_mod.main(["--source", "s"]) == 0
    assert survey.calls == [["--source", "s", "--promote"]]
    assert pipeline.calls == [["--discover", "--profile", "s"],
                              ["--batch", "--profile", "s"],
                              ["--migrate"],
                              ["--publish", "--profile", "s"]]


def test_run_chain_stops_at_first_failure(monkeypatch):
    survey, pipeline = _patch(monkeypatch, pipeline_codes=[0, 3])
    assert run_mod.main(["--source", "s"]) == 3
    assert pipeline.calls == [["--discover", "--profile", "s"],
                              ["--batch", "--profile", "s"]]
    assert survey.calls != []


def test_run_chain_skip_survey_and_limit(monkeypatch):
    survey, pipeline = _patch(monkeypatch)
    assert run_mod.main(["--source", "s", "--skip-survey", "--limit", "5"]) == 0
    assert survey.calls == []
    assert pipeline.calls[0] == ["--discover", "--profile", "s", "--limit", "5"]
    assert pipeline.calls[1] == ["--batch", "--profile", "s", "--limit", "5"]


def test_run_chain_all_sources_without_flag(monkeypatch):
    survey, pipeline = _patch(monkeypatch)
    survey.list_sources = lambda: ["dulichviet", "vietravel", "saigontourist"]
    assert run_mod.main([]) == 0
    assert [c[1] for c in survey.calls] == ["dulichviet", "vietravel", "saigontourist"]
    assert survey.calls[0] == ["--source", "dulichviet", "--promote"]
    stepped = [c for c in pipeline.calls if c[0] == "--discover"]
    assert [c[2] for c in stepped] == ["dulichviet", "vietravel", "saigontourist"]
