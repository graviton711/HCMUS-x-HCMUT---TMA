import base64
import hashlib
import json
import re
import secrets
from datetime import UTC

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, model_validator
from sqlalchemy import and_, case, func, insert, or_, select, update

from api.store import dump, jobs, sessions
from api.v2 import state
from domain.common import AppError, Identifier, Model, instant, now, uid
from domain.crawl import SourceCapability
from domain.requirements import FIELDS


class ContactContext(Model):
    session_id: Identifier | None = None
    comparison_id: Identifier | None = None


class ContactCreate(Model):
    category: str = Field(pattern=r"^(feedback|data_issue|support)$")
    message: str = Field(min_length=1, max_length=4000)
    reply_to: str | None = Field(default=None, max_length=254)
    comparison_id: Identifier | None = None
    client_submission_id: Identifier | None = None
    context: ContactContext = Field(default_factory=ContactContext)

    @model_validator(mode="after")
    def email(self):
        if self.reply_to and not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", self.reply_to):
            raise ValueError("Invalid reply_to")
        if not self.message.strip():
            raise ValueError("Empty message")
        if (
            self.comparison_id
            and self.context.comparison_id
            and self.comparison_id != self.context.comparison_id
        ):
            raise ValueError("Conflicting comparison context")
        return self


class ContactPatch(Model):
    expected_version: int = Field(ge=1)
    status: str | None = Field(default=None, pattern=r"^(new|in_progress|resolved)$")
    assignee: Identifier | None = None
    internal_note: str | None = Field(default=None, max_length=4000)


class SourceCreate(Model):
    display_name: str = Field(min_length=1, max_length=200)
    capability: SourceCapability | None = None
    domain: str | None = Field(default=None, max_length=253)
    capabilities: dict | None = None
    profile_ref: str = Field(min_length=1, max_length=200)
    policy_ref: str = Field(default="manual_review_required", min_length=1, max_length=200)

    @model_validator(mode="after")
    def draft(self):
        if (self.capability is None) == (self.domain is None):
            raise ValueError("Choose capability or domain draft")
        if self.domain and not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", self.domain):
            raise ValueError("Domain must be a lowercase hostname")
        if self.capabilities and set(self.capabilities) - {"modes", "searchable_fields", "returned_fields"}:
            raise ValueError("Unknown draft capabilities")
        return self


class ExpectedVersion(Model):
    expected_version: int = Field(ge=1)


class SourcePatch(ExpectedVersion):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    state: str | None = Field(default=None, pattern=r"^(active|paused)$")
    notes: str | None = Field(default=None, max_length=2000)
    policy_ref: str | None = Field(default=None, min_length=1, max_length=200)


class SourceApproval(ExpectedVersion):
    check_job_id: Identifier


class SourceRefresh(ExpectedVersion):
    reference_urls: list[str] = Field(default_factory=list, max_length=5)


class AccessProof(Model):
    access_status: str = Field(pattern=r"^(approved|blocked|unchecked)$")
    checked_at: str
    valid_until: str
    policy_ref: str
    profile_ref: str
    capability_digest: str

    @model_validator(mode="after")
    def timestamps(self):
        start, end = instant(self.checked_at), instant(self.valid_until)
        if start >= end:
            raise ValueError("Proof needs checked_at < valid_until")
        object.__setattr__(self, "checked_at", start.astimezone(UTC).isoformat())
        object.__setattr__(self, "valid_until", end.astimezone(UTC).isoformat())
        return self


def digest(record):
    return hashlib.sha256(dump(record["capability"]).encode()).hexdigest()


def record_audit(c, actor, action, rid, before, after):
    # Only explicitly selected metadata enters the audit, never messages/emails/secrets.
    payload = {
        "id": uid("audit"),
        "actor_id": actor,
        "action": action,
        "resource_id": rid,
        "before": before,
        "after": after,
        "timestamp": now().isoformat(),
        "trace_id": uid("trace"),
    }
    c.execute(
        insert(state.audit).values(
            id=payload["id"], created_at=payload["timestamp"], resource_id=rid, payload=dump(payload)
        )
    )


