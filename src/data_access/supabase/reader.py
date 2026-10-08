"""Bounded PostgreSQL reader. Never writes catalog tables or exposes connection errors."""

import asyncio
from datetime import date
from types import SimpleNamespace
from urllib.parse import urlsplit

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from data_access.supabase.adapter import (
    CatalogAdapter,
    candidate_id,
    lookup_url,
    relevance,
    source_id,
    supplier_id,
    wire,
)
from decision.candidates import assess_options
from domain.common import AppError, instant, now
from domain.crawl import SourceCapability
from domain.crawl_v2 import OfferSnapshotV2, TourSnapshotV2

REQUIRED = {
    "providers": {"id", "source_key", "display_name", "website", "observed_at"},
    "tours": {
        "id",
        "record_key",
        "provider_id",
        "url",
        "canonical_url",
        "observed_at",
        "tour_name",
        "departure_city",
        "destinations",
        "route",
        "transport",
        "duration_days",
        "duration_nights",
        "price",
        "currency",
        "price_type",
        "itinerary",
        "inclusions",
        "exclusions",
        "cancellation_policy",
        "surcharges",
        "child_policy",
        "evidence",
    },
    "offers": {
        "id",
        "record_key",
        "tour_id",
        "departure_date",
        "price",
        "availability",
        "price_by_age",
        "single_supplement",
        "observed_at",
        "evidence",
    },
}


def database_error(exc):
    code = getattr(getattr(exc, "orig", exc), "sqlstate", None)
    if code == "57014" or isinstance(exc, PoolTimeout):
        return AppError("SOURCE_TIMEOUT", "Kho tour quá thời hạn truy vấn.", 504, retryable=True)
    if code in {"42P01", "42703"}:
        return AppError("SUPABASE_SCHEMA_MISMATCH", "Schema kho tour không khớp contract đã cấu hình.", 502)
    if code == "42501":
        return AppError("SUPABASE_PERMISSION_DENIED", "Tài khoản database chưa có quyền đọc kho tour.", 502)
    return AppError("SUPABASE_UNAVAILABLE", "Không đọc được kho tour Supabase.", 503, retryable=True)


