"""Real API/auth/SQLite comparison binding; hosted personal REST is isolated."""

import base64
import copy
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from test_auth_history import OTHER, URL, USER, Hosted, token

from api.app import create_app
from api.profile_hub.models import TravelPreferences
from api.settings import Settings
from api.store import resources
from domain.common import now


class PersonalStore:
    def __init__(self, api_key="publishable-test"):
        self.api_key = api_key
        self.items, self.receipts, self.calls = {}, {}, []
        self.missing = False
        self.invalid = False

    def handle(self, request):
        self.calls.append(request)
        assert request.headers["apikey"] == self.api_key
        bearer = request.headers["authorization"].removeprefix("Bearer ")
        owner = json.loads(base64.urlsafe_b64decode(bearer.split(".")[1] + "=="))["sub"]
        if self.missing:
            return httpx.Response(404, json={"code": "PGRST205", "message": "SECRET PROVIDER DETAIL"})
        if self.invalid:
            return httpx.Response(200, json=[{"provider_internal_detail": "SECRET"}])
        if request.method == "GET":
            receipt = request.url.path.endswith("profile_hub_receipts")
            rows = self.receipts.values() if receipt else self.items.values()
            rows = [copy.deepcopy(r) for r in rows if r["owner_id"] == owner]
            for key, filter_value in request.url.params.items():
                if filter_value.startswith("eq."):
                    expected = filter_value[3:]
                    rows = [r for r in rows if str(r.get(key)).lower() == expected.lower()]
            return httpx.Response(200, json=rows)
        assert request.url.path.endswith("/rpc/profile_hub_mutate")
        b = json.loads(request.content)
        receipt_key = (owner, b["p_key"])
        if receipt_key in self.receipts:
            receipt = self.receipts[receipt_key]
            return httpx.Response(
                200,
                json=receipt["result"]
                if receipt["request_hash"] == b["p_request_hash"]
                else {"error": "IDEMPOTENCY_CONFLICT"},
            )
        key = owner, b["p_kind"], b["p_item_id"]
        version = self.items.get(key, {}).get("version", 0)
        if b["p_expected_version"] != version:
            return httpx.Response(200, json={"error": "VERSION_CONFLICT"})
        row = dict(
            owner_id=owner,
            kind=b["p_kind"],
            item_id=b["p_item_id"],
            version=version + 1,
            payload=b["p_payload"],
            deleted=b["p_payload"] is None,
            updated_at=now().isoformat(),
        )
        self.items[key] = row
        self.receipts[receipt_key] = dict(
            owner_id=owner,
            mutation_key=b["p_key"],
            request_hash=b["p_request_hash"],
            result=copy.deepcopy(row),
            expires_at=(now() + timedelta(days=1)).isoformat(),
        )
        return httpx.Response(200, json=row)


@pytest.fixture
def setup(tmp_path):
    personal = PersonalStore()
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'hub.db'}",
            worker_enabled=False,
            data_provider="fixture",
            supabase_auth_url=URL,
            supabase_auth_publishable_key="publishable-test",
        ),
        auth_transport=httpx.MockTransport(Hosted().handle),
        profile_transport=httpx.MockTransport(personal.handle),
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token()
        yield client, personal, app


def post(client, path, body, key="new-mutation", status=200):
    result = client.post("/v2/profile-hub/" + path, json=body, headers={"Idempotency-Key": key})
    assert result.status_code == status, result.text
    return result.json().get("data", result.json())


def test_preferences_isolation_retry_conflict_and_restore(setup):
    client, personal, _ = setup
    prefs = TravelPreferences(hotel_stars=4).model_dump(mode="json")
    body = dict(expected_version=0, preferences=prefs)
    first = post(client, "preferences", body)
    assert first["item"]["version"] == 1
    assert post(client, "preferences", body) == first
    post(client, "preferences", {**body, "preferences": {**prefs, "hotel_stars": 5}}, status=409)
    post(client, "preferences", body, key="stale-device", status=409)
    client.headers["Authorization"] = "Bearer " + token(OTHER)
    assert client.get("/v2/profile-hub").json()["data"]["preferences"] is None
    post(client, "preferences", body)
    client.headers["Authorization"] = "Bearer " + token()
    post(
        client,
        "items/delete",
        dict(kind="preferences", item_id="preferences", expected_version=1),
        key="delete",
    )
    state = client.get("/v2/profile-hub").json()["data"]
    assert state["preferences"] is None and state["preferences_version"] == 2
    assert (
        post(client, "preferences", dict(expected_version=2, preferences=prefs), key="restore")["item"][
            "version"
        ]
        == 3
    )
    assert len(personal.items) == 2


