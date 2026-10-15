"""Thin HTTP over the pipeline. Routes validate, modules decide."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.routing import APIRoute

from backend.agent.service import AgentService
from backend.data.catalog import for_settings
from backend.data.sessions import SessionStore
from backend.decide.scenarios import cost_scenario
from backend.error_logging import log_app_error, log_unexpected_error
from backend.errors import AppError
from backend.input.pipeline import validate_requirement
from backend.models import CostScenarioAssumptions, uid
from backend.settings import Settings
from backend.workflows import TourWorkflows
from shared import RequestContextMiddleware


class SafeAPIRoute(APIRoute):
    """Normalize route exceptions before Starlette logs raw server errors."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await original_handler(request)
            except AppError as exc:
                log_app_error(exc, transport="http", operation=self.path)
                return JSONResponse(status_code=exc.status, content=exc.payload())
            except Exception as exc:
                log_unexpected_error(exc, transport="http", operation=self.path)
                error = AppError("INTERNAL_ERROR", "An internal error occurred.", 500)
                return JSONResponse(status_code=error.status, content=error.payload())

        return safe_handler


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("mlai")
    except PackageNotFoundError:
        return "dev"


def _encode_page_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode().rstrip("=")


def _decode_page_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        offset = int(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise AppError("CURSOR_INVALID", "Invalid page cursor.", 422) from exc
    if offset < 0:
        raise AppError("CURSOR_INVALID", "Invalid page cursor.", 422)
    return offset


def _eliminated_offers(comparison) -> list[dict[str, Any]]:
    evaluations: dict[tuple[str, str], Any] = {
        (item.offer_id, item.condition_id): item
        for item in comparison.evaluations
    }
    hard = comparison.requirement.hard()
    items: list[dict[str, Any]] = []
    for tour in comparison.tour_snapshots:
        for offer in tour.offers:
            conditions = []
            for condition in hard:
                item = evaluations.get((offer.id, condition.id))
                conditions.append({
                    "condition_id": condition.id,
                    "alternative_id": next((
                        branch.id for branch in comparison.requirement.alternatives
                        if any(item.id == condition.id for item in branch.conditions)
                    ), None),
                    "field": condition.field,
                    "value": condition.value,
                    "state": item.state if item else "unknown",
                    "reason_code": item.reason_code if item else "EVALUATION_MISSING",
                    "reason": item.reason.strip() if item and item.reason.strip()
                    else _evaluation_reason(item.reason_code if item else "EVALUATION_MISSING", condition.field),
                    "quote": item.quote if item else "",
                })
            states = {
                condition_id: item.state
                for (candidate_offer_id, condition_id), item in evaluations.items()
                if candidate_offer_id == offer.id
            }
            common_pass = all(
                states.get(condition.id, "unknown") == "pass"
                for condition in comparison.requirement.shared_hard()
            )
            alternatives_pass = (
                not comparison.requirement.alternatives
                or any(
                    all(states.get(condition.id, "unknown") == "pass" for condition in branch.conditions)
                    for branch in comparison.requirement.alternatives
                )
            )
            if common_pass and alternatives_pass:
                continue
            items.append({
                "tour_id": tour.id,
                "tour_name": tour.name,
                "supplier": tour.supplier,
                "tour_url": tour.url,
                "offer": offer.model_dump(mode="json"),
                "conditions": conditions,
            })
    items.sort(key=lambda item: (
        str(item["tour_name"]).casefold(),
        str(item["offer"].get("departure_date", "")),
        str(item["offer"].get("id", "")),
    ))
    return items


def _evaluation_reason(code: str, field: str) -> str:
    reasons = {
        "DESTINATION_MISMATCH": "Điểm đến trong dữ liệu không khớp yêu cầu.",
        "DESTINATION_MISSING": "Tour chưa có nhãn điểm đến để xác minh.",
        "DEPARTURE_CITY_MISMATCH": "Nơi khởi hành trong dữ liệu không khớp yêu cầu.",
        "DURATION_MISMATCH": "Thời lượng tour không khớp yêu cầu.",
        "DATE_MISMATCH": "Ngày khởi hành hoặc ngày về nằm ngoài điều kiện đã chọn.",
        "FIELD_MISSING": f"Dữ liệu {field} còn thiếu.",
        "FIELD_INVALID": f"Dữ liệu {field} không hợp lệ để đối chiếu.",
        "FIELD_UNSUPPORTED": f"Chưa hỗ trợ đối chiếu trường {field}.",
        "PRICE_MISSING": "Offer chưa có giá để đối chiếu ngân sách.",
        "PRICE_CURRENCY_MISMATCH": "Tiền tệ của giá không khớp điều kiện ngân sách.",
        "PRICE_OVER_BUDGET": "Giá công bố cao hơn ngân sách tối đa.",
        "TRANSPORT_MISMATCH": "Phương tiện trong dữ liệu không khớp yêu cầu.",
        "ACCOMMODATION_MISMATCH": "Loại chỗ nghỉ trong dữ liệu không khớp yêu cầu.",
        "UNSUPPORTED_TRANSPORT": "Chưa hỗ trợ loại phương tiện này để đối chiếu.",
        "EVALUATION_MISSING": f"Chưa có dữ kiện để xác minh trường {field}.",
    }
    return reasons.get(code, f"Không đạt hoặc chưa xác minh được trường {field} ({code}).")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    tuning = settings.tuning
    store = SessionStore(settings.database_url)
    catalog = for_settings(settings)
    workflows = TourWorkflows(settings, catalog)
    agent = AgentService(settings, store)

    app = FastAPI(title="Tour Decision Backend", version=_version())
    app.router.route_class = SafeAPIRoute

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    def operation(request: Request) -> str:
        route = request.scope.get("route")
        return str(getattr(route, "path", "unknown"))

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        log_app_error(exc, transport="http", operation=operation(request))
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.get("/", response_class=HTMLResponse)
    async def landing() -> str:
        return "<p>Tour Decision Backend. Docs at <a href='/docs'>/docs</a>.</p>"

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": _version()}

    def owner_session(request: Request) -> str | None:
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        scheme, separator, token = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            raise AppError("SESSION_INVALID", "Invalid access session.", 401)
        return store.authenticate_session(token.strip())

    @app.post("/sessions", status_code=201)
    async def create_session() -> dict[str, str]:
        return store.create_session(tuning.api.session_ttl_seconds)

    @app.get("/catalog")
    async def get_catalog() -> dict[str, list[str]]:
        return {"destinations": catalog.list_destinations()}

    @app.post("/requirements")
    async def create_requirement(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if isinstance(body.get("conditions"), list):
            req = validate_requirement(
                body.get("raw_text", ""),
                body["conditions"],
                body.get("travelers", 1),
                ranking=body.get("ranking"),
                traveler_mix=body.get("traveler_mix"),
                alternatives=body.get("alternatives"),
                assumptions=body.get("assumptions"),
            )
        else:
            from backend.input.pipeline import requirement_from_form

            req = requirement_from_form(body.get("form"))
        store.save_requirement(req, owner_id)
        return {"requirement": req.model_dump()}

    @app.get("/requirements/{rid}")
    async def get_requirement(rid: str, request: Request) -> dict[str, Any]:
        return {"requirement": store.get_requirement(rid, owner_session(request)).model_dump()}

    @app.post("/comparisons")
    async def create_comparison(body: dict[str, Any], request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if not isinstance(body.get("requirement_id"), str):
            raise AppError("REQUIREMENT_REQUIRED", "A structured requirement ID is required.", 422)
        req = store.get_requirement(body["requirement_id"], owner_id)
        lo, hi = tuning.api.candidate_min, tuning.api.candidate_max
        limit = body.get("candidate_limit", settings.candidate_limit)
        limit = limit if isinstance(limit, int) and lo <= limit <= hi else settings.candidate_limit
        comp = workflows.comparison(req, limit)
        store.save_decision_snapshot(comp, owner_id)
        store.save_comparison(comp, owner_id)
        return {"comparison": comp.model_dump()}

    @app.post("/agent/sessions", status_code=201)
    async def create_agent_session(request: Request) -> dict[str, str]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for chat.", 401)
        return agent.create_session(owner_id)

    @app.post("/agent/sessions/{agent_session_id}/messages")
    async def agent_message(agent_session_id: str, body: dict[str, Any], request: Request):
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for chat.", 401)
        if "text/event-stream" in request.headers.get("accept", ""):

            async def stream_events():
                try:
                    async for event in agent.stream_message(
                        owner_id, agent_session_id, body.get("message", "")
                    ):
                        event_type = event.get("type", "progress")
                        payload = (
                            event.get("response", {})
                            if event_type == "result"
                            else {key: value for key, value in event.items() if key != "type"}
                        )
                        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        yield f"event: {event_type}\ndata: {data}\n\n"
                except AppError as exc:
                    log_app_error(exc, transport="sse", operation="agent_message")
                    data = json.dumps(
                        {"code": exc.code, "message": exc.message},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"
                except Exception as exc:
                    log_unexpected_error(exc, transport="sse", operation="agent_message")
                    data = json.dumps(
                        {"code": "INTERNAL_ERROR", "message": "An internal error occurred."},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
            )
        return await agent.message(owner_id, agent_session_id, body.get("message", ""))

    @app.post("/agent/sessions/{agent_session_id}/decisions")
    async def agent_decision(agent_session_id: str, body: dict[str, Any], request: Request):
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for chat.", 401)
        value = body.get("requirement")
        if not isinstance(value, dict):
            raise AppError("REQUIREMENT_REQUIRED", "A reviewed requirement is required.", 422)
        requirement_id = value.get("id")
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise AppError("REQUIREMENT_REQUIRED", "A reviewed requirement ID is required.", 422)
        store.get_agent_session(agent_session_id, owner_id)
        requirement = workflows.requirement(
            value.get("raw_text", ""),
            value.get("conditions"),
            value.get("travelers", 1),
            value.get("ranking"),
            requirement_id=requirement_id,
            require_weights=True,
            traveler_mix=value.get("traveler_mix"),
            alternatives=value.get("alternatives"),
            assumptions=value.get("assumptions"),
        )
        store.save_requirement(requirement, owner_id)
        if "text/event-stream" in request.headers.get("accept", ""):

            async def stream_events():
                try:
                    async for event in agent.stream_decision(owner_id, agent_session_id, requirement):
                        event_type = event.get("type", "progress")
                        payload = (
                            event.get("response", {})
                            if event_type == "result"
                            else {key: item for key, item in event.items() if key != "type"}
                        )
                        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        yield f"event: {event_type}\ndata: {data}\n\n"
                except AppError as exc:
                    log_app_error(exc, transport="sse", operation="agent_decision")
                    data = json.dumps(
                        {"code": exc.code, "message": exc.message},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"
                except Exception as exc:
                    log_unexpected_error(exc, transport="sse", operation="agent_decision")
                    data = json.dumps(
                        {"code": "INTERNAL_ERROR", "message": "An internal error occurred."},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
            )
        return await agent.decision(owner_id, agent_session_id, requirement)

    @app.get("/comparisons/{cid}")
    async def get_comparison(cid: str, request: Request) -> dict[str, Any]:
        return {"comparison": store.get_comparison(cid, owner_session(request)).model_dump()}

    @app.get("/comparisons/{cid}/eliminated")
    async def get_eliminated_offers(
        cid: str,
        request: Request,
        limit: int = 25,
        cursor: str | None = None,
        condition_id: str | None = None,
    ) -> dict[str, Any]:
        owner_id = owner_session(request)
        comparison = store.get_comparison(cid, owner_id)
        try:
            snapshot = store.get_decision_snapshot(cid, owner_id)
        except AppError as exc:
            if exc.code != "NOT_FOUND":
                raise
            raise AppError(
                "DECISION_TRACE_UNAVAILABLE",
                "This comparison does not have a retained scan snapshot. Rerun it to inspect excluded offers.",
                409,
            ) from exc
        safe_limit = min(max(limit, 1), 100)
        offset = _decode_page_cursor(cursor)
        entries = _eliminated_offers(snapshot)
        if condition_id:
            entries = [
                entry for entry in entries
                if any(condition.get("condition_id") == condition_id
                       for condition in entry.get("conditions", []))
            ]
        page = entries[offset:offset + safe_limit]
        next_offset = offset + len(page)
        total = (
            comparison.decision_trace.excluded_offers
            if comparison.decision_trace and not condition_id else len(entries)
        )
        return {
            "comparison_id": cid,
            "items": page,
            "limit": safe_limit,
            "next_cursor": _encode_page_cursor(next_offset) if next_offset < len(entries) else None,
            "total": total,
        }

    @app.post("/comparisons/{cid}/scenarios")
    async def run_comparison_scenario(
        cid: str, body: dict[str, Any], request: Request
    ):
        owner_id = owner_session(request)
        store.get_comparison(cid, owner_id)
        kind = body.get("kind")
        if kind == "cost":
            try:
                assumptions = CostScenarioAssumptions.model_validate(body.get("assumptions"))
            except (TypeError, ValueError) as exc:
                raise AppError("SCENARIO_INVALID", "Invalid cost scenario assumptions.", 422) from exc
            if (
                any(value < 0 for value in assumptions.traveler_mix.values())
                or (assumptions.traveler_mix and sum(assumptions.traveler_mix.values()) != assumptions.travelers)
                or (assumptions.single_rooms is not None and assumptions.rooms is not None
                    and assumptions.single_rooms > assumptions.rooms)
            ):
                raise AppError("SCENARIO_INVALID", "Cost assumptions are inconsistent.", 422)
            try:
                snapshot = store.get_decision_snapshot(cid, owner_id)
            except AppError as exc:
                if exc.code != "NOT_FOUND":
                    raise
                raise AppError(
                    "SCENARIO_SNAPSHOT_UNAVAILABLE",
                    "This comparison has no retained scan snapshot. Rerun it before testing a scenario.",
                    409,
                ) from exc
            scenario = cost_scenario(snapshot, assumptions)
            return {"kind": "cost", "scenario": scenario.model_dump(mode="json")}

        if kind != "criteria":
            raise AppError("SCENARIO_KIND_INVALID", "Scenario kind must be criteria or cost.", 422)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required for scenarios.", 401)
        agent_session_id = body.get("agent_session_id")
        value = body.get("requirement")
        if not isinstance(agent_session_id, str) or not isinstance(value, dict):
            raise AppError("SCENARIO_INVALID", "A scenario requirement and agent session are required.", 422)
        store.get_agent_session(agent_session_id, owner_id)
        try:
            requirement = workflows.requirement(
                value.get("raw_text", ""),
                value.get("conditions"),
                value.get("travelers", 1),
                value.get("ranking"),
                requirement_id=uid("req"),
                require_weights=True,
                traveler_mix=value.get("traveler_mix"),
                alternatives=value.get("alternatives"),
                assumptions=value.get("assumptions"),
            )
        except (TypeError, ValueError) as exc:
            raise AppError("SCENARIO_INVALID", "Invalid scenario requirement.", 422) from exc
        if "text/event-stream" in request.headers.get("accept", ""):

            async def stream_events():
                try:
                    async for event in agent.stream_decision(
                        owner_id,
                        agent_session_id,
                        requirement,
                        snapshot_comparison_id=cid,
                    ):
                        event_type = event.get("type", "progress")
                        payload = (
                            event.get("response", {}) if event_type == "result"
                            else {key: item for key, item in event.items() if key != "type"}
                        )
                        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        yield f"event: {event_type}\ndata: {data}\n\n"
                except AppError as exc:
                    log_app_error(exc, transport="sse", operation="comparison_scenario")
                    data = json.dumps(
                        {"code": exc.code, "message": exc.message},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"
                except Exception as exc:
                    log_unexpected_error(exc, transport="sse", operation="comparison_scenario")
                    data = json.dumps(
                        {"code": "INTERNAL_ERROR", "message": "An internal error occurred."},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {data}\n\n"

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
            )
        result = await agent.decision(
            owner_id,
            agent_session_id,
            requirement,
            snapshot_comparison_id=cid,
        )
        return {"kind": "criteria", **result}

    @app.get("/history")
    async def get_history(
        request: Request,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required to read history.", 401)
        before = None
        if cursor:
            try:
                padded = cursor + "=" * (-len(cursor) % 4)
                decoded = base64.urlsafe_b64decode(padded.encode()).decode("utf-8")
                cursor_data = json.loads(decoded)
                if (
                    not isinstance(cursor_data, list)
                    or len(cursor_data) != 2
                    or not all(isinstance(value, str) for value in cursor_data)
                ):
                    raise ValueError
                before = (cursor_data[0], cursor_data[1])
            except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
                raise AppError("CURSOR_INVALID", "Invalid history cursor.", 400) from None

        page_size = max(1, min(limit, 100))
        items, has_more = store.list_history(owner_id, page_size, before)
        next_cursor = None
        if has_more and items:
            last = items[-1]
            encoded = json.dumps([last["created_at"], last["id"]], separators=(",", ":"))
            next_cursor = base64.urlsafe_b64encode(encoded.encode()).decode().rstrip("=")
        return {"items": items, "next_cursor": next_cursor}

    @app.get("/history/{item_id}")
    async def get_history_item(item_id: str, request: Request) -> dict[str, Any]:
        owner_id = owner_session(request)
        if owner_id is None:
            raise AppError("SESSION_REQUIRED", "A guest access session is required to read history.", 401)
        return store.get_history_item(item_id, owner_id)

    return app
