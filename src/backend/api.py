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
    nim = NimClient(settings.nvidia_nim_api.get_secret_value(),
                    settings.nvidia_nim_model, settings.nim_timeout_seconds,
                    prompt=tuning.extract)

    app = FastAPI(title="Tour Decision Backend", version=_version())

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.get("/", response_class=HTMLResponse)
    async def landing() -> str:
        return "<p>Tour Decision Backend. Docs at <a href='/docs'>/docs</a>.</p>"

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": _version()}

    def parse_user(text: str, form: dict[str, Any] | None):
        places = catalog.list_destinations()
        ref_date = now_vn_iso()[:10]
        return build_requirement(text, form, nim, cfg=tuning.input,
                                 known_places=places, ref_date=ref_date)

    @app.post("/requirements")
    async def create_requirement(body: dict[str, Any]) -> dict[str, Any]:
        req = parse_user(str(body.get("text", "")),
                         body.get("form") if isinstance(body.get("form"), dict) else None)
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
            req = parse_user(str(body.get("text", "")),
                             body.get("form") if isinstance(body.get("form"), dict) else None)
            store.save_requirement(req)
        lo, hi = tuning.api.candidate_min, tuning.api.candidate_max
        limit = body.get("candidate_limit", settings.candidate_limit)
        limit = limit if isinstance(limit, int) and lo <= limit <= hi else settings.candidate_limit
        tours = rows_to_snapshots(catalog.list_tours(limit))

        def assess(ts, soft):
            return assess_soft_llm(ts, soft, nim,
                                   prompt=tuning.assess,
                                   excerpt_chars=tuning.decide.excerpt_chars,
                                   quote_chars=tuning.decide.quote_chars,
                                   soft_fields=tuning.decide.soft_fields)

        comp = compare(req, tours, assess if req.soft() and nim.configured() else None,
                       cfg=tuning.decide)
        store.save_comparison(comp)
        return {"comparison": comp.model_dump()}

    @app.get("/comparisons/{cid}")
    async def get_comparison(cid: str) -> dict[str, Any]:
        return {"comparison": store.get_comparison(cid).model_dump()}

    return app
