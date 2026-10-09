"""SQLite session store for requirements and comparisons. Single-writer, WAL."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.errors import AppError
from backend.models import Comparison, Requirement


def _connect(database_url: str) -> sqlite3.Connection:
    path = database_url.removeprefix("sqlite:///")
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS records"
        " (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT NOT NULL)"
    )
    return conn


class SessionStore:
    def __init__(self, database_url: str):
        self._conn = _connect(database_url)

    def save_requirement(self, req: Requirement) -> None:
        self._save("requirement", req.id, req.model_dump_json())

    def get_requirement(self, rid: str) -> Requirement:
        return Requirement.model_validate_json(self._load("requirement", rid))

    def save_comparison(self, comp: Comparison) -> None:
        self._save("comparison", comp.id, comp.model_dump_json())

    def get_comparison(self, cid: str) -> Comparison:
        return Comparison.model_validate_json(self._load("comparison", cid))

    def _save(self, kind: str, rid: str, payload: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO records (id, kind, payload, created_at)"
            " VALUES (?, ?, ?, ?)",
            (rid, kind, payload, now),
        )
        self._conn.commit()

    def _load(self, kind: str, rid: str) -> str:
        row = self._conn.execute(
            "SELECT payload FROM records WHERE id = ? AND kind = ?", (rid, kind)
        ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", f"Không tìm thấy {kind} {rid}.", 404)
        return row[0]

    def close(self) -> None:
        self._conn.close()