def source(c, sid):
    payload = c.execute(
        select(state.source_registry.c.payload).where(state.source_registry.c.id == sid)
    ).scalar()
    if payload is None:
        raise AppError("NOT_FOUND", "Không tìm thấy nguồn.", 404)
    return json.loads(payload)


def save_source(c, record, expected):
    if record["version"] != expected + 1:
        raise ValueError("Source version must increment once")
    changed = c.execute(
        update(state.source_registry)
        .where(state.source_registry.c.id == record["id"], state.source_registry.c.version == expected)
        .values(version=record["version"], payload=dump(record))
    ).rowcount
    if changed != 1:
        raise AppError("REVISION_CONFLICT", "Nguồn đã thay đổi.", 409)


def guard_source(record, version):
    if record["version"] != version:
        raise AppError("REVISION_CONFLICT", "Nguồn đã thay đổi.", 409)


def ready_source(c, record, *, activating=False):
    capability = SourceCapability.model_validate(record["capability"])
    known = set(FIELDS) - {"unsupported"}
    if any(
        not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split("."))
        for host in capability.approved_domains
    ):
        raise AppError("SOURCE_CAPABILITY_INVALID", "Approved domains phải là hostname hợp lệ.", 409)
    if (
        not capability.modes
        or not capability.returned_fields
        or set(capability.searchable_fields) - known
        or set(capability.returned_fields) - known
        or ("discover" in capability.modes and not capability.searchable_fields)
    ):
        raise AppError(
            "SOURCE_CAPABILITY_INVALID", "Cần modes và fields hợp lệ trước khi duyệt/bật nguồn.", 409
        )
    if activating:
        if record["access_status"] != "approved" or (
            record.get("access_valid_until") and instant(record["access_valid_until"]) <= now()
        ):
            raise AppError("SOURCE_BLOCKED", "Nguồn chưa được duyệt hoặc access proof hết hạn.", 409)
        for payload in c.execute(
            select(state.source_registry.c.payload).where(state.source_registry.c.id != record["id"])
        ).scalars():
            other = json.loads(payload)
            if other["state"] == "active" and set(other["capability"]["approved_domains"]) & set(
                capability.approved_domains
            ):
                raise AppError(
                    "SOURCE_DOMAIN_CONFLICT", "Domain đã thuộc nguồn active khác; pause nguồn đó trước.", 409
                )


def bootstrap(store, gateway):
    with store.transaction() as c:
        for capability in gateway.registry:
            if c.execute(
                select(state.source_registry.c.id).where(state.source_registry.c.id == capability.source_id)
            ).scalar():
                continue
            record = {
                "id": capability.source_id,
                "version": 1,
                "display_name": capability.source_id,
                "capability": capability.model_dump(mode="json"),
                "state": "active" if capability.access_status == "approved" else "paused",
                "access_status": capability.access_status,
                "profile_ref": "catalog-records" if capability.limits.get("catalog_read_only") else "bootstrap-config",
                "policy_ref": "catalog-read-only" if capability.limits.get("catalog_read_only") else "bootstrap-config",
                "checked_at": capability.checked_at,
                "access_valid_until": None,
                "last_check_job_id": None,
                "last_run_job_id": None,
                "notes": "Chỉ đọc kho đã cấu hình; không cấp quyền crawl website. TTL chưa cấu hình."
                if capability.limits.get("catalog_read_only") else "",
            }
            c.execute(insert(state.source_registry).values(id=record["id"], version=1, payload=dump(record)))


def cursor_id(cursor):
    after = ""
    if cursor:
        try:
            after = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
        except (ValueError, UnicodeError) as exc:
            raise AppError("INVALID_INPUT", "Cursor không hợp lệ.") from exc
    return after


def rows_page(c, statement, identifier, *, limit, cursor=None):
    timestamp = identifier.table.c.created_at
    if cursor:
        try:
            stamp, rid = json.loads(cursor_id(cursor))
            if not isinstance(stamp, str) or not isinstance(rid, str):
                raise ValueError("Cursor values")
            instant(stamp)
        except (ValueError, TypeError) as exc:
            raise AppError("INVALID_INPUT", "Cursor không hợp lệ.") from exc
        statement = statement.where(or_(timestamp > stamp, and_(timestamp == stamp, identifier > rid)))
    rows = c.execute(statement.order_by(timestamp, identifier).limit(limit + 1)).mappings().all()
    last = rows[limit - 1] if len(rows) > limit else None
    return {
        "items": [dict(r) for r in rows[:limit]],
        "next_cursor": base64.urlsafe_b64encode(
            json.dumps([last.get("created_at", last.get("started_at")), last["id"]]).encode()
        ).decode()
        if last
        else None,
    }


