"""Settings: YAML + environment precedence, without extraction prompts."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.settings import Settings

_YAML = """
opencode: {model: opencode/test-model}
backend:
  data_provider: fixture
  database_url: sqlite:///tmp/test.db
  api: {host: "127.0.0.1", port: 8000, candidate_default: 7, candidate_min: 1, candidate_max: 100,
    session_ttl_seconds: 2592000}
  data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3}
  decide: {soft_fields: [itinerary], quote_chars: 120,
    risk_words: [x], analysis_chars: 9, analysis_items: 2, top_n: 1}
"""


def _configs(tmp_path, yaml_text=_YAML):
    root = tmp_path / "configs"
    root.mkdir()
    (root / "settings.yaml").write_text(yaml_text, encoding="utf-8")
    return root


def test_yaml_tuning_loaded(tmp_path):
    settings = Settings.load(_configs(tmp_path))
    assert settings.data_provider == "fixture"
    assert settings.opencode.model == "opencode/test-model"
    assert settings.candidate_limit == 7
    assert settings.supabase_scan_limit == 50
    assert settings.tuning.decide.top_n == 1
    assert settings.tuning.decide.quote_chars == 120
    assert settings.tuning.data.providers_limit == 5
    assert settings.supabase_tour_freshness_seconds == {"departure_date": None}


def test_env_wins_over_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("CANDIDATE_LIMIT", "42")
    monkeypatch.setenv("OPENCODE_MODEL", "opencode/env-model-ignored")
    settings = Settings.load(_configs(tmp_path))
    assert settings.candidate_limit == 42
    assert settings.opencode.model == "opencode/test-model"


def test_legacy_price_trust_and_ttl_settings_are_ignored(tmp_path):
    yaml_text = _YAML.replace(
        "data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3}",
        "data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3, "
        "trusted_domains: [trusted.example.test], freshness_seconds: {departure_date: 7200, price: 3600}}",
    )
    settings = Settings.load(_configs(tmp_path, yaml_text))
    assert settings.supabase_tour_freshness_seconds == {"departure_date": 7200}
    assert not hasattr(settings, "supabase_tour_trusted_domains")


def test_demo_freshness_policy_can_disable_age_expiry(tmp_path):
    yaml_text = _YAML.replace(
        "data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3}",
        "data: {scan_limit: 50, providers_limit: 5, connect_timeout_s: 3, freshness_seconds: {departure_date: null}}",
    )
    settings = Settings.load(_configs(tmp_path, yaml_text))
    assert settings.supabase_tour_freshness_seconds == {"departure_date": None}


def test_dotenv_file_wins_over_yaml(tmp_path):
    env = tmp_path / "t.env"
    env.write_text("CANDIDATE_LIMIT=33\nOPENCODE_MODEL=opencode/dotenv-model\n", encoding="utf-8")
    settings = Settings.load(_configs(tmp_path), _env_file=str(env))
    assert settings.candidate_limit == 33
    assert settings.opencode.model == "opencode/test-model"


def test_cors_origins_env_accepts_bare_csv_and_json(tmp_path, monkeypatch):
    configs = _configs(tmp_path)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")
    assert Settings.load(configs).cors_origins == ["https://app.example"]
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings.load(configs).cors_origins == [
        "https://a.example",
        "https://b.example",
    ]
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example", "https://b.example"]')
    assert Settings.load(configs).cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


def test_db_url_env_strips_pasted_whitespace(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_TOUR_DB_URL", "postgresql://u:p@host:5432/postgres\n"
    )
    settings = Settings.load(_configs(tmp_path))
    assert settings.supabase_tour_db_url == "postgresql://u:p@host:5432/postgres"
    assert settings.database_url == "postgresql://u:p@host:5432/postgres"


def test_opencode_project_dir_defaults_empty_and_env_overrides(tmp_path, monkeypatch):
    configs = _configs(tmp_path)
    assert Settings.load(configs).opencode_project_dir == ""
    monkeypatch.setenv("OPENCODE_PROJECT_DIR", "/app")
    assert Settings.load(configs).opencode_project_dir == "/app"
    assert not hasattr(Settings.load(configs), "opencode_timeout_seconds")


def test_incomplete_yaml_fails_loud(tmp_path):
    root = tmp_path / "configs"
    root.mkdir()
    (root / "settings.yaml").write_text("backend:\n  api: {host: x}\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings.load(root)


def test_repo_configs_load():
    settings = Settings.load()
    assert settings.opencode.model == "opencode/muse-spark-1.3-contributor-free"
    assert settings.tuning.decide.quote_chars <= 200
    assert settings.tuning.data.providers_limit == 100
    assert settings.tuning.api.port == 8000
    import yaml

    agent = Path(".opencode/agents/travel-consultant.md").read_text(encoding="utf-8")
    frontmatter = agent.split("---", 2)[1]
    assert not any(line.startswith("model:") for line in frontmatter.splitlines())
    assert "OPENCODE_MODEL" not in Path(".env.example").read_text(encoding="utf-8")
    assert "OPENCODE_MODEL" not in Path("render.yaml").read_text(encoding="utf-8")
    assert "model" not in yaml.safe_load(Path("configs/settings.yaml").read_text(encoding="utf-8"))["survey"]
    prompt = yaml.safe_load(Path("configs/prompts/agent.yaml").read_text(encoding="utf-8"))
    assert agent.split("---", 2)[2].strip() == prompt["system"].strip()
    assert "Same-field equivalent labels may use `any`." in prompt["system"]
    assert "cannot prove absence from the full catalog" in prompt["system"]
