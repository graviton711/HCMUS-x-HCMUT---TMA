"""One orchestration boundary, with explicit legacy crawler transport."""

import asyncio

from data_access.gateway import DataGateway
from domain.common import AppError, instant, now, uid
from domain.crawl import CrawlResult, SourceCapability, SourceResult
from domain.crawl_v2 import CrawlResultV2
from domain.requirements import Readiness, RequirementState
from requirements.semantic import legacy_requirement


def core_requirement(r, mode, targets):
    if hasattr(r, "issues"):
        return legacy_requirement(r, query=True, mode=mode, targets=targets)
    data = {k: v for k, v in r.model_dump().items() if k in RequirementState.model_fields}
    data.update(schema_version="1.0", revision=max(1, r.revision), mode=mode, targets=targets)
    data["readiness"] = {k: v for k, v in data["readiness"].items() if k in Readiness.model_fields}
    return RequirementState.model_validate(data)


def merge_results(results):
    combined = {field: {} for field in ("suppliers", "tours", "offers", "evidence")}
    source_results, issues, origin = [], [], None
    coverage, retrieval = {}, []
    for result in results:
        if origin is not None and origin != result.origin:
            raise AppError("CRAWLER_INVALID_OUTPUT", "Không gộp nguồn thật và mô phỏng.", 502)
        origin = result.origin
        source_results.extend(result.source_results)
        issues.extend(result.issues)
        for key, complete in getattr(result, "offer_coverage", {}).items():
            coverage[key] = coverage.get(key, True) and complete
        if getattr(result, "retrieval", {}):
            retrieval.append(result.retrieval)
        for field, mapping in combined.items():
            key = "supplier_id" if field == "suppliers" else "id" if field == "evidence" else "snapshot_id"
            for item in getattr(result, field):
                identifier = getattr(item, key)
                if identifier in mapping and mapping[identifier] != item:
                    raise AppError("CRAWLER_INVALID_OUTPUT", "Snapshot ID trùng với nội dung khác.", 502)
                mapping[identifier] = item
    return CrawlResultV2(
        request_id=uid("crawl"),
        origin=origin or "source",
        source_results=source_results,
        issues=issues,
        offer_coverage=coverage,
        retrieval={"runs": retrieval} if retrieval else {},
        **{k: [item.model_dump() for item in v.values()] for k, v in combined.items()},
    )


