"""Stub only hosted identity; exercise real app ownership and durable history."""

import base64
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update
from test_v2 import form

from api.app import create_app
from api.settings import Settings
from api.store import dump, jobs, resources
from api.v2 import state
from domain.common import instant, now

URL = "https://identity.example.test"
USER = str(uuid4())
OTHER = str(uuid4())
SID = str(uuid4())


def token(user=USER, sid=SID, **overrides):
    claims = dict(
        sub=user,
        session_id=sid,
        iss=URL + "/auth/v1",
        aud="authenticated",
        exp=int((now() + timedelta(hours=1)).timestamp()),
        **{},
    )
    claims.update(overrides)
    return (
        "test."
        + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        + ".verified-by-stub"
    )


class Hosted:
    def __init__(self):
        self.calls = []
        self.google = False

    def handle(self, request):
        self.calls.append(request)
        path = request.url.path
        assert request.headers["apikey"] == "publishable-test"
        body = json.loads(request.content) if request.content else {}
        if path.endswith("/settings"):
            return httpx.Response(200, json={"external": {"email": True, "google": self.google}})
        if path.endswith("/signup"):
            return httpx.Response(200, json={"id": USER})
        if path.endswith("/token"):
            if body.get("password") == "invalid":
                return httpx.Response(400, json={"message": "DO NOT LEAK PROVIDER DETAIL"})
            return httpx.Response(200, json={"access_token": token(), "refresh_token": "rotated-test"})
        if path.endswith("/logout"):
            assert request.url.params["scope"] == "local"
            return httpx.Response(204)
        if path.endswith("/user"):
            raw = request.headers.get("authorization", "").removeprefix("Bearer ")
            try:
                c = json.loads(base64.urlsafe_b64decode(raw.split(".")[1] + "=="))
            except Exception:
                return httpx.Response(401, json={})
            return httpx.Response(
                200,
                json={
                    "id": c["sub"],
                    "email": "test@example.test",
                    "user_metadata": {"name": "Test"},
                    "app_metadata": {"providers": ["email"]},
                },
            )
        raise AssertionError(path)


@pytest.fixture
def identity(tmp_path):
    hosted = Hosted()
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'auth.db'}",
            data_provider="fixture",
            worker_enabled=False,
            supabase_auth_url=URL,
            supabase_auth_publishable_key="publishable-test",
        ),
        auth_transport=httpx.MockTransport(hosted.handle),
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token()
        yield client, app, hosted


def payload(response, status=200):
    assert response.status_code == status, response.text
    return response.json().get("data", response.json())


def test_register_confirmation_login_refresh_and_logout(identity):
    client, app, hosted = identity
    assert payload(client.get("/auth/config")) == dict(enabled=True, email_enabled=True, google_enabled=False)
    result = payload(
        client.post(
            "/auth/register",
            json=dict(
                email="test@example.test",
                name="Test",
                password="test-password",
                password_confirmation="test-password",
                return_url="http://127.0.0.1:5173/auth",
            ),
        )
    )
    assert result["status"] == "confirmation_required" and "access_token" not in result
    login = payload(
        client.post("/auth/login", json=dict(email="test@example.test", password="test-password"))
    )
    assert login["user"]["id"] == USER and login["refresh_token"] == "rotated-test"
    assert (
        payload(client.post("/auth/refresh", json={"refresh_token": "test-refresh"}))["access_token"]
        == token()
    )
    assert payload(client.get("/auth/me"))["user"]["email"] == "test@example.test"
    assert payload(client.patch("/auth/me", json={"name": "Changed"}))["user"]["id"] == USER
    # Even an unusually long-lived provider JWT stays revoked through its expiry.
    long_expiry = int((now() + timedelta(days=40)).timestamp())
    client.headers["Authorization"] = "Bearer " + token(exp=long_expiry)
    assert payload(client.post("/auth/logout"))["status"] == "signed_out"
    assert client.get("/v2/history").status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": "test-refresh"}).status_code == 401
    with app.state.store.engine.connect() as c:
        from api.auth.service import revoked

        row = c.execute(select(revoked)).mappings().first()
        assert row and instant(row["expires_at"]).timestamp() >= long_expiry


@pytest.mark.parametrize(
    "overrides",
    [dict(iss="https://another.test/auth/v1"), dict(exp=1), dict(aud="anon"), dict(session_id="bad")],
)
def test_rejects_invalid_account_claims_after_provider_verification(identity, overrides):
    client, _, _ = identity
    client.headers["Authorization"] = "Bearer " + token(**overrides)
    assert client.get("/v2/history").status_code == 401


