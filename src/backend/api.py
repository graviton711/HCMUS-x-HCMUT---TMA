"""Thin HTTP over the pipeline. Routes validate, modules decide."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from backend.data.catalog import for_settings
from backend.data.sessions import SessionStore
from backend.decide.engine import assess_soft_llm, compare
from backend.errors import AppError
from backend.input.nim import NimClient
from backend.input.pipeline import build_requirement
from backend.normalize.snapshots import rows_to_snapshots
from backend.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = SessionStore(settings.database_url)
    catalog = for_settings(settings)
    nim = NimClient(settings.nvidia_nim_api.get_secret_value(),
                    settings.nvidia_nim_model, settings.nim_timeout_seconds)

    app = FastAPI(title="Tour Decision Backend", version="3.0")

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.get("/", response_class=HTMLResponse)
    async def landing() -> str:
        return "<p>Tour Decision Backend. Docs at <a href='/docs'>/docs</a>.</p>"

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "3.0"}

    @app.post("/requirements")
    async def create_requirement(body: dict[str, Any]) -> dict[str, Any]:
        req = build_requirement(str(body.get("text", "")),
                                body.get("form") if isinstance(body.get("form"), dict) else None,
                                nim)
        store.save_requirement(req)
        return {"requirement": req.model_dump()}

    @app.get("/requirements/{rid}")
    async def get_requirement(rid: str) -> dict[str, Any]:
        return {"requirement": store.get_requirement(rid).model_dump()}

    @app.post("/comparisons")
    async def create_comparison(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("requirement_id"):
            req = store.get_requirement(str(body["requirement_id"]))
        else:
            req = build_requirement(str(body.get("text", "")),
                                    body.get("form") if isinstance(body.get("form"), dict) else None,
                                    nim)
            store.save_requirement(req)
        limit = body.get("candidate_limit", settings.candidate_limit)
        limit = limit if isinstance(limit, int) and 1 <= limit <= 100 else settings.candidate_limit
        tours = rows_to_snapshots(catalog.list_tours(limit))

        def assess(ts, soft):
            return assess_soft_llm(ts, soft, nim.api_key, nim.model, nim.timeout) if nim.configured() else {}

        comp = compare(req, tours, assess if req.soft() and nim.configured() else None)
        store.save_comparison(comp)
        return {"comparison": comp.model_dump()}

    @app.get("/comparisons/{cid}")
    async def get_comparison(cid: str) -> dict[str, Any]:
        return {"comparison": store.get_comparison(cid).model_dump()}

    return app
