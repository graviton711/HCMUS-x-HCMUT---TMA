"""Vercel entrypoint adapter. No network, no real credentials needed.

Importing backend.vercel_app executes create_app(), so these tests pin
DATABASE_URL to in-memory SQLite and never touch the real .env database.
"""

import importlib
import sys

import pytest


def _fresh_import():
    sys.modules.pop("backend.vercel_app", None)
    return importlib.import_module("backend.vercel_app")


def test_adapter_exposes_wsgi_app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("VERCEL", raising=False)
    module = _fresh_import()
    assert getattr(module.app, "title", "") == "Tour Decision Backend"


def test_adapter_rejects_sqlite_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/backend.db")
    sys.modules.pop("backend.vercel_app", None)
    with pytest.raises(RuntimeError, match="postgres"):
        importlib.import_module("backend.vercel_app")
    sys.modules.pop("backend.vercel_app", None)