def test_errors_redirects_and_provider_flags(identity):
    client, _, hosted = identity
    failed = client.post("/auth/login", json={"email": "test@example.test", "password": "invalid"})
    assert failed.status_code == 401 and "DO NOT LEAK" not in failed.text
    assert (
        client.post(
            "/auth/register",
            json=dict(
                email="test@example.test",
                name="Test",
                password="test-password",
                password_confirmation="test-password",
                return_url="https://evil.test/auth",
            ),
        ).status_code
        == 422
    )
    body = dict(return_url="http://127.0.0.1:5173/auth?oauth_state=test", code_challenge="a" * 43)
    assert client.post("/auth/google/start", json=body).status_code == 409
    hosted.google = True
    assert "/authorize?" in payload(client.post("/auth/google/start", json=body))["redirect_url"]
    assert (
        payload(client.post("/auth/google/exchange", json={"code": "test-code", "code_verifier": "a" * 43}))[
            "user"
        ]["id"]
        == USER
    )
    assert (
        client.post("/auth/login", json={"email": "bad", "password": "private-test-password"}).status_code
        == 422
    )
    assert (
        "private-test-password"
        not in client.post("/auth/login", json={"email": "bad", "password": "private-test-password"}).text
    )


def test_history_owner_paging_cas_archive_and_guest_link(identity):
    client, app, _ = identity
    a = payload(client.post("/v2/requirements", json=form()), 201)["id"]
    b = payload(client.post("/v2/requirements", json=form()), 201)["id"]
    first = payload(client.get("/v2/history?limit=1"))
    assert len(first["items"]) == 1 and first["next_cursor"]
    second = payload(client.get("/v2/history", params={"limit": 1, "after": first["next_cursor"]}))
    assert {first["items"][0]["requirement_id"], second["items"][0]["requirement_id"]} == {a, b}
    assert client.get("/v2/history?after=invalid").status_code == 422
    detail = payload(client.get(f"/v2/history/{a}"))
    assert detail["requirement"]["id"] == a and detail["transcript"] == {"items": [], "limited": False}
    edited = payload(
        client.patch(
            f"/v2/history/{a}",
            json={"expected_version": 0, "title": "Japan", "pinned": True},
            headers={"Idempotency-Key": "metadata-test"},
        )
    )
    assert edited["version"] == 1 and edited["pinned"]
    assert (
        payload(
            client.patch(
                f"/v2/history/{a}",
                json={"expected_version": 0, "title": "Japan", "pinned": True},
                headers={"Idempotency-Key": "metadata-test"},
            )
        )["version"]
        == 1
    )
    assert client.patch(f"/v2/history/{a}", json={"expected_version": 0, "title": "Old"}).status_code == 409
    client.headers["Authorization"] = "Bearer " + token(sid=str(uuid4()))
    assert payload(client.get(f"/v2/history/{a}"))["title"] == "Japan"
    client.headers["Authorization"] = "Bearer " + token(user=OTHER)
    assert client.get(f"/v2/history/{a}").status_code == 404
    assert payload(client.get("/v2/history"))["items"] == []
    client.headers["Authorization"] = "Bearer " + token()
    payload(client.post(f"/v2/history/{a}/archive", json={"expected_version": 1}))
    assert [x["requirement_id"] for x in payload(client.get("/v2/history"))["items"]] == [b]
    guest = payload(client.post("/v2/sessions"), 201)
    client.headers["Authorization"] = "Bearer " + guest["token"]
    guest_id = payload(client.post("/v2/requirements", json=form()), 201)["id"]
    owner = app.state.store.authenticate(guest["token"])
    with app.state.store.transaction() as c:
        jid = app.state.store.add_job(
            c, owner, guest_id, "v2_message", {"body": {"text": "Hello", "client_message_id": "message-test"}}
        )
    client.headers["Authorization"] = "Bearer " + token()
    assert (
        client.post("/v2/history/link-session", json={"anonymous_token": guest["token"]}).status_code == 409
    )
    with app.state.store.transaction() as c:
        c.execute(update(jobs).where(jobs.c.id == jid).values(status="succeeded"))
        c.execute(
            insert(state.messages).values(
                owner=owner,
                requirement_id=guest_id,
                client_message_id="message-test",
                created_at=now().isoformat(),
                payload=dump({"result": {"answer": {"text": "Answer"}}}),
            )
        )
    linked = payload(client.post("/v2/history/link-session", json={"anonymous_token": guest["token"]}))
    assert linked["linked_requirements"] == 1
    assert (
        payload(client.post("/v2/history/link-session", json={"anonymous_token": guest["token"]})) == linked
    )
    assert [x["text"] for x in payload(client.get(f"/v2/history/{guest_id}"))["transcript"]["items"]] == [
        "Hello",
        "Answer",
    ]
    client.headers["Authorization"] = "Bearer " + guest["token"]
    assert client.get(f"/v2/requirements/{guest_id}").status_code == 401
    client.headers["Authorization"] = "Bearer " + token(user=OTHER)
    assert (
        client.post("/v2/history/link-session", json={"anonymous_token": guest["token"]}).status_code == 401
    )
    client.headers["Authorization"] = "Bearer " + token()
    with app.state.store.transaction() as c:
        c.execute(update(resources).values(created_at=(now() - timedelta(days=9)).isoformat()))
    app.state.store.purge()
    assert payload(client.get("/v2/history"))["items"] == []