def test_guest_missing_migration_and_unsafe_values(setup):
    client, personal, _ = setup
    result = client.get("/v2/profile-hub", headers={"Authorization": "Bearer anonymous"})
    assert result.status_code == 401
    personal.missing = True
    result = client.get("/v2/profile-hub")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "PROFILE_HUB_MIGRATION_REQUIRED"
    assert "SECRET" not in result.text
    personal.missing = False
    post(client, "preferences", dict(expected_version=0, preferences={"hotel_stars": 6}), status=422)
    post(client, "preferences", dict(expected_version=0, preferences={"owner_id": OTHER}), status=422)
    post(
        client,
        "templates",
        dict(
            item_id="test-template",
            expected_version=0,
            template={
                "name": "Family",
                "values": {"adults": 2, "child_count": 1, "departure_date": "2026-11-05"},
            },
        ),
        status=422,
    )


def test_malformed_personal_store_is_an_actionable_error_without_provider_content(setup):
    client, personal, _ = setup
    personal.invalid = True
    response = client.get("/v2/profile-hub")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROFILE_HUB_DATA_INVALID"
    assert "SECRET" not in response.text


def seed_comparison(app, owner=USER):
    result = dict(
        origin="source",
        evaluated_at=now().isoformat(),
        columns=[
            dict(
                id="tour-a",
                tour_snapshot_id="snapshot-a",
                canonical_url="https://example.test/tour-a",
                title="Japan",
                supplier={"display_name": "Provider"},
                selected_offer_snapshot_id="offer-a",
            )
        ],
        rows=[
            dict(id="departure_date", field="departure_date"),
            dict(id="price", field="listed_price_quotes"),
        ],
        cells=[
            dict(column_id="tour-a", row_id="departure_date", data_state="present", value="2026-11-05"),
            dict(
                column_id="tour-a",
                row_id="price",
                data_state="present",
                value=[dict(kind="from", amount=33999000, currency="VND", basis="per_adult")],
            ),
        ],
        recommendations=dict(candidate_ids=[], needs_verification=["tour-a"]),
    )
    with app.state.store.transaction() as c:
        app.state.store.add_resource(
            c,
            "user_" + owner.replace("-", ""),
            "comparison-owned",
            "comparison_v2",
            dict(result=result),
            status="succeeded",
        )


def test_bookmark_bound_to_owned_snapshot_retry_after_expiry_and_notes(setup):
    client, personal, app = setup
    seed_comparison(app)
    body = dict(expected_version=0, comparison_id="comparison-owned", column_id="tour-a")
    client.headers["Authorization"] = "Bearer " + token(OTHER)
    post(client, "saved-tours", body, status=404)
    client.headers["Authorization"] = "Bearer " + token()
    item = post(client, "saved-tours", body)["item"]
    v = item["value"]
    assert v["departure_date"] == "2026-11-05" and v["price_label"].startswith("Từ 33999000")
    assert v["status_at_save"] == "needs_verification"
    post(
        client,
        f"saved-tours/{item['id']}/edit",
        dict(expected_version=1, note="Compare later", collection="Family"),
        key="note",
    )
    with app.state.store.transaction() as c:
        c.execute(delete(resources).where(resources.c.id == "comparison-owned"))
    assert post(client, "saved-tours", body)["item"]["value"] == v
    state = client.get("/v2/profile-hub").json()["data"]
    assert state["saved_tours"][0]["value"]["note"] == "Compare later"
    assert state["saved_tours"][0]["version"] == 2
    post(client, "saved-tours", body, key="new-save-after-expiry", status=404)


def test_lower_listed_price_utility_is_separate_from_hard_budget():
    from decision.v2 import preference_utility
    from domain.requirements import SourceReference
    from domain.semantic import BudgetV2, ConditionV2

    c = ConditionV2(
        id="low-price",
        field="estimated_cost",
        operator="prefer_low",
        strength="soft",
        value=BudgetV2(
            amount=40_000_000, currency="VND", basis="per_adult", coverage="tour_price", measure="listed"
        ),
        sources=[SourceReference(kind="form", field_path="preferences")],
    )

    def evaluation(amount):
        return dict(status="unknown", actual=dict(measure="listed", lower=amount, upper=amount, reasons=[]))

    assert preference_utility(c, evaluation(20_000_000)) > preference_utility(c, evaluation(35_000_000))
    assert preference_utility(c, evaluation(None)) is None
    e = evaluation(20_000_000)
    e["actual"]["reasons"] = ["FIELD_STALE"]
    assert preference_utility(c, e) is None
