"""Offline tests for ingest.audit holdout scoring. run_tour is faked; no network."""

from __future__ import annotations

import json

import ingest.audit as audit_mod
from ingest.audit import audit_urls, main


def _profile(**overrides):
    base = {"origin": "example.test", "flows": ["static"],
            "fields": {"tour_name": {"source": "css", "selector": "h1"},
                       "price": {"source": "css", "selector": ".p"}}}
    base.update(overrides)
    return base


def _detail(tmp_path, name, record, prose="<h1>T</h1><p>100</p>", raw=None,
            evidence="verified"):
    path = tmp_path / name
    path.write_text(json.dumps({"record": record, "record_raw": record if raw is None else raw,
                                "page_prose": prose, "record_evidence": evidence}),
                    encoding="utf-8")
    return str(path)


def test_audit_rejects_profile_without_fields():
    result = audit_urls(["https://example.test/1"], {"origin": "example.test"}, {}, min_evidence=0.0)
    assert not result.passed
    assert any("no fields" in f for f in result.failures)


def test_audit_passes_verified_records(tmp_path, monkeypatch):
    detail = _detail(tmp_path, "d1.json",
                     {"tour_name": "T", "price": 100}, "<h1>T</h1><p>100</p>")
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": detail})
    result = audit_urls(["https://example.test/1"], _profile(), {})
    assert result.passed, result.failures
    assert result.evidence_rate == 1.0
    assert result.fields["price"] == {"filled": 1, "tours": 1}


def test_audit_fails_unobserved_field(tmp_path, monkeypatch):
    detail = _detail(tmp_path, "d1.json", {"tour_name": "T", "price": ""})
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": detail})
    result = audit_urls(["https://example.test/1"], _profile(), {})
    assert not result.passed
    assert result.unobserved == ["price"]


def test_audit_declared_absence_is_not_a_failure(tmp_path, monkeypatch):
    profile = _profile(fields={"tour_name": {"source": "css", "selector": "h1"},
                               "visa": {"source": "css", "selector": ".v",
                                        "status": "not_observed"}})
    detail = _detail(tmp_path, "d1.json", {"tour_name": "T", "visa": ""})
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": detail})
    result = audit_urls(["https://example.test/1"], profile, {})
    assert result.passed, result.failures
    assert result.unobserved == []


def test_audit_fails_low_evidence(tmp_path, monkeypatch):
    detail = _detail(tmp_path, "d1.json",
                     {"tour_name": "Elsewhere", "price": 100}, "<h1>T</h1><p>100</p>",
                     evidence="partial")
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": detail})
    result = audit_urls(["https://example.test/1"], _profile(), {}, min_evidence=0.9)
    assert not result.passed
    assert any("evidence verified 0/1" in f for f in result.failures)


def test_audit_unreadable_detail_counts_as_failed_tour(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": str(tmp_path / "missing.json")})
    result = audit_urls(["https://example.test/1", "https://example.test/2"], _profile(), {})
    assert not result.passed
    assert len(result.failed_tours) == 2


def test_main_exit_codes(tmp_path, monkeypatch):
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://example.test/1\n", encoding="utf-8")
    detail = _detail(tmp_path, "d1.json", {"tour_name": "T", "price": 100}, "<h1>T</h1><p>100</p>")
    monkeypatch.setattr(audit_mod, "run_tour",
                        lambda url, profile, settings, out_dir: {"detail_file": detail})
    monkeypatch.setattr(audit_mod, "load_settings", lambda: {})
    monkeypatch.setattr(audit_mod, "load_profile", lambda name: _profile())
    assert main(["--profile", "x", "--urls", str(urls_file)]) == 0
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert main(["--profile", "x", "--urls", str(empty)]) == 1
