import pytest

from backend.settings import DecideCfg, InputCfg, Settings


@pytest.fixture
def settings(tmp_path):
    return Settings.load(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def input_cfg(settings) -> InputCfg:
    return settings.tuning.input


@pytest.fixture
def decide_cfg(settings) -> DecideCfg:
    return settings.tuning.decide
