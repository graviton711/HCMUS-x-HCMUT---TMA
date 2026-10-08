"""Core product policy across input, answers, edits and persisted API gates."""

import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from test_v2 import Nim, confirm, data, finish, form, propose

from api.app import create_app
from api.store import dump, revisions
from api.v2.models import RequirementV2
from requirements.semantic import finalize_v2
from requirements.v2 import InitialExtractionV2

JAPAN = "Tôi muốn tìm tour Nhật Bản khởi hành từ Hồ Chí Minh ngày 03/11/2026, đi 1 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour."


class JapanNim:
    async def extract(self, message, previous=None, *, feedback=None):
        return InitialExtractionV2(
            conditions=[
                dict(
                    id="destination",
                    field="destinations",
                    operator="contains",
                    strength="hard",
                    raw_values=["Nhật Bản"],
                    quote="Nhật Bản",
                ),
                dict(
                    id="origin",
                    field="departure_origin",
                    operator="in",
                    strength="hard",
                    raw_values=["Hồ Chí Minh"],
                    quote="khởi hành từ Hồ Chí Minh",
                ),
                dict(
                    id="date",
                    field="departure_date",
                    operator="eq",
                    strength="hard",
                    raw_values=["03/11/2026"],
                    quote="ngày 03/11/2026",
                ),
                dict(
                    id="budget",
                    field="estimated_cost",
                    operator="lte",
                    strength="hard",
                    raw_values=["30 triệu"],
                    quote="ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour",
                ),
            ],
            party=dict(adults_raw="1", adults_quote="đi 1 người lớn", children=None, rooming_quote=None),
            preference_updates=[],
            reference_urls_update=None,
            notes_update=None,
        ), {}

    extract_v2 = extract


