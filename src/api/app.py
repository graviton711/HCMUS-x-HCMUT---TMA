import asyncio
import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

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
            self.windows = defaultdict(
                deque, {k: v for k, v in self.windows.items() if v and v[-1] >= timestamp - 60}
            )


def create_app(
    settings: Settings | None = None,
    *,
    nim=None,
    gateway=None,
    access_checker=None,
    semantic_gateway=None,
    what_if_gateway=None,
    auth_transport=None,
    profile_transport=None,
) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings)
    from api.auth.service import Identity

    identity = Identity(store, auth_transport)
    gateway = gateway or DataGateway(settings)
    worker = Worker(store, nim or NimGateway(settings), gateway)
    from api.v2.admin import Admin, bootstrap
    from api.v2.service import Service

    bootstrap(store, gateway)
    worker.v2 = Service(
        store, worker.nim, gateway, semantic_gateway=semantic_gateway, what_if_gateway=what_if_gateway
    )
    worker.v2.admin = Admin(store, worker.v2, access_checker)
    lock, limits = RuntimeLock(settings.database_url), Limits()

    @asynccontextmanager
    async def lifespan(app):
        lock.acquire()
        task = None
        try:
            store.recover()
            store.purge()
            task = asyncio.create_task(worker.run()) if settings.worker_enabled else None
            app.state.worker_task = task
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            store.engine.dispose()
            if hasattr(gateway, "close"):
                gateway.close()
            lock.release()

    app = FastAPI(
        title="Tour Decision Backend",
        version="0.2.0",
        lifespan=lifespan,
        description="""Backend v2 đã có tại nhóm **v2**: session → requirement/proposal → confirm → comparison/job/events.
Xem `examples/backend-v2.md` để nối frontend. Dùng `/v2/catalog` lấy fields, controls và limits.
Nhập text cần NIM; URL-only có proposal cần confirm. Form đầy đủ/rõ tạo revision 1;
form thiếu/chưa rõ tạo draft + proposal. Form/text cần đủ năm core fields trước confirm/search.
Đọc completeness và readiness.can_confirm/can_search; hướng dẫn `examples/backend-personalized-v2.md`.
Frontend React gọi v2; `/auth` dùng Supabase Auth, `/v2/history` lấy lịch sử theo owner.
What-if tạo đề xuất sửa nhu cầu, vẫn cần review/confirm rồi search. API v1 tiếp tục hoạt động:

**Kho Supabase thật:** cấu hình `DATA_PROVIDER=supabase`, dùng nhóm **v2** và URL tour có trong catalog.
Kiểm tra `/health` thấy data_provider=supabase; `probe-supabase` kiểm tra counts và quyền chỉ đọc.
Nguồn opt-in qua SUPABASE_TOUR_TRUSTED_DOMAINS dùng dữ liệu đã kiểm tra với trạng thái catalog_validated.
Giá thiếu coverage, ngày thiếu TTL và dữ kiện không được hỗ trợ vẫn unknown;
comparison thành công không có nghĩa mọi điều kiện đã được chứng minh.
Hướng dẫn từng bước: `examples/backend-supabase-v2.md`. Provider Supabase thu thập qua v2;
các bước v1 dưới đây dùng fixture/http.

Thử API v1 theo thứ tự:

1. Execute **POST /v1/sessions**, sao chép giá trị `token` trong response.
2. Bấm **Authorize**, dán riêng token (không thêm `Bearer`). Giữ cùng session cho các bước sau.
3. **POST /v1/requirements**: chọn example **So sánh URL mô phỏng** để thử với dữ liệu fixture,
   không cần NIM/crawler. Response 201 trả `id` và `revision: 1`.
   Với example nhập nhu cầu, response 202 trả `requirement_id` và `job_id`;
   đợi job succeeded rồi GET requirement để lấy revision đã parse.
4. **POST /v1/comparisons**: thay `requirement_id` và `revision` bằng giá trị thật ở bước 3.
   Lần đầu chỉ cần hai field này. Response 202 trả `comparison_id` và `job_id`.
5. GET job đến khi kết thúc, rồi GET comparison để xem kết quả.

Session/requirement/comparison được lưu khi request hợp lệ. Refresh SQLite viewer để thấy dòng mới.
401: kiểm tra token; 404: kiểm tra ID và session; 422: kiểm tra request body.
Các URL `.invalid` là dữ liệu mô phỏng, chỉ dùng với `DATA_PROVIDER=fixture`.
""",
    )
    app.state.store, app.state.worker, app.state.gateway = store, worker, gateway
    app.state.identity = identity
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    def error_body(request, payload):
        return {
            **(
                {"schema_version": "2.0-draft", "request_id": request.state.request_id}
                if request.url.path.startswith("/v2/")
                else {}
            ),
            "error": payload,
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if not request.url.path.startswith("/v2/"):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
        error = AppError(
            "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
            "Không tìm thấy endpoint." if exc.status_code == 404 else "HTTP request không hợp lệ.",
            exc.status_code,
        )
        return JSONResponse(
            error_body(request, error.payload()), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(
            error_body(request, exc.payload()),
            status_code=exc.status,
            headers={"Retry-After": "60"} if exc.status == 429 else None,
        )

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        error = AppError("INVALID_INPUT", "Dữ liệu không đúng contract; kiểm tra field và kiểu dữ liệu.")
        payload = error.payload()
        payload["details"] = {
            "fields": [{"path": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()[:20]]
        }
        return JSONResponse(error_body(request, payload), status_code=422)

    @app.middleware("http")
    async def request_limit(request: Request, call_next):
        request.state.request_id = uid("request")
        if request.method in {"POST", "PATCH"}:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > 65536):
                return JSONResponse(
                    error_body(request, AppError("INPUT_TOO_LARGE", "Request vượt 64 KB.", 413).payload()),
                    status_code=413,
                )
            size, parts = 0, []
            async for part in request.stream():
                size += len(part)
                if size > 65536:
                    return JSONResponse(
                        error_body(
                            request, AppError("INPUT_TOO_LARGE", "Request vượt 64 KB.", 413).payload()
                        ),
                        status_code=413,
                    )
                parts.append(part)
            request._body = b"".join(parts)
        return await call_next(request)

    session_bearer = HTTPBearer(
        auto_error=False,
        scheme_name="SessionBearer",
        description="Tạo POST /v1/sessions, dán riêng giá trị token vào đây (không thêm Bearer).",
    )

    async def owner(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(session_bearer)]):
        if credentials is None:
            raise AppError("UNAUTHORIZED", "Cần bearer session token.", 401)
        result = store.authenticate(credentials.credentials)
        limits.check(f"owner:{result}", 120)
        return result

    async def owner_v2(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(session_bearer)]):
        if credentials is None:
            raise AppError("UNAUTHORIZED", "Cần bearer session hoặc tài khoản.", 401)
        token = credentials.credentials
        if token.count(".") == 2:
            result = await identity.owner(token)
        else:
            result = store.authenticate(token)
        limits.check(f"owner:{result}", 120)
        return result

    def mutate(owner_id, key, route, body, callback):
        code, result = store.mutate(owner_id, key, {"route": route, "body": body}, callback)
        return JSONResponse(result, status_code=code)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home():
        return HTMLResponse("""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Tour Decision — Backend</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 48px 24px;
           color: #173047; background: #f4f7fa; line-height: 1.6; }
    main { max-width: 640px; margin: auto; }
    h1 { line-height: 1.2; }
    a { color: #075a9c; }
    nav { display: flex; flex-wrap: wrap; gap: 16px; margin: 24px 0; }
    nav a { padding: 12px 18px; border: 1px solid #075a9c; border-radius: 8px; }
  </style>
</head>
<body>
  <main>
    <h1>Tour Decision Backend</h1>
    <p>Bạn đã kết nối được tới máy chủ API.</p>
    <p>Mở tài liệu API để thử nhập nhu cầu và so sánh tour.
       Giao diện dành cho người dùng sẽ được kết nối từ frontend.</p>
    <nav aria-label="Công cụ backend">
      <a href="docs">Mở tài liệu và thử API</a>
      <a href="health">Kiểm tra trạng thái</a>
    </nav>
    <p>Trong tài liệu API, tạo phiên bằng <code>POST /v1/sessions</code>,
       rồi bấm <strong>Authorize</strong> và dán riêng token nhận được
       (không thêm <code>Bearer</code>). Sau đó tạo requirement trước khi so sánh;
       dùng ID và revision thật từ response.</p>
  </main>
</body>
</html>""")

    @app.get("/health")
    async def health():
        task = getattr(app.state, "worker_task", None)
        healthy = not settings.worker_enabled or (task is not None and not task.done())
        return JSONResponse(
            {
                "status": "ok" if healthy else "degraded",
                "data_origin": "synthetic" if settings.data_provider == "fixture" else "source",
                "data_provider": settings.data_provider,
                "worker_enabled": settings.worker_enabled,
                "schema_version": "1.0",
                "api_versions": ["v1", "v2"],
                "database_schema_version": 2,
            },
            status_code=200 if healthy else 503,
        )

    @app.post("/v1/sessions", status_code=201)
    async def session(request: Request):
        limits.check(f"sessions:{request.client.host if request.client else 'local'}", 20)
        return store.new_session()

    @app.get("/v1/sources")
    async def sources(owner_id: str = Depends(owner)):
        return {
            "origin": "synthetic" if settings.data_provider == "fixture" else "source",
            "sources": [s.model_dump() for s in gateway.registry],
        }

    @app.post("/v1/requirements")
    async def create_requirement(
        body: Annotated[
            CreateRequirement,
            Body(
                openapi_examples={
                    "compare_urls": {
                        "summary": "So sánh URL mô phỏng",
                        "description": "Dùng DATA_PROVIDER=fixture; trả 201 với id/revision, không gọi NIM.",
                        "value": {
                            "mode": "compare_urls",
                            "urls": [
                                "https://tour-demo.invalid/tour-a",
                                "https://tour-demo.invalid/tour-b",
                            ],
                        },
                    },
                    "discover_text": {
                        "summary": "Nhập nhu cầu bằng tiếng Việt",
                        "description": "Cần cấu hình NIM. Đợi parse job succeeded rồi GET requirement.",
                        "value": {
                            "mode": "discover",
                            "text": "Đi Nhật từ Sài Gòn, 5 ngày. Giá tour tối đa 30 triệu đồng mỗi người lớn.",
                        },
                    },
                }
            ),
        ],
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(default=None),
    ):
        def action(c):
            rid = uid("req")
            targets = [Target(target_id=uid("target"), url=url) for url in body.urls]
            store.add_resource(c, owner_id, rid, "requirement", {})
            if body.text is not None:
                message = Message(id=uid("msg"), text=body.text, received_at=now().isoformat())
                jid = store.add_job(
                    c,
                    owner_id,
                    rid,
                    "parse",
                    {
                        "expected_revision": 0,
                        "message": message.model_dump(),
                        "mode": body.mode,
                        "timezone": body.timezone,
                        "targets": [t.model_dump() for t in targets],
                    },
                )
                return [202, {"requirement_id": rid, "revision": 0, "job_id": jid, "status": "queued"}]
            requirement = form_requirement(
                body.form or Form(),
                requirement_id=rid,
                mode=body.mode,
                timezone=body.timezone,
                targets=targets,
            )
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
    async def patch_requirement(
        resource_id: str,
        body: PatchRequirement,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(default=None),
    ):
        def action(c):
            previous = store.revision(owner_id, resource_id, connection=c)
            if previous.revision != body.expected_revision:
                raise AppError("REVISION_CONFLICT", "Revision đã thay đổi; tải lại trước khi sửa.", 409)
            if body.text is not None:
                message = Message(id=uid("msg"), text=body.text, received_at=now().isoformat())
                jid = store.add_job(
                    c,
                    owner_id,
                    resource_id,
                    "parse",
                    {
                        "expected_revision": body.expected_revision,
                        "message": message.model_dump(),
                        "mode": previous.mode,
                        "timezone": previous.timezone,
                        "targets": [t.model_dump() for t in previous.targets],
                    },
                )
                return [
                    202,
                    {
                        "requirement_id": resource_id,
                        "revision": previous.revision,
                        "job_id": jid,
                        "status": "queued",
                    },
                ]
            edits = body.edits if body.edits is not None else answer_edits(previous, body.answers)
            requirement = apply_edits(previous, edits)
            store.add_revision(c, owner_id, requirement, previous.revision)
            return [200, requirement.model_dump(mode="json")]

        return mutate(owner_id, idempotency_key, f"patch:{resource_id}", body.model_dump(mode="json"), action)

    @app.post("/v1/comparisons")
    async def create_comparison(
        body: Annotated[
            CreateComparison,
            Body(
                openapi_examples={
                    "first_comparison": {
                        "summary": "So sánh lần đầu — thay ID bằng response thật",
                        "description": "Tạo requirement trước trong cùng session; dùng id/revision đã parse.",
                        "value": {"requirement_id": "req_replace_with_created_id", "revision": 1},
                    }
                }
            ),
        ],
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(default=None),
    ):
        def action(c):
            requirement = store.revision(owner_id, body.requirement_id, body.revision, c)
            if not requirement.readiness.can_collect_data:
                raise AppError(
                    "REQUIREMENT_NOT_READY", "Cần làm rõ phạm vi tìm kiếm trước khi thu thập.", 409
                )
            if body.reuse_comparison_id:
                prior = store.resource(owner_id, body.reuse_comparison_id, c, "comparison")
                payload = json.loads(prior["payload"])
                if (
                    prior["status"] not in {"succeeded", "partial"}
                    or payload["result"]["requirement_id"] != requirement.id
                ):
                    raise AppError(
                        "OFFER_SELECTION_INVALID", "Comparison cũ chưa hoàn tất hoặc thuộc nhu cầu khác.", 409
                    )
                if requirement.mode == "discover" and payload["result"]["revision"] != requirement.revision:
                    raise AppError(
                        "OFFER_SELECTION_INVALID",
                        "Discovery đã đổi revision; cần thu thập lại để bảo đảm phạm vi tìm kiếm.",
                        409,
                    )
                old_targets = {t["target_id"]: t["url"] for t in payload["result"]["targets"]}
                if old_targets != {t.target_id: t.url for t in requirement.targets}:
                    raise AppError("OFFER_SELECTION_INVALID", "Targets đã đổi; cần thu thập lại.", 409)
            cid = uid("comparison")
            store.add_resource(
                c, owner_id, cid, "comparison", body.model_dump(mode="json"), revision=body.revision
            )
            jid = store.add_job(c, owner_id, cid, "comparison", body.model_dump(mode="json"))
            return [
                202,
                {
                    "comparison_id": cid,
                    "job_id": jid,
                    "requirement_id": requirement.id,
                    "revision": requirement.revision,
                    "status": "queued",
                },
            ]

        return mutate(owner_id, idempotency_key, "create_comparison", body.model_dump(mode="json"), action)

    @app.get("/v1/jobs/{job_id}")
    async def get_job(job_id: str, owner_id: str = Depends(owner)):
        return store.job(owner_id, job_id)

    @app.post("/v1/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str, owner_id: str = Depends(owner), idempotency_key: str | None = Header(default=None)
    ):
        return mutate(
            owner_id,
            idempotency_key,
            f"cancel:{job_id}",
            {},
            lambda c: [200, store.cancel(c, owner_id, job_id)],
        )

    @app.get("/v1/comparisons/{resource_id}")
    async def get_comparison(resource_id: str, owner_id: str = Depends(owner)):
        resource = store.resource(owner_id, resource_id, kind="comparison")
        payload = json.loads(resource["payload"])
        return {"id": resource_id, "status": resource["status"], "result": payload.get("result")}

    @app.get("/v1/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str, owner_id: str = Depends(owner)):
        with store.engine.connect() as c:
            rows = c.execute(
                select(resources.c.payload).where(
                    resources.c.owner == owner_id,
                    resources.c.kind == "comparison",
                    resources.c.status.in_(["succeeded", "partial"]),
                )
            ).scalars()
            for row in rows:
                for evidence in json.loads(row).get("crawl", {}).get("evidence", []):
                    if evidence["id"] == evidence_id:
                        return evidence
        raise AppError("NOT_FOUND", "Không tìm thấy evidence.", 404)

    from api.v2.routes import router

    app.include_router(router(worker.v2, worker.v2.admin, owner_v2, limits))
    from api.auth.routes import router as auth_router
    from api.v2.history import router as history_router

    app.include_router(auth_router(identity, limits))
    app.include_router(history_router(store, owner_v2))
    from api.profile_hub.routes import router as profile_router

    app.include_router(profile_router(identity, store, limits, profile_transport))
    return app
