"""Hard filter → soft LLM assess → rank → analyze. Unknown never passes."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import cmp_to_key

from backend.models import (
    Analysis,
    Comparison,
    Condition,
    DecisionView,
    Evaluation,
    OfferSnapshot,
    RankedCandidate,
    RankingKey,
    Requirement,
    State,
    TourSnapshot,
    uid,
)
from backend.settings import DecideCfg

RankValue = int | str | tuple[str, int]


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


def _unknown_reason(freshness: str, policy_seconds: int | None) -> str:
    if policy_seconds is None or policy_seconds <= 0:
        return "FIELD_FRESHNESS_POLICY_MISSING"
    if freshness == "stale":
        return "FIELD_STALE"
    return "FIELD_FRESHNESS_UNKNOWN"


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
        if offer.departure_freshness != "fresh":
            return "unknown", _unknown_reason(
                offer.departure_freshness, offer.departure_freshness_policy_seconds
            )
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
) -> int:
    return sum(
        (condition.weight_percent if condition.weight_percent is not None else 1)
        for condition in req.soft()
        if soft_verdicts.get((offer_id, condition.id), ("unknown", "", ""))[0] == "pass"
    )


def _decision_views(
    req: Requirement,
    surviving: list[tuple[TourSnapshot, str]],
    verdicts: dict[tuple[str, str], tuple[State, str, str]],
) -> list[DecisionView]:
    fit_by_offer = {
        offer_id: _soft_fit_count(req, offer_id, verdicts)
        for _, offer_id in surviving
    }
    exact = [
        (tour, offer)
        for tour, offer_id in surviving
        for offer in tour.offers
        if offer.id == offer_id and offer.price is not None
        and offer.price_basis == "exact" and offer.currency.strip()
    ]

    cheapest_rows: list[tuple[TourSnapshot, OfferSnapshot]] = []
    cheapest_by_currency: dict[str, list[tuple[TourSnapshot, OfferSnapshot]]] = {}
    for tour, offer in exact:
        cheapest_by_currency.setdefault(offer.currency.upper(), []).append((tour, offer))
    for currency in sorted(cheapest_by_currency):
        cheapest_by_currency[currency].sort(
            key=lambda pair: (
                pair[1].price,
                -fit_by_offer[pair[1].id],
                pair[0].id,
                pair[1].id,
            ),
        )
        cheapest_rows.extend(cheapest_by_currency[currency])
    cheapest: list[tuple[TourSnapshot, OfferSnapshot]] = []
    seen_tours: set[str] = set()

    def add_unique(rows: list[tuple[TourSnapshot, OfferSnapshot]], limit: int = 5) -> None:
        for pair in rows:
            if pair[0].id in seen_tours:
                continue
            cheapest.append(pair)
            seen_tours.add(pair[0].id)
            if len(cheapest) == limit:
                return

    # Show a lowest-price representative for each currency before adding more
    # options from any one currency, so the preview does not imply a global order.
    add_unique([rows[0] for _, rows in sorted(cheapest_by_currency.items()) if rows])
    add_unique(cheapest_rows)
    cheapest_currencies = sorted({offer.currency.upper() for _, offer in cheapest})

    best_offer_by_tour: dict[str, tuple[TourSnapshot, OfferSnapshot]] = {}
    for tour, offer_id in surviving:
        offer = next(item for item in tour.offers if item.id == offer_id)
        prior = best_offer_by_tour.get(tour.id)
        if prior is None or offer.id < prior[1].id:
            best_offer_by_tour[tour.id] = (tour, offer)
    best_fit_rows = sorted(
        best_offer_by_tour.values(),
        key=lambda pair: (-fit_by_offer[pair[1].id], pair[0].id, pair[1].id),
    )[:5]
    best_fit_currencies = sorted({
        offer.currency.upper() for _, offer in best_fit_rows if offer.currency.strip()
    })

    per_currency_tour: dict[tuple[str, str], tuple[TourSnapshot, OfferSnapshot]] = {}
    for tour, offer in exact:
        key = (offer.currency.upper(), tour.id)
        previous = per_currency_tour.get(key)
        if previous is None or (offer.price, offer.id) < (previous[1].price, previous[1].id):
            per_currency_tour[key] = (tour, offer)
    frontier: list[tuple[TourSnapshot, OfferSnapshot]] = []
    for currency in sorted({key[0] for key in per_currency_tour}):
        rows = [pair for key, pair in per_currency_tour.items() if key[0] == currency]
        for tour, offer in rows:
            score = fit_by_offer[offer.id]
            dominated = any(
                other_offer.price <= offer.price
                and fit_by_offer[other_offer.id] >= score
                and (other_offer.price < offer.price or fit_by_offer[other_offer.id] > score)
                for other_tour, other_offer in rows
                if other_tour.id != tour.id
            )
            if not dominated:
                frontier.append((tour, offer))
    frontier.sort(key=lambda pair: (
        pair[1].currency.upper(), -fit_by_offer[pair[1].id], pair[1].price, pair[0].id
    ))
    balanced: list[tuple[TourSnapshot, OfferSnapshot]] = []
    seen_balanced: set[str] = set()

    def add_balanced(rows: list[tuple[TourSnapshot, OfferSnapshot]]) -> None:
        for pair in rows:
            if pair[0].id in seen_balanced:
                continue
            balanced.append(pair)
            seen_balanced.add(pair[0].id)
            if len(balanced) == 5:
                return

    first_by_currency: dict[str, tuple[TourSnapshot, OfferSnapshot]] = {}
    for pair in frontier:
        first_by_currency.setdefault(pair[1].currency.upper(), pair)
    add_balanced([first_by_currency[key] for key in sorted(first_by_currency)])
    add_balanced(frontier)
    balanced_currencies = sorted({offer.currency.upper() for _, offer in balanced})

    def candidates(rows: list[tuple[TourSnapshot, OfferSnapshot]]) -> list[RankedCandidate]:
        return [RankedCandidate(
            tour_id=tour.id,
            offer_id=offer.id,
            score=float(fit_by_offer[offer.id]),
        ) for tour, offer in rows]

    soft = req.soft()
    weights_valid = not soft or (
        all(condition.weight_percent is not None for condition in soft)
        and sum(condition.weight_percent or 0 for condition in soft) == 100
    )
    if not weights_valid:
        return []
    best_fit_note = (
        "Chưa có sở thích mềm; chưa thể xếp mức độ phù hợp."
        if not soft else "Điểm là tổng trọng số của các sở thích được đánh giá là phù hợp."
    )
    return [
        DecisionView(
            kind="cheapest",
            candidates=candidates(cheapest),
            currencies=cheapest_currencies,
            note="Chỉ so sánh giá exact trong cùng đơn vị tiền tệ.",
        ),
        DecisionView(
            kind="best_fit",
            candidates=candidates(best_fit_rows) if soft else [],
            currencies=best_fit_currencies,
            note=best_fit_note,
        ),
        DecisionView(
            kind="balanced",
            candidates=candidates(balanced),
            currencies=balanced_currencies,
            note="Pareto giữa giá exact và điểm ưu tiên; giá chỉ so trong cùng đơn vị tiền tệ.",
        ),
    ]


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
    soft_fit_by_offer: dict[str, int],
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
    if isinstance(left, int) and isinstance(right, int):
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
    return Comparison(
        id=uid("cmp"),
        requirement=req,
        ranked=ranked,
        near_miss=near,
        tour_snapshots=tours,
        evaluations=evaluations,
        analysis=analyze(tours, ranked + near, cfg),
        candidates_considered=len(tours),
        ranking_currencies=sorted({
            offer.currency.upper()
            for tour, offer_id in surviving
            for offer in tour.offers
            if offer.id == offer_id and offer.price is not None
            and offer.price_basis != "contact" and offer.currency.strip()
        }),
        decision_views=_decision_views(req, surviving, verdicts),
    )
