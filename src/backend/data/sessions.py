"""SQLite session store for requirements and comparisons. Single-writer, WAL."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from backend.errors import AppError
from backend.models import Comparison, Requirement
from shared import now_vn_iso


def _connect(database_url: str) -> sqlite3.Connection:
    path = database_url.removeprefix("sqlite:///")
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS records"
        " (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT NOT NULL, owner_session_id TEXT)"
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(records)")}
    if "owner_session_id" not in columns:
        conn.execute("ALTER TABLE records ADD COLUMN owner_session_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS records_owner_created_idx"
        " ON records (owner_session_id, created_at DESC, id DESC)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions"
        " (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,"
        " created_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
    )
    return conn


class SessionStore:
    def __init__(self, database_url: str):
        self._conn = _connect(database_url)

    def create_session(self, ttl_seconds: int) -> dict[str, str]:
        if ttl_seconds < 60:
            raise ValueError("Session lifetime must be at least 60 seconds.")
        now = datetime.now(UTC)
        session_id = f"ses_{uuid4().hex}"
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(seconds=ttl_seconds)
        self._conn.execute(
            "INSERT INTO sessions (id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, hashlib.sha256(token.encode()).hexdigest(), now.isoformat(), expires_at.isoformat()),
        )
        self._conn.commit()
        return {
            "id": session_id,
            "session_id": session_id,
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat(),
        }

    def authenticate_session(self, token: str) -> str:
        if not token:
            raise AppError("SESSION_INVALID", "Phiên truy cập không hợp lệ.", 401)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = self._conn.execute(
            "SELECT id, expires_at FROM sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if row is None:
            raise AppError("SESSION_INVALID", "Phiên truy cập không hợp lệ.", 401)
        expires = datetime.fromisoformat(row[1])
        if expires.tzinfo is None or expires <= datetime.now(UTC):
            raise AppError("SESSION_EXPIRED", "Phiên truy cập đã hết hạn.", 401)
        return str(row[0])

    def save_requirement(self, req: Requirement, owner_session_id: str | None = None) -> None:
        self._save("requirement", req.id, req.model_dump_json(), owner_session_id)

    def get_requirement(self, rid: str, owner_session_id: str | None = None) -> Requirement:
        return Requirement.model_validate_json(self._load("requirement", rid, owner_session_id))

    def save_comparison(self, comp: Comparison, owner_session_id: str | None = None) -> None:
        self._save("comparison", comp.id, comp.model_dump_json(), owner_session_id)

    def get_comparison(self, cid: str, owner_session_id: str | None = None) -> Comparison:
        return Comparison.model_validate_json(self._load("comparison", cid, owner_session_id))

    def list_history(
        self,
        owner_session_id: str,
        limit: int = 100,
        before: tuple[str, str] | None = None,
    ) -> tuple[list[dict[str, str]], bool]:
        safe_limit = max(1, min(limit, 100))
        query = "SELECT id, kind, created_at FROM records WHERE owner_session_id = ?"
        params: list[str | int] = [owner_session_id]
        if before is not None:
            query += " AND (created_at < ? OR (created_at = ? AND id < ?))"
            params.extend([before[0], before[0], before[1]])
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(safe_limit + 1)
        rows = self._conn.execute(query, params).fetchall()
        has_more = len(rows) > safe_limit
        items = [
            {"id": str(row[0]), "kind": str(row[1]), "created_at": str(row[2])} for row in rows[:safe_limit]
        ]
        return items, has_more

    def get_history_item(self, item_id: str, owner_session_id: str) -> dict[str, object]:
        row = self._conn.execute(
            "SELECT kind, created_at, payload FROM records WHERE id = ? AND owner_session_id = ?",
            (item_id, owner_session_id),
        ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", f"Không tìm thấy history item {item_id}.", 404)
        kind, created_at, payload = row
        if kind == "requirement":
            resource = Requirement.model_validate_json(payload).model_dump()
        elif kind == "comparison":
            resource = Comparison.model_validate_json(payload).model_dump()
        else:
            raise AppError("RECORD_INVALID", "Loại history item không hợp lệ.", 500)
        return {"id": item_id, "kind": kind, "created_at": created_at, "resource": resource}

    def _save(self, kind: str, rid: str, payload: str, owner_session_id: str | None) -> None:
        now = now_vn_iso()
        cursor = self._conn.execute(
            "INSERT INTO records (id, kind, payload, created_at, owner_session_id)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET payload = excluded.payload,"
            " created_at = excluded.created_at"
            " WHERE records.owner_session_id IS excluded.owner_session_id",
            (rid, kind, payload, now, owner_session_id),
        )
        if cursor.rowcount != 1:
            raise AppError("OWNER_CONFLICT", "Resource thuộc phiên khác.", 409)
        self._conn.commit()

    def _load(self, kind: str, rid: str, owner_session_id: str | None) -> str:
        if owner_session_id is None:
            row = self._conn.execute(
                "SELECT payload FROM records WHERE id = ? AND kind = ? AND owner_session_id IS NULL",
                (rid, kind),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT payload FROM records WHERE id = ? AND kind = ? AND owner_session_id = ?",
                (rid, kind, owner_session_id),
            ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", f"Không tìm thấy {kind} {rid}.", 404)
        return row[0]

    def close(self) -> None:
        self._conn.close()
