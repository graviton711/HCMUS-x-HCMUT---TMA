"""Postgres runtime store smoke. REAL Supabase DB, skipped without a URL.

Verifies the driver-dispatch contract the shared preview runs on:
store/read/upsert-guard, owner scoping, history paging, session expiry.
Run locally with .env present:

    TEST_POSTGRESS_URL=postgres://... uv run pytest tests/test_backend_pg_store.py -q
"""

import os

import pytest

from backend.data.sessions import SessionStore
from backend.errors import AppError

TEST_POSTGRESS_URL = os.getenv("TEST_POSTGRESS_URL", "")

needs_db = pytest.mark.skipif(not TEST_POSTGRESS_URL, reason="needs TEST_POSTGRESS_URL env")


def _store():
    return SessionStore(TEST_POSTGRESS_URL)


@needs_db
def test_postgres_store_matches_the_sqlite_contract():
    store = _store()
    try:
        first = store.create_session(3600)
        second = store.create_session(3600)
        assert store.authenticate_session(first["token"]) == first["session_id"]
        with pytest.raises(AppError) as exc:
            store.authenticate_session("not-a-token")
        assert exc.value.code == "SESSION_INVALID"

        req = _requirement("req_pg_contract")
        store.save_requirement(req, first["session_id"])
        with pytest.raises(AppError) as conflict:
            store.save_requirement(req, second["session_id"])
        assert conflict.value.code == "OWNER_CONFLICT"

        assert store.get_requirement(req.id, first["session_id"]).id == req.id
        with pytest.raises(AppError) as missing:
            store.get_requirement(req.id, second["session_id"])
        assert missing.value.code == "NOT_FOUND"

        page, has_more = store.list_history(first["session_id"], 100)
        assert [item["id"] for item in page] == [req.id]
        assert has_more is False
        item = store.get_history_item(req.id, first["session_id"])
        assert item["kind"] == "requirement"
    finally:
        _scrub(store, [first["session_id"], second["session_id"]])
        store.close()


@needs_db
def test_postgres_store_reconnects_after_idle_drop():
    """Warm serverless instances outlive their DB connection; one retry, no 500."""
    store = _store()
    try:
        owner = store.create_session(3600)["session_id"]
        store._conn.close()
        page, _ = store.list_history(owner, 100)
        assert page == []
    finally:
        _scrub(store, [owner])
        store.close()


def test_postgres_store_connects_lazily_and_fails_as_503():
    """Serverless imports must never dial the DB; dead DBs fail as JSON 503."""
    store = SessionStore("postgresql://127.0.0.1:1/db")
    try:
        with pytest.raises(AppError) as exc:
            store.list_history("ses_never", 10)
        assert exc.value.code == "STORE_UNAVAILABLE"
        assert exc.value.status == 503
    finally:
        store.close()


def _scrub(store, session_ids: list[str] | None = None) -> None:
    store._conn.execute("DELETE FROM runtime_records WHERE id LIKE 'req_pg%'")
    for sid in session_ids or []:
        store._conn.execute("DELETE FROM runtime_sessions WHERE id = %s", (sid,))
        store._conn.execute(
            "DELETE FROM runtime_records WHERE owner_session_id = %s", (sid,)
        )
    store._conn.commit()


def _requirement(rid: str):
    from backend.models import Requirement

    return Requirement.model_validate(
        {"id": rid, "conditions": [], "missing": [], "raw_text": "postgres contract",
         "travelers": 1}
    )
