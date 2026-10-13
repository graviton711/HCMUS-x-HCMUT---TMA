"""Local MCP tool server for grounded travel-agent workflows."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from functools import wraps
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from backend.agent.results import limit_comparison
from backend.data.catalog import for_settings
from backend.decide.engine import passing_offers
from backend.error_logging import log_app_error, log_unexpected_error
from backend.errors import AppError
from backend.input.lunar import resolve_lunar
from backend.models import Requirement, State
from backend.settings import Settings
from backend.workflows import TourWorkflows

_VERDICT_STATES = {"fit": "pass", "unknown": "unknown", "not_fit": "fail"}


class QueryConditionInput(BaseModel):
    """Structured MCP input; semantic constraints are rechecked by the workflow."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique condition ID, e.g. c1.")
    field: Literal[
        "destination", "departure_city", "date_from", "date_to", "budget_max",
        "duration_days", "transport", "accommodation", "preference",
    ] = Field(description="Condition field supported by the travel requirement contract.")
    operator: Literal["contains", "any", "eq", "lte"] = Field(
        description="Operator compatible with the selected field."
    )
    value: str | int | list[str] = Field(
        description="Condition value: text, positive integer, or destination choices."
    )
    strength: Literal["hard", "soft"] = Field(description="Whether this is a hard or soft condition.")
    quote: str = Field(description="Exact substring copied from raw_text that supports this condition.")


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class AgentTools:
    def __init__(self, settings: Settings, catalog: Any, workflows: TourWorkflows):
        self.settings = settings
        self.catalog = catalog
        self.workflows = workflows
        self._destination_names: dict[str, str] | None = None

    def ask_choice(
        self, question: str, options: list[dict[str, str]], allow_custom: bool = True
    ) -> str:
        clean = []
        seen: set[str] = set()
        for option in options[:8]:
            label = option.get("label", "").strip()
            value = option.get("value", "").strip()
            canonical_value = self._canonical_destination(value)
            if _fold_catalog_text(label) == _fold_catalog_text(value):
                label = canonical_value
            else:
                label = self._canonical_destination(label)
            value = canonical_value
            key = _fold_catalog_text(value)
            if label and value and key not in seen:
                clean.append({"label": label[:100], "value": value[:200]})
                seen.add(key)
        if not question.strip() or len(clean) < 2:
            return _json({"error": "Provide a question and at least two distinct choices."})
        return _json({"question": question[:240], "options": clean, "allow_custom": allow_custom})

    def _canonical_destination(self, value: str) -> str:
        if self._destination_names is None:
            names = self.catalog.list_destinations()
            folded: dict[str, set[str]] = {}
            for name in names:
                if isinstance(name, str) and name.strip():
                    folded.setdefault(_fold_catalog_text(name), set()).add(name.strip())
            self._destination_names = {
                key: next(iter(matches)) for key, matches in folded.items() if len(matches) == 1
            }
        return self._destination_names.get(_fold_catalog_text(value), value)

    def catalog_facets(self) -> str:
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        destinations = sorted({value for tour in tours for value in tour.destinations})
        prices = sorted({
            offer.price for tour in tours for offer in tour.offers
            if offer.price is not None and offer.currency == "VND"
        })
        dates = sorted({
            offer.departure_date for tour in tours for offer in tour.offers
            if _is_iso_date(offer.departure_date)
        })
        return _json({
            "destinations": destinations,
            "prices_vnd": prices,
            "departure_dates": dates,
            "scanned_tours": len(tours),
            "scan_limit": self.settings.supabase_scan_limit,
        })

    def query_tours(
        self, raw_text: str, conditions: list[QueryConditionInput], travelers: int = 1
    ) -> str:
        structured_conditions = [
            item.model_dump(mode="json")
            if isinstance(item, QueryConditionInput)
            else QueryConditionInput.model_validate(item).model_dump(mode="json")
            for item in conditions
        ]
        requirement = self.workflows.requirement(raw_text, structured_conditions, travelers)
        comparison = self.workflows.comparison(requirement, self.settings.supabase_scan_limit)
        hard_ids = {condition.id for condition in requirement.hard()}
        evaluations: dict[str, list[Any]] = {}
        for item in comparison.evaluations:
            if item.condition_id not in hard_ids:
                continue
            evaluations.setdefault(item.offer_id, []).append(item)
        candidates = []
        for tour in comparison.tour_snapshots:
            for offer in tour.offers:
                items = evaluations.get(offer.id, [])
                states = [item.state for item in items]
                state: State = (
                    "fail" if "fail" in states else
                    "unknown" if "unknown" in states else "pass"
                )
                candidates.append({
                    "tour_id": tour.id,
                    "offer_id": offer.id,
                    "hard_state": state,
                    "reason_codes": [item.reason_code for item in items if item.reason_code],
                })
        limited_comparison = limit_comparison(comparison)
        return _json({
            "requirement": requirement.model_dump(mode="json"),
            "comparison": limited_comparison.model_dump(mode="json"),
            "candidates": candidates,
            "candidate_count": len(candidates),
            "scanned_tours": len(comparison.tour_snapshots),
            "scan_limit": self.settings.supabase_scan_limit,
        })

    def tour_detail(self, tour_id: str) -> str:
        tours = self.workflows.snapshots(self.settings.supabase_scan_limit)
        tour = next((tour for tour in tours if tour.id == tour_id), None)
        if tour is None:
            return _json({"error": "Tour not found in the active catalog."})
        return _json(tour.model_dump(mode="json"))

    def score_soft(
        self,
        requirement: dict[str, Any],
        verdicts: list[dict[str, Any]],
    ) -> str:
        req = _validate_requirement_object(self.workflows, requirement)
        if not req.soft():
            return _json({"error": "No soft preferences were supplied."})
        base = self.workflows.comparison(req, self.settings.supabase_scan_limit)
        allowed = {offer_id for _, offer_id in passing_offers(req, base.tour_snapshots, base.evaluations)}
        conditions = {condition.id for condition in req.soft()}
        text_by_offer: dict[str, str] = {}
        for tour in base.tour_snapshots:
            raw = "\n".join(
                str(getattr(tour, field, "")) for field in self.settings.tuning.decide.soft_fields
            )
            for offer in tour.offers:
                text_by_offer[offer.id] = raw

        validated: dict[tuple[str, str], tuple[State, str, str]] = {}
        seen: set[tuple[str, str]] = set()
        max_quote = min(self.settings.tuning.decide.quote_chars, 200)
        for item in verdicts:
            offer_id = str(item.get("offer_id", ""))
            condition_id = str(item.get("condition_id", ""))
            key = (offer_id, condition_id)
            if key in seen:
                continue
            seen.add(key)
            if offer_id not in allowed or condition_id not in conditions:
                continue
            state = _VERDICT_STATES.get(str(item.get("verdict", "")))
            quote = item.get("quote") if isinstance(item.get("quote"), str) else ""
            reason = item.get("reason") if isinstance(item.get("reason"), str) else ""
            quote_is_grounded = bool(quote) and len(quote) <= max_quote and quote in text_by_offer[offer_id]
            reason_is_bounded = bool(reason.strip()) and len(reason) <= 500 and _sentence_count(reason) <= 2
            if state is None or not quote_is_grounded or not reason_is_bounded:
                validated[key] = ("unknown", "", "Chưa có trích dẫn hợp lệ để xác nhận.")
            else:
                validated[key] = (state, quote, reason.strip())

        comparison = self.workflows.comparison(
            req,
            candidate_limit=self.settings.supabase_scan_limit,
            soft_verdicts=validated,
        )
        return _json({
            "requirement": req.model_dump(mode="json"),
            "comparison": limit_comparison(comparison).model_dump(mode="json"),
            "accepted_verdicts": len(validated),
        })

    def relax_criterion(self, requirement: dict[str, Any], condition_id: str) -> str:
        req = _validate_requirement_object(self.workflows, requirement)
        condition = next((item for item in req.hard() if item.id == condition_id), None)
        if condition is None:
            return _json({"error": "Only an existing hard condition can be relaxed."})
        updated = self.workflows.requirement(
            req.raw_text,
            [item.model_dump(mode="json") for item in req.conditions if item.id != condition_id],
            req.travelers,
        )
        comparison = limit_comparison(self.workflows.comparison(
            updated, self.settings.supabase_scan_limit
        ))
        return _json({
            "removed_condition": condition.model_dump(mode="json"),
            "requirement": updated.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json"),
        })

    def clarify_date(self, calendar: str, year: int, month: int, day: int, leap: bool = False) -> str:
        if calendar == "lunar":
            result = resolve_lunar({"year": year, "month": month, "day": day, "leap": leap})
        elif calendar == "solar":
            try:
                result = date(year, month, day).isoformat()
            except ValueError:
                result = None
        else:
            result = None
        return _json({"calendar": calendar, "iso_date": result, "valid": result is not None})


