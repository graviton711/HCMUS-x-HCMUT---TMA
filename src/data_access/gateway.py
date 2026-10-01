import json
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from pydantic import TypeAdapter, ValidationError

from data_access.fixtures import fixture_registry, fixture_result
from domain.common import AppError, instant, now, uid
from domain.crawl import CrawlRequest, CrawlResult, Fact, SourceCapability, SourceResult, validate_fields
from domain.requirements import QuerySpec, Requirement


class DataGateway:
    def __init__(self, settings, registry: list[SourceCapability] | None = None, transport=None):
        self.settings = settings
        self.transport = transport
        if registry is not None:
            self.registry = registry
        elif settings.data_provider == "fixture":
            self.registry = fixture_registry()
        elif settings.crawler_registry_path:
            self.registry = TypeAdapter(list[SourceCapability]).validate_json(
                settings.crawler_registry_path.read_text(encoding="utf-8"))
        else:
            self.registry = []
        if len({s.source_id for s in self.registry}) != len(self.registry):
            raise ValueError("Duplicate registry source")

    def source_for(self, url: str) -> SourceCapability | None:
        host = (urlsplit(url).hostname or "").lower()
        matches = [s for s in self.registry if host in s.approved_domains]
        return matches[0] if len(matches) == 1 else None

    def validate_binding(self, result: CrawlResult, request: CrawlRequest):
        if result.request_id != request.request_id:
            raise AppError("CRAWLER_INVALID_OUTPUT", "Crawler trả sai request_id.", 502)
        if self.settings.data_provider == "http" and result.origin != "source":
            raise AppError("CRAWLER_INVALID_OUTPUT", "HTTP crawler phải khai báo origin source.", 502)
        source_map = {s.source_id: s for s in self.registry}
        tours = {t.snapshot_id: t for t in result.tours}
        offers = {o.snapshot_id: o for o in result.offers}
        targets = {t.target_id: t for t in request.targets}
        seen, owned_tours, owned_offers = set(), set(), set()
        for sr in result.source_results:
            key = (sr.source_id, sr.target_id)
            if key in seen or sr.source_id not in request.source_ids:
                raise AppError("CRAWLER_INVALID_OUTPUT", "Source ngoài request hoặc trùng kết quả.", 502)
            seen.add(key)
            source = source_map[sr.source_id]
            if request.mode == "compare_urls":
                if sr.target_id not in targets or self.source_for(targets[sr.target_id].url) != source:
                    raise AppError("CRAWLER_INVALID_OUTPUT", "Target/source không khớp.", 502)
            elif sr.target_id is not None:
                raise AppError("CRAWLER_INVALID_OUTPUT", "Discover không có target id.", 502)
            for tid in sr.tour_snapshot_ids:
                tour = tours[tid]
                if tour.supplier_id != source.supplier_id or self.source_for(tour.canonical_url) != source:
                    raise AppError("CRAWLER_INVALID_OUTPUT", "Tour không thuộc source.", 502)
                owned_tours.add(tid)
            owned_offers.update(sr.offer_snapshot_ids)
        if set(tours) != owned_tours or set(offers) != owned_offers:
            raise AppError("CRAWLER_INVALID_OUTPUT", "Snapshot không được source result khai báo.", 502)
        max_time = now() + timedelta(minutes=5)
        for evidence in result.evidence:
            tid = offers[evidence.snapshot_id].tour_snapshot_id if evidence.snapshot_id in offers else evidence.snapshot_id
            if self.source_for(evidence.url) != self.source_for(tours[tid].canonical_url) or instant(evidence.observed_at) > max_time:
                raise AppError("CRAWLER_INVALID_OUTPUT", "Nguồn hoặc thời gian evidence không hợp lệ.", 502)
        for snapshot in [*result.tours, *result.offers]:
            facts = list(snapshot.fields.values())
            if hasattr(snapshot, "price_quotes"):
                facts += snapshot.price_quotes + snapshot.extra_charges
                if snapshot.pricing_complete:
                    facts.append(snapshot.pricing_complete)
            if any(instant(f.observed_at) > max_time for f in facts):
                raise AppError("CRAWLER_INVALID_OUTPUT", "Field có thời gian quan sát ở tương lai.", 502)

    def isolate_invalid_fields(self, payload: dict) -> dict:
        # A corrupt field is not allowed to invalidate unrelated, usable fields.
        for kind in ("tours", "offers"):
            for snapshot in payload.get(kind, []):
                for name, raw in list(snapshot.get("fields", {}).items()):
                    try:
                        fact = Fact.model_validate(raw)
                        validate_fields({name: fact}, offer=kind == "offers")
                    except (ValueError, TypeError, ValidationError):
                        del snapshot["fields"][name]
                        source = next((s for s in payload.get("source_results", [])
                                       if snapshot.get("snapshot_id") in s.get("tour_snapshot_ids" if kind == "tours" else "offer_snapshot_ids", [])), None)
                        if source:
                            payload.setdefault("issues", []).append({"code": "INVALID_FIELD", "source_id": source["source_id"],
                                "snapshot_id": snapshot["snapshot_id"], "field_path": name,
                                "explanation": "Field không đúng schema; không dùng để đánh giá.", "retryable": False})
        return payload

    async def collect(self, r: Requirement, deadline_at: str) -> CrawlResult:
        rejected, accepted, source_ids = [], [], []
        if r.mode == "compare_urls":
            for target in r.targets:
                source = self.source_for(target.url)
                reason = ("SOURCE_NOT_APPROVED" if source is None else "SOURCE_BLOCKED" if source.access_status != "approved"
                          else "SOURCE_UNSUPPORTED" if r.mode not in source.modes else None)
                if reason:
                    rejected.append(SourceResult(source_id=source.source_id if source else "unapproved", target_id=target.target_id,
                                                 status="blocked" if reason == "SOURCE_BLOCKED" else "unsupported", reason_code=reason))
                else:
                    accepted.append(target)
                    source_ids.append(source.source_id)
        else:
            source_ids = [s.source_id for s in self.registry if s.access_status == "approved" and "discover" in s.modes]
        request = CrawlRequest(request_id=uid("crawl"), mode=r.mode, source_ids=list(dict.fromkeys(source_ids)),
                               query=QuerySpec.from_requirement(r), targets=accepted, deadline_at=deadline_at)
        if not source_ids:
            return CrawlResult(request_id=request.request_id, origin="synthetic" if self.settings.data_provider == "fixture" else "source",
                               source_results=rejected)
        if self.settings.data_provider == "fixture":
            result = fixture_result(request)
            # Discovery fixtures contain one record per tour; group by source like a real crawl envelope.
            if r.mode == "discover":
                result.source_results = [SourceResult(source_id="demo", status="ok",
                    tour_snapshot_ids=[t.snapshot_id for t in result.tours], offer_snapshot_ids=[o.snapshot_id for o in result.offers])]
        else:
            if not self.settings.crawler_url:
                raise AppError("CRAWLER_NOT_CONFIGURED", "Chưa cấu hình endpoint crawler.", 503)
            try:
                async with httpx.AsyncClient(timeout=self.settings.crawler_timeout_seconds,
                                             transport=self.transport, follow_redirects=False) as client:
                    headers = {}
                    if self.settings.crawler_api_key.get_secret_value():
                        headers["Authorization"] = f"Bearer {self.settings.crawler_api_key.get_secret_value()}"
                    async with client.stream("POST", self.settings.crawler_url, json=request.model_dump(mode="json"), headers=headers) as response:
                        if response.status_code != 200:
                            raise AppError("CRAWLER_UPSTREAM_ERROR", "Crawler trả lỗi upstream.", 502, retryable=True)
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 4_000_000:
                                raise AppError("CRAWLER_INVALID_OUTPUT", "Crawler payload vượt giới hạn.", 502)
                            chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
                result = CrawlResult.model_validate(self.isolate_invalid_fields(payload))
            except httpx.TimeoutException as exc:
                raise AppError("SOURCE_TIMEOUT", "Crawler quá thời hạn.", 504, retryable=True) from exc
            except httpx.HTTPError as exc:
                raise AppError("CRAWLER_UPSTREAM_ERROR", "Không kết nối được crawler.", 502, retryable=True) from exc
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise AppError("CRAWLER_INVALID_OUTPUT", "Crawler payload không đúng contract.", 502) from exc
        self.validate_binding(result, request)
        for target in accepted:
            if not any(s.target_id == target.target_id for s in result.source_results):
                rejected.append(SourceResult(source_id=self.source_for(target.url).source_id, target_id=target.target_id,
                                             status="error", reason_code="TARGET_RESULT_MISSING"))
        if r.mode == "discover":
            for sid in request.source_ids:
                if not any(s.source_id == sid for s in result.source_results):
                    rejected.append(SourceResult(source_id=sid, status="error", reason_code="SOURCE_RESULT_MISSING"))
        return result.model_copy(update={"source_results": [*result.source_results, *rejected]})
