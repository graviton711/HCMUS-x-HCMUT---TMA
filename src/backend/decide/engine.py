"""Hard filter → soft LLM assess → rank → analyze. Unknown never passes."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import cmp_to_key

from backend.decide.metrics import build_metric_profiles
from backend.models import (
    Analysis,
    Comparison,
    Condition,
    DecisionBlockerCount,
    DecisionConditionCount,
    DecisionFunnelStep,
    DecisionOption,
    DecisionTrace,
    DecisionView,
    Evaluation,
    ExtractedTourFacts,
    MetricEvidence,
    MetricProfile,
    OfferSnapshot,
    OptionMetricComparison,
    RankedCandidate,
    RankingKey,
    Requirement,
    State,
    TourSnapshot,
    uid,
)
from backend.settings import DecideCfg

RankValue = int | float | str | tuple[str, int | float]


def _contains(haystack: str, needle: str) -> bool:
    return _fold(needle) in _fold(haystack)


def _fold(value: str) -> str:
    text = value.replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _destination_state(value: str, tour: TourSnapshot) -> State:
    if any(_contains(place, value) for place in tour.destinations):
        return "pass"
    return "fail" if tour.destinations else "unknown"


def eval_hard(condition: Condition, tour: TourSnapshot, offer: OfferSnapshot) -> tuple[State, str]:
    """Per-offer hard evaluation. Anything unprovable is `unknown`."""
    f, v = condition.field, condition.value
    any_op = condition.operator == "any" and isinstance(v, list)
    if f == "destination":
        vals = v if any_op else [v]
        states = [_destination_state(str(x), tour) for x in vals]
        return (
            ("pass", "")
            if "pass" in states
            else (
                ("unknown", "DESTINATION_MISSING")
                if "unknown" in states
                else ("fail", "DESTINATION_MISMATCH")
            )
        )
    if f == "departure_city":
        vals = v if any_op else [v]
        return (
            ("pass", "")
            if any(_contains(tour.departure_city, str(x)) for x in vals)
            else ("fail", "DEPARTURE_CITY_MISMATCH")
        )
    if f == "transport":
        if str(v) not in ("flight", "bus", "train", "cruise", "mixed"):
            return "unknown", "UNSUPPORTED_TRANSPORT"
        return (
            ("pass", "")
            if tour.transport == str(v)
            else (("unknown", "FIELD_MISSING") if not tour.transport else ("fail", "TRANSPORT_MISMATCH"))
        )
    if f == "accommodation":
        return (
            ("pass", "")
            if _contains(tour.accommodation, str(v))
            else (
                ("unknown", "FIELD_MISSING") if not tour.accommodation else ("fail", "ACCOMMODATION_MISMATCH")
            )
        )
    if f == "duration_days":
        return (
            ("unknown", "FIELD_MISSING")
            if tour.duration_days is None
            else (("pass", "") if tour.duration_days == v else ("fail", "DURATION_MISMATCH"))
        )
    if f in ("date_from", "date_to"):
        if not offer.departure_date:
            return "unknown", "FIELD_MISSING"
        try:
            day = date.fromisoformat(offer.departure_date)
            bound = date.fromisoformat(str(v))
        except ValueError:
            return "unknown", "FIELD_INVALID"
        ok = day >= bound if f == "date_from" else day <= bound
        return ("pass", "") if ok else ("fail", "DATE_MISMATCH")
    if f == "budget_max":
        if offer.price is None or isinstance(v, list):
            return "unknown", "PRICE_MISSING"
        amount = v
        currency = "VND"
        basis = "per_adult"
        coverage = "tour_price"
        if currency and currency.upper() != offer.currency.upper():
            return "unknown", "PRICE_CURRENCY_MISMATCH"
        if basis not in ("", "per_adult") or coverage not in ("", "tour_price"):
            return "unknown", "PRICE_BASIS_MISMATCH"
        try:
            maximum = int(amount)
        except (TypeError, ValueError):
            return "unknown", "PRICE_BUDGET_INVALID"
        if offer.price_basis == "from":
            return (
                ("fail", "PRICE_LOWER_BOUND_OVER_BUDGET")
                if offer.price > maximum
                else ("unknown", "PRICE_FROM_LOWER_BOUND")
            )
        if offer.price_basis != "exact":
            return "unknown", "PRICE_NOT_EXACT"
        return ("pass", "") if offer.price <= maximum else ("fail", "PRICE_OVER_BUDGET")
    return "unknown", "FIELD_UNSUPPORTED"


def hard_filter(req: Requirement, tours: list[TourSnapshot]) -> list[Evaluation]:
    hard = req.hard()
    evals: list[Evaluation] = []
    for tour in tours:
        for offer in tour.offers:
            for cond in hard:
                state, reason = eval_hard(cond, tour, offer)
                evals.append(
                    Evaluation(offer_id=offer.id, condition_id=cond.id, state=state, reason_code=reason)
                )
    return evals


def passing_offers(
    req: Requirement, tours: list[TourSnapshot], evals: list[Evaluation]
) -> list[tuple[TourSnapshot, str]]:
    hard_ids = {c.id for c in req.hard()}
    states: dict[str, dict[str, State]] = {}
    for e in evals:
        if e.condition_id in hard_ids:
            states.setdefault(e.offer_id, {})[e.condition_id] = e.state
    out = []
    for tour in tours:
        for offer in tour.offers:
            if all(states.get(offer.id, {}).get(condition_id) == "pass" for condition_id in hard_ids):
                out.append((tour, offer.id))
    return out


def near_miss(
    req: Requirement,
    tours: list[TourSnapshot],
    evals: list[Evaluation],
    ranked_offer_ids: set[str],
    max_fails: int,
) -> list[RankedCandidate]:
    """Eliminated offers that only fail a few hard conditions, best first.

    Order: most passes, then fewest fails, then cheapest exact price.
    `unknown` counts as neither, so missing data is never penalized.
    """
    hard_ids = {c.id for c in req.hard()}
    if not hard_ids or max_fails < 0:
        return []
    fails: dict[str, int] = {}
    passes: dict[str, int] = {}
    unknowns: dict[str, int] = {}
    for e in evals:
        if e.condition_id not in hard_ids:
            continue
        if e.state == "fail":
            fails[e.offer_id] = fails.get(e.offer_id, 0) + 1
        elif e.state == "pass":
            passes[e.offer_id] = passes.get(e.offer_id, 0) + 1
        else:
            unknowns[e.offer_id] = unknowns.get(e.offer_id, 0) + 1
    scored = []
    for tour in tours:
        for offer in tour.offers:
            if offer.id in ranked_offer_ids:
                continue
            failed = fails.get(offer.id, 0)
            unknown = unknowns.get(offer.id, 0)
            if failed > max_fails or (failed == 0 and unknown == 0):
                continue
            passed = passes.get(offer.id, 0)
            price_key = offer.price if (offer.price is not None and offer.price_basis == "exact") else 10**15
            scored.append((passed, -failed, -unknown, -price_key, tour.id, offer.id))
    scored.sort(key=lambda r: (r[0], r[1], r[2], r[3]), reverse=True)
    return [
        RankedCandidate(tour_id=t, offer_id=o, score=float(p + f + u))
        for p, f, u, _, t, o in scored
    ]


def rank(
    req: Requirement,
    surviving: list[tuple[TourSnapshot, str]],
    soft_verdicts: dict[tuple[str, str], tuple[State, str, str]],
) -> list[RankedCandidate]:
    offers_by_id = {
        offer.id: offer
        for tour, offer_id in surviving
        for offer in tour.offers
        if offer.id == offer_id
    }
    soft_fit_by_offer = {
        offer_id: _soft_fit_count(req, offer_id, soft_verdicts)
        for _, offer_id in surviving
    }
    ordered = sorted(
        surviving,
        key=cmp_to_key(lambda left, right: _compare_candidates(
            left, right, _ranking_order(req), soft_fit_by_offer, offers_by_id
        )),
    )
    return [
        RankedCandidate(
            tour_id=tour.id,
            offer_id=offer_id,
            score=float(soft_fit_by_offer[offer_id]),
        )
        for tour, offer_id in ordered
    ]


def soft_review_candidates(
    req: Requirement,
    tours: list[TourSnapshot],
    evaluations: list[Evaluation],
    limit: int | None = None,
) -> list[tuple[TourSnapshot, str]]:
    """Return one representative passing offer for every tour in the scan.

    Preference evidence belongs to the tour, not to a pre-ranked top-N slice.
    Every hard-pass tour must be scored before weighted views can be computed.
    ``limit`` remains accepted for callers from the previous interface but is
    intentionally ignored.
    """
    passing = passing_offers(req, tours, evaluations)
    if not passing:
        return []
    representative: dict[str, tuple[TourSnapshot, str]] = {}
    for tour, offer_id in passing:
        previous = representative.get(tour.id)
        if previous is None or offer_id < previous[1]:
            representative[tour.id] = (tour, offer_id)
    return [representative[key] for key in sorted(representative)]


def _ranking_order(req: Requirement) -> list[RankingKey]:
    if req.ranking is not None:
        return req.ranking.order_by
    if req.soft():
        return [RankingKey(field="soft_fit", direction="desc"), RankingKey(field="price", direction="asc")]
    return [RankingKey(field="price", direction="asc")]


def _soft_fit_count(
    req: Requirement,
    offer_id: str,
    soft_verdicts: dict[tuple[str, str], tuple[State, str, str]],
) -> float:
    return sum(
        (condition.weight_percent if condition.weight_percent is not None else 1)
        * {"pass": 1.0, "partial": 0.5, "fail": 0.0}.get(
            soft_verdicts.get((offer_id, condition.id), ("unknown", "", ""))[0], 0.0
        )
        for condition in req.soft()
        if soft_verdicts.get((offer_id, condition.id), ("unknown", "", ""))[0] != "unknown"
    )


def _decision_views(
    req: Requirement,
    surviving: list[tuple[TourSnapshot, str]],
    verdicts: dict[tuple[str, str], tuple[State, str, str]],
    profiles: list[MetricProfile],
) -> list[DecisionView]:
    soft = req.soft()
    if soft and (
        any(condition.weight_percent is None for condition in soft)
        or sum(condition.weight_percent or 0 for condition in soft) != 100
    ):
        return []

    profile_by_offer = {profile.offer_id: profile for profile in profiles}
    rows = [
        (tour, offer, profile_by_offer[offer_id])
        for tour, offer_id in surviving
        for offer in tour.offers if offer.id == offer_id and offer_id in profile_by_offer
    ]

    def candidates(items: list[tuple[TourSnapshot, OfferSnapshot, float]]) -> list[RankedCandidate]:
        seen: set[str] = set()
        result: list[RankedCandidate] = []
        for tour, offer, score in items:
            if tour.id in seen:
                continue
            result.append(RankedCandidate(tour_id=tour.id, offer_id=offer.id, score=score))
            seen.add(tour.id)
            if len(result) == 5:
                break
        return result

    exact_by_currency: dict[str, list[tuple[TourSnapshot, OfferSnapshot, MetricProfile]]] = {}
    fit_rows: list[tuple[TourSnapshot, OfferSnapshot, float, float]] = []
    for tour, offer, profile in rows:
        if offer.price is not None and offer.price_basis == "exact" and offer.currency.strip():
            exact_by_currency.setdefault(offer.currency.upper(), []).append((tour, offer, profile))
        fit = profile.metrics.get("preference_fit")
        if soft and fit is not None and fit.lower_bound is not None:
            fit_rows.append((
                tour, offer, fit.lower_bound,
                fit.upper_bound if fit.upper_bound is not None else 1.0,
            ))

    cheapest_rows: list[tuple[TourSnapshot, OfferSnapshot, float]] = []
    cheapest_seen: set[str] = set()
    for currency in sorted(exact_by_currency):
        currency_rows = sorted(
            exact_by_currency[currency],
            key=lambda row: (
                row[1].price,
                -(row[2].metrics.get("preference_fit").lower_bound or 0)
                if row[2].metrics.get("preference_fit") else 0,
                row[0].id,
                row[1].id,
            ),
        )
        for tour, offer, _profile in currency_rows:
            if tour.id not in cheapest_seen:
                cheapest_rows.append((tour, offer, 0.0))
                cheapest_seen.add(tour.id)
                break
    all_exact = sorted(
        (row for values in exact_by_currency.values() for row in values),
        key=lambda row: (row[1].currency.upper(), row[1].price, row[0].id, row[1].id),
    )
    for tour, offer, _profile in all_exact:
        if tour.id in cheapest_seen:
            continue
        cheapest_rows.append((tour, offer, 0.0))
        cheapest_seen.add(tour.id)
        if len(cheapest_rows) >= 5:
            break
    cheapest = candidates(cheapest_rows)
    cheapest_currencies = sorted({
        next(offer.currency.upper() for tour, offer, _ in rows if tour.id == item.tour_id and offer.id == item.offer_id)
        for item in cheapest
    })

    fit_rows.sort(key=lambda row: (-row[2], -row[3], row[0].id, row[1].id))
    best_fit = candidates([
        (tour, offer, round(lower * 100, 2)) for tour, offer, lower, _upper in fit_rows
    ])
    best_fit_currencies = sorted({
        offer.currency.upper() for tour, offer, _score, _upper in fit_rows[:5] if offer.currency.strip()
    })

    # Pareto dominance is evaluated only within one currency. A candidate with
    # an unknown preference interval or unreviewed cost evidence cannot be
    # eliminated on that axis. Cost transparency is a count of explicit
    # unresolved/conditional items, not a monetary or probability score.
    frontier: list[tuple[TourSnapshot, OfferSnapshot, float]] = []
    for _currency, currency_rows in exact_by_currency.items():
        cost_axis_available = any(
            (row[2].metrics.get("unpriced_cost_exposures") is not None)
            and row[2].metrics["unpriced_cost_exposures"].state == "observed"
            for row in currency_rows
        )
        for tour, offer, profile in currency_rows:
            own_fit = profile.metrics.get("preference_fit")
            own_cost = profile.metrics.get("unpriced_cost_exposures")
            own_count = own_cost.value.get("count") if own_cost and own_cost.state == "observed" else None
            dominated = False
            for other_tour, other_offer, other_profile in currency_rows:
                if other_tour.id == tour.id:
                    continue
                other_fit = other_profile.metrics.get("preference_fit")
                other_cost = other_profile.metrics.get("unpriced_cost_exposures")
                other_count = other_cost.value.get("count") if other_cost and other_cost.state == "observed" else None
                if soft and (
                    own_fit is None or other_fit is None
                    or own_fit.lower_bound is None or other_fit.lower_bound is None
                    or other_fit.lower_bound < (own_fit.upper_bound if own_fit.upper_bound is not None else 1.0)
                ):
                    continue
                if cost_axis_available and (
                    own_count is None or other_count is None or other_count > own_count
                ):
                    continue
                no_worse = other_offer.price <= offer.price
                strict = other_offer.price < offer.price
                if cost_axis_available:
                    strict = strict or other_count < own_count
                if soft:
                    own_upper = own_fit.upper_bound if own_fit.upper_bound is not None else 1.0
                    no_worse = no_worse and other_fit.lower_bound >= own_upper
                    strict = strict or other_fit.lower_bound > own_upper
                if no_worse and strict:
                    dominated = True
                    break
            if not dominated:
                score = (own_fit.lower_bound * 100) if soft and own_fit and own_fit.lower_bound is not None else 0.0
                frontier.append((tour, offer, round(score, 2)))
    frontier.sort(key=lambda row: (row[1].currency.upper(), row[1].price, -row[2], row[0].id))
    balanced = candidates(frontier)
    balanced_currencies = sorted({row[1].currency.upper() for row in frontier[:5]})

    best_fit_note = (
        "Chưa có sở thích mềm để xếp mức độ phù hợp."
        if not soft else "Xếp theo cận dưới điểm ưu tiên; điểm chưa rõ giữ khoảng 0–100 và không được coi là bằng chứng trượt."
    )
    balanced_note = (
        "Tập Pareto theo giá exact cùng tiền tệ và số khoản chi phí có điều kiện/chưa định giá; "
        "nếu có ưu tiên mềm, giữ cả khoảng điểm phù hợp. Không cộng thành một điểm tổng."
    )
    return [
        DecisionView(
            kind="cheapest", candidates=cheapest, currencies=cheapest_currencies,
            note="Chỉ xếp giá exact theo giá niêm yết trong cùng tiền tệ; giá từ/liên hệ không vào thứ tự này.",
        ),
        DecisionView(
            kind="best_fit", candidates=best_fit, currencies=best_fit_currencies,
            note=best_fit_note,
        ),
        DecisionView(
            kind="balanced", candidates=balanced, currencies=balanced_currencies,
            note=balanced_note,
        ),
    ]


def _measure_number(profile: MetricProfile, key: str, nested: str = "") -> float | None:
    metric = profile.metrics.get(key)
    if metric is None or metric.state == "unknown":
        return None
    value = metric.value
    if nested:
        value = value.get(nested) if isinstance(value, dict) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _objective_views(profiles: list[MetricProfile], base: list[DecisionView]) -> list[DecisionView]:
    def candidates_for(rows: list[tuple[float, str, MetricProfile]], *, reverse: bool = False):
        rows.sort(key=lambda row: (row[0] if reverse else -row[0], row[1]))
        seen: set[str] = set()
        result: list[RankedCandidate] = []
        for value, _tour_id, profile in rows:
            if profile.tour_id in seen:
                continue
            result.append(RankedCandidate(
                tour_id=profile.tour_id, offer_id=profile.offer_id, score=value
            ))
            seen.add(profile.tour_id)
            if len(result) == 5:
                break
        return result

    experience = []
    route = []
    cancellation = []
    family = []
    included: list[tuple[float, MetricProfile]] = []
    for profile in profiles:
        count = _measure_number(profile, "experience_density", "activity_count")
        if count is not None:
            experience.append((count, profile.tour_id, profile))
        legs = _measure_number(profile, "route_complexity", "explicit_legs")
        if legs is not None:
            route.append((legs, profile.tour_id, profile))
        free_days = _measure_number(profile, "cancellation_flexibility")
        if free_days is not None:
            # A smaller number means the user may cancel closer to departure.
            cancellation.append((-free_days, profile.tour_id, profile))
        child_detail = _measure_number(profile, "family_suitability")
        if child_detail is not None:
            family.append((child_detail, profile.tour_id, profile))
        coverage = _measure_number(profile, "included_coverage", "ratio")
        if coverage is not None:
            included.append((coverage, profile))

    base_by_kind = {view.kind: view for view in base}
    included.sort(key=lambda row: (-row[0], row[1].tour_id))
    included_candidates: list[RankedCandidate] = []
    included_seen: set[str] = set()
    for ratio, profile in included:
        if profile.tour_id in included_seen:
            continue
        included_candidates.append(RankedCandidate(
            tour_id=profile.tour_id, offer_id=profile.offer_id, score=ratio
        ))
        included_seen.add(profile.tour_id)
        if len(included_candidates) == 5:
            break
    notes = {
        "experience_rich": "Xếp theo số hoạt động/điểm tham quan nêu rõ; số lượng không khẳng định chất lượng.",
        "fewest_legs": "Chỉ đếm chặng được nêu rõ trong route/lịch trình; không suy ra thời gian hay quãng đường.",
        "cancellation_flexible": "Xếp theo mốc gần ngày đi nhất vẫn được hoàn 100%, khi điều khoản nêu rõ.",
        "family_friendly": "Chưa đủ dữ liệu tuổi cụ thể để xếp mức phù hợp cho nhóm; xem các điều khoản trẻ em có trích dẫn riêng.",
        "included_value": "Tỷ lệ hạng mục gồm/ gồm một phần; các khoản loại trừ chưa định giá được liệt kê riêng, không gộp vào điểm.",
    }
    additional = [
        DecisionView(kind="experience_rich", candidates=candidates_for(experience), note=notes["experience_rich"]),
        DecisionView(kind="fewest_legs", candidates=candidates_for(route, reverse=True), note=notes["fewest_legs"]),
        DecisionView(kind="cancellation_flexible", candidates=candidates_for(cancellation), note=notes["cancellation_flexible"]),
        DecisionView(kind="family_friendly", candidates=candidates_for(family), note=notes["family_friendly"]),
        DecisionView(kind="included_value", candidates=included_candidates, note=notes["included_value"]),
    ]
    base_by_kind.update({view.kind: view for view in additional})
    return [base_by_kind[key] for key in (
        "cheapest", "best_fit", "experience_rich", "fewest_legs",
        "cancellation_flexible", "family_friendly", "included_value", "balanced",
    ) if key in base_by_kind]


def _option_tradeoffs(profile: MetricProfile) -> list[str]:
    tradeoffs: list[str] = []
    cost = profile.cost
    if cost.group_total_calculated is not None:
        suffix = " (tạm tính tối thiểu)" if cost.total_is_lower_bound else ""
        tradeoffs.append(f"Tổng nhóm tính được: {cost.group_total_calculated:,} {cost.currency}{suffix}")
    elif cost.listed_price is not None:
        basis = "giá từ" if cost.price_basis == "from" else "giá niêm yết"
        tradeoffs.append(f"{basis}: {cost.listed_price:,} {cost.currency}; chưa tính tổng nhóm")
    if cost.unpriced_exclusions:
        tradeoffs.append(f"{len(cost.unpriced_exclusions)} khoản loại trừ/chi phí chưa thể định giá")
    conditional_count = sum(
        item.obligation == "conditional" for item in cost.optional_or_conditional
    )
    if conditional_count:
        tradeoffs.append(f"{conditional_count} khoản có điều kiện, chưa cộng vào tổng nhóm")
    fit = profile.metrics.get("preference_fit")
    if fit is not None:
        tradeoffs.append(f"Khớp ưu tiên: {fit.lower_bound or 0:.0f}–{fit.upper_bound or 0:.0f}/100")
    activities = _measure_number(profile, "experience_density", "activity_count")
    if activities is not None:
        tradeoffs.append(f"{int(activities)} hoạt động được nêu rõ")
    legs = _measure_number(profile, "route_complexity", "explicit_legs")
    if legs is not None:
        tradeoffs.append(f"{int(legs)} chặng được ghi rõ")
    coverage = _measure_number(profile, "included_coverage", "ratio")
    if coverage is not None:
        tradeoffs.append(f"Tỷ lệ hạng mục gồm/ gồm một phần: {coverage * 100:.0f}% trên phần đã biết")
    return tradeoffs


def _decision_trace(
    req: Requirement, tours: list[TourSnapshot], evaluations: list[Evaluation]
) -> DecisionTrace:
    hard = req.hard()
    offers = [(tour, offer) for tour in tours for offer in tour.offers]
    by_offer: dict[str, dict[str, Evaluation]] = {}
    for item in evaluations:
        by_offer.setdefault(item.offer_id, {})[item.condition_id] = item

    def state(offer_id: str, condition_id: str) -> State:
        item = by_offer.get(offer_id, {}).get(condition_id)
        return item.state if item else "unknown"

    eligible_ids = {
        offer.id for _tour, offer in offers
        if all(state(offer.id, condition.id) == "pass" for condition in hard)
    }
    eligible_tours = {
        tour.id for tour, offer in offers if offer.id in eligible_ids
    }
    condition_counts: list[DecisionConditionCount] = []
    for condition in hard:
        states_by_offer = {offer.id: state(offer.id, condition.id) for _, offer in offers}
        condition_counts.append(DecisionConditionCount(
            condition_id=condition.id,
            pass_offers=sum(value == "pass" for value in states_by_offer.values()),
            fail_offers=sum(value == "fail" for value in states_by_offer.values()),
            unknown_offers=sum(value == "unknown" for value in states_by_offer.values()),
            pass_tours=len({tour.id for tour, offer in offers if states_by_offer[offer.id] == "pass"}),
            fail_tours=len({tour.id for tour, offer in offers if states_by_offer[offer.id] == "fail"}),
            unknown_tours=len({tour.id for tour, offer in offers if states_by_offer[offer.id] == "unknown"}),
        ))

    surviving = {offer.id for _, offer in offers}
    funnel: list[DecisionFunnelStep] = []
    for index, condition in enumerate(hard, 1):
        before = set(surviving)
        surviving = {offer_id for offer_id in before if state(offer_id, condition.id) == "pass"}
        before_tours = {tour.id for tour, offer in offers if offer.id in before}
        after_tours = {tour.id for tour, offer in offers if offer.id in surviving}
        funnel.append(DecisionFunnelStep(
            condition_id=condition.id,
            stage=index,
            offers_before=len(before),
            offers_after=len(surviving),
            tours_before=len(before_tours),
            tours_after=len(after_tours),
        ))

    blockers: dict[tuple[str, str], list[str]] = {}
    for _tour, offer in offers:
        if offer.id in eligible_ids:
            continue
        for condition in hard:
            value = state(offer.id, condition.id)
            if value != "pass":
                blockers.setdefault((condition.id, value), []).append(offer.id)
                break
    offer_tour = {offer.id: tour.id for tour, offer in offers}
    first_blockers = [
        DecisionBlockerCount(
            condition_id=condition.id,
            state=value,
            offers=len(ids),
            tours=len({offer_tour[offer_id] for offer_id in ids}),
        )
        for condition in hard
        for value in ("fail", "unknown")
        for ids in [blockers.get((condition.id, value), [])]
        if ids
    ]
    return DecisionTrace(
        scanned_tours=len(tours),
        scanned_offers=len(offers),
        eligible_tours=len(eligible_tours),
        eligible_offers=len(eligible_ids),
        excluded_offers=len(offers) - len(eligible_ids),
        condition_counts=condition_counts,
        sequential_funnel=funnel,
        first_blockers=first_blockers,
        snapshot_available=True,
    )


def _option_metric_comparisons(
    candidate: MetricProfile, profiles: list[MetricProfile], tours: list[TourSnapshot]
) -> list[OptionMetricComparison]:
    tour_by_offer = {
        offer.id: (tour, offer) for tour in tours for offer in tour.offers
    }
    specs: list[tuple[str, str, str, float | None, float | None, str, list[MetricEvidence]]] = []
    cost = candidate.cost
    offer_pair = tour_by_offer.get(candidate.offer_id)
    cost_evidence: list[MetricEvidence] = []
    if offer_pair:
        tour, offer = offer_pair
        quote = next((str(item.get("quote", "")) for item in offer.price_quotes
                      if item.get("quote")), "")
        cost_evidence = [MetricEvidence(
            source_field="offers.price_by_age" if offer.price_by_age else "offers.price",
            quote=quote or f"{offer.price} {offer.currency} mỗi khách",
            observed_at=offer.evidence.observed_at or tour.observed_at,
            url=offer.evidence.url or tour.url,
        )] if offer.price is not None else []
    if cost.group_total_calculated is not None and cost.state == "observed" and not cost.total_is_lower_bound:
        comparable = [p.cost.group_total_calculated for p in profiles
                      if p.cost.currency.upper() == cost.currency.upper()
                      and p.cost.group_total_calculated is not None
                      and p.cost.state == "observed" and not p.cost.total_is_lower_bound]
        median = _median(comparable)
        specs.append(("group_total", "VND" if cost.currency.upper() == "VND" else cost.currency.upper(),
                      cost.currency.upper(), float(cost.group_total_calculated), median, "observed", cost_evidence))
    else:
        specs.append(("group_total", "VND" if cost.currency.upper() == "VND" else cost.currency.upper(),
                      cost.currency.upper(), float(cost.group_total_calculated)
                      if cost.group_total_calculated is not None else None, None,
                      cost.state, cost_evidence))

    directions = {
        "preference_fit": ("weighted preference points", True),
        "experience_density": ("distinct stated activities", True),
        "route_complexity": ("explicit legs", False),
        "included_coverage": ("known category ratio", True),
        "cancellation_flexibility": ("days before departure for full refund", True),
    }
    for key, (unit, _higher_is_better) in directions.items():
        metric = candidate.metrics.get(key)
        value = None
        evidence: list[MetricEvidence] = []
        if metric and metric.state != "unknown":
            if key == "preference_fit":
                value = metric.lower_bound * 100 if metric.lower_bound is not None else None
                evidence = metric.evidence
            elif key == "experience_density":
                raw = metric.value if isinstance(metric.value, dict) else {}
                value = raw.get("activity_count")
                evidence = metric.evidence
            elif key == "route_complexity":
                raw = metric.value if isinstance(metric.value, dict) else {}
                value = raw.get("explicit_legs")
                evidence = metric.evidence
            elif key == "included_coverage":
                raw = metric.value if isinstance(metric.value, dict) else {}
                value = raw.get("ratio")
                evidence = metric.evidence
            else:
                value = metric.value if isinstance(metric.value, (int, float)) else None
                evidence = metric.evidence
        candidate_state = metric.state if metric else "unknown"
        if key == "preference_fit" and metric and metric.lower_bound != metric.upper_bound:
            candidate_state = "partial"
        reference_values = []
        for profile in profiles:
            other = profile.metrics.get(key)
            if other is None or other.state != "observed":
                continue
            if key == "preference_fit":
                v = other.lower_bound * 100 if other.lower_bound is not None and other.lower_bound == other.upper_bound else None
            elif key in ("experience_density", "route_complexity", "included_coverage"):
                raw = other.value if isinstance(other.value, dict) else {}
                v = raw.get({"experience_density": "activity_count", "route_complexity": "explicit_legs", "included_coverage": "ratio"}[key])
            else:
                v = other.value if isinstance(other.value, (int, float)) else None
            if isinstance(v, (int, float)):
                reference_values.append(float(v))
        median = _median(reference_values)
        specs.append((key, unit, "", float(value) if isinstance(value, (int, float)) else None,
                      median, candidate_state, evidence))

    output: list[OptionMetricComparison] = []
    for key, unit, currency, value, median, candidate_state, evidence in specs:
        higher = directions.get(key, ("", False))[1] if key != "group_total" else False
        relation: str = "unknown"
        state = "unknown"
        state = candidate_state if candidate_state in ("partial", "observed") and value is not None else "unknown"
        if state == "observed" and value is not None and median is not None:
            relation = "similar" if abs(value - median) < 1e-9 else (
                "favorable" if (value > median) == higher else "tradeoff"
            )
        output.append(OptionMetricComparison(
            key=key, value=value, reference_median=median, unit=unit, currency=currency,
            scope="Hard-pass offer pool; median in matching currency/unit" if median is not None else "",
            state=state, relation=relation, higher_is_better=higher, evidence=evidence,
        ))
    return output


def _median(values: list[float | int | None]) -> float | None:
    ordered = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not ordered:
        return None
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _decision_options(
    views: list[DecisionView],
    profiles: list[MetricProfile],
    ranked: list[RankedCandidate],
    tours: list[TourSnapshot],
) -> list[DecisionOption]:
    profile_by_offer = {profile.offer_id: profile for profile in profiles}
    offer_by_id = {
        offer.id: offer for tour in tours for offer in tour.offers
    }
    views_by_kind = {view.kind: view for view in views}
    selected: list[DecisionOption] = []
    seen: set[str] = set()
    objective_order = (
        "cheapest", "best_fit", "experience_rich", "fewest_legs",
        "cancellation_flexible", "included_value", "balanced",
    )
    max_depth = max((len(views_by_kind[kind].candidates) for kind in objective_order if kind in views_by_kind), default=0)
    for depth in range(max_depth):
        for kind in objective_order:
            view = views_by_kind.get(kind)
            if view is None or depth >= len(view.candidates):
                continue
            candidate = view.candidates[depth]
            if candidate.tour_id in seen:
                continue
            profile = profile_by_offer.get(candidate.offer_id)
            if profile is None:
                continue
            if kind == "cheapest":
                offer = offer_by_id.get(candidate.offer_id)
                reason = (
                    f"Giá exact {offer.price:,} {offer.currency.upper()} thuộc nhóm thấp nhất "
                    "trong cùng tiền tệ; tổng nhóm và khoản loại trừ được trình bày riêng."
                    if offer and offer.price is not None and offer.currency
                    else view.note
                )
            elif kind == "best_fit":
                fit = profile.metrics.get("preference_fit")
                reason = (
                    f"Cận điểm khớp ưu tiên {fit.lower_bound * 100:.0f}–{(fit.upper_bound or 1) * 100:.0f}/100 "
                    "theo trọng số đã duyệt."
                    if fit and fit.lower_bound is not None else view.note
                )
            elif kind == "experience_rich":
                count = _measure_number(profile, "experience_density", "activity_count")
                reason = f"Lịch trình nêu rõ {int(count)} hoạt động/điểm ghé." if count is not None else view.note
            elif kind == "fewest_legs":
                count = _measure_number(profile, "route_complexity", "explicit_legs")
                reason = f"Có {int(count)} chặng được nguồn nêu rõ." if count is not None else view.note
            elif kind == "cancellation_flexible":
                days = _measure_number(profile, "cancellation_flexibility")
                reason = f"Điều khoản nêu hoàn 100% đến {int(days)} ngày trước khởi hành." if days is not None else view.note
            elif kind == "included_value":
                coverage = _measure_number(profile, "included_coverage", "ratio")
                reason = f"{coverage * 100:.0f}% hạng mục đã biết được gồm hoặc gồm một phần." if coverage is not None else view.note
            elif kind == "balanced":
                reason = "Nằm trên tập Pareto theo các metric có dữ kiện; không bị phương án khác vượt trội đồng thời."
            else:
                reason = view.note
            selected.append(DecisionOption(
                tour_id=candidate.tour_id,
                offer_id=candidate.offer_id,
                objective=kind,
                title={
                    "cheapest": "Giá thấp nhất trong nhóm so sánh",
                    "best_fit": "Khớp ưu tiên nhất",
                    "experience_rich": "Nhiều trải nghiệm được nêu rõ",
                    "fewest_legs": "Ít chặng được ghi rõ",
                    "cancellation_flexible": "Hủy linh hoạt nhất theo điều khoản",
                    "included_value": "Nhiều hạng mục bao gồm",
                    "balanced": "Phương án cân bằng",
                }.get(kind, "Phương án"),
                reason=reason,
                tradeoffs=_option_tradeoffs(profile),
                metric_comparisons=_option_metric_comparisons(profile, profiles, tours),
            ))
            seen.add(candidate.tour_id)
            if len(selected) >= 3:
                return selected
    # Keep three real choices visible when the scan has at least three hard-pass tours,
    # even if some metrics are unavailable; mark them as unranked candidates.
    for candidate in ranked:
        if candidate.tour_id in seen:
            continue
        profile = profile_by_offer.get(candidate.offer_id)
        if profile is None:
            continue
        selected.append(DecisionOption(
            tour_id=candidate.tour_id,
            offer_id=candidate.offer_id,
            objective="multi_objective",
            title="Phương án để cân nhắc",
            reason="Metric hiện có chưa đủ để xếp hạng riêng phương án này.",
            tradeoffs=_option_tradeoffs(profile),
            metric_comparisons=_option_metric_comparisons(profile, profiles, tours),
        ))
        seen.add(candidate.tour_id)
        if len(selected) >= 3:
            break
    return selected


def _group_value(field: str, tour: TourSnapshot, offer: OfferSnapshot) -> RankValue | None:
    if field == "price":
        if offer.price is None or offer.price_basis == "contact" or not offer.currency.strip():
            return None
        return (offer.currency.upper(), offer.price)
    return _candidate_value(field, tour, offer, 0)


def _candidate_value(
    field: str,
    tour: TourSnapshot,
    offer: OfferSnapshot,
    soft_fit: int,
) -> RankValue | None:
    if field == "price":
        return (
            offer.price
            if offer.price is not None and offer.price_basis != "contact" and offer.currency.strip()
            else None
        )
    if field == "departure_date":
        return offer.departure_date if _is_iso_date(offer.departure_date) else None
    if field == "duration_days":
        return tour.duration_days
    if field == "tour_name":
        return tour.name.casefold() or None
    if field == "soft_fit":
        return soft_fit
    return None


def _compare_candidates(
    left: tuple[TourSnapshot, str],
    right: tuple[TourSnapshot, str],
    order: list[RankingKey],
    soft_fit_by_offer: dict[str, float],
    offers_by_id: dict[str, OfferSnapshot],
) -> int:
    left_tour, left_id = left
    right_tour, right_id = right
    left_offer = offers_by_id[left_id]
    right_offer = offers_by_id[right_id]
    for item in order:
        left_fit = soft_fit_by_offer.get(left_id, 0) if item.field == "soft_fit" else 0
        right_fit = soft_fit_by_offer.get(right_id, 0) if item.field == "soft_fit" else 0
        left_value = _candidate_value(item.field, left_tour, left_offer, left_fit)
        right_value = _candidate_value(item.field, right_tour, right_offer, right_fit)
        if left_value is None and right_value is not None:
            return 1
        if right_value is None and left_value is not None:
            return -1
        if left_value is None or right_value is None:
            continue
        if item.field == "price" and left_offer.currency.upper() != right_offer.currency.upper():
            compared = _compare_values(left_offer.currency.upper(), right_offer.currency.upper())
        else:
            compared = _compare_values(left_value, right_value)
        if compared:
            return compared if item.field == "price" and left_offer.currency.upper() != right_offer.currency.upper() else (
                compared if item.direction == "asc" else -compared
            )
    left_key = (left_tour.id, left_id)
    right_key = (right_tour.id, right_id)
    return 0 if left_key == right_key else (-1 if left_key < right_key else 1)


def _compare_values(left: RankValue, right: RankValue) -> int:
    if (isinstance(left, (int, float)) and not isinstance(left, bool)
            and isinstance(right, (int, float)) and not isinstance(right, bool)):
        return 0 if left == right else (-1 if left < right else 1)
    if isinstance(left, str) and isinstance(right, str):
        return 0 if left == right else (-1 if left < right else 1)
    if isinstance(left, tuple) and isinstance(right, tuple):
        return _compare_values(left[0], right[0]) or _compare_values(left[1], right[1])
    raise TypeError("Ranking values for the same field must have the same type.")


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def analyze(tours: list[TourSnapshot], ranked: list[RankedCandidate], cfg: DecideCfg) -> Analysis:
    by_id = {t.id: t for t in tours}
    costs, conds, risks, benefits = [], [], [], []
    for cand in ranked[: cfg.top_n]:
        tour = by_id[cand.tour_id]
        for label, text in (
            ("Phụ thu", tour.surcharges),
            ("Loại trừ", tour.exclusions),
            ("Hủy", tour.cancellation_policy),
            ("Trẻ em", tour.child_policy),
        ):
            if text.strip():
                conds.append(f"{tour.name} — {label}: {text[: cfg.analysis_chars]}")
        if tour.surcharges.strip():
            costs.append(f"{tour.name}: {tour.surcharges[: cfg.analysis_chars]}")
        if tour.exclusions.strip():
            risks.append(f"{tour.name} chưa gồm: {tour.exclusions[: cfg.analysis_chars]}")
        avail = "/".join(o.availability for o in tour.offers)
        if any(w in (tour.cancellation_policy + avail).lower() for w in cfg.risk_words):
            risks.append(f"{tour.name}: chính sách hủy/khan hiếm cần đọc kỹ.")
        if tour.inclusions.strip():
            benefits.append(f"{tour.name}: {tour.inclusions[: cfg.analysis_chars]}")

    def dedup(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))[: cfg.analysis_items]

    return Analysis(
        hidden_costs=dedup(costs), conditions=dedup(conds), risks=dedup(risks), benefits=dedup(benefits)
    )


def compare(
    req: Requirement,
    tours: list[TourSnapshot],
    cfg: DecideCfg,
    soft_verdicts: dict[tuple[str, str], tuple[State, str, str]] | None = None,
    metric_facts: dict[str, ExtractedTourFacts] | None = None,
) -> Comparison:
    evals = hard_filter(req, tours)
    surviving = passing_offers(req, tours, evals)
    verdicts = soft_verdicts or {}
    pass_ids = {offer_id for _, offer_id in surviving}
    evaluations = list(evals)
    for offer_id in pass_ids:
        for condition in req.soft():
            state, quote, reason = verdicts.get((offer_id, condition.id), ("unknown", "", ""))
            evaluations.append(Evaluation(
                offer_id=offer_id,
                condition_id=condition.id,
                state=state,
                quote=quote,
                reason=reason,
                reason_code=f"SOFT_{state.upper()}",
            ))
    ranked = rank(req, surviving, verdicts)
    near = near_miss(req, tours, evaluations, {c.offer_id for c in ranked}, cfg.near_miss_max_fails)
    near = near[: cfg.top_n]
    profiles = build_metric_profiles(req, surviving, verdicts, metric_facts)
    views = _objective_views(profiles, _decision_views(req, surviving, verdicts, profiles))
    options = _decision_options(views, profiles, ranked, tours)
    return Comparison(
        id=uid("cmp"),
        requirement=req,
        ranked=ranked,
        near_miss=near,
        tour_snapshots=tours,
        evaluations=evaluations,
        analysis=analyze(tours, ranked + near, cfg),
        candidates_considered=len(tours),
        decision_trace=_decision_trace(req, tours, evals),
        ranking_currencies=sorted({
            offer.currency.upper()
            for tour, offer_id in surviving
            for offer in tour.offers
            if offer.id == offer_id and offer.price is not None
            and offer.price_basis != "contact" and offer.currency.strip()
        }),
        decision_views=views,
        metric_profiles=profiles,
        decision_options=options,
        extracted_facts=list((metric_facts or {}).values()),
    )
