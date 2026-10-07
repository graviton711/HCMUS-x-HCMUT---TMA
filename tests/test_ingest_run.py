"""Offline tests for the full-chain runner. No network, no agent, no DB."""

import ingest.run as run_mod


class _Stub:
    def __init__(self, codes):
        self.codes = list(codes or [])
        self.calls: list = []

    def main(self, argv):
        self.calls.append(list(argv))
        return self.codes.pop(0) if self.codes else 0


def _patch(monkeypatch, survey_codes=None, pipeline_codes=None, audit_codes=None):
    survey, pipeline, audit = (_Stub(survey_codes), _Stub(pipeline_codes),
                               _Stub(audit_codes))
    monkeypatch.setattr(run_mod, "survey_mod", survey)
    monkeypatch.setattr(run_mod, "pipeline_mod", pipeline)
    monkeypatch.setattr(run_mod, "audit_mod", audit)
    return survey, pipeline, audit


def test_run_chain_full_order(monkeypatch):
    survey, pipeline, audit = _patch(monkeypatch)
    assert run_mod.main(["--source", "s"]) == 0
    assert survey.calls == [["--source", "s", "--promote"]]
    assert pipeline.calls == [["--discover", "--profile", "s"],
                              ["--batch", "--profile", "s"],
                              ["--migrate"],
                              ["--publish", "--profile", "s"]]
    assert audit.calls == [["--profile", "s"]]


def test_run_chain_stops_at_first_failure(monkeypatch):
    survey, pipeline, audit = _patch(monkeypatch, pipeline_codes=[0, 3])
    assert run_mod.main(["--source", "s"]) == 3
    assert pipeline.calls == [["--discover", "--profile", "s"],
                              ["--batch", "--profile", "s"]]
    assert audit.calls == [] and survey.calls != []


def test_run_chain_audit_gates_publish_unless_skipped(monkeypatch):
    survey, pipeline, audit = _patch(monkeypatch, audit_codes=[1])
    assert run_mod.main(["--source", "s"]) == 1
    assert pipeline.calls == [["--discover", "--profile", "s"],
                              ["--batch", "--profile", "s"]]
    assert run_mod.main(["--source", "s", "--skip-audit"]) == 0


def test_run_chain_skip_survey_and_limit(monkeypatch):
    survey, pipeline, audit = _patch(monkeypatch)
    assert run_mod.main(["--source", "s", "--skip-survey", "--limit", "5"]) == 0
    assert survey.calls == []
    assert pipeline.calls[0] == ["--discover", "--profile", "s", "--limit", "5"]
    assert pipeline.calls[1] == ["--batch", "--profile", "s", "--limit", "5"]
