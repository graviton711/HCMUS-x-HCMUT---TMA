"""Data sessions: save/load round-trip, missing raises."""

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from backend.data.sessions import SessionStore
from backend.errors import AppError
from backend.input.pipeline import requirement_from_form


def test_requirement_round_trip(settings):
    store = SessionStore(settings.database_url)
    req = requirement_from_form({"destinations": ["Đà Lạt"], "duration_days": 3, "budget_max": 8_000_000})
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


def test_history_pages_are_stable_and_owner_scoped(settings):
    store = SessionStore(settings.database_url)
    owner_a = store.create_session(3600)["id"]
    owner_b = store.create_session(3600)["id"]
    requirements = [requirement_from_form({"destinations": [f"Đà Lạt {index}" ]}) for index in range(3)]
    for requirement in requirements:
        store.save_requirement(requirement, owner_a)
    other = requirement_from_form({"destinations": ["Phú Quốc"]})
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


def test_legacy_unowned_records_survive_owner_scope_migration(settings):
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    requirement = requirement_from_form({"destinations": ["Đà Lạt"]})
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


def test_resource_id_cannot_be_reassigned_to_another_owner(settings):
    store = SessionStore(settings.database_url)
    owner_a = store.create_session(3600)["id"]
    owner_b = store.create_session(3600)["id"]
    requirement = requirement_from_form({"destinations": ["Đà Lạt"]})
    store.save_requirement(requirement, owner_a)

    with pytest.raises(AppError) as exc:
        store.save_requirement(requirement, owner_b)
    assert exc.value.status == 409
    assert store.get_requirement(requirement.id, owner_a).id == requirement.id
    store.close()


def test_agent_session_mapping_reuses_records_and_is_owner_scoped(settings):
    store = SessionStore(settings.database_url)
    owner = store.create_session(3600)["id"]
    other = store.create_session(3600)["id"]
    local_id = store.create_agent_session(owner)
    assert local_id.startswith("agt_")
    assert store.get_agent_session(local_id, owner) is None
    store.save_agent_session(local_id, owner, "ses_abcdefgh12345678")
    assert store.get_agent_session(local_id, owner) == "ses_abcdefgh12345678"
    store.save_agent_session(local_id, owner, "01900123-abcd-4567-8901-234567890123", "codex")
    assert store.get_agent_session(local_id, owner, "codex") == "01900123-abcd-4567-8901-234567890123"
    assert store.get_agent_session(local_id, owner) == "ses_abcdefgh12345678"
    store.clear_agent_session(local_id, owner, "codex")
    assert store.get_agent_session(local_id, owner, "codex") is None
    assert store.get_agent_session(local_id, owner) == "ses_abcdefgh12345678"
    with pytest.raises(AppError) as exc:
        store.get_agent_session(local_id, other)
    assert exc.value.status == 404
    assert store.list_history(owner) == ([], False)
    store.close()


def test_soft_review_expansion_claim_is_atomic_and_idempotent(settings):
    first = SessionStore(settings.database_url)
    second = SessionStore(settings.database_url)
    owner = first.create_session(3600)["id"]
    other = first.create_session(3600)["id"]
    barrier = Barrier(2)

    def claim(store):
        barrier.wait()
        return store.claim_soft_review_expansion("cmp_parent", owner)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, (first, second)))
    assert sorted(results) == [False, True]
    assert first.get_soft_review_expansion("cmp_parent", owner) == {"child_comparison_id": None}
    assert first.get_soft_review_expansion("cmp_parent", other) is None

    first.complete_soft_review_expansion("cmp_parent", owner, "cmp_child")
    assert second.get_soft_review_expansion("cmp_parent", owner) == {
        "child_comparison_id": "cmp_child",
    }
    first.release_soft_review_expansion("cmp_parent", owner)
    assert first.get_soft_review_expansion("cmp_parent", owner) == {
        "child_comparison_id": "cmp_child",
    }
    first.close()
    second.close()
def test_conversation_turns_round_trip_and_trim_oldest_first(settings):
    store = SessionStore(settings.database_url)
    store.save_conversation_turn("agt_conv", "first message " + "x" * 7900)
    store.save_conversation_turn("agt_conv", "second")
    text = store.get_conversation_text("agt_conv")
    assert "second" in text
    assert len(text) <= 8000
    assert store.get_conversation_text("agt_nope") is None
    store.save_conversation_turn("agt_conv", "   ")
    assert store.get_conversation_text("agt_conv") == text
    store.close()
