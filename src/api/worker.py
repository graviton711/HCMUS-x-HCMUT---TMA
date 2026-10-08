import asyncio
import json

from pydantic import ValidationError

from decision.engine import compare
from domain.common import AppError, instant, now, uid
from domain.crawl import CrawlResult
from domain.requirements import Message, Target
from requirements.nim import parse_validated


class Worker:
    def __init__(self, store, nim, gateway):
        self.store, self.nim, self.gateway = store, nim, gateway
        self.id = uid("worker")

    async def run_once(self):
        row = self.store.claim(self.id)
        if row is None:
            return False
        payload = json.loads(row["payload"])
        try:
            timeout = max(0.001, (instant(row["deadline_at"]) - now()).total_seconds())
            async with asyncio.timeout(timeout):
                if row["kind"].startswith("v2_"):
                    await self.v2.run_job(row, self.id, payload)
                elif row["kind"] == "parse":
                    previous = (
                        self.store.revision(row["owner"], row["resource_id"], payload["expected_revision"])
                        if payload["expected_revision"]
                        else None
                    )
                    message = Message.model_validate(payload["message"])
                    r, metrics = await parse_validated(
                        self.nim,
                        message,
                        previous,
                        requirement_id=row["resource_id"],
                        mode=payload["mode"],
                        timezone=payload["timezone"],
                        targets=[Target.model_validate(t) for t in payload["targets"]],
                    )
                    self.store.commit_job(row, self.id, r=r, metrics=metrics)
                else:
                    r = self.store.revision(row["owner"], payload["requirement_id"], payload["revision"])
                    if payload.get("reuse_comparison_id"):
                        previous = json.loads(
                            self.store.resource(
                                row["owner"], payload["reuse_comparison_id"], kind="comparison"
                            )["payload"]
                        )
                        crawl = CrawlResult.model_validate(previous["crawl"])
                        # Check current access policy before reusing any previous source.
                        approved = {
                            s.source_id for s in self.gateway.registry if s.access_status == "approved"
                        }
                        if any(
                            s.source_id not in approved for s in crawl.source_results if s.tour_snapshot_ids
                        ):
                            raise AppError(
                                "SOURCE_BLOCKED", "Nguồn đã bị chặn; không thể dùng lại snapshot.", 409
                            )
                    else:
                        crawl = await self.gateway.collect(r, row["deadline_at"])
                    result = compare(
                        r, crawl, self.gateway.registry, now().isoformat(), payload.get("offer_selections")
                    )
                    attempted_failures = [s for s in crawl.source_results if s.status in {"error", "timeout"}]
                    if attempted_failures and not result["candidates"]:
                        raise AppError(
                            "SOURCES_UNAVAILABLE",
                            "Các nguồn được gọi chưa trả dữ liệu dùng được.",
                            502,
                            retryable=True,
                        )
                    comparison = {
                        "result": result,
                        "crawl": crawl.model_dump(),
                        "job_status": "partial" if attempted_failures else "succeeded",
                    }
                    self.store.commit_job(row, self.id, comparison=comparison)
        except asyncio.CancelledError:
            with self.store.transaction() as c:
                self.store.fail(
                    c,
                    row,
                    AppError("JOB_INTERRUPTED", "Backend dừng khi job đang chạy.", 503, retryable=True),
                )
            raise
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                error = AppError("JOB_DEADLINE_EXCEEDED", "Tác vụ vượt quá thời hạn.", 504, retryable=True)
            elif isinstance(exc, AppError):
                error = exc
            elif isinstance(exc, ValidationError):
                error = AppError(
                    "LLM_INVALID_OUTPUT"
                    if row["kind"] in {"parse", "v2_parse", "v2_message"}
                    else "CRAWLER_INVALID_OUTPUT",
                    "Dữ liệu upstream không hợp lệ.",
                    502,
                )
            else:
                error = AppError("INTERNAL_ERROR", "Backend không hoàn tất được tác vụ.", 500)
            with self.store.transaction() as c:
                self.store.fail(c, row, error)
        return True

    async def run(self):
        while True:
            if not await self.run_once():
                await asyncio.sleep(self.store.settings.worker_poll_seconds)