@pytest.fixture
def app(settings):
    return create_app(settings, nim=Nim())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        token = data(c.post("/v2/sessions"), 201)["token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


def states(r):
    return {f["field_path"]: f for f in r["completeness"]["fields"]}


def proposal_for(client, accepted):
    return data(client.get(f"/v2/proposals/{accepted['proposal_id']}"))


def answer(client, p, edits):
    return data(
        client.post(
            f"/v2/requirements/{p['requirement_id']}/proposals",
            json={
                "expected_revision": p["base_revision"],
                "proposal_id": p["id"],
                "expected_proposal_version": p["version"],
                "input": {"kind": "structured", "edits": edits},
            },
        )
    )


def core_answers(p, source_form=None):
    source_form = source_form or form()["input"]["form"]
    cs = {c["field"]: c for c in source_form["conditions"]}
    result = []
    for q in p["clarifications"]:
        if q["field_path"] == "party.adults":
            value = {"adults": source_form["party"]["adults"]}
        elif q["field_path"].startswith("trip."):
            c = copy.deepcopy(cs[q["field_path"].removeprefix("trip.")])
            c["id"] = "answer_" + c["id"]
            value = {"condition": c}
        else:
            continue
        result.append({"op": "answer_clarification", "clarification_id": q["id"], "answer": value})
    return result


@pytest.mark.parametrize(
    "field", ["destinations", "departure_origin", "departure_date", "party.adults", "estimated_cost"]
)
def test_each_missing_form_field_creates_draft_and_blocks_confirmation(client, field):
    body = form()
    f = body["input"]["form"]
    if field == "party.adults":
        f["party"]["adults"] = None
    else:
        f["conditions"] = [c for c in f["conditions"] if c["field"] != field]
    accepted = data(client.post("/v2/requirements", json=body), 201)
    assert accepted["revision"] == 0
    p = proposal_for(client, accepted)
    assert states(p["preview"])[field]["status"] == "missing"
    response = confirm(client, p)
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert not details["readiness"]["can_confirm"] and details["clarifications"]
    completed = answer(client, p, core_answers(p))
    assert data(confirm(client, completed))["completeness"]["is_complete"]


def test_text_only_destination_is_extracted_but_needs_four_core_slots(client, app):
    accepted = data(client.post("/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}}), 202)
    finish(app)
    p = proposal_for(client, accepted)
    assert states(p["preview"])["destinations"]["status"] == "resolved"
    assert len(p["clarifications"]) == 4
    assert p["preview"]["readiness"]["can_collect_data"]
    assert p["preview"]["readiness"]["can_evaluate_hard_constraints"]
    assert not p["preview"]["readiness"]["can_confirm"]
    assert confirm(client, p).status_code == 409
    p = answer(client, p, core_answers(p))
    r = data(confirm(client, p))
    assert r["party"]["adults"] == 2 and r["revision"] == 1
    assert len([c for c in r["conditions"] if c["field"] == "destinations"]) == 1
    assert data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)


def test_japan_text_and_structured_have_identical_normalized_predicates(settings):
    app = create_app(settings, nim=JapanNim())
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + data(c.post("/v2/sessions"), 201)["token"]
        accepted = data(c.post("/v2/requirements", json={"input": {"kind": "text", "text": JAPAN}}), 202)
        finish(app)
        p = proposal_for(c, accepted)
        r = data(confirm(c, p))
        assert len(r["conditions"]) == 4 and r["party"]["adults"] == 1
        assert r["completeness"]["is_complete"] and not r["clarifications"]
        body = form(date="2026-11-03")
        f = body["input"]["form"]
        f["conditions"] = [x for x in f["conditions"] if x["field"] != "duration_days"]
        f["party"]["adults"] = 1
        f["conditions"][3]["value"]["amount"] = 30000000
        structured = data(c.post("/v2/requirements", json=body), 201)

        def predicates(req):
            from domain.semantic import ConditionV2
            from requirements.semantic import legacy_condition

            return {
                x["field"]: (
                    x["operator"],
                    x["strength"],
                    legacy_condition(ConditionV2.model_validate(x)).value.model_dump(),
                )
                for x in req["conditions"]
            }

        assert predicates(r) == predicates(structured)


@pytest.mark.parametrize("change", ["soft", "near", "lower", "zero", "currency", "basis"])
def test_budget_must_be_resolved_positive_hard_upper_cap(client, change):
    body = form()
    b = body["input"]["form"]["conditions"][3]
    if change == "soft":
        b["strength"] = "soft"
    elif change == "near":
        b.update(strength="soft", operator="near")
    elif change == "lower":
        b["operator"] = "gte"
    elif change == "zero":
        b["value"]["amount"] = 0
    else:
        b["value"][change] = None
    accepted = data(client.post("/v2/requirements", json=body), 201)
    p = proposal_for(client, accepted)
    assert states(p["preview"])["estimated_cost"]["status"] == "needs_clarification"
    assert confirm(client, p).status_code == 409
    # Do not turn a soft/lower bound into a cap behind the user's back.
    found = next(c for c in p["preview"]["conditions"] if c["id"] == "budget")
    assert found["strength"] == b["strength"] and found["operator"] == b["operator"]


@pytest.mark.parametrize("field,op", [("destinations", "excludes"), ("departure_origin", "not_in")])
def test_negative_only_location_does_not_fill_positive_slot(client, field, op):
    body = form()
    next(c for c in body["input"]["form"]["conditions"] if c["field"] == field)["operator"] = op
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    assert states(p["preview"])[field]["status"] != "resolved"
    assert confirm(client, p).status_code == 409


def test_or_tree_cannot_bypass_mandatory_budget(client):
    body = form()
    body["input"]["form"]["hard_tree"] = {
        "kind": "any",
        "children": [
            {"kind": "predicate", "condition_id": cid} for cid in ("destination", "origin", "date", "budget")
        ],
    }
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    assert "CORE_FIELD_BRANCH_REQUIRED" in states(p["preview"])["estimated_cost"]["reasons"]
    assert confirm(client, p).status_code == 409


def test_url_only_exempt_but_hybrid_cannot_bypass_missing_slots(client, app):
    urls = ["https://tour-demo.invalid/tour-a"]
    accepted = data(
        client.post("/v2/requirements", json={"input": {"kind": "urls"}, "reference_urls": urls}), 201
    )
    r = data(confirm(client, proposal_for(client, accepted)))
    assert r["completeness"] == {
        "policy_version": "personalized-core-v1",
        "profile": "url_only",
        "fields": [],
        "is_complete": True,
    }
    assert data(client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1}), 202)
    accepted = data(
        client.post(
            "/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}, "reference_urls": urls}
        ),
        202,
    )
    finish(app, 2)
    p = proposal_for(client, accepted)
    assert p["preview"]["mode"] == "hybrid" and not p["preview"]["readiness"]["can_confirm"]


