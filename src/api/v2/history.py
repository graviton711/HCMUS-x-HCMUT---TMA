import base64
import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field, SecretStr
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Table,
    and_,
    delete,
    func,
    insert,
    or_,
    select,
    update,
)

from api.store import dump, idempotency, jobs, metadata, resources, sessions
from api.v2 import state
from api.v2.routes import envelope
from domain.common import AppError, Model, instant, now

conversation_meta = Table(
    "conversation_metadata",
    metadata,
    Column("requirement_id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("version", Integer),
    Column("title", String),
    Column("pinned", Boolean),
    Column("archived", Boolean),
    Column("updated_at", String),
)
linked_sessions = Table(
    "linked_guest_sessions",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("owner", String, index=True),
    Column("count", Integer),
    Column("expires_at", String),
)


class HistoryEdit(Model):
    expected_version: int = Field(ge=0)
    title: str | None = Field(default=None, max_length=100)
    pinned: bool | None = None


class GuestLink(Model):
    anonymous_token: SecretStr = Field(min_length=1, max_length=512)


def meta(c, owner, rid):
    row = (
        c.execute(
            select(conversation_meta).where(
                conversation_meta.c.requirement_id == rid, conversation_meta.c.owner == owner
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else dict(version=0, title="", pinned=False, archived=False, updated_at=None)


def refs(c, owner, rid):
    proposals = (
        c.execute(
            select(state.proposals.c.id).where(
                state.proposals.c.owner == owner,
                state.proposals.c.requirement_id == rid,
                state.proposals.c.status.in_(["pending", "needs_clarification"]),
                func.json_extract(state.proposals.c.payload, "$.expires_at") > now().isoformat(),
            )
        )
        .scalars()
        .all()
    )
    comparisons = (
        c.execute(
            select(resources.c.id, resources.c.created_at, resources.c.revision, resources.c.status)
            .where(
                resources.c.owner == owner,
                resources.c.kind == "comparison_v2",
                func.coalesce(
                    func.json_extract(resources.c.payload, "$.result.requirement_id"),
                    func.json_extract(resources.c.payload, "$.requirement_id"),
                )
                == rid,
            )
            .order_by(resources.c.created_at.desc(), resources.c.id.desc())
            .limit(51)
        )
        .mappings()
        .all()
    )
    pending = (
        c.execute(
            select(jobs.c.id, jobs.c.kind, jobs.c.resource_id)
            .where(
                jobs.c.owner == owner,
                jobs.c.status.in_(["queued", "running"]),
                or_(
                    jobs.c.resource_id == rid,
                    func.json_extract(jobs.c.payload, "$.requirement_id") == rid,
                    jobs.c.resource_id.in_([x["id"] for x in comparisons]),
                ),
            )
            .order_by(jobs.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    completed = [x for x in comparisons if x["status"] in {"succeeded", "partial"}]
    analysis = c.execute(
        select(resources.c.id)
        .where(
            resources.c.owner == owner,
            resources.c.kind == "what_if_v2",
            func.coalesce(
                func.json_extract(resources.c.payload, "$.result.requirement_id"),
                func.json_extract(resources.c.payload, "$.requirement_id"),
            )
            == rid,
        )
        .order_by(resources.c.created_at.desc(), resources.c.id.desc())
        .limit(1)
    ).scalar()
    pending_message = None
    if pending and pending["kind"] == "v2_message":
        payload = c.execute(select(jobs.c.payload).where(jobs.c.id == pending["id"])).scalar()
        pending_message = json.loads(payload).get("body", {}).get("client_message_id")
    return dict(
        proposal_id=proposals[0] if len(proposals) == 1 else None,
        comparison_id=completed[0]["id"] if completed else None,
        pending_comparison_id=pending["resource_id"]
        if pending and pending["kind"] == "v2_comparison"
        else None,
        job_id=pending["id"] if pending else None,
        analysis_id=analysis,
        pending_message_id=pending_message,
        runs=[dict(id=x["id"], revision=x["revision"], created_at=x["created_at"]) for x in completed[:50]],
        runs_limited=len(comparisons) > 50,
    )


def item(c, owner, row):
    info = meta(c, owner, row["id"])
    return dict(
        requirement_id=row["id"],
        revision=row["revision"],
        status=row["status"],
        title=info["title"],
        pinned=info["pinned"],
        version=info["version"],
        created_at=row["created_at"],
        updated_at=info["updated_at"] or row["created_at"],
        **refs(c, owner, row["id"]),
    )


def cursor(value):
    try:
        a, b = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if not isinstance(a, str) or not isinstance(b, str) or not b.startswith("req_") or len(b) > 128:
            raise ValueError()
        instant(a)
        return a, b
    except (ValueError, TypeError, KeyError):
        raise AppError("INVALID_CURSOR", "Cursor lịch sử không hợp lệ.") from None


def transcript(c, owner, rid, requirement):
    # Accepted message content lives in the durable job body; don't expose the whole job payload.
    rows = (
        c.execute(
            select(jobs.c.payload, jobs.c.created_at)
            .where(
                jobs.c.owner == owner, jobs.c.resource_id == rid, jobs.c.kind.in_(["v2_message", "v2_parse"])
            )
            .order_by(jobs.c.created_at, jobs.c.id)
            .limit(201)
        )
        .mappings()
        .all()
    )
    lines, seen = [], set()
    for row in rows[:200]:
        p = json.loads(row["payload"])
        message = p.get("message") or {}
        body = p.get("body") or {}
        text = body.get("text") or message.get("text")
        mid = body.get("client_message_id") or p.get("message_id") or message.get("id")
        if text and mid and mid not in seen:
            seen.add(mid)
            lines.append(dict(id=mid, role="user", text=text, occurred_at=row["created_at"]))
        if body.get("client_message_id"):
            record = c.execute(
                select(state.messages.c.payload).where(
                    state.messages.c.owner == owner,
                    state.messages.c.requirement_id == rid,
                    state.messages.c.client_message_id == body["client_message_id"],
                )
            ).scalar()
            result = (json.loads(record).get("result") or {}) if record else {}
            answer = (result.get("answer") or {}).get("text")
            if answer:
                lines.append(
                    dict(id=mid + ":reply", role="assistant", text=answer, occurred_at=row["created_at"])
                )
    # Older versions may have retained the revision after jobs were purged.
    if not lines:
        for m in requirement.get("messages", [])[:200]:
            lines.append(dict(id=m["id"], role="user", text=m["text"], occurred_at=m["received_at"]))
    return dict(items=lines, limited=len(rows) > 200)


def router(store, owner):
    routes = APIRouter(prefix="/v2", tags=["history"])

    @routes.get("/history")
    async def listing(
        request: Request,
        owner_id: str = Depends(owner),
        limit: int = Query(default=30, ge=1, le=100),
        after: str | None = Query(default=None, max_length=512),
    ):
        with store.engine.connect() as c:
            q = select(
                resources.c.id, resources.c.revision, resources.c.status, resources.c.created_at
            ).where(
                resources.c.owner == owner_id,
                resources.c.kind == "requirement_v2",
                resources.c.id.not_in(
                    select(conversation_meta.c.requirement_id).where(
                        conversation_meta.c.owner == owner_id, conversation_meta.c.archived.is_(True)
                    )
                ),
            )
            if after:
                at, rid = cursor(after)
                q = q.where(
                    or_(resources.c.created_at < at, and_(resources.c.created_at == at, resources.c.id < rid))
                )
            rows = (
                c.execute(q.order_by(resources.c.created_at.desc(), resources.c.id.desc()).limit(limit + 1))
                .mappings()
                .all()
            )
            next_cursor = (
                base64.urlsafe_b64encode(
                    dump([rows[limit - 1]["created_at"], rows[limit - 1]["id"]]).encode()
                )
                .decode()
                .rstrip("=")
                if len(rows) > limit
                else None
            )
            return envelope(
                request,
                dict(
                    items=[item(c, owner_id, r) for r in rows[:limit]],
                    next_cursor=next_cursor,
                    retention_days=store.settings.retention_days,
                ),
            )

    @routes.get("/history/{rid}")
    async def detail(rid: str, request: Request, owner_id: str = Depends(owner)):
        with store.engine.connect() as c:
            row = store.resource(owner_id, rid, c, "requirement_v2")
            r = state.revision(store, c, owner_id, rid).model_dump(mode="json")
            return envelope(
                request,
                dict(**item(c, owner_id, row), requirement=r, transcript=transcript(c, owner_id, rid, r)),
            )

    def edit(c, owner_id, rid, body, archive=False):
        store.resource(owner_id, rid, c, "requirement_v2")
        saved = meta(c, owner_id, rid)
        if saved["version"] != body.expected_version:
            raise AppError("HISTORY_CONFLICT", "Lịch sử đã thay đổi; tải lại trước khi sửa.", 409)
        values = dict(version=saved["version"] + 1, updated_at=now().isoformat())
        if archive:
            values["archived"] = True
        else:
            values.update(
                {k: v for k, v in dict(title=body.title, pinned=body.pinned).items() if v is not None}
            )
        if saved["version"] == 0:
            c.execute(
                insert(conversation_meta).values(
                    **dict(
                        requirement_id=rid,
                        owner=owner_id,
                        **{**dict(title="", pinned=False, archived=False), **values},
                    )
                )
            )
        else:
            c.execute(
                update(conversation_meta)
                .where(
                    conversation_meta.c.requirement_id == rid,
                    conversation_meta.c.owner == owner_id,
                    conversation_meta.c.version == body.expected_version,
                )
                .values(**values)
            )
        return meta(c, owner_id, rid)

    @routes.patch("/history/{rid}")
    async def patch(
        rid: str,
        body: HistoryEdit,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        data = store.mutate(
            owner_id,
            idempotency_key,
            dict(route=f"history:{rid}", body=body.model_dump()),
            lambda c: edit(c, owner_id, rid, body),
        )
        return envelope(request, data)

    @routes.post("/history/{rid}/archive")
    async def archive(
        rid: str,
        body: HistoryEdit,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        data = store.mutate(
            owner_id,
            idempotency_key,
            dict(route=f"archive:{rid}", body=body.model_dump()),
            lambda c: edit(c, owner_id, rid, body, True),
        )
        return envelope(request, data)

    @routes.post("/history/link-session")
    async def link(body: GuestLink, request: Request, owner_id: str = Depends(owner)):
        if not owner_id.startswith("user_"):
            raise AppError("ACCOUNT_REQUIRED", "Cần đăng nhập tài khoản để nhập phiên ẩn danh.", 403)
        digest = hashlib.sha256(body.anonymous_token.get_secret_value().encode()).hexdigest()
        with store.transaction() as c:
            prior = (
                c.execute(
                    select(linked_sessions).where(
                        linked_sessions.c.token_hash == digest,
                        linked_sessions.c.expires_at > now().isoformat(),
                    )
                )
                .mappings()
                .first()
            )
            if prior:
                if prior["owner"] != owner_id:
                    raise AppError("UNAUTHORIZED", "Phiên đã được nhập vào tài khoản khác.", 401)
                return envelope(request, dict(linked_requirements=prior["count"]))
            guest = c.execute(
                select(sessions.c.id).where(
                    sessions.c.token_hash == digest, sessions.c.expires_at > now().isoformat()
                )
            ).scalar()
            if not guest:
                raise AppError("UNAUTHORIZED", "Phiên ẩn danh không hợp lệ hoặc đã hết hạn.", 401)
            if c.execute(
                select(jobs.c.id).where(jobs.c.owner == guest, jobs.c.status.in_(["queued", "running"]))
            ).first():
                raise AppError(
                    "SESSION_BUSY", "Đợi tác vụ của phiên ẩn danh hoàn tất trước khi nhập lịch sử.", 409
                )
            # Idempotency keys are scoped to the former guest; discard them instead of colliding with account keys.
            c.execute(delete(idempotency).where(idempotency.c.owner == guest))
            count = c.execute(
                select(func.count())
                .select_from(resources)
                .where(resources.c.owner == guest, resources.c.kind == "requirement_v2")
            ).scalar()
            for table in (
                resources,
                jobs,
                state.proposals,
                state.snapshots,
                state.contacts,
                state.messages,
                state.activities,
                conversation_meta,
            ):
                c.execute(update(table).where(table.c.owner == guest).values(owner=owner_id))
            expires = c.execute(select(sessions.c.expires_at).where(sessions.c.id == guest)).scalar()
            c.execute(
                insert(linked_sessions).values(
                    token_hash=digest, owner=owner_id, count=count, expires_at=expires
                )
            )
            c.execute(delete(sessions).where(sessions.c.id == guest))
        return envelope(request, dict(linked_requirements=count))

    return routes
