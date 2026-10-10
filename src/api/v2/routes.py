import hashlib
import json
from typing import Annotated
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Body, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from sqlalchemy import insert, select

from api.store import resources
from api.v2 import state
from api.v2.admin import ContactCreate, admin_router
from api.v2.models import (
    ComparisonV2,
    ConfirmProposal,
    ConversationMessage,
    CreateComparisonV2,
    CreateProposal,
    CreateRequirementV2,
    DiscardChanges,
    Envelope,
    Proposal,
    ProposalVersion,
    RequirementV2,
)
from domain.common import AppError, now, uid
from domain.semantic import FIELDS_V2
from domain.what_if import ApplyWhatIf, CreateWhatIf, WhatIfAnalysis
from requirements.catalog import CATALOG_VERSION, PLACE_ENTRIES, PLACE_RELATIONS


def envelope(request, data, status=200):
    result = Envelope[JsonValue](request_id=request.state.request_id, data=data)
    return JSONResponse(result.model_dump(mode="json"), status_code=status)


def router(service, admin, owner, limits):
    routes = APIRouter(prefix="/v2", tags=["v2"])
    store = service.store

    def mutation(request, owner_id, key, name, body, callback):
        if key is not None and (not 1 <= len(key) <= 128 or any(ord(x) < 33 or ord(x) > 126 for x in key)):
            raise AppError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key không hợp lệ.")
        scoped_key = hashlib.sha256(json.dumps([name, key]).encode()).hexdigest() if key else None
        payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body

        def action(c):
            result = callback(c)
            if owner_id.startswith("session_"):
                is_message = name.startswith("message:") or (
                    isinstance(payload, dict) and payload.get("input", {}).get("kind") in {"message", "text"}
                )
                activity_id = (
                    "activity_"
                    + hashlib.sha256(
                        json.dumps([owner_id, name, payload["client_message_id"]]).encode()
                    ).hexdigest()
                    if isinstance(payload, dict) and payload.get("client_message_id")
                    else uid("activity")
                )
                if not c.execute(
                    select(state.activities.c.id).where(state.activities.c.id == activity_id)
                ).scalar():
                    c.execute(
                        insert(state.activities).values(
                            id=activity_id,
                            owner=owner_id,
                            kind="message"
                            if is_message
                            else "comparison"
                            if name == "comparison"
                            else "edit",
                            created_at=now().isoformat(),
                        )
                    )
            return result

        status, data = store.mutate(owner_id, scoped_key, {"route": name, "body": payload}, action)
        return envelope(request, data, status)

    @routes.post("/sessions", status_code=201, response_model=Envelope[dict[str, JsonValue]])
    async def session(request: Request):
        limits.check(f"sessions:{request.client.host if request.client else 'local'}", 20)
        data = store.new_session()
        return envelope(request, {**data, "id": data["session_id"]}, 201)

    @routes.get("/catalog", response_model=Envelope[dict[str, JsonValue]])
    async def catalog(request: Request):
        labels = {
            "country:jp": "Nhật Bản",
            "country:kr": "Hàn Quốc",
            "country:vn": "Việt Nam",
            "country:th": "Thái Lan",
            "country:sg": "Singapore",
            "country:tw": "Đài Loan",
            "country:cn": "Trung Quốc",
            "city:vn:hcmc": "TP. Hồ Chí Minh",
            "city:vn:hanoi": "Hà Nội",
            "city:vn:danang": "Đà Nẵng",
            "city:jp:tokyo": "Tokyo",
            "city:jp:kyoto": "Kyoto",
            "city:jp:osaka": "Osaka",
            "city:kr:seoul": "Seoul",
            "city:kr:busan": "Busan",
            "region:vn:central": "Miền Trung",
        }
        labels.update({eid: aliases[0] for eid, aliases in PLACE_ENTRIES.items()})
        return envelope(
            request,
            {
                "catalog_version": CATALOG_VERSION,
                "destinations": [
                    {
                        "id": identifier,
                        "label": label,
                        "parent_id": next(iter(PLACE_RELATIONS.get(identifier, ())), None),
                    }
                    for identifier, label in labels.items()
                ],
                "origins": [
                    {"id": key, "label": labels[key]} for key in labels if key.startswith("city:vn:")
                ],
                "fields": [
                    {
                        "id": field,
                        "operators": sorted(operators),
                        "processing_methods": ["semantic_assessment"]
                        if field in {"supplier_reputation", "service_quality", "price_value", "unsupported"}
                        else ["structured", "semantic_assessment"]
                        if field in {"nature", "included_services"}
                        else ["structured"],
                        "strength_choices": ["hard", "soft"],
                    }
                    for field, operators in FIELDS_V2.items()
                ],
                "required_by_input_kind": {
                    "structured": ["form"],
                    "urls": ["reference_urls"],
                    "text": ["text"],
                },
                "required_before_confirm": {
                    "structured": [
                        "destinations",
                        "departure_origin",
                        "departure_date",
                        "party.adults",
                        "estimated_cost",
                    ],
                    "text": [
                        "destinations",
                        "departure_origin",
                        "departure_date",
                        "party.adults",
                        "estimated_cost",
                    ],
                    "urls": ["reference_urls"],
                },
                "personalized_policy": {
                    "version": "personalized-core-v1",
                    "incomplete_form_creates_proposal": True,
                    "budget": {
                        "strength": "hard",
                        "operator": "lte",
                        "currency": "VND",
                        "basis": "per_adult",
                        "coverage": "tour_price",
                        "measure": "listed",
                    },
                    "budget_defaults_apply_to": "labeled_form_only",
                    "text_preserves_explicit_strength_and_asks_missing_cap": True,
                    "readiness_requires_confirmed_revision_at_search_endpoint": True,
                    "core_condition_answer": {"shape": "condition: FormConditionV2", "new_id_required": True},
                    "core_party_answer": {"adults": 2},
                },
                "defaults": {"budget_coverage": {"value": "tour_price", "origin": "system_default"}},
                "qualitative_policy": {
                    "default_strength": "soft",
                    "explicit_mandatory_strength": "hard",
                    "unsupported_metrics": ["supplier_reputation", "service_quality", "price_value"],
                },
                "assessment_policy": {
                    "enabled": store.settings.semantic_assessment_enabled,
                    "policy_version": "semantic-assessment-v1",
                    "max_candidates": store.settings.semantic_max_candidates,
                    "max_pairs": store.settings.semantic_max_pairs,
                    "max_input_chars": store.settings.semantic_max_input_chars,
                    "excerpt_chars": store.settings.semantic_excerpt_chars,
                    "timeout_seconds": store.settings.semantic_timeout_seconds,
                    "ranking_policy": "rank-v2.3-bounds",
                    "unsupported_fields": ["supplier_reputation", "service_quality", "price_value"],
                    "strength_independent_of_processing": True,
                },
                "what_if_policy": {
                    "version": "what-if-v1",
                    "requires_completed_comparison": True,
                    "baseline": "recomputed_on_analysis_snapshot",
                    "max_joint_groups": 2,
                    "scenario_attempts_default": 32,
                    "scenario_attempts_max": 64,
                    "candidate_limit_default": 100,
                    "candidate_limit_max": 500,
                    "explanation_enabled": store.settings.what_if_explanation_enabled,
                    "explanation_timeout_seconds": store.settings.what_if_explanation_timeout_seconds,
                    "percentage_meaning": "proven_blocked / scenario_eligible_in_acquired_snapshot",
                    "apply_creates_proposal": True,
                },
                "transports": [
                    {"id": "motor_vehicle", "label": "Ô tô (loại rộng)"},
                    {"id": "coach", "label": "Xe khách"},
                    {"id": "car", "label": "Xe con"},
                    {"id": "flight", "label": "Máy bay"},
                    {"id": "train", "label": "Tàu hỏa"},
                ],
                "tour_types": [
                    {"id": "join_group", "label": "Ghép đoàn"},
                    {"id": "private_group", "label": "Đoàn riêng"},
                ],
                "preference_dimensions": [
                    {
                        "id": d,
                        "min": 0,
                        "max": 5,
                        "default": {"level": 3, "origin": "system_default"},
                        "supported": d in {"cost", "comfort"},
                    }
                    for d in ("cost", "comfort", "pace", "culture")
                ],
                "limits": {
                    "reference_urls": 5,
                    "recommendations": 3,
                    "candidate_limit_default": 20,
                    "text_characters": 2000,
                    "contact_characters": 4000,
                    "page_default": 25,
                    "page_max": 100,
                    "body_bytes": 65536,
                },
                "upstream_contract": "supabase-catalog-v2"
                if store.settings.data_provider == "supabase"
                else "crawler-v1-adapter",
                "catalog_validation": {
                    "policy_version": "catalog-validation-v1",
                    "configured_domains": store.settings.supabase_tour_trusted_domains
                    if store.settings.data_provider == "supabase"
                    else [],
                    "verification_states": [
                        "unverified",
                        "catalog_validated",
                        "supplier_published",
                        "independently_verified",
                    ],
                    "independent_verification": False,
                    "field_proof_required_for_trusted_catalog": False,
                    "volatile_freshness_required": True,
                },
            },
        )

    @routes.get("/sources", response_model=Envelope[dict[str, JsonValue]])
    async def sources(request: Request, owner_id: str = Depends(owner)):
        return envelope(
            request,
            {
                "origin": "synthetic" if store.settings.data_provider == "fixture" else "source",
                "items": [s.model_dump(mode="json") for s in service.registry()],
            },
        )

    @routes.post("/requirements", response_model=Envelope[RequirementV2 | dict[str, JsonValue]])
    async def create_requirement(
        body: Annotated[
            CreateRequirementV2,
            Body(
                openapi_examples={
                    "urls": {
                        "summary": "Một URL mô phỏng — xác nhận proposal trước khi so sánh",
                        "value": {
                            "input": {"kind": "urls"},
                            "reference_urls": ["https://tour-demo.invalid/tour-a"],
                        },
                    },
                    "text": {
                        "summary": "Nhu cầu tiếng Việt — cần NIM",
                        "value": {
                            "input": {
                                "kind": "text",
                                "text": "Đi Nhật từ Sài Gòn ngày 03/11/2026, 1 người lớn. Giá tour tối đa 30 triệu VND mỗi người lớn.",
                            }
                        },
                    },
                }
            ),
        ],
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            "requirement",
            body,
            lambda c: service.create_requirement(c, owner_id, body),
        )

    @routes.get("/requirements/{rid}", response_model=Envelope[dict[str, JsonValue]])
    async def current(rid: str, request: Request, owner_id: str = Depends(owner)):
        return envelope(request, service.current(owner_id, rid))

    @routes.get("/requirements/{rid}/revisions/{revision}", response_model=Envelope[RequirementV2])
    async def revision(rid: str, revision: int, request: Request, owner_id: str = Depends(owner)):
        if revision < 1:
            raise AppError("INVALID_INPUT", "Revision đã xác nhận phải >=1.")
        with store.engine.connect() as c:
            data = state.revision(store, c, owner_id, rid, revision)
        return envelope(request, data.model_dump(mode="json"))

    @routes.post("/requirements/{rid}/proposals", response_model=Envelope[Proposal | dict[str, JsonValue]])
    async def propose(
        rid: str,
        body: CreateProposal,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"proposal:{rid}",
            body,
            lambda c: service.propose(c, owner_id, rid, body),
        )

    @routes.get("/proposals/{pid}", response_model=Envelope[Proposal])
    async def proposal(pid: str, request: Request, owner_id: str = Depends(owner)):
        with store.engine.connect() as c:
            data = state.proposal(c, owner_id, pid)
        return envelope(request, data.model_dump(mode="json"))

    @routes.post("/proposals/{pid}/confirm", response_model=Envelope[RequirementV2])
    async def confirm(
        pid: str,
        body: ConfirmProposal,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"confirm:{pid}",
            body,
            lambda c: service.confirm(c, owner_id, pid, body),
        )

    @routes.post("/proposals/{pid}/cancel", response_model=Envelope[dict[str, JsonValue]])
    async def cancel(
        pid: str,
        body: ProposalVersion,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"cancel_proposal:{pid}",
            body,
            lambda c: service.cancel(c, owner_id, pid, body),
        )

    @routes.post("/proposals/{pid}/discard-changes", response_model=Envelope[Proposal])
    async def discard(
        pid: str,
        body: DiscardChanges,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"discard:{pid}",
            body,
            lambda c: service.discard(c, owner_id, pid, body),
        )

    @routes.post("/conversations/{rid}/messages", response_model=Envelope[dict[str, JsonValue]])
    async def message(
        rid: str,
        body: ConversationMessage,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key or f"message:{rid}:{body.client_message_id}",
            f"message:{rid}",
            body,
            lambda c: service.conversation(c, owner_id, rid, body),
        )

    @routes.get(
        "/conversations/{rid}/messages/{client_message_id}", response_model=Envelope[dict[str, JsonValue]]
    )
    async def message_result(
        rid: str, client_message_id: str, request: Request, owner_id: str = Depends(owner)
    ):
        with store.engine.connect() as c:
            store.resource(owner_id, rid, c, "requirement_v2")
            payload = c.execute(
                select(state.messages.c.payload).where(
                    state.messages.c.requirement_id == rid,
                    state.messages.c.client_message_id == client_message_id,
                )
            ).scalar()
        if payload is None:
            raise AppError("NOT_FOUND", "Không tìm thấy tin nhắn.", 404)
        data = json.loads(payload)
        return envelope(request, {"accepted": data["accepted"], "result": data["result"]})

    @routes.post("/comparisons", response_model=Envelope[dict[str, JsonValue]])
    async def comparison(
        body: CreateComparisonV2,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            "comparison",
            body,
            lambda c: service.create_comparison(c, owner_id, body),
        )

    @routes.get("/comparisons/{cid}", response_model=Envelope[dict[str, JsonValue]])
    async def get_comparison(cid: str, request: Request, owner_id: str = Depends(owner)):
        record = store.resource(owner_id, cid, kind="comparison_v2")
        payload = json.loads(record["payload"])
        result = payload.get("result")
        if result:
            result = ComparisonV2.model_validate(result).model_dump(mode="json")
        return envelope(request, {"id": cid, "status": record["status"], "result": result})

    @routes.post("/comparisons/{cid}/what-if", response_model=Envelope[dict[str, JsonValue]])
    async def create_what_if(
        cid: str,
        body: CreateWhatIf,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"what_if:{cid}",
            body,
            lambda c: service.create_what_if(c, owner_id, cid, body),
        )

    @routes.get("/what-if/{aid}", response_model=Envelope[dict[str, JsonValue]])
    async def what_if(aid: str, request: Request, owner_id: str = Depends(owner)):
        record = store.resource(owner_id, aid, kind="what_if_v2")
        result = json.loads(record["payload"]).get("result")
        if result:
            result = WhatIfAnalysis.model_validate(result).model_dump(mode="json")
        return envelope(request, dict(id=aid, status=record["status"], result=result))

    @routes.post("/what-if/{aid}/scenarios/{sid}/proposals", response_model=Envelope[Proposal])
    async def apply_what_if(
        aid: str,
        sid: str,
        body: ApplyWhatIf,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"apply_what_if:{aid}:{sid}",
            body,
            lambda c: service.apply_what_if(c, owner_id, aid, sid, body),
        )

    @routes.get("/jobs/{jid}", response_model=Envelope[dict[str, JsonValue]])
    async def job(jid: str, request: Request, owner_id: str = Depends(owner)):
        data = store.job(owner_id, jid)
        return envelope(request, {**data, "stage": data["phase"], "resource_ref": data["resource_id"]})

    @routes.get("/jobs/{jid}/events", response_model=Envelope[dict[str, JsonValue]])
    async def events(
        jid: str,
        request: Request,
        after_seq: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=100),
        owner_id: str = Depends(owner),
    ):
        return envelope(request, state.events(store, owner_id, jid, after_seq, limit))

    @routes.post("/jobs/{jid}/cancel", response_model=Envelope[dict[str, JsonValue]])
    async def cancel_job(
        jid: str, request: Request, owner_id: str = Depends(owner), idempotency_key: str | None = Header(None)
    ):
        return mutation(
            request,
            owner_id,
            idempotency_key,
            f"cancel_job:{jid}",
            {},
            lambda c: (200, store.cancel(c, owner_id, jid)),
        )

    @routes.get("/evidence/{eid}", response_model=Envelope[dict[str, JsonValue]])
    async def evidence(eid: str, request: Request, owner_id: str = Depends(owner)):
        with store.engine.connect() as c:
            row = (
                c.execute(
                    select(state.snapshots)
                    .join(resources, resources.c.id == state.snapshots.c.comparison_id)
                    .where(
                        state.snapshots.c.id == eid,
                        state.snapshots.c.owner == owner_id,
                        state.snapshots.c.kind == "evidence",
                        resources.c.status.in_(["succeeded", "partial"]),
                    )
                    .order_by(state.snapshots.c.comparison_id)
                    .limit(1)
                )
                .mappings()
                .first()
            )
        if row is None:
            raise AppError("NOT_FOUND", "Không tìm thấy evidence thuộc kết quả của bạn.", 404)
        ev = json.loads(row["payload"])
        source_matches = [
            s
            for s in service.registry()
            if (urlsplit(ev["url"]).hostname or "").lower() in s.approved_domains
        ]
        source = source_matches[0] if len(source_matches) == 1 else None
        allowed = (
            source is not None and (urlsplit(ev["url"]).hostname or "").lower() in source.approved_domains
        )
        allowed = allowed and source.access_status == "approved"
        link = (
            ev["url"].split("#", 1)[0] + "#:~:text=" + quote(ev["raw_quote"], safe="")
            if allowed and ev["method"] not in {"synthetic_fixture", "database_record"}
            else ev["url"]
            if allowed
            else None
        )
        return envelope(
            request,
            {
                **ev,
                "source_url": ev["url"],
                "source_id": source.source_id if source else None,
                "locator": {
                    "section_title": None,
                    "element_id": None,
                    "css_selector": None,
                    "text_quote": {
                        "exact": ev["raw_quote"] if ev["method"] != "database_record" else None,
                        "prefix": None,
                        "suffix": None,
                    },
                    "upstream_locator": ev["locator"],
                },
                "deep_link": {
                    "url": link,
                    "method": "text_fragment"
                    if allowed and ev["method"] not in {"synthetic_fixture", "database_record"}
                    else "page",
                    "status": "best_effort" if allowed else "unavailable",
                    "verified_at": None,
                    "reason": "Giá trị lưu trong database; trang nguồn chưa có locator/quote được kiểm chứng."
                    if allowed and ev["method"] == "database_record"
                    else "Mở trang nguồn; có thể cần tìm trích đoạn."
                    if allowed
                    else "Nguồn chưa được duyệt hoặc đã dừng.",
                },
                "retained_excerpt_url": None,
                "quality": {
                    "origin": "synthetic" if ev["method"] == "synthetic_fixture" else "source",
                    "verification": "catalog_validated" if ev.get("catalog_validation") else "unverified",
                    "independently_verified": False,
                    "provenance_kind": "database_record"
                    if ev["method"] == "database_record"
                    else "website_excerpt",
                },
            },
        )

    @routes.post("/contacts", response_model=Envelope[dict[str, JsonValue]])
    async def contact(
        body: ContactCreate,
        request: Request,
        owner_id: str = Depends(owner),
        idempotency_key: str | None = Header(None),
    ):
        return mutation(
            request, owner_id, idempotency_key, "contact", body, lambda c: admin.contact(c, owner_id, body)
        )

    routes.include_router(admin_router(admin, store.settings, envelope, mutation, limits))
    return routes
