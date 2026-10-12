import pytest

from backend.settings import DecideCfg, Settings

_ENV_VARS = ("DATABASE_URL", "DATA_PROVIDER", "CANDIDATE_LIMIT",
             "SUPABASE_TOUR_DB_URL", "SUPABASE_SCAN_LIMIT")


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    empty = tmp_path / "test.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr("backend.settings.Settings.load", _guarded_load(empty))


def _guarded_load(empty):
    original = Settings.load

    def load(path=None, **overrides):
        overrides.setdefault("_env_file", str(empty))
        return original(path, **overrides)

    return load


@pytest.fixture
def settings(tmp_path):
    return Settings.load(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def decide_cfg(settings) -> DecideCfg:
    return settings.tuning.decide
