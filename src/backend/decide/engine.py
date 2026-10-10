"""Hard filter → soft LLM assess → rank → analyze. Unknown never passes."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from datetime import date

from backend.errors import AppError
from backend.input.nim import NimClient
from backend.models import (
    Analysis,
    Comparison,
    Condition,
    Evaluation,
    OfferSnapshot,
    RankedCandidate,
    Requirement,
    State,
    TourSnapshot,
    uid,
)
from backend.settings import DecideCfg, PromptCfg


def _contains(haystack: str, needle: str) -> bool:
    return _fold(needle) in _fold(haystack)


def _fold(value: str) -> str:
    text = value.replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text.lower())


_COUNTRY_ALIASES = {
    "vn": {"vietnam", "trongnuoc"},
    "cn": {"china", "trungquoc"},
    "tw": {"taiwan", "dailoan"},
    "bn": {"brunei", "bruneidarussalam"},
    "jp": {"japan", "nhatban"},
    "kr": {"korea", "southkorea", "hanquoc"},
    "th": {"thailand", "thailan"},
    "sg": {"singapore"},
    "my": {"malaysia"},
    "id": {"indonesia"},
    "ph": {"philippines"},
    "la": {"laos"},
    "kh": {"cambodia", "campuchia"},
}


def _destination_state(value: str, tour: TourSnapshot) -> State:
    key = _fold(value)
    country = next((code for code, aliases in _COUNTRY_ALIASES.items() if key in aliases), None)
    if country:
        if country in tour.destination_countries:
            return "pass"
        return "fail" if tour.destination_country_complete else "unknown"
    if any(_contains(place, value) for place in tour.destinations):
        return "pass"
    return "fail" if tour.destination_country_complete else "unknown"


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
        return ("pass", "") if "pass" in states else (("unknown", "DESTINATION_PARTIAL") if "unknown" in states else ("fail", "DESTINATION_MISMATCH"))
    if f == "departure_city":
        vals = v if any_op else [v]
        return ("pass", "") if any(_contains(tour.departure_city, str(x)) for x in vals) else ("fail", "DEPARTURE_CITY_MISMATCH")
    if f == "transport":
        if str(v) not in ("flight", "bus", "train", "cruise", "mixed"):
            return "unknown", "UNSUPPORTED_TRANSPORT"
        return (("pass", "") if tour.transport == str(v) else (("unknown", "FIELD_MISSING") if not tour.transport else ("fail", "TRANSPORT_MISMATCH")))
    if f == "accommodation":
        return (("pass", "") if _contains(tour.accommodation, str(v)) else (("unknown", "FIELD_MISSING") if not tour.accommodation else ("fail", "ACCOMMODATION_MISMATCH")))
    if f == "duration_days":
        return (("unknown", "FIELD_MISSING") if tour.duration_days is None else (("pass", "") if tour.duration_days == v else ("fail", "DURATION_MISMATCH")))
    if f in ("date_from", "date_to"):
        if offer.departure_freshness != "fresh":
            return "unknown", _unknown_reason(offer.departure_freshness, offer.departure_freshness_policy_seconds)
        if not offer.departure_date:
            return "unknown", "FIELD_MISSING"
        try:
            day = date.fromisoformat(offer.departure_date)
            bound = date.fromisoformat(str(v))
        except ValueError:
            return "unknown", "FIELD_INVALID"
        ok = day >= bound if f == "date_from" else day <= bound
        return (("pass", "") if ok else ("fail", "DATE_MISMATCH"))
    if f == "budget_max":
        if offer.price_freshness != "fresh":
            return "unknown", _unknown_reason(offer.price_freshness, offer.price_freshness_policy_seconds)
        if not offer.price_trusted:
            return "unknown", "PRICE_UNVERIFIED"
        if offer.price is None or isinstance(v, list):
            return "unknown", "PRICE_MISSING"
        amount = v
        currency = "VND"
        basis = "per_adult"
        coverage = "tour_price"
        if isinstance(v, dict):
            amount = v.get("amount", v.get("upper"))
            currency = str(v.get("currency") or "")
            basis = str(v.get("basis") or "")
            coverage = str(v.get("coverage") or "")
        if currency and currency.upper() != offer.currency.upper():
            return "unknown", "PRICE_CURRENCY_MISMATCH"
        if basis not in ("", "per_adult") or coverage not in ("", "tour_price"):
            return "unknown", "PRICE_BASIS_MISMATCH"
        try:
            maximum = int(amount)
        except (TypeError, ValueError):
            return "unknown", "PRICE_BUDGET_INVALID"
        if offer.price_basis == "from":
            return (("fail", "PRICE_LOWER_BOUND_OVER_BUDGET") if offer.price > maximum else ("unknown", "PRICE_FROM_LOWER_BOUND"))
        if offer.price_basis != "exact":
            return "unknown", "PRICE_NOT_EXACT"
        return (("pass", "") if offer.price <= maximum else ("fail", "PRICE_OVER_BUDGET"))
    return "unknown", "FIELD_UNSUPPORTED"


def hard_filter(req: Requirement, tours: list[TourSnapshot]) -> list[Evaluation]:
    hard = req.hard()
    evals: list[Evaluation] = []
    for tour in tours:
        for offer in tour.offers:
            for cond in hard:
                state, reason = eval_hard(cond, tour, offer)
                evals.append(Evaluation(offer_id=offer.id, condition_id=cond.id,
                                        state=state, reason_code=reason))
    return evals


def passing_offers(req: Requirement, tours: list[TourSnapshot],
                   evals: list[Evaluation]) -> list[tuple[TourSnapshot, str]]:
    hard_ids = {c.id for c in req.hard()}
    bad: set[str] = set()
    for e in evals:
        if e.condition_id in hard_ids and e.state == "fail":
            bad.add(e.offer_id)
    out = []
    for tour in tours:
        for offer in tour.offers:
            if offer.id not in bad:
                out.append((tour, offer.id))
    return out


def assess_soft_llm(tours: list[TourSnapshot], soft: list[Condition],
                    nim: NimClient | None,
                    prompt: PromptCfg | None,
                    excerpt_chars: int, quote_chars: int,
                    soft_fields: list[str]) -> dict[tuple[str, str], tuple[float, str]]:
    """One bounded LLM call over survivors. Returns {(tour_id, cond_id): (score, quote)}."""
    if not soft or nim is None or not nim.configured():
        return {}
    if prompt is None or not prompt.system.strip():
        raise AppError("PROMPT_NOT_CONFIGURED", "Thiếu prompt assess.", 500)
    docs = []
    for tour in tours:
        blob = "\n".join(f"{f}: {getattr(tour, f, '')}" for f in soft_fields)[:excerpt_chars]
        docs.append({"tour_id": tour.id, "text": blob})
    user = json.dumps({"criteria": [{"id": c.id, "text": str(c.value)} for c in soft],
                       "tours": docs}, ensure_ascii=False)
    scores = nim.complete_json(system=prompt.system, user=user,
                               max_tokens=prompt.max_tokens,
                               temperature=prompt.temperature).get("scores", [])
    out: dict[tuple[str, str], tuple[float, str]] = {}
    for s in scores:
        try:
            out[(str(s["tour_id"]), str(s["condition_id"]))] = (
                max(0.0, min(1.0, float(s["score"]))), str(s.get("quote", ""))[:quote_chars])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def rank(req: Requirement, surviving: list[tuple[TourSnapshot, str]],
         soft_scores: dict[tuple[str, str], tuple[float, str]]) -> list[RankedCandidate]:
    soft_ids = [c.id for c in req.soft()]
    scored = []
    for tour, offer_id in surviving:
        offer = next(o for o in tour.offers if o.id == offer_id)
        soft_avg = 0.0
        if soft_ids:
            vals = [soft_scores.get((tour.id, cid), (0.0, ""))[0] for cid in soft_ids]
            soft_avg = sum(vals) / len(vals)
        price_key = offer.price if (offer.price is not None and offer.price_basis == "exact") else 10**15
        scored.append((soft_avg, -price_key, tour.id, offer_id))
    scored.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [RankedCandidate(tour_id=t, offer_id=o, score=s) for s, _, t, o in scored]


def analyze(tours: list[TourSnapshot], ranked: list[RankedCandidate],
            cfg: DecideCfg) -> Analysis:
    by_id = {t.id: t for t in tours}
    costs, conds, risks, benefits = [], [], [], []
    for cand in ranked[:cfg.top_n]:
        tour = by_id[cand.tour_id]
        for label, text in (("Phụ thu", tour.surcharges), ("Loại trừ", tour.exclusions),
                            ("Hủy", tour.cancellation_policy), ("Trẻ em", tour.child_policy)):
            if text.strip():
                conds.append(f"{tour.name} — {label}: {text[:cfg.analysis_chars]}")
        if tour.surcharges.strip():
            costs.append(f"{tour.name}: {tour.surcharges[:cfg.analysis_chars]}")
        if tour.exclusions.strip():
            risks.append(f"{tour.name} chưa gồm: {tour.exclusions[:cfg.analysis_chars]}")
        avail = "/".join(o.availability for o in tour.offers)
        if any(w in (tour.cancellation_policy + avail).lower() for w in cfg.risk_words):
            risks.append(f"{tour.name}: chính sách hủy/khan hiếm cần đọc kỹ.")
        if tour.inclusions.strip():
            benefits.append(f"{tour.name}: {tour.inclusions[:cfg.analysis_chars]}")
    def dedup(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))[:cfg.analysis_items]

    return Analysis(hidden_costs=dedup(costs),
                    conditions=dedup(conds), risks=dedup(risks), benefits=dedup(benefits))


AssessFn = Callable[[list[TourSnapshot], list[Condition]], dict[tuple[str, str], tuple[float, str]]]


def compare(req: Requirement, tours: list[TourSnapshot],
            assess: AssessFn | None, cfg: DecideCfg) -> Comparison:
    evals = hard_filter(req, tours)
    surviving = passing_offers(req, tours, evals)
    seen: set[str] = set()
    survivor_tours = [t for t, _ in surviving if not (t.id in seen or seen.add(t.id))]
    soft_scores = assess(survivor_tours, req.soft()) if assess and req.soft() else {}
    evaluations = list(evals)
    for (tour_id, cid), (_, quote) in soft_scores.items():
        offer_ids = [o.id for t in tours if t.id == tour_id for o in t.offers]
        for oid in offer_ids:
            evaluations.append(Evaluation(offer_id=oid, condition_id=cid,
                                          state="pass", quote=quote))
    ranked = rank(req, surviving, soft_scores)
    return Comparison(id=uid("cmp"), requirement=req, ranked=ranked,
                      evaluations=evaluations,
                      analysis=analyze(tours, ranked, cfg),
                      candidates_considered=len(tours))