def test_removed_budget_cannot_confirm_and_discard_restores_it(client):
    r = data(client.post("/v2/requirements", json=form()), 201)
    p = propose(client, r, [{"op": "remove_condition", "condition_id": "budget"}])
    assert confirm(client, p).status_code == 409
    removed = next(ch for ch in p["changes"] if ch["condition_id"] == "budget")
    p = data(
        client.post(
            f"/v2/proposals/{p['id']}/discard-changes",
            json={
                "expected_revision": 1,
                "expected_proposal_version": p["version"],
                "change_ids": [removed["id"]],
            },
        )
    )
    assert data(confirm(client, p))["readiness"]["can_search"]


@pytest.mark.parametrize("value", [True, 1.5, "2", 0, 101])
def test_invalid_adult_answer_is_atomic(client, value):
    body = form()
    body["input"]["form"]["party"]["adults"] = None
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    edit = core_answers(p)[0]
    edit["answer"] = {"adults": value}
    response = client.post(
        f"/v2/requirements/{p['requirement_id']}/proposals",
        json={
            "expected_revision": 0,
            "proposal_id": p["id"],
            "expected_proposal_version": p["version"],
            "input": {"kind": "structured", "edits": [edit]},
        },
    )
    assert response.status_code == 422
    assert data(client.get(f"/v2/proposals/{p['id']}"))["version"] == p["version"]


def test_adult_answer_preserves_children_rooming_and_rejects_mixed_edit(client):
    body = form()
    body["input"]["form"]["party"] = {
        "adults": None,
        "children": [{"id": "child", "age": 8}],
        "rooming": "2 phòng",
    }
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    edit = core_answers(p)[0]
    mixed = client.post(
        f"/v2/requirements/{p['requirement_id']}/proposals",
        json={
            "expected_revision": 0,
            "proposal_id": p["id"],
            "expected_proposal_version": p["version"],
            "input": {"kind": "structured", "edits": [edit, {"op": "replace_party", "party": {"adults": 3}}]},
        },
    )
    assert mixed.status_code == 422
    completed = answer(client, p, [edit])
    party = completed["preview"]["party"]
    assert party["children"] == [{"id": "child", "age": 8}] and party["rooming"] == "2 phòng"
    stale = client.post(
        f"/v2/requirements/{p['requirement_id']}/proposals",
        json={
            "expected_revision": 0,
            "proposal_id": p["id"],
            "expected_proposal_version": completed["version"],
            "input": {"kind": "structured", "edits": [edit]},
        },
    )
    assert stale.status_code == 409


def test_persisted_readiness_cannot_bypass_gate_or_rewrite_history(client, app):
    r = data(client.post("/v2/requirements", json=form()), 201)
    with app.state.store.transaction() as c:
        old = json.loads(
            c.execute(select(revisions.c.payload).where(revisions.c.resource_id == r["id"])).scalar()
        )
        old["conditions"] = [x for x in old["conditions"] if x["id"] != "budget"]
        old["hard_tree"]["children"] = [
            x for x in old["hard_tree"]["children"] if x["condition_id"] != "budget"
        ]
        old.pop("completeness")
        old["readiness"].update(can_confirm=True, can_search=True)
        c.execute(update(revisions).where(revisions.c.resource_id == r["id"]).values(payload=dump(old)))
    response = client.post("/v2/comparisons", json={"requirement_id": r["id"], "revision": 1})
    assert response.status_code == 409
    assert "estimated_cost" in {
        f["field_path"]
        for f in response.json()["error"]["details"]["completeness"]["fields"]
        if f["status"] == "missing"
    }
    read = data(client.get(f"/v2/requirements/{r['id']}/revisions/1"))
    assert not read["readiness"]["can_search"]
    with app.state.store.engine.connect() as c:
        assert (
            json.loads(
                c.execute(select(revisions.c.payload).where(revisions.c.resource_id == r["id"])).scalar()
            )
            == old
        )


