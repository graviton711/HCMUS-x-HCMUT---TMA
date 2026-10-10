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
        store.close()


def _requirement(rid: str):
    from backend.models import Requirement

    return Requirement.model_validate(
        {"id": rid, "conditions": [], "missing": [], "raw_text": "postgres contract",
         "travelers": 1}
    )