def _validate_requirement_object(workflows: TourWorkflows, value: dict[str, Any]) -> Requirement:
    return workflows.requirement(
        str(value.get("raw_text", "")), value.get("conditions"), value.get("travelers", 1)
    )


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _sentence_count(value: str) -> int:
    sentences = [item for item in re.split(r"(?<=[.!?。！？])\s+", value.strip()) if item]
    return len(sentences) or (1 if value.strip() else 0)


def _fold_catalog_text(value: str) -> str:
    folded = unicodedata.normalize("NFD", value.strip().casefold().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(char for char in folded if not unicodedata.combining(char)))


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.load()
    catalog = for_settings(settings)
    workflows = TourWorkflows(settings, catalog)
    tools = AgentTools(settings, catalog, workflows)
    server = FastMCP("tour-catalog")

    server.tool()(_guard_tool("ask_choice", tools.ask_choice))
    server.tool()(_guard_tool("catalog_facets", tools.catalog_facets))
    server.tool()(_guard_tool("query_tours", tools.query_tours))
    server.tool()(_guard_tool("tour_detail", tools.tour_detail))
    server.tool()(_guard_tool("score_soft", tools.score_soft))
    server.tool()(_guard_tool("relax_criterion", tools.relax_criterion))
    server.tool()(_guard_tool("clarify_date", tools.clarify_date))
    return server


def _guard_tool(name: str, function: Any) -> Any:
    """Convert tool exceptions to a safe JSON error and log them once."""

    @wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> str:
        try:
            return function(*args, **kwargs)
        except AppError as exc:
            log_app_error(exc, transport="mcp", operation=name)
            return _json(exc.payload())
        except Exception as exc:
            log_unexpected_error(exc, transport="mcp", operation=name)
            return _json(
                {"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}}
            )

    return guarded


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