class GatewayV2:
    def __init__(self, gateway, registry):
        # Do not mutate the v1 gateway or share mutable registry state across awaits.
        self.gateway = DataGateway(
            gateway.settings,
            registry=registry,
            transport=gateway.transport,
            result_model=CrawlResultV2,
            catalog_repository=getattr(gateway, "catalog_repository", None),
        )
        self.registry = registry

    async def collect_analysis(self, r, deadline_at, *, candidate_limit=100, exclusions=()):
        """One unfiltered acquisition for baseline AND scenarios; never merge separate reads."""
        mode = "compare_urls" if r.mode == "compare_urls" else "discover"
        neutral = r.model_copy(
            update={
                "conditions": [],
                "hard_tree": type(r.hard_tree)(kind="all"),
                "preference_tree": type(r.preference_tree)(kind="all"),
                "issues": [],
            }
        )
        core = core_requirement(neutral, mode, r.targets if mode == "compare_urls" else [])
        result = await self.gateway.collect(
            core,
            deadline_at,
            catalog_conditions=r.conditions,
            catalog_requirement=r,
            candidate_limit=candidate_limit,
            exclusions=exclusions,
            catalog_analysis=True,
        )
        result = CrawlResultV2.model_validate(result.model_dump())
        # HTTP/fixture may ignore candidate budgets. Bound the retained universe consistently.
        if len(result.tours) > candidate_limit:
            keep = {t.snapshot_id for t in result.tours[:candidate_limit]}
            offers = [o for o in result.offers if o.tour_snapshot_id in keep]
            snapshots = keep | {o.snapshot_id for o in offers}
            result = result.model_copy(
                update={
                    "tours": result.tours[:candidate_limit],
                    "offers": offers,
                    "evidence": [e for e in result.evidence if e.snapshot_id in snapshots],
                    "offer_coverage": {k: v for k, v in result.offer_coverage.items() if k in keep},
                    "source_results": [
                        s.model_copy(
                            update={
                                "tour_snapshot_ids": [t for t in s.tour_snapshot_ids if t in keep],
                                "offer_snapshot_ids": [o for o in s.offer_snapshot_ids if o in snapshots],
                                "truncated": True,
                            }
                        )
                        for s in result.source_results
                    ],
                    "retrieval": {**result.retrieval, "pool_truncated": True},
                }
            )
        result.retrieval = {
            **result.retrieval,
            "analysis_acquisition": True,
            "requested_mode": mode,
            "consistency": "repeatable_read"
            if self.gateway.settings.data_provider == "supabase"
            else "single_upstream_response",
            "upstream_scope": "bounded_catalog"
            if self.gateway.settings.data_provider == "supabase"
            else "reference_urls"
            if mode == "compare_urls"
            else "bounded_upstream_response",
        }
        return CrawlResultV2.model_validate(result.model_dump())

    async def collect(self, r, deadline_at, *, candidate_limit=20, exclusions=()):
        tasks = []
        if r.targets:
            tasks.append(core_requirement(r, "compare_urls", r.targets))
        has_scope = any(
            c.field in {"destinations", "supplier"} and c.operator not in {"excludes", "not_in"}
            for c in r.conditions
        )
        if r.mode in {"discover", "hybrid"} and has_scope:
            tasks.append(core_requirement(r, "discover", []))

        async def acquire(requirement):
            try:
                if self.gateway.settings.data_provider == "supabase":
                    return await self.gateway.collect(
                        requirement,
                        deadline_at,
                        catalog_conditions=r.conditions,
                        candidate_limit=candidate_limit,
                        exclusions=exclusions,
                        catalog_requirement=r,
                    )
                return await self.gateway.collect(requirement, deadline_at)
            except AppError as exc:
                statuses = []
                if requirement.targets:
                    for t in requirement.targets:
                        s = self.gateway.source_for(t.url)
                        statuses.append(
                            SourceResult(
                                source_id=s.source_id if s else "unapproved",
                                target_id=t.target_id,
                                status="timeout"
                                if exc.code in {"SOURCE_TIMEOUT", "JOB_DEADLINE_EXCEEDED"}
                                else "error",
                                reason_code=exc.code,
                            )
                        )
                else:
                    statuses = [
                        SourceResult(source_id=s.source_id, status="error", reason_code=exc.code)
                        for s in self.registry
                        if "discover" in s.modes and s.access_status == "approved"
                    ]
                return CrawlResult(
                    request_id=uid("crawl"),
                    origin="synthetic" if self.gateway.settings.data_provider == "fixture" else "source",
                    source_results=statuses,
                )

        results = await asyncio.gather(*(acquire(t) for t in tasks))
        if not results:
            return CrawlResult(
                request_id=uid("crawl"),
                origin="synthetic" if self.gateway.settings.data_provider == "fixture" else "source",
                source_results=[],
            )
        return merge_results(results)


def registry_from_records(records):
    registry = [
        SourceCapability.model_validate(
            {
                **record["capability"],
                "access_status": record["access_status"]
                if record["state"] == "active"
                and (not record.get("access_valid_until") or instant(record["access_valid_until"]) > now())
                else "blocked",
            }
        )
        for record in records
    ]
    active_domains = {
        domain
        for capability in registry
        if capability.access_status == "approved"
        for domain in capability.approved_domains
    }
    routed = []
    for capability in registry:
        domains = (
            capability.approved_domains
            if capability.access_status == "approved"
            else [domain for domain in capability.approved_domains if domain not in active_domains]
        )
        if domains:
            routed.append(capability.model_copy(update={"approved_domains": domains}))
    return routed
