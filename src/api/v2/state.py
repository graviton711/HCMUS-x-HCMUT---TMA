"""Durable v2 records; the caller owns transaction and job publication gates."""

import json

from sqlalchemy import Column, Integer, String, Table, Text, delete, func, insert, select, update

from api.store import dump, jobs, metadata, revisions
from api.v2.models import JobEvent, Proposal, RequirementV2
from domain.common import AppError, now

proposals = Table(
    "proposals",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("requirement_id", String, index=True),
    Column("version", Integer),
    Column("status", String),
    Column("payload", Text),
)
job_events = Table(
    "job_events",
    metadata,
    Column("job_id", String, primary_key=True),
    Column("seq", Integer, primary_key=True),
    Column("payload", Text),
)
snapshots = Table(
    "snapshot_records",
    metadata,
    Column("comparison_id", String, primary_key=True),
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("kind", String),
    Column("payload", Text),
)
source_registry = Table(
    "source_registry",
    metadata,
    Column("id", String, primary_key=True),
    Column("version", Integer),
    Column("payload", Text),
)
contacts = Table(
    "contacts",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("version", Integer),
    Column("status", String),
    Column("created_at", String, index=True),
    Column("payload", Text),
)
audit = Table(
    "admin_audit",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String, index=True),
    Column("resource_id", String, index=True),
    Column("payload", Text),
)
messages = Table(
    "conversation_messages",
    metadata,
    Column("requirement_id", String, primary_key=True),
    Column("client_message_id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("payload", Text),
    Column("created_at", String),
)
activities = Table(
    "session_activity",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("kind", String),
    Column("created_at", String, index=True),
)


def emit(c, job_id, stage, status, summary, **kwargs):
    seq = (
        c.execute(select(func.max(job_events.c.seq)).where(job_events.c.job_id == job_id)).scalar() or 0
    ) + 1
    event = JobEvent(
        seq=seq,
        job_id=job_id,
        stage=stage,
        status=status,
        occurred_at=now().isoformat(),
        summary=summary,
        **kwargs,
    )
    c.execute(insert(job_events).values(job_id=job_id, seq=seq, payload=event.model_dump_json()))


def revision(store, c, owner, rid, rev=None):
    from requirements.completeness import apply_completeness
    from requirements.semantic import finalize_v2

    resource = store.resource(owner, rid, c, "requirement_v2")
    number = resource["revision"] if rev is None else rev
    if number == 0:
        return apply_completeness(RequirementV2.model_validate_json(resource["payload"]))
    payload = c.execute(
        select(revisions.c.payload).where(revisions.c.resource_id == rid, revisions.c.revision == number)
    ).scalar()
    if payload is None:
        raise AppError("NOT_FOUND", "Không tìm thấy revision.", 404)
    return finalize_v2(RequirementV2.model_validate_json(payload))


def proposal(c, owner, pid):
    from requirements.semantic import finalize_v2

    row = (
        c.execute(select(proposals).where(proposals.c.id == pid, proposals.c.owner == owner))
        .mappings()
        .first()
    )
    if row is None:
        raise AppError("NOT_FOUND", "Không tìm thấy proposal.", 404)
    p = Proposal.model_validate_json(row["payload"])
    preview = finalize_v2(p.preview)
    p = p.model_copy(
        update={"preview": preview, "clarifications": [q.model_dump() for q in preview.clarifications]}
    )
    if p.status in {"pending", "needs_clarification"}:
        p = p.model_copy(update={"status": "needs_clarification" if preview.clarifications else "pending"})
    if p.status in {"pending", "needs_clarification"} and p.expires_at <= now().isoformat():
        p = p.model_copy(update={"status": "expired"})
    return p


def save_proposal(c, owner, p, expected=None):
    values = dict(version=p.version, status=p.status, payload=p.model_dump_json())
    if expected is None:
        c.execute(insert(proposals).values(id=p.id, owner=owner, requirement_id=p.requirement_id, **values))
    else:
        count = c.execute(
            update(proposals)
            .where(proposals.c.id == p.id, proposals.c.owner == owner, proposals.c.version == expected)
            .values(**values)
        ).rowcount
        if count != 1:
            raise AppError("PROPOSAL_CONFLICT", "Proposal đã thay đổi; tải phiên bản mới.", 409)


def guard_proposal(store, c, owner, p, rev, version, *, allow_parse=False):
    current = revision(store, c, owner, p.requirement_id)
    if current.revision != rev or p.base_revision != rev:
        raise AppError(
            "REVISION_CONFLICT",
            "Yêu cầu đã thay đổi; tải revision mới.",
            409,
            details={"current_revision": current.revision, "requirement_id": current.id},
        )
    if p.version != version:
        raise AppError(
            "PROPOSAL_CONFLICT",
            "Proposal đã thay đổi; tải phiên bản mới.",
            409,
            details={"proposal_id": p.id, "current_version": p.version},
        )
    if p.status == "expired":
        raise AppError("PROPOSAL_EXPIRED", "Proposal đã hết hạn.", 410)
    if p.status not in {"pending", "needs_clarification"}:
        raise AppError("PROPOSAL_CONFLICT", "Proposal không còn chỉnh sửa được.", 409)
    if p.parse_job_id and not allow_parse:
        job = c.execute(select(jobs.c.status).where(jobs.c.id == p.parse_job_id)).scalar()
        if job != "succeeded":
            raise AppError(
                "PROPOSAL_NOT_READY", "Parse chưa thành công; sửa hoặc thử lại trước khi xác nhận.", 409
            )
    return current


def running(c, row, worker_id):
    current = (
        c.execute(
            select(jobs).where(
                jobs.c.id == row["id"], jobs.c.status == "running", jobs.c.lease_owner == worker_id
            )
        )
        .mappings()
        .first()
    )
    if current is None:
        return False
    if current["deadline_at"] <= now().isoformat():
        raise AppError("JOB_DEADLINE_EXCEEDED", "Job vượt thời hạn.", 504, retryable=True)
    return True


def finish(c, row, worker_id, status="succeeded", metrics=None):
    if not running(c, row, worker_id):
        return False
    c.execute(
        update(jobs)
        .where(jobs.c.id == row["id"])
        .values(
            status=status,
            phase="completed",
            completed_at=now().isoformat(),
            metrics=dump(metrics) if metrics else None,
        )
    )
    emit(
        c, row["id"], "publication", "partial" if status == "partial" else "completed", "Kết quả đã được lưu."
    )
    return True


def events(store, owner, jid, after_seq, limit):
    store.job(owner, jid)
    with store.engine.connect() as c:
        rows = (
            c.execute(
                select(job_events)
                .where(job_events.c.job_id == jid, job_events.c.seq > after_seq)
                .order_by(job_events.c.seq)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
    return {
        "items": [json.loads(r["payload"]) for r in rows[:limit]],
        "next_seq": rows[min(limit, len(rows)) - 1]["seq"] if rows else after_seq,
        "has_more": len(rows) > limit,
    }


def persist_snapshots(c, owner, cid, crawl):
    for kind, records in (("tour", crawl.tours), ("offer", crawl.offers), ("evidence", crawl.evidence)):
        for record in records:
            identifier = record.id if kind == "evidence" else record.snapshot_id
            c.execute(
                insert(snapshots).values(
                    comparison_id=cid, id=identifier, owner=owner, kind=kind, payload=record.model_dump_json()
                )
            )


def purge(c, resource_ids, job_ids):
    c.execute(delete(proposals).where(proposals.c.requirement_id.in_(resource_ids)))
    c.execute(delete(messages).where(messages.c.requirement_id.in_(resource_ids)))
    c.execute(delete(snapshots).where(snapshots.c.comparison_id.in_(resource_ids)))
    c.execute(delete(job_events).where(job_events.c.job_id.in_(job_ids)))