def interval_filters(column, start=None, end=None):
    try:
        start = instant(start).astimezone(UTC) if start else None
        end = instant(end).astimezone(UTC) if end else None
    except ValueError as exc:
        raise AppError("INVALID_INPUT", "Interval cần timestamp có timezone.") from exc
    if start and end and start >= end:
        raise AppError("INVALID_INPUT", "Interval cần from < to.")
    return ([column >= start.isoformat()] if start else []) + ([column < end.isoformat()] if end else [])


def page(c, table, *, limit, cursor=None, filters=()):
    after = cursor_id(cursor)
    rows = (
        c.execute(select(table).where(table.c.id > after, *filters).order_by(table.c.id).limit(limit + 1))
        .mappings()
        .all()
    )
    items = [json.loads(row["payload"]) for row in rows[:limit]]
    return {
        "items": items,
        "next_cursor": base64.urlsafe_b64encode(rows[limit - 1]["id"].encode()).decode()
        if len(rows) > limit
        else None,
    }


class Admin:
    def __init__(self, store, service, checker=None):
        self.store, self.service, self.checker = store, service, checker

    def contact(self, c, owner, body):
        if body.context.session_id and body.context.session_id != owner:
            raise AppError("NOT_FOUND", "Contact context không thuộc phiên của bạn.", 404)
        comparison_id = body.context.comparison_id or body.comparison_id
        if comparison_id:
            self.store.resource(owner, comparison_id, c, "comparison_v2")
        if body.client_submission_id:
            existing = c.execute(
                select(state.contacts.c.payload).where(state.contacts.c.owner == owner)
            ).scalars()
            for payload in existing:
                old = json.loads(payload)
                if old["client_submission_id"] == body.client_submission_id:
                    if (
                        old["submission_digest"]
                        != hashlib.sha256(dump(body.model_dump()).encode()).hexdigest()
                    ):
                        raise AppError(
                            "IDEMPOTENCY_CONFLICT", "Submission ID đã dùng với nội dung khác.", 409
                        )
                    return 201, {
                        "ticket_id": old["id"],
                        "status": old["status"],
                        "created_at": old["created_at"],
                    }
        record = {
            **body.model_dump(),
            "id": uid("contact"),
            "version": 1,
            "owner": owner,
            "submission_digest": hashlib.sha256(dump(body.model_dump()).encode()).hexdigest(),
            "status": "new",
            "assignee": None,
            "internal_notes": [],
            "created_at": now().isoformat(),
            "resolved_at": None,
        }
        c.execute(
            insert(state.contacts).values(
                id=record["id"],
                owner=owner,
                version=1,
                status="new",
                created_at=record["created_at"],
                payload=dump(record),
            )
        )
        record_audit(c, owner, "contact.create", record["id"], None, {"status": "new", "version": 1})
        return 201, {"ticket_id": record["id"], "status": "new", "created_at": record["created_at"]}

    async def check_job(self, row, worker_id, payload):
        if self.checker is None:
            raise AppError(
                "ACCESS_CHECKER_NOT_CONFIGURED",
                "Chưa có checker robots/terms/profile; không tự duyệt nguồn.",
                503,
            )
        with self.store.engine.connect() as c:
            record = source(c, payload["source_id"])
        proof = AccessProof.model_validate(await self.checker(record))
        if (
            proof.policy_ref != record["policy_ref"]
            or proof.profile_ref != record["profile_ref"]
            or proof.capability_digest != digest(record)
        ):
            raise AppError("CONTRACT_INVALID", "Access proof sai binding.", 502)
        if instant(proof.checked_at) > now() or instant(proof.valid_until) <= now():
            raise AppError("CONTRACT_INVALID", "Access proof hết hạn hoặc thời gian sai.", 502)
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                return
            latest = source(c, record["id"])
            guard_source(latest, payload["expected_version"])
            updated = {
                **latest,
                "version": latest["version"] + 1,
                "last_check_job_id": row["id"],
                "last_check": proof.model_dump(),
                "checked_at": proof.checked_at,
            }
            if proof.access_status != "approved":
                updated.update(state="paused", access_status=proof.access_status, access_valid_until=None)
                updated["capability"] = {
                    **latest["capability"],
                    "access_status": proof.access_status,
                    "checked_at": proof.checked_at,
                }
            save_source(c, updated, latest["version"])
            record_audit(
                c,
                row["owner"],
                "source.check",
                record["id"],
                {"version": latest["version"]},
                {"version": updated["version"], "access_status": proof.access_status},
            )
            state.finish(c, row, worker_id)

    async def refresh_job(self, row, worker_id, payload):
        from api.v2.models import RequirementV2
        from data_access.v2 import GatewayV2
        from domain.requirements import Target

        with self.store.engine.connect() as c:
            record = source(c, payload["source_id"])
        guard_source(record, payload["expected_version"])
        with self.store.engine.connect() as c:
            ready_source(c, record, activating=True)
        if record["state"] != "active":
            raise AppError("SOURCE_BLOCKED", "Nguồn chưa được bật/duyệt.", 409)
        urls = payload["reference_urls"]
        requirement = RequirementV2(
            id="admin_refresh",
            revision=1,
            input_kind="urls" if urls else "structured",
            mode="compare_urls" if urls else "discover",
            reference_urls=urls,
            targets=[Target(target_id=uid("target"), url=u) for u in urls],
        )
        gateway = GatewayV2(self.service.gateway, [SourceCapability.model_validate(record["capability"])])
        # Explicit operator refresh can discover all configured source records.
        if not urls:
            from data_access.v2 import core_requirement

            crawl = await gateway.gateway.collect(
                core_requirement(requirement, "discover", []), row["deadline_at"]
            )
        else:
            crawl = await gateway.collect(requirement, row["deadline_at"])
        if any(s.status in {"error", "timeout"} for s in crawl.source_results) and not crawl.tours:
            raise AppError("SOURCES_UNAVAILABLE", "Refresh không có dữ liệu dùng được.", 502)
        with self.store.transaction() as c:
            if not state.running(c, row, worker_id):
                return
            latest = source(c, record["id"])
            guard_source(latest, payload["expected_version"])
            ready_source(c, latest, activating=True)
            if latest["state"] != "active":
                raise AppError("SOURCE_BLOCKED", "Nguồn bị dừng trong lúc refresh.", 409)
            state.persist_snapshots(c, row["owner"], row["id"], crawl)
            updated = {
                **latest,
                "version": latest["version"] + 1,
                "last_run_job_id": row["id"],
                "data_counts": {"tours": len(crawl.tours), "offers": len(crawl.offers)},
            }
            save_source(c, updated, latest["version"])
            record_audit(
                c,
                row["owner"],
                "source.refresh",
                record["id"],
                None,
                {"version": updated["version"], "data_counts": updated["data_counts"]},
            )
            state.finish(
                c,
                row,
                worker_id,
                "partial"
                if any(s.status in {"error", "timeout"} for s in crawl.source_results)
                else "succeeded",
            )


