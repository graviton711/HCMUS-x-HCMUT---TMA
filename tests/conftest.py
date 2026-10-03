import pytest

from api.settings import Settings
from domain.common import now
from domain.requirements import Condition, Requirement, SourceReference
from requirements.service import conjunction, finalize


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        worker_enabled=False,
        nvidia_nim_api="unit-test-token",
        nim_timeout_seconds=1,
    )


def condition(field, value, operator="eq", strength="hard", cid="c1"):
    return Condition(
        id=cid,
        field=field,
        operator=operator,
        value=value,
        strength=strength,
        sources=[SourceReference(kind="form", field_path=f"conditions.{cid}")],
    )


def requirement(conditions=None, **kwargs):
    conditions = conditions or []
    return finalize(
        Requirement(
            id="req_test",
            revision=1,
            mode="discover",
            conditions=conditions,
            hard_tree=conjunction(conditions, False),
            preference_tree=conjunction(conditions, True),
            **kwargs,
        )
    )


@pytest.fixture
def timestamp():
    return now().isoformat()
