"""Vercel entrypoint adapter. No network, no real credentials needed.

Importing vercel_backend executes create_app(), so these tests pin
DATABASE_URL to in-memory SQLite and never touch the real .env database.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1] / "vercel_backend.py"


def _fresh_import():
    sys.modules.pop("vercel_backend", None)
    spec = importlib.util.spec_from_file_location("vercel_backend", _ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("vercel_backend", None)
        raise
    sys.modules["vercel_backend"] = module
    return module


def test_adapter_exposes_wsgi_app(monkeypatch):
    from sample_rows import StaticCatalog

    import backend.api as backend_api

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("VERCEL", raising=False)
    # No SUPABASE_TOUR_DB_URL offline: serve the in-memory sample catalog.
    monkeypatch.setattr(backend_api, "for_settings", lambda _settings: StaticCatalog())
    try:
        module = _fresh_import()
        assert getattr(module.app, "title", "") == "Tour Decision Backend"
    finally:
        sys.modules.pop("vercel_backend", None)


def test_adapter_rejects_sqlite_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/backend.db")
    with pytest.raises(RuntimeError, match="postgres"):
        _fresh_import()
    assert "vercel_backend" not in sys.modules