def admin_router(admin, settings, envelope, mutation, limits):
    router = APIRouter(prefix="/admin", tags=["v2 admin"])
    bearer = HTTPBearer(auto_error=False, scheme_name="AdminBearer")

    bearer_dependency = Depends(bearer)

    def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = bearer_dependency):
        limits.check(f"admin_ip:{request.client.host if request.client else 'local'}", 120)
        if credentials:
            for role, secret in (
                ("admin", settings.admin_token),
                ("operator", settings.admin_operator_token),
                ("viewer", settings.admin_viewer_token),
            ):
                token = secret.get_secret_value()
                if token and secrets.compare_digest(credentials.credentials, token):
                    return {"role": role, "id": "admin_" + hashlib.sha256(token.encode()).hexdigest()[:24]}
        raise AppError("FORBIDDEN", "Cần danh tính admin riêng; session user không có quyền.", 403)

    actor_dependency = Depends(principal)

    def require(actor, role):
        if {"viewer": 0, "operator": 1, "admin": 2}[actor["role"]] < {"viewer": 0, "operator": 1, "admin": 2}[
            role
        ]:
            raise AppError("FORBIDDEN", "Role không cho phép thao tác này.", 403)

    @router.get("/sources")
    async def sources(
        request: Request,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        actor=actor_dependency,
    ):
        with admin.store.engine.connect() as c:
            data = page(
                c,
                state.source_registry,
                limit=limit,
                cursor=cursor,
                filters=[func.json_extract(state.source_registry.c.payload, "$.state") == status]
                if status
                else [],
            )
        return envelope(request, data)

    @router.get("/sources/{sid}")
    async def get_source(sid: str, request: Request, actor=actor_dependency):
        with admin.store.engine.connect() as c:
            data = source(c, sid)
        return envelope(request, data)

    @router.post("/sources")
    async def create_source(
        body: SourceCreate,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        require(actor, "admin")

        def action(c):
            capability_model = body.capability or SourceCapability(
                source_id=uid("source"),
                supplier_id=uid("supplier"),
                approved_domains=[body.domain],
                access_status="unchecked",
                checked_at=now().isoformat(),
                modes=body.capabilities.get("modes", []) if body.capabilities else [],
                searchable_fields=body.capabilities.get("searchable_fields", []) if body.capabilities else [],
                returned_fields=body.capabilities.get("returned_fields", []) if body.capabilities else [],
            )
            sid = capability_model.source_id
            if c.execute(
                select(state.source_registry.c.id).where(state.source_registry.c.id == sid)
            ).scalar():
                raise AppError("REVISION_CONFLICT", "Source ID đã tồn tại.", 409)
            capability = capability_model.model_dump(mode="json")
            capability["access_status"] = "unchecked"
            record = {
                "id": sid,
                "version": 1,
                "display_name": body.display_name,
                "capability": capability,
                "state": "paused",
                "access_status": "unchecked",
                "profile_ref": body.profile_ref,
                "policy_ref": body.policy_ref,
                "checked_at": None,
                "access_valid_until": None,
                "last_check_job_id": None,
                "last_run_job_id": None,
                "notes": "",
            }
            c.execute(insert(state.source_registry).values(id=sid, version=1, payload=dump(record)))
            record_audit(
                c,
                actor["id"],
                "source.create",
                sid,
                None,
                {"version": 1, "state": "paused", "access_status": "unchecked"},
            )
            return 201, record

        return mutation(request, actor["id"], idempotency_key, "admin:create_source", body, action)

    @router.patch("/sources/{sid}")
    async def patch_source(
        sid: str,
        body: SourcePatch,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        require(actor, "operator")
        if actor["role"] != "admin" and (
            body.state != "paused"
            or any(v is not None for v in (body.display_name, body.notes, body.policy_ref))
        ):
            raise AppError("FORBIDDEN", "Operator chỉ được pause nguồn.", 403)

        def action(c):
            old = source(c, sid)
            guard_source(old, body.expected_version)
            updated = {
                **old,
                **body.model_dump(exclude={"expected_version"}, exclude_none=True),
                "version": old["version"] + 1,
            }
            if body.policy_ref and body.policy_ref != old["policy_ref"]:
                updated.update(state="paused", access_status="unchecked", last_check_job_id=None)
            if updated["state"] == "active":
                ready_source(c, updated, activating=True)
            save_source(c, updated, old["version"])
            record_audit(
                c,
                actor["id"],
                "source.patch",
                sid,
                {"version": old["version"], "state": old["state"]},
                {
                    "version": updated["version"],
                    "state": updated["state"],
                    "access_status": updated["access_status"],
                },
            )
            return 200, updated

        return mutation(request, actor["id"], idempotency_key, f"admin:source:{sid}", body, action)

    @router.post("/sources/{sid}/checks")
    async def check(
        sid: str,
        body: ExpectedVersion,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        require(actor, "admin")

        def action(c):
            record = source(c, sid)
            guard_source(record, body.expected_version)
            jid = admin.store.add_job(
                c,
                actor["id"],
                sid,
                "v2_source_check",
                {"source_id": sid, "expected_version": body.expected_version},
            )
            record_audit(c, actor["id"], "source.check_requested", sid, None, {"job_id": jid})
            return 202, {"job_id": jid, "status": "queued"}

        return mutation(request, actor["id"], idempotency_key, f"admin:check:{sid}", body, action)

    @router.post("/sources/{sid}/approvals")
    async def approve(
        sid: str,
        body: SourceApproval,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        require(actor, "admin")

        def action(c):
            old = source(c, sid)
            guard_source(old, body.expected_version)
            ready_source(c, old)
            job = (
                c.execute(
                    select(jobs).where(
                        jobs.c.id == body.check_job_id,
                        jobs.c.resource_id == sid,
                        jobs.c.kind == "v2_source_check",
                        jobs.c.status == "succeeded",
                    )
                )
                .mappings()
                .first()
            )
            proof = old.get("last_check")
            if (
                not job
                or body.check_job_id != old["last_check_job_id"]
                or not proof
                or proof["access_status"] != "approved"
                or instant(proof["valid_until"]) <= now()
                or proof["capability_digest"] != digest(old)
            ):
                raise AppError("SOURCE_BLOCKED", "Cần check thành công, đúng version và còn hiệu lực.", 409)
            updated = {
                **old,
                "version": old["version"] + 1,
                "access_status": "approved",
                "state": "paused",
                "access_valid_until": proof["valid_until"],
            }
            updated["capability"] = {
                **old["capability"],
                "access_status": "approved",
                "checked_at": proof["checked_at"],
            }
            save_source(c, updated, old["version"])
            record_audit(
                c,
                actor["id"],
                "source.approve",
                sid,
                {"version": old["version"]},
                {"version": updated["version"], "state": "paused"},
            )
            return 200, updated

        return mutation(request, actor["id"], idempotency_key, f"admin:approve:{sid}", body, action)

    @router.post("/sources/{sid}/refreshes")
    async def refresh(
        sid: str,
        body: SourceRefresh,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        from api.v2.models import canonical_urls

        require(actor, "operator")

        def action(c):
            record = source(c, sid)
            guard_source(record, body.expected_version)
            ready_source(c, record, activating=True)
            if record["state"] != "active":
                raise AppError("SOURCE_BLOCKED", "Nguồn chưa active/approved.", 409)
            urls = canonical_urls(body.reference_urls)
            from urllib.parse import urlsplit

            if any(urlsplit(u).hostname not in record["capability"]["approved_domains"] for u in urls):
                raise AppError("INVALID_INPUT", "Refresh URL phải thuộc source.")
            jid = admin.store.add_job(
                c,
                actor["id"],
                sid,
                "v2_source_refresh",
                {"source_id": sid, "expected_version": record["version"], "reference_urls": urls},
            )
            record_audit(c, actor["id"], "source.refresh_requested", sid, None, {"job_id": jid})
            return 202, {"job_id": jid, "status": "queued"}

        return mutation(request, actor["id"], idempotency_key, f"admin:refresh:{sid}", body, action)

    @router.get("/jobs/{jid}")
    async def job(jid: str, request: Request, actor=actor_dependency):
        with admin.store.engine.connect() as c:
            row = c.execute(
                select(jobs.c.owner).where(
                    jobs.c.id == jid, jobs.c.kind.in_(["v2_source_check", "v2_source_refresh"])
                )
            ).first()
        if row is None:
            raise AppError("NOT_FOUND", "Không tìm thấy admin job.", 404)
        return envelope(request, admin.store.job(row.owner, jid))

    @router.get("/sources/{sid}/runs")
    async def runs(
        sid: str,
        request: Request,
        actor=actor_dependency,
        cursor: str | None = None,
        limit: int = Query(25, ge=1, le=100),
    ):
        with admin.store.engine.connect() as c:
            source(c, sid)
            result = rows_page(
                c,
                select(jobs.c.id, jobs.c.kind, jobs.c.status, jobs.c.created_at, jobs.c.error).where(
                    jobs.c.resource_id == sid, jobs.c.kind.in_(["v2_source_check", "v2_source_refresh"])
                ),
                jobs.c.id,
                limit=limit,
                cursor=cursor,
            )
        for item in result["items"]:
            item["error"] = json.loads(item["error"]) if item["error"] else None
        return envelope(request, result)

    @router.get("/contacts")
    async def contact_list(
        request: Request,
        status: str | None = None,
        category: str | None = None,
        cursor: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        actor=actor_dependency,
    ):
        with admin.store.engine.connect() as c:
            result = page(
                c,
                state.contacts,
                limit=limit,
                cursor=cursor,
                filters=([state.contacts.c.status == status] if status else [])
                + (
                    [func.json_extract(state.contacts.c.payload, "$.category") == category]
                    if category
                    else []
                ),
            )
        for record in result["items"]:
            for key in ("submission_digest", "client_submission_id"):
                record.pop(key, None)
            if actor["role"] == "viewer":
                for key in ("message", "reply_to", "internal_notes"):
                    record.pop(key, None)
        return envelope(request, result)

    @router.patch("/contacts/{tid}")
    async def contact_patch(
        tid: str,
        body: ContactPatch,
        request: Request,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        require(actor, "operator")

        def action(c):
            payload = c.execute(select(state.contacts.c.payload).where(state.contacts.c.id == tid)).scalar()
            if payload is None:
                raise AppError("NOT_FOUND", "Không tìm thấy ticket.", 404)
            old = json.loads(payload)
            if old["version"] != body.expected_version:
                raise AppError("REVISION_CONFLICT", "Ticket đã thay đổi.", 409)
            record = {**old, "version": old["version"] + 1}
            if body.status:
                allowed = {
                    "new": {"new", "in_progress"},
                    "in_progress": {"in_progress", "resolved", "new"},
                    "resolved": {"resolved", "in_progress", "new"},
                }
                if body.status not in allowed[old["status"]]:
                    raise AppError("INVALID_INPUT", "Chuyển trạng thái ticket không hợp lệ.")
                record.update(
                    status=body.status, resolved_at=now().isoformat() if body.status == "resolved" else None
                )
            if body.assignee is not None:
                record["assignee"] = body.assignee
            if body.internal_note:
                record["internal_notes"] = [
                    *old["internal_notes"],
                    {"actor_id": actor["id"], "text": body.internal_note, "created_at": now().isoformat()},
                ]
            c.execute(
                update(state.contacts)
                .where(state.contacts.c.id == tid, state.contacts.c.version == body.expected_version)
                .values(version=record["version"], status=record["status"], payload=dump(record))
            )
            record_audit(
                c,
                actor["id"],
                "contact.patch",
                tid,
                {"version": old["version"], "status": old["status"]},
                {
                    "version": record["version"],
                    "status": record["status"],
                    "note_added": bool(body.internal_note),
                },
            )
            return 200, {
                k: v for k, v in record.items() if k not in {"submission_digest", "client_submission_id"}
            }

        return mutation(request, actor["id"], idempotency_key, f"admin:contact:{tid}", body, action)

    @router.get("/audit")
    async def audits(
        request: Request,
        resource_id: str | None = None,
        cursor: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        actor=actor_dependency,
    ):
        with admin.store.engine.connect() as c:
            result = page(
                c,
                state.audit,
                limit=limit,
                cursor=cursor,
                filters=[state.audit.c.resource_id == resource_id] if resource_id else [],
            )
        return envelope(request, result)

    @router.get("/overview")
    async def overview(
        request: Request,
        from_: str = Query(alias="from"),
        to: str = Query(),
        timezone: str = "Asia/Ho_Chi_Minh",
        actor=actor_dependency,
    ):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(timezone)
            start, end = instant(from_).astimezone(UTC), instant(to).astimezone(UTC)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise AppError("INVALID_INPUT", "Interval/timezone không hợp lệ.") from exc
        if start >= end:
            raise AppError("INVALID_INPUT", "Interval cần from < to.")
        with admin.store.engine.connect() as c:
            rows = (
                c.execute(
                    select(state.activities).where(
                        state.activities.c.created_at >= start.isoformat(),
                        state.activities.c.created_at < end.isoformat(),
                    )
                )
                .mappings()
                .all()
            )
            runs = (
                c.execute(
                    select(jobs.c.status).where(
                        jobs.c.kind == "v2_comparison",
                        jobs.c.created_at >= start.isoformat(),
                        jobs.c.created_at < end.isoformat(),
                    )
                )
                .scalars()
                .all()
            )
            registry = [json.loads(p) for p in c.execute(select(state.source_registry.c.payload)).scalars()]
            tickets = c.execute(select(state.contacts.c.status)).scalars().all()
        return envelope(
            request,
            {
                "scope": "api_v2",
                "origin": "synthetic" if settings.data_provider == "fixture" else "source",
                "metric_definition_version": "metrics-v2.1",
                "updated_at": now().isoformat(),
                "interval": {"from": start.isoformat(), "to": end.isoformat(), "timezone": timezone},
                "distinct_sessions": len({r["owner"] for r in rows}),
                "user_messages": sum(r["kind"] == "message" for r in rows),
                "comparison_runs": len(runs),
                "active_jobs": sum(s in {"queued", "running"} for s in runs),
                "terminal_breakdown": {
                    s: runs.count(s) for s in ("succeeded", "partial", "failed", "cancelled")
                },
                "source_health": {s: sum(r["state"] == s for r in registry) for s in ("active", "paused")},
                "contact_counts": {s: tickets.count(s) for s in ("new", "in_progress", "resolved")},
            },
        )

    @router.get("/sessions")
    async def session_list(
        request: Request,
        actor=actor_dependency,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = None,
        from_: str | None = Query(None, alias="from"),
        to: str | None = None,
        status: str | None = Query(None, pattern="^(active|expired)$"),
    ):
        summary = (
            select(
                state.activities.c.owner.label("owner"),
                func.max(state.activities.c.created_at).label("last_active_at"),
                func.sum(case((state.activities.c.kind == "message", 1), else_=0)).label(
                    "user_message_count"
                ),
                func.sum(case((state.activities.c.kind == "comparison", 1), else_=0)).label(
                    "comparison_count"
                ),
            )
            .group_by(state.activities.c.owner)
            .subquery()
        )
        last_job = (
            select(jobs.c.id)
            .where(jobs.c.owner == sessions.c.id, jobs.c.kind.like("v2_%"))
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(1)
            .correlate(sessions)
            .scalar_subquery()
        )
        filters = interval_filters(sessions.c.created_at, from_, to)
        if status:
            filters.append(
                sessions.c.expires_at > now().isoformat()
                if status == "active"
                else sessions.c.expires_at <= now().isoformat()
            )
        with admin.store.engine.connect() as c:
            result = rows_page(
                c,
                select(
                    sessions.c.id,
                    sessions.c.created_at.label("started_at"),
                    sessions.c.expires_at,
                    summary.c.last_active_at,
                    func.coalesce(summary.c.user_message_count, 0).label("user_message_count"),
                    func.coalesce(summary.c.comparison_count, 0).label("comparison_count"),
                    last_job.label("last_job_ref"),
                )
                .select_from(sessions.outerjoin(summary, sessions.c.id == summary.c.owner))
                .where(*filters),
                sessions.c.id,
                limit=limit,
                cursor=cursor,
            )
        for item in result["items"]:
            item["state"] = "active" if instant(item["expires_at"]) > now() else "expired"
        result["scope"] = "api_v2_activity"
        return envelope(request, result)

    @router.get("/sessions/{sid}/activity")
    async def activity(
        sid: str,
        request: Request,
        actor=actor_dependency,
        cursor: str | None = None,
        limit: int = Query(25, ge=1, le=100),
    ):
        with admin.store.engine.connect() as c:
            if not c.execute(select(sessions.c.id).where(sessions.c.id == sid)).scalar():
                raise AppError("NOT_FOUND", "Không tìm thấy phiên.", 404)
            result = rows_page(
                c,
                select(state.activities).where(state.activities.c.owner == sid),
                state.activities.c.id,
                limit=limit,
                cursor=cursor,
            )
        return envelope(request, result)

    return router
