"""Loopback-only browser harness. Hosted identity is stubbed; no user/cloud writes."""

import argparse
import base64
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import uvicorn
from test_v2 import Nim

from api.app import create_app
from api.settings import Settings
from domain.common import now


def create_test_app(auth=False):
    user_id = str(uuid4())
    refreshes, issued, names = {}, {}, {user_id: "Browser tester"}
    url = "https://browser-auth.example.test"

    def hosted(request):
        body = json.loads(request.content) if request.content else {}
        path = request.url.path
        if path.endswith("/settings"):
            return httpx.Response(200, json={"external": {"email": True, "google": False}})
        if path.endswith("/signup"):
            return httpx.Response(200, json={"id": user_id})
        if path.endswith("/token"):
            if request.url.params.get("grant_type") == "password":
                if body.get("email") != "browser@example.test" or body.get("password") != "test-password":
                    return httpx.Response(400, json={})
                sid = str(uuid4())
            else:
                sid = refreshes.get(body.get("refresh_token"))
                if not sid:
                    return httpx.Response(401, json={})
            claims = dict(
                sub=user_id,
                session_id=sid,
                iss=url + "/auth/v1",
                aud="authenticated",
                exp=int((now() + timedelta(hours=1)).timestamp()),
            )
            access = (
                "test." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".test"
            )
            refresh = uuid4().hex
            refreshes[refresh] = sid
            issued[access] = user_id
            return httpx.Response(200, json={"access_token": access, "refresh_token": refresh})
        if path.endswith("/logout"):
            return httpx.Response(204)
        if path.endswith("/user"):
            bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
            uid = issued.get(bearer)
            if not uid:
                return httpx.Response(401, json={})
            if request.method == "PUT":
                names[uid] = body.get("data", {}).get("name", names[uid])
            return httpx.Response(
                200,
                json={
                    "id": uid,
                    "email": "browser@example.test",
                    "user_metadata": {"name": names[uid]},
                    "app_metadata": {"providers": ["email"]},
                },
            )
        return httpx.Response(404, json={})

    return create_app(
        Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            data_provider="fixture",
            nvidia_nim_api="test-only",
            worker_enabled=True,
            supabase_auth_url=url if auth else None,
            supabase_auth_publishable_key="test-only" if auth else "",
            cors_origins=["http://127.0.0.1:15173", "http://127.0.0.1:15174"],
        ),
        nim=Nim(),
        auth_transport=httpx.MockTransport(hosted),
    )


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--port", type=int, default=18000)
    args.add_argument("--auth", action="store_true")
    options = args.parse_args()
    uvicorn.run(create_test_app(options.auth), host="127.0.0.1", port=options.port)