def test_catalog_gap_is_backend_issue_without_duplicate_place_question(client):
    body = form()
    body["input"]["form"]["conditions"][0]["value"] = {
        "kind": "entities",
        "catalog_version": "test",
        "members": [
            {"raw": "Atlantis", "entity_type": "place", "status": "catalog_missing", "entity_id": None}
        ],
    }
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    s = states(p["preview"])["destinations"]
    assert s["status"] == "unsupported" and s["responsibility"] == "backend"
    assert not s["clarification_ids"] and not p["clarifications"]
    assert confirm(client, p).status_code == 409


def test_soft_locations_remain_soft_and_budget_cap_stays_hard(client):
    body = form()
    body["input"]["form"]["conditions"][0]["strength"] = "soft"
    r = data(client.post("/v2/requirements", json=body), 201)
    assert r["completeness"]["is_complete"]
    assert next(c for c in r["conditions"] if c["id"] == "destination")["strength"] == "soft"


def test_completeness_serialized_flags_are_not_authoritative(client):
    r = data(client.post("/v2/requirements", json=form()), 201)
    req = RequirementV2.model_validate(r)
    altered = req.model_copy(update={"party": req.party.model_copy(update={"adults": None})})
    recalculated = finalize_v2(altered)
    assert not recalculated.completeness.is_complete and not recalculated.readiness.can_search


def test_core_policy_does_not_change_v1():
    from conftest import condition, requirement

    from domain.requirements import SetValue

    r = requirement([condition("destinations", SetValue(items=["country:jp"]), "contains")])
    assert r.readiness.status == "ready" and "completeness" not in r.model_dump()


def test_typed_unknown_canonical_id_is_not_a_resolved_destination(client):
    body = form()
    body["input"]["form"]["conditions"][0]["value"]["items"] = ["country:invented"]
    p = proposal_for(client, data(client.post("/v2/requirements", json=body), 201))
    assert states(p["preview"])["destinations"]["status"] == "unsupported"
    assert not p["clarifications"] and confirm(client, p).status_code == 409


def test_date_window_satisfies_core_without_forcing_exact_departure(client):
    body = form()
    c = body["input"]["form"]["conditions"][2]
    c.update(operator="between", value={"kind": "date", "value": "2026-11-01", "upper": "2026-11-10"})
    r = data(client.post("/v2/requirements", json=body), 201)
    assert r["readiness"]["can_search"]
    assert next(x for x in r["conditions"] if x["id"] == "date")["operator"] == "between"


def test_update_omission_guard_keeps_explicit_budget_and_adults_in_core_reply(client, app):
    from domain.common import AppError, now
    from domain.requirements import Message
    from requirements.v2 import UpdateExtractionV2, coverage_guard

    accepted = data(client.post("/v2/requirements", json={"input": {"kind": "text", "text": "Đi Nhật"}}), 202)
    finish(app)
    previous = RequirementV2.model_validate(proposal_for(client, accepted)["preview"])
    message = Message(
        id="reply",
        text="Đi 2 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn.",
        received_at=now().isoformat(),
    )
    with pytest.raises(AppError) as exc:
        coverage_guard(
            UpdateExtractionV2(preference_updates=[], reference_urls_update=None, notes_update=None),
            message,
            previous,
        )
    assert "estimated_cost" in exc.value.repair_hint and "party.adults_raw" in exc.value.repair_hint


