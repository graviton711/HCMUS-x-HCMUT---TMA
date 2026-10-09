"""Evidence-bound v2 predicates; no invented quality or trust metrics."""

from decision.engine import evaluate as evaluate_legacy
from decision.engine import fold_tree, usable
from domain.requirements import DateValue, SetValue
from domain.semantic import EntityMember, EntitySetValue, QualitativeValue, TemporalValue
from requirements.catalog import CATALOG_VERSION, TYPE_BY_FIELD, expand_entities, known_entity_ids


def semantic_fact(tour, name):
    return tour.fields.get(name) or getattr(tour, "semantic_fields", {}).get(name)


def evaluate(c, tour, offer, party, source, at, synthetic=False, offer_reason=None):
    value = c.value
    if isinstance(value, TemporalValue):
        if value.resolved_date:
            return evaluate_legacy(
                c.model_copy(update={"value": DateValue(value=value.resolved_date)}),
                tour,
                offer,
                party,
                source,
                at,
                synthetic,
                offer_reason,
            )
        return {
            "condition_id": c.id,
            "field": c.field,
            "strength": c.strength,
            "status": "unknown",
            "actual": None,
            "reason_code": value.reason,
            "evidence_ids": [],
            "data_quality": {},
        }
    if isinstance(value, SetValue) and c.field in TYPE_BY_FIELD:
        value = EntitySetValue(
            catalog_version=CATALOG_VERSION,
            members=[
                EntityMember(raw=eid, entity_type=TYPE_BY_FIELD[c.field], entity_id=eid, status="resolved")
                for eid in value.items
            ],
        )
    if not isinstance(value, (EntitySetValue, QualitativeValue)):
        return evaluate_legacy(c, tour, offer, party, source, at, synthetic, offer_reason)
    out = {
        "condition_id": c.id,
        "field": c.field,
        "strength": c.strength,
        "status": "unknown",
        "actual": None,
        "reason_code": "FIELD_MISSING",
        "evidence_ids": [],
        "data_quality": {},
    }
    if isinstance(value, QualitativeValue) and value.metric_policy is None:
        out["reason_code"] = "METRIC_UNSUPPORTED"
        return out
    fact = semantic_fact(tour, c.field)
    ok, reason = usable(fact, c.field, source, at, synthetic)
    out["reason_code"] = reason
    if fact:
        out.update(
            actual=fact.value,
            evidence_ids=fact.evidence_ids,
            data_quality={
                "state": fact.data_state,
                "verification": fact.verification,
                "completeness": fact.completeness,
                "scope": fact.scope,
            },
        )
    if not ok:
        return out
    scope = getattr(c, "scope", None)
    if scope and fact.scope != scope:
        out["reason_code"] = "FIELD_SCOPE_INCOMPATIBLE"
        return out
    found = set(fact.value if isinstance(fact.value, list) else [fact.value])
    if isinstance(value, QualitativeValue):
        state = "pass" if found else "fail" if fact.completeness == "complete" else "unknown"
        if c.operator == "excludes":
            state = {"pass": "fail", "fail": "pass", "unknown": "unknown"}[state]
    else:
        actual_ids = found
        entity_type = TYPE_BY_FIELD[c.field]
        unreviewed = actual_ids - known_entity_ids(entity_type)
        found = expand_entities(found, entity_type)
        statuses = {
            str(i): "unknown"
            if member.entity_id is None
            else "pass"
            if member.entity_id in found
            else "unknown"
            if unreviewed
            or actual_ids & (expand_entities({member.entity_id}, entity_type) - {member.entity_id})
            else "fail"
            if fact.completeness == "complete"
            else "unknown"
            for i, member in enumerate(value.members)
        }
        from domain.requirements import Tree

        kind = "all" if c.operator in {"contains", "contains_all"} else "any"
        tree = Tree(kind=kind, children=[Tree(kind="predicate", condition_id=i) for i in statuses])
        state = fold_tree(tree, statuses)
        if c.operator in {"excludes", "not_in"}:
            state = {"pass": "fail", "fail": "pass", "unknown": "unknown"}[state]
    out.update(
        status=state,
        reason_code="ENTITY_FACT_CATALOG_MISSING"
        if isinstance(value, EntitySetValue) and state == "unknown" and unreviewed
        else "CONDITION_EVALUATED",
    )
    return out