class SupabaseRepository:
    def __init__(self, settings, *, engine=None):
        self.settings = settings
        self.providers = None
        if engine is None:
            try:
                url = make_url(settings.supabase_tour_db_url.get_secret_value()).set(
                    drivername="postgresql+psycopg"
                )
                engine = create_engine(
                    url,
                    pool_size=settings.supabase_tour_pool_size,
                    max_overflow=0,
                    pool_timeout=settings.supabase_tour_connect_timeout_seconds,
                    pool_pre_ping=True,
                    hide_parameters=True,
                    isolation_level="REPEATABLE READ",
                    connect_args={
                        "connect_timeout": settings.supabase_tour_connect_timeout_seconds,
                        "sslmode": "require",
                        "options": "-c default_transaction_read_only=on -c statement_timeout="
                        + str(settings.supabase_tour_query_timeout_seconds * 1000),
                    },
                )
            except (ValueError, TypeError):
                raise AppError(
                    "SUPABASE_NOT_CONFIGURED", "Chưa cấu hình PostgreSQL tour database URL hợp lệ.", 503
                ) from None
        self.engine = engine

    def close(self):
        self.engine.dispose()

    def _schema(self, c):
        rows = c.execute(
            text(
                "SELECT table_name,column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name IN ('providers','tours','offers')"
            )
        ).mappings()
        present = {name: set() for name in REQUIRED}
        for row in rows:
            present[row["table_name"]].add(row["column_name"])
        missing = {
            name: sorted(fields - present[name])
            for name, fields in REQUIRED.items()
            if fields - present[name]
        }
        if missing:
            raise AppError(
                "SUPABASE_SCHEMA_MISMATCH",
                "Kho tour thiếu columns bắt buộc.",
                502,
                details={"missing_columns": missing},
            )

    def registry(self):
        try:
            with self.engine.connect() as c, c.begin():
                self._schema(c)
                self.providers = [
                    dict(r)
                    for r in c.execute(
                        text("SELECT * FROM public.providers ORDER BY id LIMIT 101")
                    ).mappings()
                ]
            if len(self.providers) > 100:
                raise AppError("CATALOG_PROVIDER_LIMIT", "Kho tour vượt giới hạn 100 nhà cung cấp.", 502)
            capabilities = []
            for p in self.providers:
                u = urlsplit(p["website"])
                lookup_url(p["website"])
                capabilities.append(
                    SourceCapability(
                        source_id=source_id(p),
                        supplier_id=supplier_id(p),
                        approved_domains=[u.hostname.lower()],
                        access_status="approved",
                        checked_at=wire(p["observed_at"]),
                        modes=["discover", "compare_urls"],
                        searchable_fields=["destinations", "departure_origin"],
                        returned_fields=[
                            "destinations",
                            "departure_origin",
                            "transport",
                            "duration_days",
                            "duration_nights",
                            "departure_date",
                        ],
                        limits={"catalog_read_only": 1, "live_refresh": 0},
                        freshness_seconds=dict(self.settings.supabase_tour_freshness_seconds),
                    )
                )
            for capability in capabilities:
                if capability.approved_domains[0] in self.settings.supabase_tour_trusted_domains:
                    capability.limits["catalog_validated"] = 1
            return capabilities
        except SQLAlchemyError as exc:
            raise database_error(exc) from None
        except (ValueError, TypeError, KeyError):
            raise AppError(
                "CATALOG_PROVIDER_INVALID", "Provider metadata trong kho tour không hợp lệ.", 502
            ) from None

    def probe(self):
        registry = self.registry()
        try:
            with self.engine.connect() as c, c.begin():
                counts = dict(
                    c.execute(
                        text(
                            "SELECT (SELECT count(*) FROM public.providers) AS providers, "
                            "(SELECT count(*) FROM public.tours) AS tours,(SELECT count(*) FROM public.offers) AS offers"
                        )
                    )
                    .mappings()
                    .one()
                )
                read_only = c.execute(text("SHOW transaction_read_only")).scalar_one()
            return {
                "status": "ok",
                "provider": "supabase",
                "transaction_read_only": read_only,
                "counts": counts,
                "sources": [{"id": s.source_id, "domains": s.approved_domains} for s in registry],
                "freshness_policy": "configured"
                if self.settings.supabase_tour_freshness_seconds
                else "unknown_until_configured",
                "catalog_policy": "catalog-validation-v1",
                "trusted_domains": self.settings.supabase_tour_trusted_domains,
            }
        except SQLAlchemyError as exc:
            raise database_error(exc) from None

    def _collect(self, request, conditions, limit, exclusions, requirement=None, registry=(), analysis=False):
        adapter = CatalogAdapter(
            request.request_id,
            registry=registry,
            trusted_domains=self.settings.supabase_tour_trusted_domains,
        )
        criteria = requirement or SimpleNamespace(
            conditions=conditions,
            hard_tree=request.query.hard_tree,
            party=request.query.party,
            readiness=SimpleNamespace(can_evaluate_hard_constraints=True),
        )
        sources = {s.source_id: s for s in registry}
        checked_at = now().isoformat()
        static_rejected = 0
        try:
            with self.engine.connect() as c, c.begin():
                remaining = (instant(request.deadline_at) - now()).total_seconds()
                if remaining <= 0:
                    raise AppError("JOB_DEADLINE_EXCEEDED", "Job đã quá thời hạn.", 504, retryable=True)
                ms = max(1, int(min(remaining, self.settings.supabase_tour_query_timeout_seconds) * 1000))
                c.execute(text("SELECT set_config('statement_timeout', :ms, true)"), {"ms": str(ms)})
                current_providers = [
                    dict(r)
                    for r in c.execute(
                        text("SELECT * FROM public.providers ORDER BY id LIMIT 101")
                    ).mappings()
                ]
                cached = {source_id(p): p for p in self.providers or []}
                providers = {}
                for p in current_providers:
                    sid = source_id(p)
                    if sid in request.source_ids:
                        if sid not in cached or p["website"] != cached[sid]["website"]:
                            raise AppError(
                                "CATALOG_PROVIDER_CHANGED",
                                "Provider metadata đã đổi; cần kiểm tra lại registry trước khi đọc.",
                                409,
                            )
                        providers[p["id"]] = p
                stmt = text(
                    "SELECT * FROM public.tours WHERE provider_id IN :ids ORDER BY id LIMIT :lim"
                ).bindparams(bindparam("ids", expanding=True))
                rows = [
                    dict(r)
                    for r in c.execute(
                        stmt, {"ids": list(providers), "lim": self.settings.supabase_tour_scan_limit + 1}
                    ).mappings()
                ]
                scan_truncated = len(rows) > self.settings.supabase_tour_scan_limit
                rows = rows[: self.settings.supabase_tour_scan_limit]
                valid_rows = []
                for row in rows:
                    try:
                        urls = [u for u in [row.get("url"), row.get("canonical_url")] if u]
                        if not urls:
                            raise ValueError("Tour URL is missing")
                        for url in urls:
                            lookup_url(url)
                        valid_rows.append(row)
                    except (ValueError, TypeError, AttributeError):
                        adapter.issue(
                            "CATALOG_RECORD_INVALID",
                            source_id(providers[row["provider_id"]]),
                            "Tour URL không hợp lệ; đã cách ly record.",
                        )
                rows = valid_rows
                selected, bindings, failures = {}, [], []
                if request.mode == "compare_urls":
                    for target in request.targets:
                        matches = [
                            r
                            for r in rows
                            if any(
                                lookup_url(x) == lookup_url(target.url)
                                for x in [r.get("url"), r.get("canonical_url")]
                                if x
                            )
                        ]
                        sid = next(
                            (
                                source_id(p)
                                for p in providers.values()
                                if urlsplit(p["website"]).hostname == urlsplit(target.url).hostname
                            ),
                            "unapproved",
                        )
                        if len(matches) != 1:
                            failures.append(
                                {
                                    "source_id": sid,
                                    "target_id": target.target_id,
                                    "status": "partial" if scan_truncated else "unsupported",
                                    "reason_code": "CATALOG_LOOKUP_TRUNCATED"
                                    if scan_truncated
                                    else "CATALOG_URL_AMBIGUOUS"
                                    if matches
                                    else "CATALOG_URL_NOT_FOUND",
                                    "truncated": scan_truncated,
                                }
                            )
                        else:
                            selected[matches[0]["id"]] = matches[0]
                            bindings.append((sid, target.target_id, [matches[0]["id"]]))
                else:
                    available = []
                    for row in rows:
                        try:
                            if candidate_id(row, providers[row["provider_id"]]) not in exclusions:
                                available.append((relevance(row, conditions), row))
                        except (ValueError, TypeError, KeyError, AttributeError):
                            adapter.issue(
                                "CATALOG_RECORD_INVALID",
                                source_id(providers[row["provider_id"]]),
                                "Tour record không đúng contract; đã cách ly.",
                            )
                    available.sort(key=lambda x: (-x[0], x[1]["id"]))
                    selected = {row["id"]: row for _, row in available}
                    for p in providers.values():
                        bindings.append(
                            (
                                source_id(p),
                                None,
                                [r["id"] for r in selected.values() if r["provider_id"] == p["id"]],
                            )
                        )
                retained = {}
                for row in selected.values():
                    try:
                        url = row.get("canonical_url") or row["url"]
                        if (
                            urlsplit(url).hostname
                            != urlsplit(providers[row["provider_id"]]["website"]).hostname
                        ):
                            raise ValueError("Catalog tour domain does not match provider")
                        retained[row["id"]] = adapter.add_tour(row, providers[row["provider_id"]])
                        if request.mode == "discover" and not analysis:
                            tour = TourSnapshotV2.model_validate(retained[row["id"]])
                            source = sources.get(source_id(providers[row["provider_id"]]))
                            if (
                                assess_options(criteria, tour, [], source, checked_at)["hard_status"]
                                == "fail"
                            ):
                                retained.pop(row["id"])
                                static_rejected += 1
                    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
                        retained.pop(row["id"], None)
                        adapter.issue(
                            "CATALOG_RECORD_INVALID",
                            source_id(providers[row["provider_id"]]),
                            "Tour record không đúng contract; đã cách ly.",
                        )
                offer_truncated = False
                if retained:
                    remaining = (instant(request.deadline_at) - now()).total_seconds()
                    if remaining <= 0:
                        raise AppError("JOB_DEADLINE_EXCEEDED", "Job đã quá thời hạn.", 504, retryable=True)
                    c.execute(
                        text("SELECT set_config('statement_timeout', :ms, true)"),
                        {
                            "ms": str(
                                max(
                                    1,
                                    int(
                                        min(remaining, self.settings.supabase_tour_query_timeout_seconds)
                                        * 1000
                                    ),
                                )
                            )
                        },
                    )
                    anchor = (
                        None
                        if analysis
                        else next(
                            (
                                getattr(cn.value, "resolved_date", None) or getattr(cn.value, "value", None)
                                for cn in conditions
                                if cn.field == "departure_date"
                            ),
                            None,
                        )
                    )
                    try:
                        anchor = date.fromisoformat(anchor) if isinstance(anchor, str) else None
                    except ValueError:
                        anchor = None
                    query = text(
                        "SELECT * FROM (SELECT offers.*,count(*) OVER (PARTITION BY tour_id) AS catalog_total,row_number() OVER (PARTITION BY tour_id "
                        "ORDER BY CASE WHEN CAST(:anchor AS date) IS NULL THEN 0 ELSE abs(departure_date - CAST(:anchor AS date)) END, "
                        "departure_date NULLS LAST,id) AS catalog_order FROM public.offers WHERE tour_id IN :ids) picked "
                        "ORDER BY catalog_order,tour_id LIMIT :lim"
                    ).bindparams(bindparam("ids", expanding=True))
                    offer_rows = [
                        dict(r)
                        for r in c.execute(
                            query,
                            {
                                "ids": list(retained),
                                "anchor": anchor,
                                "lim": self.settings.supabase_tour_max_offers + 1,
                            },
                        ).mappings()
                    ]
                    offer_truncated = len(offer_rows) > self.settings.supabase_tour_max_offers
                    totals = {}
                    loaded = {}
                    for row in offer_rows[: self.settings.supabase_tour_max_offers]:
                        row.pop("catalog_order", None)
                        total = row.pop("catalog_total", None)
                        if total is not None:
                            totals[row["tour_id"]] = total
                        try:
                            adapter.add_offer(row)
                            loaded[row["tour_id"]] = loaded.get(row["tour_id"], 0) + 1
                        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
                            adapter.issue(
                                "CATALOG_RECORD_INVALID",
                                source_id(providers[selected[row["tour_id"]]["provider_id"]]),
                                "Offer không đúng contract; đã cách ly.",
                                snapshot_id=retained[row["tour_id"]]["snapshot_id"],
                            )
                else:
                    totals, loaded = {}, {}
                assessments = {}
                coverage = {}
                for tid, raw in retained.items():
                    tour = TourSnapshotV2.model_validate(raw)
                    complete = loaded.get(tid, 0) == totals[tid] if tid in totals else not offer_truncated
                    # A quarantined offer means coverage is incomplete even without a global LIMIT.
                    if any(
                        i.get("snapshot_id") == tour.snapshot_id and i["code"] == "CATALOG_RECORD_INVALID"
                        for i in adapter.payload["issues"]
                    ):
                        complete = False
                    coverage[tour.snapshot_id] = complete
                    options = [
                        OfferSnapshotV2.model_validate(o)
                        for o in adapter.payload["offers"]
                        if o["tour_snapshot_id"] == tour.snapshot_id
                    ]
                    assessments[tid] = assess_options(
                        criteria,
                        tour,
                        options,
                        sources.get(source_id(providers[selected[tid]["provider_id"]])),
                        checked_at,
                        complete=complete,
                    )
                offer_rejected = 0
                pool_truncated = False
                if request.mode == "discover":
                    surviving = [
                        tid for tid in retained if analysis or assessments[tid]["hard_status"] != "fail"
                    ]
                    offer_rejected = len(retained) - len(surviving)
                    surviving.sort(
                        key=lambda tid: (
                            0 if analysis or assessments[tid]["hard_status"] in {None, "pass"} else 1,
                            -relevance(selected[tid], conditions),
                            tid,
                        )
                    )
                    pool_truncated = len(surviving) > limit
                    retained = {tid: retained[tid] for tid in surviving[:limit]}
                    bindings = [
                        (
                            source_id(p),
                            None,
                            [tid for tid in retained if selected[tid]["provider_id"] == p["id"]],
                        )
                        for p in providers.values()
                    ]
                kept = {t["snapshot_id"] for t in retained.values()}
                adapter.payload["tours"] = [t for t in adapter.payload["tours"] if t["snapshot_id"] in kept]
                adapter.payload["offers"] = [
                    o for o in adapter.payload["offers"] if o["tour_snapshot_id"] in kept
                ]
                snapshot_ids = kept | {o["snapshot_id"] for o in adapter.payload["offers"]}
                adapter.payload["evidence"] = [
                    e for e in adapter.payload["evidence"] if e["snapshot_id"] in snapshot_ids
                ]
                adapter.payload["issues"] = adapter.payload["issues"][:1990]
                adapter.payload["offer_coverage"] = {k: v for k, v in coverage.items() if k in kept}
                adapter.payload["retrieval"] = dict(
                    policy_version="what-if-acquisition-v1" if analysis else "structured-retrieval-v1",
                    scanned_count=len(rows),
                    static_rejected=static_rejected,
                    offer_rejected=offer_rejected,
                    retained_count=len(retained),
                    pass_count=sum(assessments[tid]["hard_status"] == "pass" for tid in retained),
                    unknown_count=sum(assessments[tid]["hard_status"] == "unknown" for tid in retained),
                    scan_truncated=scan_truncated,
                    pool_truncated=pool_truncated,
                    offer_truncated=offer_truncated,
                    candidate_limit=limit,
                    filtering="unfiltered_analysis_universe" if analysis else "evidence_bound_before_pool",
                )
            adapter.payload["source_results"].extend(failures)
            for sid, target, ids in bindings:
                tours = [retained[i]["snapshot_id"] for i in ids if i in retained]
                offers = [
                    o["snapshot_id"] for o in adapter.payload["offers"] if o["tour_snapshot_id"] in tours
                ]
                adapter.payload["source_results"].append(
                    {
                        "source_id": sid,
                        "target_id": target,
                        "status": "partial" if tours else "ok" if not ids else "error",
                        "reason_code": "CATALOG_FIELD_EVIDENCE_INCOMPLETE"
                        if tours
                        else "CATALOG_RECORDS_INVALID"
                        if ids
                        else "CATALOG_NO_MATCHES",
                        "tour_snapshot_ids": tours,
                        "offer_snapshot_ids": offers,
                        "truncated": scan_truncated or offer_truncated or pool_truncated,
                    }
                )
                if tours:
                    adapter.issue(
                        "CATALOG_FIELD_EVIDENCE_INCOMPLETE",
                        sid,
                        "Dữ liệu catalog thật; một số fields chỉ có record provenance, chưa đủ bằng chứng để kết luận điều kiện.",
                    )
            return adapter.finish()
        except SQLAlchemyError as exc:
            raise database_error(exc) from None

    async def collect(
        self,
        request,
        *,
        conditions=(),
        candidate_limit=20,
        exclusions=(),
        requirement=None,
        registry=(),
        analysis=False,
    ):
        remaining = (instant(request.deadline_at) - now()).total_seconds()
        if remaining <= 0:
            raise AppError("JOB_DEADLINE_EXCEEDED", "Job đã quá thời hạn.", 504, retryable=True)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._collect,
                    request,
                    conditions,
                    min(candidate_limit, 500 if analysis else 100),
                    set(exclusions),
                    requirement,
                    registry,
                    analysis,
                ),
                timeout=remaining,
            )
        except TimeoutError:
            raise AppError("SOURCE_TIMEOUT", "Kho tour quá thời hạn của job.", 504, retryable=True) from None
