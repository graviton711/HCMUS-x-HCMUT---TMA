"""Data sessions: save/load round-trip, missing raises."""

import pytest

from backend.data.sessions import SessionStore
from backend.errors import AppError
from backend.input.pipeline import build_requirement


def test_requirement_round_trip(settings):
    store = SessionStore(settings.database_url)
    req = build_requirement("Đà Lạt 3 ngày, tối đa 8 triệu")
    store.save_requirement(req)
    loaded = store.get_requirement(req.id)
    assert loaded.id == req.id
    assert [c.field for c in loaded.conditions] == [c.field for c in req.conditions]
    store.close()


def test_missing_comparison_raises(settings):
    store = SessionStore(settings.database_url)
    with pytest.raises(AppError) as exc:
        store.get_comparison("cmp_nope")
    assert exc.value.status == 404
    store.close()