@pytest.mark.parametrize("mistake", ["empty_type", "location_with_duplicate_party"])
def test_generic_tour_does_not_create_an_empty_tour_type_and_repairs(settings, mistake):
    from requirements.v2 import RawConditionV2

    class EmptyTypeNim(JapanNim):
        def __init__(self):
            self.calls = 0

        async def extract(self, message, previous=None, *, feedback=None):
            self.calls += 1
            raw, metrics = await super().extract(message, previous, feedback=feedback)
            if self.calls == 1:
                body = raw.model_dump()
                body["conditions"].append(
                    RawConditionV2(
                        id="group",
                        field="tour_type",
                        operator="in",
                        strength="hard",
                        raw_values=[],
                        quote="tour Nhật Bản",
                    ).model_dump()
                )
                if mistake == "location_with_duplicate_party":
                    body["conditions"].pop()
                    body["conditions"][0].update(field="tour_type", operator="in")
                    body["conditions"].append(
                        dict(
                            id="duplicate_party",
                            field="unsupported",
                            operator="unresolved",
                            strength="soft",
                            raw_values=["1"],
                            quote="đi 1 người lớn",
                        )
                    )
                raw = InitialExtractionV2.model_validate(body)
            else:
                assert "loại tour" in feedback
                if mistake == "location_with_duplicate_party":
                    assert "địa danh" in feedback and "duplicate_party" in feedback
            return raw, metrics

        extract_v2 = extract

    nim = EmptyTypeNim()
    app = create_app(settings, nim=nim)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + data(client.post("/v2/sessions"), 201)["token"]
        accepted = data(client.post("/v2/requirements", json={"input": {"kind": "text", "text": JAPAN}}), 202)
        finish(app)
        p = proposal_for(client, accepted)
        assert nim.calls == 2 and p["preview"]["readiness"]["can_confirm"]
        assert len(p["preview"]["conditions"]) == 4


def tet_previous():
    from test_semantics import parsed

    return finalize_v2(RequirementV2.model_validate({**parsed().model_dump(), "input_kind": "text"}))


def test_mixed_reply_generation_separates_questions_and_condition_targets():
    from domain.common import now
    from domain.requirements import Message
    from requirements.v2 import UpdateExtractionV2, generation_schema

    previous = tet_previous()
    message = Message(
        id="mixed",
        text="Nhóm có 2 người lớn. Giá tour tối đa 10 triệu VND mỗi người lớn. Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên.",
        received_at=now().isoformat(),
    )
    schema = generation_schema(UpdateExtractionV2, message, previous)
    assert schema["properties"]["answers"]["minItems"] == 3
    targets = schema["$defs"]["OperationV2"]["properties"]["target_id"]["anyOf"][0]["enum"]
    assert set(targets) == {c.id for c in previous.conditions}
    answer_ids = set(schema["$defs"]["RawAnswer"]["properties"]["clarification_id"]["enum"])
    assert answer_ids == {
        q.id
        for q in previous.clarifications
        if q.reason_code
        in {"DATE_YEAR_REQUIRED", "TEMPORAL_SEMANTICS_REQUIRED", "CONDITION_STRENGTH_REQUIRED"}
    }
    assert not answer_ids & {q.id for q in previous.clarifications if q.reason_code == "CORE_FIELD_REQUIRED"}


