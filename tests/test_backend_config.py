"""Settings: YAML base, env wins, code fallbacks. Hermetic via tmp files."""

from backend.settings import Settings

_YAML = """
backend:
  api: {candidate_default: 7}
  data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3}
  nim: {model: test-model, timeout_s: 9}
  input: {window_before: 5, window_budget: 9, quote_chars: 9}
  decide: {excerpt_chars: 99, quote_chars: 9,
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
    assert settings.candidate_limit == 7
    assert settings.supabase_scan_limit == 50
    assert settings.nvidia_nim_model == "test-model"
    assert settings.nim_timeout_seconds == 9
    assert settings.tuning.decide.top_n == 1
    assert settings.tuning.data.providers_limit == 5
    assert settings.tuning.extract.system.strip() == "EXTRACT!"
    assert settings.tuning.extract.max_tokens == 11
    assert settings.tuning.extract.temperature == 0.5
    assert settings.tuning.assess.system.strip() == "ASSESS!"
    assert settings.tuning.assess.max_tokens == 22


def test_env_wins_over_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("CANDIDATE_LIMIT", "42")
    assert Settings.load(_configs(tmp_path)).candidate_limit == 42


def test_code_fallback_models():
    from backend.settings import AssessPromptCfg, DecideCfg, ExtractPromptCfg, InputCfg

    assert InputCfg().window_before == 16
    assert DecideCfg().top_n == 3
    assert "Trích yêu cầu tour" in ExtractPromptCfg().system
    assert ExtractPromptCfg().max_tokens == 1024
    assert AssessPromptCfg().max_tokens == 2048


def test_repo_configs_load(tmp_path):
    settings = Settings.load()
    assert settings.tuning.input.window_before == 16
    assert settings.tuning.decide.excerpt_chars == 6000
    assert settings.tuning.data.providers_limit == 100
    assert settings.tuning.api.port == 8000
    assert "Trích yêu cầu tour" in settings.tuning.extract.system
