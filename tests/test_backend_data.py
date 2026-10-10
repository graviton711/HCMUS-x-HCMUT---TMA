"""Data sessions: save/load round-trip, missing raises."""

import hashlib

import pytest

from backend.data.sessions import SessionStore
from backend.errors import AppError
from backend.input.pipeline import build_requirement


def test_requirement_round_trip(settings, input_cfg):
    store = SessionStore(settings.database_url)
    req = build_requirement("Đà Lạt 3 ngày, tối đa 8 triệu", cfg=input_cfg,
                            known_places=["Đà Lạt"])
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


def test_guest_session_stores_only_token_hash(settings):
    store = SessionStore(settings.database_url)
    session = store.create_session(3600)

    assert session["id"].startswith("ses_")
    assert session["token"]
    assert store.authenticate_session(session["token"]) == session["id"]
    row = store._conn.execute(
        "SELECT token_hash FROM sessions WHERE id = ?", (session["id"],)
    ).fetchone()
    assert row[0] == hashlib.sha256(session["token"].encode()).hexdigest()
    assert session["token"] not in row[0]
    store.close()


def test_expired_guest_session_is_rejected(settings):
    store = SessionStore(settings.database_url)
    session = store.create_session(3600)
    store._conn.execute(
        "UPDATE sessions SET expires_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00+00:00", session["id"]),
    )
    store._conn.commit()

    with pytest.raises(AppError) as exc:
        store.authenticate_session(session["token"])
    assert exc.value.status == 401
    assert exc.value.code == "SESSION_EXPIRED"
    store.close()


def test_history_pages_are_stable_and_owner_scoped(settings, input_cfg):
    store = SessionStore(settings.database_url)
    owner_a = store.create_session(3600)["id"]
    owner_b = store.create_session(3600)["id"]
    requirements = [
        build_requirement(f"Đà Lạt {index} ngày", cfg=input_cfg, known_places=["Đà Lạt"])
        for index in range(3)
    ]
    for requirement in requirements:
        store.save_requirement(requirement, owner_a)
    other = build_requirement("Phú Quốc", cfg=input_cfg, known_places=["Phú Quốc"])
    store.save_requirement(other, owner_b)

    first = store.list_history(owner_a, 2)
    assert len(first) == 3
    cursor = (first[1]["created_at"], first[1]["id"])
    second = store.list_history(owner_a, 2, cursor)
    assert {item["id"] for item in first[:2]}.isdisjoint(item["id"] for item in second)
    assert all(item["id"] != other.id for item in first + second)
    assert {item["id"] for item in first + second} == {item.id for item in requirements}
    store.close()