def test_mixed_reply_keeps_original_intent_while_filling_core_and_semantics():
    from domain.common import now
    from domain.requirements import Message
    from domain.semantic import ConditionV2, SemanticRequirement
    from requirements.nim import parse_validated
    from requirements.semantic import normalize_v2
    from requirements.v2 import SlotExtractor, UpdateExtractionV2

    previous = tet_previous()
    quote_by_reason = {
        "DATE_YEAR_REQUIRED": ("2027", "Tết 2027"),
        "TEMPORAL_SEMANTICS_REQUIRED": (
            "Đây là khoảng thời gian tôi có thể đi",
            "Đây là khoảng thời gian tôi có thể đi",
        ),
        "CONDITION_STRENGTH_REQUIRED": ("ưu tiên", "Đi dọc miền Trung chỉ là ưu tiên"),
    }

    class MixedNim:
        async def extract(self, message, previous=None, *, feedback=None):
            answers = [
                dict(
                    clarification_id=q.id,
                    value_raw=quote_by_reason[q.reason_code][0],
                    quote=quote_by_reason[q.reason_code][1],
                )
                for q in previous.clarifications
                if q.reason_code in quote_by_reason
            ]
            return UpdateExtractionV2(
                party=dict(
                    adults_raw="2", adults_quote="Nhóm có 2 người lớn", children=None, rooming_quote=None
                ),
                operations=[
                    dict(
                        op="add",
                        condition=dict(
                            id="cap",
                            field="estimated_cost",
                            operator="lte",
                            strength="hard",
                            raw_values=["10 triệu"],
                            quote="Giá tour tối đa 10 triệu VND mỗi người lớn",
                        ),
                        quote="Giá tour tối đa 10 triệu VND mỗi người lớn",
                    )
                ],
                answers=answers,
                preference_updates=[],
                reference_urls_update=None,
                notes_update=None,
            ), {}

    message = Message(
        id="mixed",
        text="Nhóm có 2 người lớn. Giá tour tối đa 10 triệu VND mỗi người lớn. Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên.",
        received_at=now().isoformat(),
    )
    result, metrics = asyncio.run(
        parse_validated(
            SlotExtractor(MixedNim()),
            message,
            previous,
            requirement_id=previous.id,
            mode=previous.mode,
            timezone=previous.timezone,
            targets=[],
            requirement_model=SemanticRequirement,
            normalizer=normalize_v2,
            finalizer=finalize_v2,
            condition_model=ConditionV2,
            batch_validation=True,
        )
    )
    updated = finalize_v2(
        RequirementV2.model_validate(
            {**result.model_dump(), "input_kind": "text", "schema_version": "2.0-draft"}
        )
    )
    assert not metrics["repair_used"] and updated.readiness.can_confirm
    assert updated.party.adults == 2
    old = {c.id: c for c in previous.conditions}
    for c in updated.conditions:
        if c.field in {
            "destinations",
            "departure_origin",
            "supplier_reputation",
            "service_quality",
            "price_value",
            "nature",
            "transport",
            "tour_type",
        }:
            assert c == old[c.id]
    assert next(c for c in updated.conditions if c.field == "departure_date").operator == "gte"
    assert next(c for c in updated.conditions if c.field == "return_date").operator == "lte"


@pytest.mark.parametrize("quote,identifier", [("ghép đoàn", "join_group"), ("đoàn riêng", "private_group")])
def test_specific_tour_type_is_kept(quote, identifier):
    from domain.common import now
    from domain.requirements import Message
    from requirements.semantic import normalize_v2
    from requirements.v2 import RawConditionV2

    raw = RawConditionV2(
        id="type", field="tour_type", operator="in", strength="hard", raw_values=[quote], quote=quote
    )
    c = normalize_v2(
        raw, Message(id="m", text=f"Tôi muốn đi {quote}.", received_at=now().isoformat()), "Asia/Ho_Chi_Minh"
    )
    assert c.value.members[0].entity_id == identifier


@pytest.mark.parametrize("explicit_soft", [False, True])
def test_budget_value_update_requires_preserved_strength_unless_user_changes_it(client, explicit_soft):
    from domain.common import AppError, now
    from domain.requirements import Message
    from requirements.v2 import UpdateExtractionV2, coverage_guard

    previous = RequirementV2.model_validate(data(client.post("/v2/requirements", json=form()), 201))
    quote = (
        "Ưu tiên ngân sách 32 triệu VND mỗi người lớn"
        if explicit_soft
        else "Ngân sách 32 triệu VND mỗi người lớn"
    )
    raw = UpdateExtractionV2(
        operations=[
            dict(
                op="replace",
                target_id="budget",
                condition=dict(
                    id="budget",
                    field="estimated_cost",
                    operator="lte",
                    strength="soft",
                    raw_values=["32 triệu"],
                    quote=quote,
                ),
                quote=quote,
            )
        ],
        preference_updates=[],
        reference_urls_update=None,
        notes_update=None,
    )
    message = Message(id="m", text=quote, received_at=now().isoformat())
    if explicit_soft:
        coverage_guard(raw, message, previous)
    else:
        with pytest.raises(AppError) as exc:
            coverage_guard(raw, message, previous)
        assert "hard budget strength" in exc.value.repair_hint


