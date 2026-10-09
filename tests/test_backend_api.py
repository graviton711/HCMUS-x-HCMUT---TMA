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
