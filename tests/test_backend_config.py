"""Settings: YAML + env required, no code fallbacks. Hermetic via tmp files."""

import pytest
from pydantic import ValidationError

from backend.settings import Settings

_YAML = """
backend:
  data_provider: fixture
  database_url: sqlite:///tmp/test.db
  api: {host: "127.0.0.1", port: 8000, candidate_default: 7, candidate_min: 1, candidate_max: 100}
  data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3}
  nim: {model: test-model, timeout_s: 9}
  input: {money_units: {trieu: 1000000}, budget_words: [bw], departure_markers: [dm],
    required_slots: [destination], window_before: 5, window_budget: 9, quote_chars: 9}
  decide: {soft_fields: [itinerary], excerpt_chars: 99, quote_chars: 9,
    risk_words: [x], analysis_chars: 9, analysis_items: 2, top_n: 1}
"""


def _configs(tmp_path, yaml_text=_YAML, extract="EXTRACT!", assess="ASSESS!"):
    root = tmp_path / "configs"
    (root / "prompts").mkdir(parents=True)
    (root / "settings.yaml").write_text(yaml_text, encoding="utf-8")
    (root / "prompts" / "extract.yaml").write_text(
        f"description: t\nmax_tokens: 11\ntemperature: 0.5\nsystem: |\n  {extract}\n",
        encoding="utf-8")
    (root / "prompts" / "assess.yaml").write_text(
        f"description: t\nmax_tokens: 22\ntemperature: 0.5\nsystem: |\n  {assess}\n",
        encoding="utf-8")
    return root


def test_yaml_tuning_and_prompts_loaded(tmp_path):
    settings = Settings.load(_configs(tmp_path))
    assert settings.data_provider == "fixture"
    assert settings.candidate_limit == 7
    assert settings.supabase_scan_limit == 50
    assert settings.nvidia_nim_model == "test-model"
    assert settings.nim_timeout_seconds == 9
    assert settings.tuning.input.budget_words == ["bw"]
    assert settings.tuning.input.required_slots == ["destination"]
    assert settings.tuning.decide.top_n == 1
    assert settings.tuning.data.providers_limit == 5
    assert settings.tuning.extract.system.strip() == "EXTRACT!"
    assert settings.tuning.extract.max_tokens == 11
    assert settings.tuning.assess.system.strip() == "ASSESS!"


def test_env_wins_over_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("CANDIDATE_LIMIT", "42")
    assert Settings.load(_configs(tmp_path)).candidate_limit == 42


def test_incomplete_yaml_fails_loud(tmp_path):
    root = tmp_path / "configs"
    root.mkdir()
    (root / "settings.yaml").write_text("backend:\n  api: {host: x}\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings.load(root)


def test_missing_prompt_fails_loud_in_calls():
    from backend.decide.engine import assess_soft_llm
    from backend.errors import AppError
    from backend.input.nim import NimClient
    from backend.models import Condition

    nim = NimClient("key", "model", 9.0)
    with pytest.raises(AppError) as exc:
        nim.extract("test")
    assert exc.value.code == "PROMPT_NOT_CONFIGURED"
    with pytest.raises(AppError) as exc:
        assess_soft_llm([], [Condition(id="s1", field="preference", value="x", strength="soft")],
                        nim, None, 99, 9, ["itinerary"])
    assert exc.value.code == "PROMPT_NOT_CONFIGURED"


def test_repo_configs_load():
    settings = Settings.load()
    assert settings.tuning.input.window_before == 16
    assert settings.tuning.decide.excerpt_chars == 6000
    assert settings.tuning.data.providers_limit == 100
    assert settings.tuning.api.port == 8000
    assert "Trích yêu cầu tour" in settings.tuning.extract.system