async def test_nim_mixed_reply_metadata_does_not_generate_answer_values(settings):
    import httpx

    from domain.common import now
    from domain.requirements import Message
    from requirements.nim import NimGateway
    from requirements.v2 import UpdateExtractionV2

    def handler(request):
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        tasks = context["clarification_reply_targets"]
        assert {task["reason_code"] for task in tasks} == {
            "DATE_YEAR_REQUIRED",
            "TEMPORAL_SEMANTICS_REQUIRED",
            "CONDITION_STRENGTH_REQUIRED",
        }
        assert all(
            task["output_location"] == "answers" and "value_raw" not in task and "quote" not in task
            for task in tasks
        )
        assert {task["clarification_id"] for task in tasks} == set(context["required_clarification_ids"])
        raw = UpdateExtractionV2(preference_updates=[], reference_urls_update=None, notes_update=None)
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": raw.model_dump_json()}}]}
        )

    await NimGateway(settings, httpx.MockTransport(handler)).extract_v2(
        Message(
            id="m",
            text="Nhóm có 2 người lớn. Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên.",
            received_at=now().isoformat(),
        ),
        tet_previous(),
    )


def test_qualitative_polarity_and_invented_slider_are_repaired_together():
    from domain.common import AppError, now
    from domain.requirements import Message
    from requirements.v2 import InitialExtractionV2, coverage_guard

    raw = InitialExtractionV2(
        conditions=[
            dict(
                id="nature",
                field="nature",
                operator="excludes",
                strength="hard",
                raw_values=[],
                quote="Không cần ưu tiên thiên nhiên",
            ),
            dict(
                id="value",
                field="price_value",
                operator="prefer",
                strength="soft",
                raw_values=[],
                quote="chỉ ưu tiên giá hợp lý",
            ),
        ],
        preference_updates=[dict(dimension="cost", level=0, quote="chỉ ưu tiên giá hợp lý")],
        reference_urls_update=None,
        notes_update=None,
    )
    with pytest.raises(AppError) as exc:
        coverage_guard(
            raw,
            Message(
                id="m",
                text="Không cần ưu tiên thiên nhiên, chỉ ưu tiên giá hợp lý.",
                received_at=now().isoformat(),
            ),
            None,
        )
    assert "nature:" in exc.value.repair_hint and "preference_updates.cost" in exc.value.repair_hint


def test_duplicate_guard_does_not_hide_bad_date_quote():
    from domain.common import AppError, now
    from domain.requirements import Message
    from requirements.v2 import InitialExtractionV2, coverage_guard

    raw = InitialExtractionV2(
        conditions=[
            dict(
                id="end",
                field="return_date",
                operator="lte",
                strength="hard",
                raw_values=["mùng 4 Tết"],
                quote="không bắt buộc khởi hành đúng ngày 27/12 âm",
            ),
            dict(
                id="end2",
                field="return_date",
                operator="lte",
                strength="hard",
                raw_values=["mùng 4 Tết"],
                quote="Tour phải về không muộn hơn mùng 4 Tết",
            ),
        ],
        preference_updates=[],
        reference_urls_update=None,
        notes_update=None,
    )
    message = Message(
        id="m",
        text="không bắt buộc khởi hành đúng ngày 27/12 âm. Tour phải về không muộn hơn mùng 4 Tết.",
        received_at=now().isoformat(),
    )
    with pytest.raises(AppError) as exc:
        coverage_guard(raw, message, None)
    assert (
        "end2" in exc.value.repair_hint
        and "end:" in exc.value.repair_hint
        and "không có trong quote" in exc.value.repair_hint
    )
