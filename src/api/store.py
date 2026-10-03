import hashlib
import json
import secrets
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.pool import StaticPool

from domain.common import AppError, now, uid

metadata = MetaData()
sessions = Table(
    "sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("token_hash", String, unique=True),
    Column("expires_at", String),
    Column("created_at", String),
)
resources = Table(
    "resources",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("kind", String),
    Column("revision", Integer),
    Column("status", String),
    Column("payload", Text),
    Column("created_at", String),
)
revisions = Table(
    "requirement_revisions",
    metadata,
    Column("resource_id", String, primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("payload", Text),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, index=True),
    Column("resource_id", String),
    Column("kind", String),
    Column("status", String, index=True),
    Column("payload", Text),
    Column("error", Text),
    Column("metrics", Text),
    Column("phase", String),
    Column("created_at", String),
    Column("deadline_at", String),
    Column("completed_at", String),
    Column("lease_owner", String),
    Column("lease_until", String),
)
idempotency = Table(
    "idempotency",
    metadata,
    Column("owner", String, primary_key=True),
    Column("key", String, primary_key=True),
    Column("body_hash", String),
    Column("response", Text),
    Column("expires_at", String),
)
schema_info = Table("schema_info", metadata, Column("version", Integer, primary_key=True))
TERMINAL = {"succeeded", "partial", "failed", "cancelled"}


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class Store:
    def __init__(self, settings):
        self.settings = settings
        filename = settings.database_url.removeprefix("sqlite:///")
        if filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False, "timeout": 15},
            **({"poolclass": StaticPool} if filename == ":memory:" else {}),
        )
        metadata.create_all(self.engine)
        with self.transaction() as c:
            version = c.execute(select(schema_info.c.version)).scalar()
            if version is None:
                c.execute(insert(schema_info).values(version=1))
            elif version != 1:
                raise RuntimeError("Unsupported database schema; migration required")

    @contextmanager
    def transaction(self):
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def new_session(self):
        token, owner, timestamp = secrets.token_urlsafe(32), uid("session"), now()
        expiry = (timestamp + timedelta(hours=self.settings.session_ttl_hours)).isoformat()
        with self.transaction() as c:
            c.execute(
                insert(sessions).values(
                    id=owner,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    created_at=timestamp.isoformat(),
                    expires_at=expiry,
                )
            )
        return {"session_id": owner, "token": token, "token_type": "bearer", "expires_at": expiry}

    def authenticate(self, token):
        with self.engine.connect() as c:
            owner = c.execute(
                select(sessions.c.id).where(
                    sessions.c.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                    sessions.c.expires_at > now().isoformat(),
                )
            ).scalar()
        if owner is None:
            raise AppError("UNAUTHORIZED", "Session thiếu, không hợp lệ hoặc đã hết hạn.", 401)
        return owner

    def mutate(self, owner, key, fingerprint, callback):
        if key is not None and (not 1 <= len(key) <= 128 or any(ord(x) < 33 or ord(x) > 126 for x in key)):
            raise AppError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key không hợp lệ.")
        hashed = hashlib.sha256(dump(fingerprint).encode()).hexdigest()
        with self.transaction() as c:
            if key:
                old = (
                    c.execute(
                        select(idempotency).where(idempotency.c.owner == owner, idempotency.c.key == key)
                    )
                    .mappings()
                    .first()
                )
                if old and old["expires_at"] <= now().isoformat():
                    c.execute(
                        delete(idempotency).where(idempotency.c.owner == owner, idempotency.c.key == key)
                    )
                    old = None
                if old:
                    if old["body_hash"] != hashed:
                        raise AppError("IDEMPOTENCY_CONFLICT", "Key đã dùng với nội dung khác.", 409)
                    return json.loads(old["response"])
            result = callback(c)
            if key:
                c.execute(
                    insert(idempotency).values(
                        owner=owner,
                        key=key,
                        body_hash=hashed,
                        response=dump(result),
                        expires_at=(now() + timedelta(days=1)).isoformat(),
                    )
                )
            return result

    def resource(self, owner, resource_id, connection=None, kind=None):
        def read(c):
            row = (
                c.execute(select(resources).where(resources.c.owner == owner, resources.c.id == resource_id))
                .mappings()
                .first()
            )
            if row is None or (kind and row["kind"] != kind):
                raise AppError("NOT_FOUND", "Không tìm thấy resource.", 404)
            return dict(row)

        if connection is not None:
            return read(connection)
        with self.engine.connect() as c:
            return read(c)

    def revision(self, owner, resource_id, revision=None, connection=None):
        def read(c):
            resource = self.resource(owner, resource_id, c, "requirement")
            rev = resource["revision"] if revision is None else revision
            row = c.execute(
                select(revisions.c.payload).where(
                    revisions.c.resource_id == resource_id, revisions.c.revision == rev
                )
            ).scalar()
            if row is None:
                raise AppError("REQUIREMENT_NOT_PARSED", "Revision chưa tồn tại hoặc chưa parse xong.", 409)
            from domain.requirements import Requirement

            return Requirement.model_validate_json(row)

        if connection is not None:
            return read(connection)
        with self.engine.connect() as c:
            return read(c)

    def add_resource(self, c, owner, resource_id, kind, payload, revision=0, status="queued"):
        c.execute(
            insert(resources).values(
                id=resource_id,
                owner=owner,
                kind=kind,
                payload=dump(payload),
                revision=revision,
                status=status,
                created_at=now().isoformat(),
            )
        )

    def add_revision(self, c, owner, r, expected):
        changed = c.execute(
            update(resources)
            .where(resources.c.id == r.id, resources.c.owner == owner, resources.c.revision == expected)
            .values(revision=r.revision, status="ready")
        ).rowcount
        if changed != 1:
            raise AppError("REVISION_CONFLICT", "Nhu cầu đã thay đổi; tải revision mới trước khi sửa.", 409)
        c.execute(
            insert(revisions).values(resource_id=r.id, revision=r.revision, payload=r.model_dump_json())
        )

    def add_job(self, c, owner, resource_id, kind, payload):
        pending = c.execute(
            select(jobs.c.id).where(jobs.c.owner == owner, jobs.c.status.in_(["queued", "running"]))
        ).all()
        total = c.execute(select(jobs.c.id).where(jobs.c.status.in_(["queued", "running"])).limit(100)).all()
        if len(pending) >= self.settings.max_pending_jobs or len(total) >= 100:
            raise AppError("TOO_MANY_JOBS", "Đang có quá nhiều tác vụ chờ.", 429, retryable=True)
        job_id, timestamp = uid("job"), now()
        c.execute(
            insert(jobs).values(
                id=job_id,
                owner=owner,
                resource_id=resource_id,
                kind=kind,
                status="queued",
                payload=dump(payload),
                error=None,
                metrics=None,
                phase="queued",
                created_at=timestamp.isoformat(),
                deadline_at=(timestamp + timedelta(seconds=self.settings.job_timeout_seconds)).isoformat(),
            )
        )
        return job_id

    def job(self, owner, job_id):
        with self.engine.connect() as c:
            row = c.execute(select(jobs).where(jobs.c.owner == owner, jobs.c.id == job_id)).mappings().first()
        if row is None:
            raise AppError("NOT_FOUND", "Không tìm thấy job.", 404)
        return {
            k: (json.loads(v) if v else None) if k in {"error", "metrics"} else v
            for k, v in row.items()
            if k not in {"payload", "owner", "lease_owner", "lease_until"}
        }

    def cancel(self, c, owner, job_id):
        row = c.execute(select(jobs).where(jobs.c.id == job_id, jobs.c.owner == owner)).mappings().first()
        if row is None:
            raise AppError("NOT_FOUND", "Không tìm thấy job.", 404)
        if row["status"] not in TERMINAL:
            c.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(status="cancelled", phase="cancelled", completed_at=now().isoformat())
            )
            if row["kind"] == "comparison" or json.loads(row["payload"]).get("expected_revision") == 0:
                c.execute(
                    update(resources).where(resources.c.id == row["resource_id"]).values(status="cancelled")
                )
        return {"job_id": job_id, "status": row["status"] if row["status"] in TERMINAL else "cancelled"}

    def recover(self):
        with self.transaction() as c:
            rows = c.execute(select(jobs).where(jobs.c.status == "running")).mappings().all()
            for row in rows:
                self.fail(
                    c,
                    row,
                    AppError(
                        "JOB_INTERRUPTED",
                        "Backend đã khởi động lại; hãy gửi lại tác vụ.",
                        503,
                        retryable=True,
                    ),
                )

    def fail(self, c, row, error):
        count = c.execute(
            update(jobs)
            .where(jobs.c.id == row["id"], jobs.c.status.in_(["queued", "running"]))
            .values(
                status="failed", phase="failed", error=dump(error.payload()), completed_at=now().isoformat()
            )
        ).rowcount
        if count and (
            row["kind"] == "comparison" or json.loads(row["payload"]).get("expected_revision") == 0
        ):
            c.execute(update(resources).where(resources.c.id == row["resource_id"]).values(status="failed"))

    def claim(self, worker_id):
        with self.transaction() as c:
            row = (
                c.execute(select(jobs).where(jobs.c.status == "queued").order_by(jobs.c.created_at).limit(1))
                .mappings()
                .first()
            )
            if not row:
                return None
            if row["deadline_at"] <= now().isoformat():
                self.fail(
                    c,
                    row,
                    AppError(
                        "JOB_DEADLINE_EXCEEDED", "Tác vụ hết thời hạn trong hàng chờ.", 504, retryable=True
                    ),
                )
                return None
            changed = c.execute(
                update(jobs)
                .where(jobs.c.id == row["id"], jobs.c.status == "queued")
                .values(
                    status="running",
                    phase="extracting" if row["kind"] == "parse" else "collecting",
                    lease_owner=worker_id,
                    lease_until=row["deadline_at"],
                )
            ).rowcount
            return dict(row) if changed else None

    def commit_job(self, row, worker_id, r=None, comparison=None, metrics=None):
        with self.transaction() as c:
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
                return
            if current["deadline_at"] <= now().isoformat():
                self.fail(
                    c, current, AppError("JOB_DEADLINE_EXCEEDED", "Tác vụ hết thời hạn.", 504, retryable=True)
                )
                return
            status = "succeeded"
            if r is not None:
                self.add_revision(c, row["owner"], r, json.loads(row["payload"])["expected_revision"])
            if comparison is not None:
                status = comparison.pop("job_status")
                c.execute(
                    update(resources)
                    .where(resources.c.id == row["resource_id"])
                    .values(status=status, payload=dump(comparison))
                )
            c.execute(
                update(jobs)
                .where(jobs.c.id == row["id"], jobs.c.status == "running", jobs.c.lease_owner == worker_id)
                .values(
                    status=status,
                    phase="completed",
                    metrics=dump(metrics) if metrics else None,
                    completed_at=now().isoformat(),
                )
            )

    def purge(self):
        cutoff = (now() - timedelta(days=self.settings.retention_days)).isoformat()
        with self.transaction() as c:
            pending = c.execute(select(jobs).where(jobs.c.status.in_(["queued", "running"]))).mappings().all()
            protected = {j["resource_id"] for j in pending}
            for job in pending:
                payload = json.loads(job["payload"])
                protected.update(
                    payload[k] for k in ("requirement_id", "reuse_comparison_id") if payload.get(k)
                )
            ids = list(
                c.execute(
                    select(resources.c.id).where(
                        resources.c.created_at < cutoff, resources.c.id.not_in(protected)
                    )
                ).scalars()
            )
            if ids:
                c.execute(delete(revisions).where(revisions.c.resource_id.in_(ids)))
                c.execute(delete(jobs).where(jobs.c.resource_id.in_(ids)))
                c.execute(delete(resources).where(resources.c.id.in_(ids)))
            c.execute(delete(idempotency).where(idempotency.c.expires_at < now().isoformat()))
            c.execute(delete(sessions).where(sessions.c.expires_at < now().isoformat()))
        return {"resources_deleted": len(ids)}
