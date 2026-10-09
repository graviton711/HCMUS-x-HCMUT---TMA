"""Hard filter → soft LLM assess → rank → analyze. Unknown never passes."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import httpx

from backend.errors import AppError
from backend.models import (
    Analysis,
    Comparison,
    Condition,
    Evaluation,
    RankedCandidate,
    Requirement,
    State,
    TourSnapshot,
    uid,
)

_SOFT_TEXT_FIELDS = ("itinerary", "inclusions", "exclusions", "child_policy",
                     "cancellation_policy")


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def eval_hard(condition: Condition, tour: TourSnapshot, offer_price: int | None,
              offer_basis: str, offer_date: str) -> State:
    """Per-offer hard evaluation. Anything unprovable is `unknown`."""
    f, v = condition.field, condition.value
    if f == "destination":
        return "pass" if any(_contains(d, str(v)) for d in tour.destinations) else "fail"
    if f == "departure_city":
        return "pass" if _contains(tour.departure_city, str(v)) else "fail"
    if f == "transport":
        return "pass" if tour.transport == str(v) else ("unknown" if not tour.transport else "fail")
    if f == "accommodation":
        return "pass" if _contains(tour.accommodation, str(v)) else ("unknown" if not tour.accommodation else "fail")
    if f == "duration_days":
        return "unknown" if tour.duration_days is None else ("pass" if tour.duration_days == v else "fail")
    if f in ("date_from", "date_to"):
        if not offer_date:
            return "unknown"
        try:
            day = date.fromisoformat(offer_date)
            bound = date.fromisoformat(str(v))
        except ValueError:
            return "unknown"
        ok = day >= bound if f == "date_from" else day <= bound
        return "pass" if ok else "fail"
    if f == "budget_max":
        if offer_price is None or offer_basis != "exact":
            return "unknown"
        try:
            return "pass" if offer_price <= int(v) else "fail"
        except (TypeError, ValueError):
            return "unknown"
    return "unknown"


def hard_filter(req: Requirement, tours: list[TourSnapshot]) -> list[Evaluation]:
    hard = req.hard()
    evals: list[Evaluation] = []
    for tour in tours:
        for offer in tour.offers:
            for cond in hard:
                state = eval_hard(cond, tour, offer.price, offer.price_basis, offer.departure_date)
                evals.append(Evaluation(offer_id=offer.id, condition_id=cond.id, state=state))
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
                    api_key: str, model: str, timeout: float,
                    transport: httpx.BaseTransport | None = None) -> dict[tuple[str, str], tuple[float, str]]:
    """One bounded LLM call over survivors. Returns {(tour_id, cond_id): (score, quote)}."""
    if not soft or not api_key:
        return {}
    docs = []
    for tour in tours:
        blob = "\n".join(f"{f}: {getattr(tour, f, '')}" for f in _SOFT_TEXT_FIELDS)[:6000]
        docs.append({"tour_id": tour.id, "text": blob})
    body = {
        "model": model,
        "stream": False,
        "temperature": 0,
        "max_tokens": 2048,
        "messages": [
            {"role": "system",
             "content": "Chấm từng tour theo từng tiêu chí mềm. Trả JSON {scores: [{tour_id, condition_id, score 0..1, quote}]}."
                        " quote là trích nguyên văn ngắn từ văn bản tour. Không suy đoán ngoài văn bản."},
            {"role": "user",
             "content": json.dumps({"criteria": [{"id": c.id, "text": str(c.value)} for c in soft],
                                    "tours": docs}, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions", json=body,
                headers={"Authorization": f"Bearer {api_key}"})
        if response.status_code != 200:
            raise AppError("LLM_UPSTREAM_ERROR", "NIM không đánh giá được tiêu chí mềm.",
                           502, retryable=True)
        items = response.json()["choices"][0]["message"]["content"]
        scores = json.loads(items).get("scores", [])
    except AppError:
        raise
    except Exception as exc:
        raise AppError("LLM_INVALID_OUTPUT", "NIM trả sai định dạng.", 502) from exc
    out: dict[tuple[str, str], tuple[float, str]] = {}
    for s in scores:
        try:
            out[(str(s["tour_id"]), str(s["condition_id"]))] = (
                max(0.0, min(1.0, float(s["score"]))), str(s.get("quote", ""))[:300])
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


_RISK_WORDS = ("không hoàn", "thu phí 100%", "sold_out", "unknown")


def analyze(tours: list[TourSnapshot], ranked: list[RankedCandidate]) -> Analysis:
    by_id = {t.id: t for t in tours}
    costs, conds, risks, benefits = [], [], [], []
    for cand in ranked[:3]:
        tour = by_id[cand.tour_id]
        for label, text in (("Phụ thu", tour.surcharges), ("Loại trừ", tour.exclusions),
                            ("Hủy", tour.cancellation_policy), ("Trẻ em", tour.child_policy)):
            if text.strip():
                conds.append(f"{tour.name} — {label}: {text[:160]}")
        if tour.surcharges.strip():
            costs.append(f"{tour.name}: {tour.surcharges[:160]}")
        if tour.exclusions.strip():
            risks.append(f"{tour.name} chưa gồm: {tour.exclusions[:160]}")
        avail = "/".join(o.availability for o in tour.offers)
        if any(w in (tour.cancellation_policy + avail).lower() for w in _RISK_WORDS):
            risks.append(f"{tour.name}: chính sách hủy/khan hiếm cần đọc kỹ.")
        if tour.inclusions.strip():
            benefits.append(f"{tour.name}: {tour.inclusions[:160]}")
    def dedup(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))[:6]

    return Analysis(hidden_costs=dedup(costs),
                    conditions=dedup(conds), risks=dedup(risks), benefits=dedup(benefits))


AssessFn = Callable[[list[TourSnapshot], list[Condition]], dict[tuple[str, str], tuple[float, str]]]


def compare(req: Requirement, tours: list[TourSnapshot],
            assess: AssessFn | None = None) -> Comparison:
    evals = hard_filter(req, tours)
    surviving = passing_offers(req, tours, evals)
    soft_scores = assess(tours, req.soft()) if assess and req.soft() else {}
    evaluations = list(evals)
    for (tour_id, cid), (_, quote) in soft_scores.items():
        offer_ids = [o.id for t in tours if t.id == tour_id for o in t.offers]
        for oid in offer_ids:
            evaluations.append(Evaluation(offer_id=oid, condition_id=cid,
                                          state="pass", quote=quote))
    ranked = rank(req, surviving, soft_scores)
    return Comparison(id=uid("cmp"), requirement=req, ranked=ranked,
                      evaluations=evaluations,
                      analysis=analyze(tours, ranked),
                      candidates_considered=len(tours))
