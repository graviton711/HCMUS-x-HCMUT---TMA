"""Runtime store for requirements and comparisons.

`DATABASE_URL` picks the driver without changing the SessionStore contract:
`sqlite://…` (file or `:memory:`) for local dev/test, `postgres://…` for a
shared/preview deployment. SQLite stays single-writer WAL; Postgres tables come
from `migrations/004_runtime_store.sql` (the ingest migration runner applies
them — the backend never runs DDL itself).
"""

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


class BaseStore:
    """SQL with shared semantics. Drivers override tables, placeholder, I/O."""

    driver = "sqlite"
    records_table = "records"
    sessions_table = "sessions"
    placeholder = "?"
    # Guard the upsert: an existing row may only be overwritten by its owner.
    # SQLite compares NULL valently with `IS`; Postgres needs `IS NOT DISTINCT FROM`.
    owner_guard = "{t}.owner_session_id IS excluded.owner_session_id"

    # --- driver hooks ---

    def _execute(self, sql: str, params: tuple) -> object:
        raise NotImplementedError

    def _query(self, sql: str, params: tuple) -> list[tuple]:
        raise NotImplementedError

    def _commit(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    # --- store API (identical across drivers) ---

    def create_session(self, ttl_seconds: int) -> dict[str, str]:
        if ttl_seconds < 60:
            raise ValueError("Session lifetime must be at least 60 seconds.")
        now = datetime.now(UTC)
        session_id = f"ses_{uuid4().hex}"
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(seconds=ttl_seconds)
        self._execute(
            self._sql(
                f"INSERT INTO {self.sessions_table}"
                " (id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)"
            ),
            (
                session_id,
                hashlib.sha256(token.encode()).hexdigest(),
                now.isoformat(),
                expires_at.isoformat(),
            ),
        )
        self._commit()
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
        rows = self._query(
            self._sql(
                f"SELECT id, expires_at FROM {self.sessions_table} WHERE token_hash = ?"
            ),
            (token_hash,),
        )
        row = rows[0] if rows else None
        if row is None:
            raise AppError("SESSION_INVALID", "Phiên truy cập không hợp lệ.", 401)
        expires = _parse_dt(row[1])
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
        query = (
            f"SELECT id, kind, created_at FROM {self.records_table} WHERE owner_session_id = ?"
        )
        params: list[object] = [owner_session_id]
        if before is not None:
            query += " AND (created_at < ? OR (created_at = ? AND id < ?))"
            params.extend([before[0], before[0], before[1]])
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(safe_limit + 1)
        rows = self._query(self._sql(query), tuple(params))
        items = [
            {
                "id": str(row[0]),
                "kind": str(row[1]),
                "created_at": _parse_dt(row[2]).isoformat(),
            }
            for row in rows[:safe_limit]
        ]
        return items, len(rows) > safe_limit

    def get_history_item(self, item_id: str, owner_session_id: str) -> dict[str, object]:
        rows = self._query(
            self._sql(
                f"SELECT kind, created_at, payload FROM {self.records_table}"
                " WHERE id = ? AND owner_session_id = ?"
            ),
            (item_id, owner_session_id),
        )
        row = rows[0] if rows else None
        if row is None:
            raise AppError("NOT_FOUND", f"Không tìm thấy history item {item_id}.", 404)
        kind, created_at, payload = row
        if kind == "requirement":
            resource = Requirement.model_validate_json(payload).model_dump()
        elif kind == "comparison":
            resource = Comparison.model_validate_json(payload).model_dump()
        else:
            raise AppError("RECORD_INVALID", "Loại history item không hợp lệ.", 500)
        return {
            "id": item_id,
            "kind": kind,
            "created_at": _parse_dt(created_at).isoformat(),
            "resource": resource,
        }

    # --- internals ---

    def _save(self, kind: str, rid: str, payload: str, owner_session_id: str | None) -> None:
        cursor = self._execute(
            self._sql(
                f"INSERT INTO {self.records_table} (id, kind, payload, created_at, owner_session_id)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (id) DO UPDATE SET payload = excluded.payload,"
                " created_at = excluded.created_at"
                " WHERE " + self.owner_guard.format(t=self.records_table)
            ),
            (rid, kind, payload, now_vn_iso(), owner_session_id),
        )
        if getattr(cursor, "rowcount", 1) != 1:
            raise AppError("OWNER_CONFLICT", "Resource thuộc phiên khác.", 409)
        self._commit()

    def _load(self, kind: str, rid: str, owner_session_id: str | None) -> str:
        scope = " AND owner_session_id IS NULL" if owner_session_id is None else (
            " AND owner_session_id = ?"
        )
        params = (rid, kind) if owner_session_id is None else (rid, kind, owner_session_id)
        rows = self._query(
            self._sql(
                f"SELECT payload FROM {self.records_table} WHERE id = ? AND kind = ?{scope}"
            ),
            params,
        )
        row = rows[0] if rows else None
        if row is None:
            raise AppError("NOT_FOUND", f"Không tìm thấy {kind} {rid}.", 404)
        return str(row[0])

    def _sql(self, sql: str) -> str:
        """Swap the shared `?` placeholders for the driver mark."""
        return sql if self.placeholder == "?" else sql.replace("?", self.placeholder)


class _SqliteStore(BaseStore):
    driver = "sqlite"

    def __init__(self, database_url: str):
        path = database_url.removeprefix("sqlite:///")
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS records"
            " (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,"
            " created_at TEXT NOT NULL, owner_session_id TEXT)"
        )
        self._migrate_owner_column()
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS records_owner_created_idx"
            " ON records (owner_session_id, created_at DESC, id DESC)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions"
            " (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,"
            " created_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
        )
        self._conn.commit()

    def _migrate_owner_column(self) -> None:
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(records)")}
        if "owner_session_id" not in columns:
            self._conn.execute("ALTER TABLE records ADD COLUMN owner_session_id TEXT")
            self._conn.commit()

    def _execute(self, sql: str, params: tuple) -> object:
        return self._conn.execute(sql, params)

    def _query(self, sql: str, params: tuple) -> list[tuple]:
        return self._conn.execute(sql, params).fetchall()

    def _commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class _PostgresStore(BaseStore):
    driver = "postgres"
    records_table = "runtime_records"
    sessions_table = "runtime_sessions"
    placeholder = "%s"
    owner_guard = "{t}.owner_session_id IS NOT DISTINCT FROM EXCLUDED.owner_session_id"

    def __init__(self, database_url: str):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise AppError("STORE_DRIVER_MISSING", "Thiếu psycopg.", 500) from exc
        self._conn = psycopg.connect(database_url, connect_timeout=8, autocommit=True)

    def _execute(self, sql: str, params: tuple) -> object:
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def _query(self, sql: str, params: tuple) -> list[tuple]:
        with self._conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def _commit(self) -> None:
        return None

    def close(self) -> None:
        self._conn.close()


def _parse_dt(value: object) -> datetime:
    """Drivers return datetime or ISO text; compare on instants either way."""
    if isinstance(value, datetime):
        return value
    text = str(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def SessionStore(database_url: str) -> BaseStore:
    """Store factory. Same behavior, driver chosen by DATABASE_URL scheme."""
    if database_url.startswith("postgres"):
        return _PostgresStore(database_url)
    return _SqliteStore(database_url)
