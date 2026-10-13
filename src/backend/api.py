"""Thin HTTP over the pipeline. Routes validate, modules decide."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.routing import APIRoute

from backend.agent.service import AgentService
from backend.data.catalog import for_settings
from backend.data.sessions import SessionStore
from backend.error_logging import log_app_error, log_unexpected_error
from backend.errors import AppError
from backend.input.pipeline import validate_requirement
from backend.settings import Settings
from backend.workflows import TourWorkflows


class SafeAPIRoute(APIRoute):
    """Normalize route exceptions before Starlette logs raw server errors."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await original_handler(request)
            except AppError as exc:
                log_app_error(exc, transport="http", operation=self.path)
                return JSONResponse(status_code=exc.status, content=exc.payload())
            except Exception as exc:
                log_unexpected_error(exc, transport="http", operation=self.path)
                error = AppError("INTERNAL_ERROR", "An internal error occurred.", 500)
                return JSONResponse(status_code=error.status, content=error.payload())

        return safe_handler


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
    workflows = TourWorkflows(settings, catalog)
    agent = AgentService(settings, store)

    app = FastAPI(title="Tour Decision Backend", version=_version())
    app.router.route_class = SafeAPIRoute

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    def operation(request: Request) -> str:
        route = request.scope.get("route")
        return str(getattr(route, "path", "unknown"))

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        log_app_error(exc, transport="http", operation=operation(request))
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

    @app.post("/requirements")
    async def create_requirement(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if isinstance(body.get("conditions"), list):
            req = validate_requirement(
                body.get("raw_text", ""), body["conditions"], body.get("travelers", 1)
            )
        else:
            from backend.input.pipeline import requirement_from_form

            req = requirement_from_form(body.get("form"))
        store.save_requirement(req, owner_id)
        return {"requirement": req.model_dump()}

    @app.get("/requirements/{rid}")
    async def get_requirement(rid: str, request: Request) -> dict[str, Any]:
        return {"requirement": store.get_requirement(rid, owner_session(request)).model_dump()}

    @app.post("/comparisons")
    async def create_comparison(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if not isinstance(body.get("requirement_id"), str):
            raise AppError("REQUIREMENT_REQUIRED", "A structured requirement ID is required.", 422)
        req = store.get_requirement(body["requirement_id"], owner_id)
        lo, hi = tuning.api.candidate_min, tuning.api.candidate_max
        limit = body.get("candidate_limit", settings.candidate_limit)
        limit = limit if isinstance(limit, int) and lo <= limit <= hi else settings.candidate_limit
        comp = workflows.comparison(req, limit)
        store.save_comparison(comp, owner_id)
        return {"comparison": comp.model_dump()}

    @app.post("/agent/sessions", status_code=201)
    async def create_agent_session(request: Request) -> dict[str, str]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for chat.", 401)
        return agent.create_session(owner_id)

    @app.post("/agent/sessions/{agent_session_id}/messages")
    async def agent_message(agent_session_id: str, body: dict[str, Any], request: Request):
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for chat.", 401)
        if "text/event-stream" in request.headers.get("accept", ""):

            async def stream_events():
                try:
                    async for event in agent.stream_message(
                        owner_id, agent_session_id, body.get("message", "")
                    ):
                        event_type = event.get("type", "progress")
                        payload = (
                            event.get("response", {})
                            if event_type == "result"
                            else {key: value for key, value in event.items() if key != "type"}
                        )
                        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        yield f"event: {event_type}\ndata: {data}\n\n"
                except AppError as exc:
                    log_app_error(exc, transport="sse", operation="agent_message")
                    data = json.dumps(
                        {"code": exc.code, "message": exc.message},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"
                except Exception as exc:
                    log_unexpected_error(exc, transport="sse", operation="agent_message")
                    data = json.dumps(
                        {"code": "INTERNAL_ERROR", "message": "An internal error occurred."},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
            )
        return await agent.message(owner_id, agent_session_id, body.get("message", ""))

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
