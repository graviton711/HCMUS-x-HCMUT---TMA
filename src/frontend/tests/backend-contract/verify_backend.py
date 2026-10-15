"""Emit real current-backend responses for frontend contract tests; no upstream network."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fastapi.testclient import TestClient  # noqa: E402
from sample_rows import StaticCatalog  # noqa: E402

import backend.api as backend_api  # noqa: E402
from backend.api import create_app  # noqa: E402
from backend.settings import Settings  # noqa: E402

# Offline contract capture: serve the in-memory sample catalog, no network.
backend_api.for_settings = lambda _settings: StaticCatalog()


def collect() -> list[dict[str, object]]:
    settings = Settings.load(
        database_url="sqlite:///:memory:",
    )
    captured: list[dict[str, object]] = []

    def save(name: str, validator: str, response, expected_status: int = 200) -> dict:
        assert response.status_code == expected_status, response.text
        body = response.json()
        captured.append({"name": name, "validator": validator, "response": body})
        return body

    with TestClient(create_app(settings)) as client:
        save("health", "health", client.get("/health"))
        session = save("guest session", "session", client.post("/sessions"), 201)
        headers = {"Authorization": f"Bearer {session['token']}"}
        save("basic catalog", "catalog", client.get("/catalog"))
        req = save(
            "requirement",
            "requirement",
            client.post(
                "/requirements", headers=headers,
                json={"text": "Đà Lạt", "form": {"destinations": ["Đà Lạt"]}},
            ),
        )["requirement"]
        save("saved requirement", "requirement", client.get(f"/requirements/{req['id']}", headers=headers))
        comp = save(
            "comparison",
            "comparison",
            client.post("/comparisons", headers=headers, json={"requirement_id": req["id"]}),
        )["comparison"]
        save("saved comparison", "comparison", client.get(f"/comparisons/{comp['id']}", headers=headers))
        save("guest history", "history", client.get("/history", headers=headers))
        save("guest history detail", "history_detail", client.get(f"/history/{req['id']}", headers=headers))
    return captured


if __name__ == "__main__":
    sys.stdout.buffer.write(json.dumps(collect(), ensure_ascii=False).encode("utf-8"))
