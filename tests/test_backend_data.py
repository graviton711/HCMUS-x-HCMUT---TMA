"""Data sessions: save/load round-trip, missing raises."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from backend.data.sessions import SessionStore
from backend.errors import AppError
from backend.input.pipeline import build_requirement


def test_requirement_round_trip(settings, input_cfg):
    store = SessionStore(settings.database_url)
    req = build_requirement("Đà Lạt 3 ngày, tối đa 8 triệu", cfg=input_cfg, known_places=["Đà Lạt"])
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
    row = store._conn.execute("SELECT token_hash FROM sessions WHERE id = ?", (session["id"],)).fetchone()
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

    first, first_has_more = store.list_history(owner_a, 2)
    assert len(first) == 2
    assert first_has_more
    cursor = (first[-1]["created_at"], first[-1]["id"])
    second, second_has_more = store.list_history(owner_a, 2, cursor)
    assert not second_has_more
    assert {item["id"] for item in first}.isdisjoint(item["id"] for item in second)
    assert all(item["id"] != other.id for item in first + second)
    assert {item["id"] for item in first + second} == {item.id for item in requirements}
    store.close()


def test_legacy_unowned_records_survive_owner_scope_migration(settings, input_cfg):
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    requirement = build_requirement("Đà Lạt", cfg=input_cfg, known_places=["Đà Lạt"])
    legacy = sqlite3.connect(path)
    legacy.execute(
        "CREATE TABLE records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    legacy.execute(
        "INSERT INTO records (id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
        (requirement.id, "requirement", requirement.model_dump_json(), "2026-01-01T00:00:00+07:00"),
    )
    legacy.commit()
    legacy.close()

    store = SessionStore(settings.database_url)
    assert store.get_requirement(requirement.id).id == requirement.id
    owner_id = store.create_session(3600)["id"]
    with pytest.raises(AppError) as exc:
        store.get_requirement(requirement.id, owner_id)
    assert exc.value.status == 404
    assert store.list_history(owner_id) == ([], False)
    store.close()


def test_resource_id_cannot_be_reassigned_to_another_owner(settings, input_cfg):
    store = SessionStore(settings.database_url)
    owner_a = store.create_session(3600)["id"]
    owner_b = store.create_session(3600)["id"]
    requirement = build_requirement("Đà Lạt", cfg=input_cfg, known_places=["Đà Lạt"])
    store.save_requirement(requirement, owner_a)

    with pytest.raises(AppError) as exc:
        store.save_requirement(requirement, owner_b)
    assert exc.value.status == 409
    assert store.get_requirement(requirement.id, owner_a).id == requirement.id
    store.close()
