"""Thin HTTP over the pipeline. Routes validate, modules decide."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from backend.data.catalog import for_settings
from backend.data.sessions import SessionStore
from backend.decide.engine import assess_soft_llm, compare
from backend.errors import AppError
from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement
from backend.normalize.snapshots import rows_to_snapshots
from backend.settings import Settings
from shared import now_vn_iso


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("mlai")
    except PackageNotFoundError:
        return "dev"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    tuning = settings.tuning
    store = SessionStore(settings.database_url)
    catalog = for_settings(settings)
    nim = NimClient(
        settings.nvidia_nim_api.get_secret_value(),
        settings.nvidia_nim_model,
        httpx.Timeout(settings.nim_timeout_seconds, connect=settings.nim_connect_timeout_s),
        prompt=tuning.extract,
    )

    app = FastAPI(title="Tour Decision Backend", version=_version())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.get("/", response_class=HTMLResponse)
    async def landing() -> str:
        return "<p>Tour Decision Backend. Docs at <a href='/docs'>/docs</a>.</p>"

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": _version()}

    def owner_session(request: Request) -> str | None:
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        scheme, separator, token = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            raise AppError("SESSION_INVALID", "Invalid access session.", 401)
        return store.authenticate_session(token.strip())

    @app.post("/sessions", status_code=201)
    async def create_session() -> dict[str, str]:
        return store.create_session(tuning.api.session_ttl_seconds)

    @app.get("/catalog")
    async def get_catalog() -> dict[str, list[str]]:
        return {"destinations": catalog.list_destinations()}

    def parse_user(text: str, form: dict[str, Any] | None, drop: Any = None):
        places = catalog.list_destinations()
        ref_date = now_vn_iso()[:10]
        drop_fields = [str(f) for f in drop] if isinstance(drop, list) else None
        return build_requirement(text, form, nim, cfg=tuning.input, known_places=places,
                                 ref_date=ref_date, drop_fields=drop_fields)

    @app.post("/requirements")
    async def create_requirement(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        req = parse_user(
            str(body.get("text", "")), body.get("form") if isinstance(body.get("form"), dict) else None,
            body.get("drop_fields"),
        )
        store.save_requirement(req, owner_id)
        return {"requirement": req.model_dump()}

    @app.get("/requirements/{rid}")
    async def get_requirement(rid: str, request: Request) -> dict[str, Any]:
        return {"requirement": store.get_requirement(rid, owner_session(request)).model_dump()}

    @app.post("/comparisons")
    async def create_comparison(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if body.get("requirement_id"):
            req = store.get_requirement(str(body["requirement_id"]), owner_id)
        else:
            req = parse_user(
                str(body.get("text", "")), body.get("form") if isinstance(body.get("form"), dict) else None,
                body.get("drop_fields"),
            )
            store.save_requirement(req, owner_id)
        lo, hi = tuning.api.candidate_min, tuning.api.candidate_max
        limit = body.get("candidate_limit", settings.candidate_limit)
        limit = limit if isinstance(limit, int) and lo <= limit <= hi else settings.candidate_limit
        tours = rows_to_snapshots(
            catalog.list_tours(limit),
            trusted_domains=settings.supabase_tour_trusted_domains,
            freshness_seconds=settings.supabase_tour_freshness_seconds,
            require_trusted_pricing=settings.data_provider == "supabase",
        )

        def assess(ts, soft):
            return assess_soft_llm(
                ts,
                soft,
                nim,
                prompt=tuning.assess,
                excerpt_chars=tuning.decide.excerpt_chars,
                quote_chars=tuning.decide.quote_chars,
                soft_fields=tuning.decide.soft_fields,
            )

        comp = compare(req, tours, assess if req.soft() and nim.configured() else None, cfg=tuning.decide)
        store.save_comparison(comp, owner_id)
        return {"comparison": comp.model_dump()}

    @app.get("/comparisons/{cid}")
    async def get_comparison(cid: str, request: Request) -> dict[str, Any]:
        return {"comparison": store.get_comparison(cid, owner_session(request)).model_dump()}

    @app.get("/history")
    async def get_history(
        request: Request,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required to read history.", 401)
        before = None
        if cursor:
            try:
                padded = cursor + "=" * (-len(cursor) % 4)
                decoded = base64.urlsafe_b64decode(padded.encode()).decode("utf-8")
                cursor_data = json.loads(decoded)
                if (
                    not isinstance(cursor_data, list)
                    or len(cursor_data) != 2
                    or not all(isinstance(value, str) for value in cursor_data)
                ):
                    raise ValueError
                before = (cursor_data[0], cursor_data[1])
            except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
                raise AppError("CURSOR_INVALID", "Invalid history cursor.", 400) from None

        page_size = max(1, min(limit, 100))
        items, has_more = store.list_history(owner_id, page_size, before)
        next_cursor = None
        if has_more and items:
            last = items[-1]
            encoded = json.dumps([last["created_at"], last["id"]], separators=(",", ":"))
            next_cursor = base64.urlsafe_b64encode(encoded.encode()).decode().rstrip("=")
        return {"items": items, "next_cursor": next_cursor}

    @app.get("/history/{item_id}")
    async def get_history_item(item_id: str, request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required to read history.", 401)
        return store.get_history_item(item_id, owner_id)

    return app
