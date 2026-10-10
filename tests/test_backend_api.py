"""API: health → requirement → comparison → fetch. Fixture provider."""

from fastapi.testclient import TestClient

from backend.api import create_app


def _client(tmp_path):
    from backend.settings import Settings

    settings = Settings.load(database_url=f"sqlite:///{tmp_path / 'api.db'}")
    assert settings.data_provider == "fixture"
    return TestClient(create_app(settings))


def test_health(tmp_path):
    body = _client(tmp_path).get("/health").json()
    assert body["status"] == "ok"
    assert body["version"]


def test_full_compare_flow(tmp_path):
    client = _client(tmp_path)
    req = client.post("/requirements", json={"text": "Đà Lạt 3 ngày, từ Sài Gòn, tối đa 8 triệu/người"}).json()["requirement"]
    assert req["id"]
    assert "destination" not in req["missing"]

    comp = client.post("/comparisons", json={"requirement_id": req["id"]}).json()["comparison"]
    assert comp["ranked"], "fixture Đà Lạt under 8tr must rank"
    assert comp["analysis"]["benefits"]

    again = client.get(f"/comparisons/{comp['id']}").json()["comparison"]
    assert again["id"] == comp["id"]


def test_text_only_comparison(tmp_path):
    client = _client(tmp_path)
    comp = client.post("/comparisons", json={"text": "Phú Quốc 4 ngày"}).json()["comparison"]
    assert comp["candidates_considered"] == 3
    assert {c["tour_id"] for c in comp["ranked"]} == {"vtr-phuquoc-4n"}


def test_unknown_requirement_id_is_404(tmp_path):
    response = _client(tmp_path).post("/comparisons", json={"requirement_id": "req_nope"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_guest_session_scopes_requirements_and_history(tmp_path):
    client = _client(tmp_path)
    guest_a = client.post("/sessions")
    guest_b = client.post("/sessions")
    assert guest_a.status_code == guest_b.status_code == 201
    token_a = guest_a.json()["token"]
    token_b = guest_b.json()["token"]

    created = client.post(
        "/requirements",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"text": "Đà Lạt"},
    )
    assert created.status_code == 200
    requirement_id = created.json()["requirement"]["id"]

    own = client.get(
        f"/requirements/{requirement_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    foreign = client.get(
        f"/requirements/{requirement_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert own.status_code == 200
    assert foreign.status_code == 404

    own_history = client.get("/history", headers={"Authorization": f"Bearer {token_a}"})
    foreign_history = client.get("/history", headers={"Authorization": f"Bearer {token_b}"})
    assert own_history.status_code == 200
    assert [item["id"] for item in own_history.json()["items"]] == [requirement_id]
    assert foreign_history.json()["items"] == []


def test_history_requires_valid_guest_session_and_catalog_is_read_only(tmp_path):
    client = _client(tmp_path)
    assert client.get("/history").status_code == 401
    assert client.get("/history", headers={"Authorization": "Bearer invalid"}).status_code == 401

    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["destinations"]


def test_history_cursor_and_detail_are_owner_scoped(tmp_path):
    client = _client(tmp_path)
    session = client.post("/sessions").json()
    headers = {"Authorization": f"Bearer {session['token']}"}
    requirement_ids = []
    for text in ("Đà Lạt", "Phú Quốc"):
        response = client.post("/requirements", headers=headers, json={"text": text})
        requirement_ids.append(response.json()["requirement"]["id"])

    first = client.get("/history?limit=1", headers=headers)
    assert first.status_code == 200
    assert len(first.json()["items"]) == 1
    assert first.json()["next_cursor"]
    second = client.get(
        "/history?limit=1&cursor=" + first.json()["next_cursor"], headers=headers
    )
    assert second.status_code == 200
    assert second.json()["next_cursor"] is None
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]

    item_id = first.json()["items"][0]["id"]
    detail = client.get(f"/history/{item_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["resource"]["id"] == item_id

    other = client.post("/sessions").json()
    forbidden = client.get(
        f"/history/{item_id}", headers={"Authorization": f"Bearer {other['token']}"}
    )
    assert forbidden.status_code == 404

    invalid = client.get("/history?cursor=not-a-cursor", headers=headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "CURSOR_INVALID"
