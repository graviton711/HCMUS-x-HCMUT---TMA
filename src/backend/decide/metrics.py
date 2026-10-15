"""Evidence-backed metric profiles and conservative group-cost calculations."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from backend.models import (
    ActivityFact,
    CostExposure,
    CostProfile,
    CoverageFact,
    ExtractedTourFacts,
    MetricEvidence,
    MetricMeasure,
    MetricProfile,
    PreferenceScore,
    Requirement,
    TourSnapshot,
)

_AGE_GROUPS = ("adult", "child", "small_child", "infant")
_FACT_EXTRACTOR_VERSION = "tour-facts-v3"


def fact_cache_id(tour: TourSnapshot) -> str:
    fields = {
        "route": tour.route if tour.route_observed else [],
        "itinerary": tour.itinerary,
        "inclusions": tour.inclusions,
        "exclusions": tour.exclusions,
        "surcharges": tour.surcharges,
        "cancellation_policy": tour.cancellation_policy,
        "child_policy": tour.child_policy,
    }
    source_hash = hashlib.sha256(
        json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return "metric_" + hashlib.sha256(f"{_FACT_EXTRACTOR_VERSION}:{source_hash}".encode()).hexdigest()


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", plain)


def _party_base(req: Requirement, tour: TourSnapshot, offer) -> tuple[int | None, str]:
    if offer.price is None or not offer.currency:
        return None, ""
    mix = req.traveler_mix
    if not mix or sum(mix.values()) != req.travelers:
        return None, "Chưa có cơ cấu độ tuổi; chỉ có giá niêm yết."
    total = 0
    for age_group in _AGE_GROUPS:
        count = mix.get(age_group, 0)
        if not count:
            continue
        age_price = offer.price_by_age.get(age_group)
        if age_price is None and age_group == "adult":
            age_price = offer.price
        if age_price is None:
            return None, f"Thiếu giá cho nhóm {age_group}."
        total += age_price * count
    return total, ""


def _exposure_quantity(unit: str, req: Requirement, tour: TourSnapshot) -> int | None:
    mix = req.traveler_mix
    if unit == "per_booking":
        return 1
    if unit == "per_person":
        return req.travelers if mix and sum(mix.values()) == req.travelers else None
    if unit == "per_adult":
        return mix.get("adult") if mix and "adult" in mix else None
    if unit == "per_child":
        return (mix.get("child", 0) + mix.get("small_child", 0)) if mix else None
    if unit == "per_day":
        return tour.duration_days
    if unit == "per_night":
        return tour.duration_nights
    return None


def _price_exposures(
    facts: ExtractedTourFacts, req: Requirement, tour: TourSnapshot, offer
) -> tuple[list[CostExposure], list[CostExposure], list[CostExposure], int, bool]:
    priced: list[CostExposure] = []
    unpriced: list[CostExposure] = []
    optional: list[CostExposure] = []
    priced_total = 0
    unresolved_mandatory = False
    for source in (*facts.exclusions, *facts.surcharges):
        item = source.model_copy(deep=True)
        currency = item.currency.upper()
        qty = _exposure_quantity(item.unit, req, tour)
        if item.obligation in ("optional", "conditional"):
            optional.append(item)
            if item.obligation == "conditional":
                unresolved_mandatory = True
                if item.amount is None or item.unit == "unknown" or qty is None or not currency:
                    unpriced.append(item)
        elif item.obligation == "mandatory":
            if (
                item.amount is not None
                and item.unit != "unknown"
                and qty is not None
                and bool(currency)
                and currency == offer.currency.upper()
            ):
                item.calculated_total = item.amount * qty
                priced_total += item.calculated_total
                priced.append(item)
            else:
                unresolved_mandatory = True
                unpriced.append(item)
        else:
            unresolved_mandatory = True
            unpriced.append(item)
    if offer.single_supplement is not None:
        # Number of rooms and whether single occupancy applies are not known.
        optional.append(CostExposure(
            name="Phụ thu phòng đơn",
            obligation="conditional",
            amount=offer.single_supplement,
            currency=offer.currency.upper(),
            unit="per_room",
            source_field="offers.single_supplement",
        ))
        unresolved_mandatory = True
    return priced, unpriced, optional, priced_total, unresolved_mandatory


def _preference_scores(req: Requirement, offer_id: str, verdicts, tour: TourSnapshot) -> tuple[list[PreferenceScore], float, float, int]:
    scores: list[PreferenceScore] = []
    lower = upper = 0.0
    covered = 0
    weight_sum = sum(condition.weight_percent or 0 for condition in req.soft())
    for condition in req.soft():
        state, quote, _reason = verdicts.get((offer_id, condition.id), ("unknown", "", ""))
        weight = condition.weight_percent or 0
        score = {"pass": 1.0, "partial": 0.5, "fail": 0.0}.get(state)
        if score is None:
            low, high = 0.0, 1.0
            metric_state = "unknown"
        else:
            low = high = score
            metric_state = "observed"
            covered += 1
        evidence: list[MetricEvidence] = []
        if quote:
            source_fields = (
                ("itinerary", tour.itinerary), ("inclusions", tour.inclusions),
                ("exclusions", tour.exclusions), ("surcharges", tour.surcharges),
                ("cancellation_policy", tour.cancellation_policy), ("child_policy", tour.child_policy),
            )
            source = next((name for name, text in source_fields if quote in text), "soft_preference")
            evidence = [MetricEvidence(
                source_field=source, quote=quote,
                observed_at=tour.observed_at, url=tour.url,
            )]
        scores.append(PreferenceScore(
            condition_id=condition.id,
            lower_score=low,
            upper_score=high,
            state=metric_state,
            evidence=evidence,
        ))
        lower += weight * low
        upper += weight * high
    if weight_sum:
        lower /= weight_sum
        upper /= weight_sum
    return scores, lower, upper, covered


def build_metric_profiles(
    req: Requirement,
    surviving: list[tuple[TourSnapshot, str]],
    verdicts,
    facts_by_tour: dict[str, ExtractedTourFacts] | None = None,
) -> list[MetricProfile]:
    facts_by_tour = facts_by_tour or {}
    profiles: list[MetricProfile] = []
    for tour, offer_id in surviving:
        offer = next((item for item in tour.offers if item.id == offer_id), None)
        if offer is None:
            continue
        facts = facts_by_tour.get(tour.id, ExtractedTourFacts(tour_id=tour.id))
        if facts.tour_id != tour.id:
            facts = ExtractedTourFacts(tour_id=tour.id)
        group_base, group_note = _party_base(req, tour, offer)
        priced, unpriced, optional, extra_total, unresolved = _price_exposures(facts, req, tour, offer)
        if not {"exclusions", "surcharges"}.issubset(facts.reviewed_fields):
            unresolved = True
        group_total = None
        total_scope = group_note
        cost_state = "unknown"
        if group_base is not None:
            group_total = group_base + extra_total
            total_scope = (
                "Tạm tính theo khoản bắt buộc đã biết; còn chi phí chưa xác định"
                if unresolved else "Tổng nhóm theo giá và khoản bắt buộc đã biết"
            )
            cost_state = "partial" if unresolved else "observed"
        elif offer.price is not None:
            cost_state = "partial"
        cost = CostProfile(
            listed_price=offer.price,
            price_basis=offer.price_basis,
            currency=offer.currency,
            group_total_calculated=group_total,
            group_total_scope=total_scope,
            total_is_lower_bound=False,
            priced_extras=priced,
            unpriced_exclusions=unpriced,
            optional_or_conditional=optional,
            state=cost_state,
        )

        unique_activities: dict[str, ActivityFact] = {}
        for activity in facts.activities:
            unique_activities.setdefault(_fold(activity.name), activity)
        activity_count = len(unique_activities)
        activity_evidence = [activity.evidence for activity in unique_activities.values()]
        experience_state = "observed" if activity_count else "unknown"
        measures: dict[str, MetricMeasure] = {
            "experience_density": MetricMeasure(
                value={
                    "activity_count": activity_count,
                    "per_day": round(activity_count / tour.duration_days, 2)
                    if activity_count and tour.duration_days else None,
                },
                unit="distinct_stated_activities",
                state=experience_state,
                evidence=activity_evidence,
                method_version=facts.method_version,
            ),
        }

        if tour.route_observed:
            route_count = max(0, len(tour.route) - 1)
            route_evidence = [MetricEvidence(
                source_field="route", quote=" → ".join(tour.route),
                observed_at=tour.observed_at, url=tour.url,
            )]
        else:
            route_count = len(facts.route_legs)
            route_evidence = [leg.evidence for leg in facts.route_legs]
        modes = [leg.mode.casefold() for leg in facts.route_legs if leg.mode.strip()]
        mode_changes = sum(left != right for left, right in zip(modes, modes[1:], strict=False)) if modes else None
        measures["route_complexity"] = MetricMeasure(
            value={"explicit_legs": route_count, "transport_changes": mode_changes},
            unit="legs_and_changes",
            state="observed" if route_evidence else "unknown",
            evidence=route_evidence,
            method_version=facts.method_version,
        )

        coverage_counts = {status: 0 for status in ("included", "partial", "excluded", "unknown")}
        facts_by_category: dict[str, list[CoverageFact]] = {}
        for item in facts.inclusions:
            facts_by_category.setdefault(item.category, []).append(item)
        for category_facts in facts_by_category.values():
            statuses = {item.status for item in category_facts}
            status = next(iter(statuses)) if len(statuses) == 1 else "unknown"
            coverage_counts[status] += 1
        known_coverage = sum(coverage_counts[key] for key in ("included", "partial", "excluded"))
        coverage_ratio = (
            (coverage_counts["included"] + coverage_counts["partial"] * 0.5) / known_coverage
            if known_coverage else None
        )
        inclusion_evidence = [item.evidence for item in facts.inclusions]
        measures["included_coverage"] = MetricMeasure(
            value={**coverage_counts, "known_categories": known_coverage, "ratio": coverage_ratio},
            unit="category_coverage_ratio",
            state="observed" if known_coverage else "unknown",
            evidence=inclusion_evidence,
            method_version=facts.method_version,
        )

        unresolved_cost_map = {
            (item.source_field, _fold(item.name), item.quote): item
            for item in [
                *unpriced,
                *(item for item in optional if item.obligation == "conditional"),
            ]
        }
        unresolved_costs = list(unresolved_cost_map.values())
        reviewed_cost_fields = {
            name for name in ("exclusions", "surcharges") if name in facts.reviewed_fields
        }
        measures["unpriced_cost_exposures"] = MetricMeasure(
            value={
                "count": len(unresolved_costs),
                "reviewed_fields": sorted(reviewed_cost_fields),
            },
            unit="documented_unpriced_or_conditional_items",
            state=(
                "observed" if len(reviewed_cost_fields) == 2
                else "partial" if reviewed_cost_fields
                else "unknown"
            ),
            evidence=[
                MetricEvidence(
                    source_field=item.source_field,
                    quote=item.quote,
                    observed_at=tour.observed_at,
                    url=tour.url,
                )
                for item in unresolved_costs if item.quote
            ],
            method_version=facts.method_version,
        )

        full_refund_days = [
            rule.days_before_departure for rule in facts.cancellation_rules
            if rule.refund_percent == 100 and rule.days_before_departure is not None
        ]
        measures["cancellation_flexibility"] = MetricMeasure(
            value=min(full_refund_days) if full_refund_days else None,
            unit="days_before_departure_for_full_refund",
            state="observed" if facts.cancellation_rules else "unknown",
            evidence=[rule.evidence for rule in facts.cancellation_rules],
            method_version=facts.method_version,
        )

        family_evidence = [fact.evidence for fact in facts.family_facts]
        measures["family_suitability"] = MetricMeasure(
            value=None,
            unit="age_eligibility_and_party_match",
            state="unknown",
            evidence=family_evidence,
            method_version=facts.method_version,
        )
        measures["family_policy_coverage"] = MetricMeasure(
            value=len(facts.family_facts),
            unit="explicit_child_policy_facts",
            state="observed" if facts.family_facts else "unknown",
            evidence=family_evidence,
            method_version=facts.method_version,
        )

        fit_scores, fit_low, fit_high, fit_covered = _preference_scores(req, offer_id, verdicts, tour)
        if req.soft():
            measures["preference_fit"] = MetricMeasure(
                lower_bound=fit_low,
                upper_bound=fit_high,
                unit="weighted_points_0_100",
                state="observed" if fit_low == fit_high else "partial",
                evidence=[e for score in fit_scores for e in score.evidence],
                method_version="preference-weight-v1",
            )

        applicable = ["cost", "experience_density", "route_complexity", "included_coverage",
                      "unpriced_cost_exposures", "cancellation_flexibility", "family_suitability"]
        if req.soft():
            applicable.append("preference_fit")
        observed = sum(
            name == "cost" and cost.state != "unknown"
            or name in measures and measures[name].state != "unknown"
            for name in applicable
        )
        measures["evidence_coverage"] = MetricMeasure(
            value={"observed_metrics": observed, "applicable_metrics": len(applicable),
                   "ratio": observed / len(applicable) if applicable else 0.0},
            unit="observed_metric_ratio",
            state="observed" if observed else "unknown",
            method_version="coverage-v1",
        )
        profiles.append(MetricProfile(
            tour_id=tour.id,
            offer_id=offer_id,
            cost=cost,
            preference_fit=fit_scores,
            metrics=measures,
            inclusions=[MetricMeasure(
                value={"category": item.category, "status": item.status},
                unit="coverage_status", state="observed", evidence=[item.evidence],
                method_version=facts.method_version,
            ) for item in facts.inclusions],
            exclusions=[*facts.exclusions, *facts.surcharges],
            cancellation_rules=facts.cancellation_rules,
            family_facts=facts.family_facts,
        ))
    return profiles
