import argparse
import asyncio
import json
from pathlib import Path


def main():
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tour decision backend")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    export = commands.add_parser("export-schemas")
    export.add_argument("--output", type=Path, default=Path("contracts"))
    commands.add_parser("probe-nim")
    commands.add_parser("probe-supabase")
    evaluate = commands.add_parser("evaluate-nim")
    evaluate.add_argument("--cases", type=Path, default=Path("tests/fixtures/requirements-smoke.json"))
    evaluate.add_argument("--output", type=Path, default=Path("data/evaluation.local.json"))
    semantic = commands.add_parser("evaluate-nim-v2")
    semantic.add_argument("--cases", type=Path, default=Path("tests/fixtures/requirements-semantic.json"))
    semantic.add_argument("--output", type=Path, default=Path("data/evaluation-v2.local.json"))
    semantic.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    commands.add_parser("purge")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("api.app:create_app", factory=True, host=args.host, port=args.port, workers=1)
    elif args.command == "export-schemas":
        from api.dto import CreateComparison, CreateRequirement, PatchRequirement
        from api.v2.admin import (
            ContactCreate,
            ContactPatch,
            ExpectedVersion,
            SourceApproval,
            SourceCreate,
            SourcePatch,
            SourceRefresh,
        )
        from api.v2.models import (
            ComparisonV2,
            ConfirmProposal,
            ConversationMessage,
            CreateComparisonV2,
            CreateProposal,
            CreateRequirementV2,
            DiscardChanges,
            JobEvent,
            Proposal,
            ProposalVersion,
            RequirementV2,
        )
        from domain.crawl import CrawlRequest, CrawlResult, SourceCapability
        from domain.crawl_v2 import CatalogFieldProof, CrawlResultV2
        from domain.requirements import Requirement
        from requirements.extraction import Extraction
        from requirements.v2 import InitialExtractionV2, UpdateExtractionV2
        from semantic_assessment.models import AssessmentBatch, SemanticReport

        args.output.mkdir(parents=True, exist_ok=True)
        for model in (
            CreateRequirement,
            PatchRequirement,
            CreateComparison,
            Requirement,
            CrawlRequest,
            CrawlResult,
            SourceCapability,
            Extraction,
        ):
            (args.output / f"{model.__name__}.schema.json").write_text(
                json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        v2_output = args.output / "v2"
        v2_output.mkdir(parents=True, exist_ok=True)
        for model in (
            CreateRequirementV2,
            RequirementV2,
            CreateProposal,
            Proposal,
            ConfirmProposal,
            ProposalVersion,
            DiscardChanges,
            CreateComparisonV2,
            ComparisonV2,
            ConversationMessage,
            JobEvent,
            ContactCreate,
            ContactPatch,
            SourceCreate,
            SourcePatch,
            ExpectedVersion,
            SourceApproval,
            SourceRefresh,
            InitialExtractionV2,
            UpdateExtractionV2,
            CrawlResultV2,
            CatalogFieldProof,
            AssessmentBatch,
            SemanticReport,
        ):
            (v2_output / f"{model.__name__}.schema.json").write_text(
                json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(f"Exported schemas to {args.output.resolve()}")
    elif args.command == "probe-supabase":
        from api.settings import Settings
        from data_access.supabase.reader import SupabaseRepository
        from domain.common import AppError

        repository = SupabaseRepository(Settings(data_provider="supabase"))
        try:
            print(json.dumps(repository.probe(), ensure_ascii=False))
        except AppError as exc:
            print(json.dumps(exc.payload(), ensure_ascii=False))
            raise SystemExit(1) from None
        finally:
            repository.close()
    elif args.command == "purge":
        from api.runtime_lock import RuntimeLock
        from api.settings import Settings
        from api.store import Store

        settings = Settings()
        lock = RuntimeLock(settings.database_url)
        lock.acquire()
        try:
            store = Store(settings)
            print(json.dumps(store.purge()))
            store.engine.dispose()
        finally:
            lock.release()
    elif args.command == "probe-nim":
        asyncio.run(probe())
    elif args.command == "evaluate-nim":
        from api.settings import Settings
        from requirements.evaluation import evaluate_smoke

        report = asyncio.run(evaluate_smoke(Settings(), args.cases, args.output))
        print(
            f"{report['passed']}/{report['total']} curated smoke cases passed; report: {args.output.resolve()}"
        )
        if report["passed"] != report["total"]:
            raise SystemExit(1)
    elif args.command == "evaluate-nim-v2":
        from api.settings import Settings
        from requirements.evaluation_v2 import evaluate_semantic

        report = asyncio.run(evaluate_semantic(Settings(), args.cases, args.output, args.repeat))
        print(
            f"{report['passed']}/{report['total']} semantic smoke runs passed; report: {args.output.resolve()}"
        )
        if report["passed"] != report["total"]:
            raise SystemExit(1)


async def probe():
    from api.settings import Settings
    from domain.common import AppError, now, uid
    from domain.requirements import Message
    from requirements.nim import NimGateway, parse_validated

    message = Message(
        id=uid("msg"),
        text="Nhật hoặc Hàn, từ Sài Gòn, 5 ngày. Tối đa 60 triệu đồng cả nhà 2 người lớn và bé 8 tuổi. Ưu tiên khách sạn 4 sao.",
        received_at=now().isoformat(),
    )
    try:
        async with asyncio.timeout(180):
            r, metrics = await parse_validated(
                NimGateway(Settings()),
                message,
                requirement_id="probe",
                mode="discover",
                timezone="Asia/Ho_Chi_Minh",
                targets=[],
            )
        print(
            json.dumps(
                {
                    "metrics": metrics,
                    "conditions": [c.model_dump() for c in r.conditions],
                    "party": r.party.model_dump(),
                    "readiness": r.readiness.model_dump(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except AppError as exc:
        print(json.dumps({"error": exc.payload()}, ensure_ascii=False))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
