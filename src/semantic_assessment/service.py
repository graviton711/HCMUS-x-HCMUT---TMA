import asyncio
import hashlib
import json

from domain.common import AppError, instant, now
from semantic_assessment.gateway import NimSemanticGateway
from semantic_assessment.models import POLICY, Assessment, AssessmentBatch, SemanticReport

SEMANTIC_FIELDS = {"nature", "included_services", "unsupported"}


def fingerprint(r, candidates):
    data = [POLICY, r.model_dump(mode="json"), sorted((c["id"], c["tour"].snapshot_id) for c in candidates)]
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepare(r, candidates, crawl, settings):
    evidence = {e.id: e for e in crawl.evidence}
    pairs, excerpts = [], {}
    eligible = [c for c in candidates if c["hard_status"] in {"pass", None}]
    limited = len(eligible) > settings.semantic_max_candidates
    budget = settings.semantic_max_input_chars
    for candidate in eligible[: settings.semantic_max_candidates]:
        conditions = [
            c
            for c in r.conditions
            if c.strength == "soft"
            and c.field in SEMANTIC_FIELDS
            and next(e for e in candidate["evaluations"] if e["condition_id"] == c.id)["status"] == "unknown"
        ]
        if not conditions:
            continue
        remaining_pairs = settings.semantic_max_pairs - len(pairs)
        if len(conditions) > remaining_pairs:
            limited = True
        conditions = conditions[:remaining_pairs]
        if not conditions:
            break
        tour = candidate["tour"]
        facts = {
            "itinerary": tour.catalog_fields.get("itinerary"),
            **{f"policies.{k}": v for k, v in tour.policies.items() if k in {"inclusions", "exclusions"}},
        }
        candidate_excerpts = []
        for field, fact in facts.items():
            if (
                not fact
                or fact.data_state != "present"
                or not isinstance(fact.value, str)
                or not fact.value.strip()
            ):
                continue
            bound = [
                e for e in fact.evidence_ids if e in evidence and evidence[e].snapshot_id == tour.snapshot_id
            ]
            if not bound:
                continue
            # Read the whole value within per-field/global limits; never advertise truncated input as complete.
            size = min(len(fact.value), settings.semantic_excerpt_chars, budget)
            if size <= 0:
                limited = True
                continue
            text = fact.value[:size]
            budget -= size
            truncated = size < len(fact.value)
            limited = limited or truncated
            eid = "excerpt_" + hashlib.sha256(json.dumps([candidate["id"], field]).encode()).hexdigest()[:24]
            excerpts[eid] = dict(
                id=eid,
                candidate_id=candidate["id"],
                tour_snapshot_id=tour.snapshot_id,
                field=field,
                text=text,
                evidence_ids=bound,
                verification=fact.verification,
                complete=fact.completeness == "complete" and not truncated,
            )
            excerpts[eid]["source_quotes"] = [evidence[e].raw_quote for e in bound]
            candidate_excerpts.append(eid)
        if candidate_excerpts:
            for condition in conditions:
                pairs.append(
                    dict(
                        candidate_id=candidate["id"],
                        condition_id=condition.id,
                        field=condition.field,
                        value=condition.value.model_dump(mode="json"),
                        requirement_quotes=[s.quote for s in condition.sources if s.kind == "text"],
                        excerpt_ids=candidate_excerpts,
                    )
                )

    def public_payload():
        used = {eid for pair in pairs for eid in pair["excerpt_ids"]}
        return {
            "pairs": pairs,
            "excerpts": [
                {k: v for k, v in e.items() if k != "source_quotes"}
                for eid, e in excerpts.items()
                if eid in used
            ],
        }

    payload = public_payload()
    while len(json.dumps(payload, ensure_ascii=False)) > settings.semantic_max_input_chars:
        limited = True
        longest = max(payload["excerpts"], key=lambda e: len(e["text"]), default=None)
        if longest and len(longest["text"]) > 128:
            original = excerpts[longest["id"]]
            original["text"] = original["text"][: max(128, len(original["text"]) // 2)]
            original["complete"] = False
        else:
            pairs.pop()
        payload = public_payload()
    used = {e["id"] for e in payload["excerpts"]}
    return payload, {eid: e for eid, e in excerpts.items() if eid in used}, limited


def validate(batch, payload, excerpts):
    expected = {(p["candidate_id"], p["condition_id"]): p for p in payload["pairs"]}
    items = batch.items
    keys = [(a.candidate_id, a.condition_id) for a in items]
    if len(set(keys)) != len(keys) or set(keys) != expected.keys():
        raise ValueError("Assessment must cover each requested pair exactly once")
    result = []
    for item in items:
        pair = expected[item.candidate_id, item.condition_id]
        refs = []
        for citation in item.citations:
            excerpt = excerpts.get(citation.excerpt_id)
            if (
                excerpt is None
                or citation.excerpt_id not in pair["excerpt_ids"]
                or citation.quote not in excerpt["text"]
            ):
                raise ValueError("Citation does not match the candidate snapshot")
            if item.status == "not_matched" and not excerpt["complete"]:
                raise ValueError("Incomplete excerpt cannot establish negative assessment")
            refs.append(excerpt)
        usable = (
            item.status != "unknown"
            and bool(refs)
            and all(e["verification"] != "unverified" for e in refs)
            and all(
                any(c.quote in quote for quote in excerpts[c.excerpt_id]["source_quotes"])
                for c in item.citations
            )
        )
        snapshot = excerpts[pair["excerpt_ids"][0]]["tour_snapshot_id"]
        result.append(
            Assessment(
                **item.model_dump(),
                tour_snapshot_id=snapshot,
                evidence_ids=sorted({eid for e in refs for eid in e["evidence_ids"]}),
                usable_for_ranking=usable,
                reason_code="TEXT_SUPPORT"
                if usable and item.status == "matched"
                else "TEXT_CONTRADICTION"
                if usable
                else "MODEL_INTERPRETATION_UNVERIFIED"
                if item.status != "unknown"
                else "INSUFFICIENT_EVIDENCE",
            )
        )
    return result


class SemanticAssessor:
    def __init__(self, settings, gateway=None):
        self.settings = settings
        self.injected = gateway is not None
        self.gateway = gateway or NimSemanticGateway(settings)

    async def run(self, r, candidates, crawl, deadline_at, *, previous=None):
        signature = fingerprint(r, candidates)
        report = SemanticReport(state="skipped", fingerprint=signature)
        if previous:
            saved = SemanticReport.model_validate(previous)
            if (
                saved.fingerprint == signature
                and saved.policy_version == POLICY
                and saved.model == self.settings.nvidia_nim_model
            ):
                return saved
        if not self.settings.semantic_assessment_enabled:
            return report.model_copy(update={"reason_code": "ASSESSMENT_DISABLED"})
        if crawl.origin == "synthetic" and not self.injected:
            return report.model_copy(update={"reason_code": "SYNTHETIC_ASSESSMENT_DISABLED"})
        payload, excerpts, limited = prepare(r, candidates, crawl, self.settings)
        report = report.model_copy(update={"requested_pairs": len(payload["pairs"]), "limited": limited})
        if not payload["pairs"]:
            return report.model_copy(update={"reason_code": "NO_ELIGIBLE_SEMANTIC_INPUT"})
        stop = min(
            instant(deadline_at).timestamp(), now().timestamp() + self.settings.semantic_timeout_seconds
        )
        feedback = None
        for attempt in range(2):
            remaining = stop - now().timestamp()
            if remaining <= 0:
                return report.model_copy(update={"state": "partial", "reason_code": "LLM_TIMEOUT"})
            try:
                batch = await asyncio.wait_for(
                    self.gateway.assess(payload, timeout=remaining, feedback=feedback), remaining
                )
                batch = AssessmentBatch.model_validate(batch)
                items = validate(batch, payload, excerpts)
                return report.model_copy(
                    update={
                        "state": "completed",
                        "model": self.settings.nvidia_nim_model,
                        "items": items,
                        "assessed_pairs": len(items),
                        "repair_used": bool(attempt),
                    }
                )
            except (ValueError, AppError, TimeoutError) as exc:
                code = (
                    exc.code
                    if isinstance(exc, AppError)
                    else "LLM_TIMEOUT"
                    if isinstance(exc, TimeoutError)
                    else "LLM_INVALID_OUTPUT"
                )
                if code != "LLM_INVALID_OUTPUT" or attempt:
                    return report.model_copy(
                        update={
                            "state": "partial",
                            "model": self.settings.nvidia_nim_model,
                            "reason_code": code,
                            "repair_used": bool(attempt),
                        }
                    )
                feedback = "Return exactly the requested pairs; exact quotes from their own excerpt_ids. Negative assessment requires complete untruncated excerpts. No other IDs or fields."
        return report
