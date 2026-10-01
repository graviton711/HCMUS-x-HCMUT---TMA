import asyncio
import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select

from api.dto import CreateComparison, CreateRequirement, Form, PatchRequirement
from api.runtime_lock import RuntimeLock
from api.settings import Settings
from api.store import Store, resources
from api.worker import Worker
from data_access.gateway import DataGateway
from domain.common import AppError, now, uid
from domain.requirements import Message, Target
from requirements.edits import answer_edits, apply_edits, form_requirement
from requirements.nim import NimGateway


class Limits:
    def __init__(self):
        self.windows = defaultdict(deque)

    def check(self, key, limit):
        timestamp = time.monotonic()
        window = self.windows[key]
        while window and window[0] < timestamp - 60:
            window.popleft()
        if len(window) >= limit:
            raise AppError("RATE_LIMITED", "Có quá nhiều yêu cầu; hãy thử lại sau.", 429, retryable=True)
        window.append(timestamp)
        if len(self.windows) > 10000:
            self.windows = defaultdict(deque, {k: v for k, v in self.windows.items() if v and v[-1] >= timestamp - 60})


def create_app(settings: Settings | None = None, *, nim=None, gateway=None) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings)
    gateway = gateway or DataGateway(settings)
    worker = Worker(store, nim or NimGateway(settings), gateway)
    lock, limits = RuntimeLock(settings.database_url), Limits()

    @asynccontextmanager
    async def lifespan(app):
        lock.acquire()
        task = None
        try:
            store.recover()
            store.purge()
            task = asyncio.create_task(worker.run()) if settings.worker_enabled else None
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            store.engine.dispose()
            lock.release()

    app = FastAPI(title="Tour Decision Backend", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.worker, app.state.gateway = store, worker, gateway
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse({"error": exc.payload()}, status_code=exc.status,
                            headers={"Retry-After": "60"} if exc.status == 429 else None)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        error = AppError("INVALID_INPUT", "Dữ liệu không đúng contract; kiểm tra field và kiểu dữ liệu.")
        payload = error.payload()
        payload["details"] = {"fields": [{"path": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()[:20]]}
        return JSONResponse({"error": payload}, status_code=422)

    @app.middleware("http")
    async def request_limit(request: Request, call_next):
        if request.method in {"POST", "PATCH"}:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > 65536):
                return JSONResponse({"error": AppError("INPUT_TOO_LARGE", "Request vượt 64 KB.", 413).payload()}, status_code=413)
            size, parts = 0, []
            async for part in request.stream():
                size += len(part)
                if size > 65536:
                    return JSONResponse({"error": AppError("INPUT_TOO_LARGE", "Request vượt 64 KB.", 413).payload()}, status_code=413)
                parts.append(part)
            request._body = b"".join(parts)
        return await call_next(request)

    async def owner(request: Request, authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise AppError("UNAUTHORIZED", "Cần bearer session token.", 401)
        result = store.authenticate(authorization[7:])
        limits.check(f"owner:{result}", 120)
        return result

    def mutate(owner_id, key, route, body, callback):
        code, result = store.mutate(owner_id, key, {"route": route, "body": body}, callback)
        return JSONResponse(result, status_code=code)

    @app.get("/health")
    async def health():
        return {"status": "ok", "data_origin": "synthetic" if settings.data_provider == "fixture" else "source",
                "worker_enabled": settings.worker_enabled, "schema_version": "1.0"}

    @app.post("/v1/sessions", status_code=201)
    async def session(request: Request):
        limits.check(f"sessions:{request.client.host if request.client else 'local'}", 20)
        return store.new_session()

    @app.get("/v1/sources")
    async def sources(owner_id: str = Depends(owner)):
        return {"origin": "synthetic" if settings.data_provider == "fixture" else "source",
                "sources": [s.model_dump() for s in gateway.registry]}

    @app.post("/v1/requirements")
    async def create_requirement(body: CreateRequirement, owner_id: str = Depends(owner), idempotency_key: str | None = Header(default=None)):
        def action(c):
            rid = uid("req")
            targets = [Target(target_id=uid("target"), url=url) for url in body.urls]
            store.add_resource(c, owner_id, rid, "requirement", {})
            if body.text is not None:
                message = Message(id=uid("msg"), text=body.text, received_at=now().isoformat())
                jid = store.add_job(c, owner_id, rid, "parse", {"expected_revision": 0, "message": message.model_dump(),
                    "mode": body.mode, "timezone": body.timezone, "targets": [t.model_dump() for t in targets]})
                return [202, {"requirement_id": rid, "revision": 0, "job_id": jid, "status": "queued"}]
            requirement = form_requirement(body.form or Form(), requirement_id=rid, mode=body.mode, timezone=body.timezone, targets=targets)
            store.add_revision(c, owner_id, requirement, 0)
            return [201, requirement.model_dump(mode="json")]
        return mutate(owner_id, idempotency_key, "create_requirement", body.model_dump(mode="json"), action)

    @app.get("/v1/requirements/{resource_id}")
    async def get_requirement(resource_id: str, owner_id: str = Depends(owner)):
        resource = store.resource(owner_id, resource_id, kind="requirement")
        if resource["revision"] == 0:
            return {"id": resource_id, "revision": 0, "status": resource["status"]}
        return {**store.revision(owner_id, resource_id).model_dump(mode="json"), "status": resource["status"]}

    @app.patch("/v1/requirements/{resource_id}")
    async def patch_requirement(resource_id: str, body: PatchRequirement, owner_id: str = Depends(owner), idempotency_key: str | None = Header(default=None)):
        def action(c):
            previous = store.revision(owner_id, resource_id, connection=c)
            if previous.revision != body.expected_revision:
                raise AppError("REVISION_CONFLICT", "Revision đã thay đổi; tải lại trước khi sửa.", 409)
            if body.text is not None:
                message = Message(id=uid("msg"), text=body.text, received_at=now().isoformat())
                jid = store.add_job(c, owner_id, resource_id, "parse", {"expected_revision": body.expected_revision,
                    "message": message.model_dump(), "mode": previous.mode, "timezone": previous.timezone,
                    "targets": [t.model_dump() for t in previous.targets]})
                return [202, {"requirement_id": resource_id, "revision": previous.revision, "job_id": jid, "status": "queued"}]
            edits = body.edits if body.edits is not None else answer_edits(previous, body.answers)
            requirement = apply_edits(previous, edits)
            store.add_revision(c, owner_id, requirement, previous.revision)
            return [200, requirement.model_dump(mode="json")]
        return mutate(owner_id, idempotency_key, f"patch:{resource_id}", body.model_dump(mode="json"), action)

    @app.post("/v1/comparisons")
    async def create_comparison(body: CreateComparison, owner_id: str = Depends(owner), idempotency_key: str | None = Header(default=None)):
        def action(c):
            requirement = store.revision(owner_id, body.requirement_id, body.revision, c)
            if not requirement.readiness.can_collect_data:
                raise AppError("REQUIREMENT_NOT_READY", "Cần làm rõ phạm vi tìm kiếm trước khi thu thập.", 409)
            if body.reuse_comparison_id:
                prior = store.resource(owner_id, body.reuse_comparison_id, c, "comparison")
                payload = json.loads(prior["payload"])
                if prior["status"] not in {"succeeded", "partial"} or payload["result"]["requirement_id"] != requirement.id:
                    raise AppError("OFFER_SELECTION_INVALID", "Comparison cũ chưa hoàn tất hoặc thuộc nhu cầu khác.", 409)
                old_targets = {t["target_id"]: t["url"] for t in payload["result"]["targets"]}
                if old_targets != {t.target_id: t.url for t in requirement.targets}:
                    raise AppError("OFFER_SELECTION_INVALID", "Targets đã đổi; cần thu thập lại.", 409)
            cid = uid("comparison")
            store.add_resource(c, owner_id, cid, "comparison", body.model_dump(mode="json"), revision=body.revision)
            jid = store.add_job(c, owner_id, cid, "comparison", body.model_dump(mode="json"))
            return [202, {"comparison_id": cid, "job_id": jid, "requirement_id": requirement.id,
                          "revision": requirement.revision, "status": "queued"}]
        return mutate(owner_id, idempotency_key, "create_comparison", body.model_dump(mode="json"), action)

    @app.get("/v1/jobs/{job_id}")
    async def get_job(job_id: str, owner_id: str = Depends(owner)):
        return store.job(owner_id, job_id)

    @app.post("/v1/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str, owner_id: str = Depends(owner), idempotency_key: str | None = Header(default=None)):
        return mutate(owner_id, idempotency_key, f"cancel:{job_id}", {}, lambda c: [200, store.cancel(c, owner_id, job_id)])

    @app.get("/v1/comparisons/{resource_id}")
    async def get_comparison(resource_id: str, owner_id: str = Depends(owner)):
        resource = store.resource(owner_id, resource_id, kind="comparison")
        payload = json.loads(resource["payload"])
        return {"id": resource_id, "status": resource["status"], "result": payload.get("result")}

    @app.get("/v1/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str, owner_id: str = Depends(owner)):
        with store.engine.connect() as c:
            rows = c.execute(select(resources.c.payload).where(resources.c.owner == owner_id, resources.c.kind == "comparison",
                                                               resources.c.status.in_(["succeeded", "partial"]))).scalars()
            for row in rows:
                for evidence in json.loads(row).get("crawl", {}).get("evidence", []):
                    if evidence["id"] == evidence_id:
                        return evidence
        raise AppError("NOT_FOUND", "Không tìm thấy evidence.", 404)

    return app
