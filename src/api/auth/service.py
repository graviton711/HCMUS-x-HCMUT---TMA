import base64
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
from sqlalchemy import Column, String, Table, insert, select

from api.store import metadata
from domain.common import AppError, now

revoked = Table(
    "revoked_auth_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("expires_at", String),
)


class Identity:
    def __init__(self, store, transport=None):
        self.store, self.settings, self.transport = store, store.settings, transport

    @property
    def url(self):
        return (self.settings.supabase_auth_url or self.settings.supabase_tour_url or "").rstrip("/")

    @property
    def key(self):
        return (
            self.settings.supabase_auth_publishable_key.get_secret_value()
            or self.settings.supabase_tour_publishable_key.get_secret_value()
        )

    @property
    def enabled(self):
        return bool(self.url and self.key)

    async def call(self, method, path, *, token=None, body=None, params=None):
        if not self.enabled:
            raise AppError("AUTH_NOT_CONFIGURED", "Chưa cấu hình Supabase Auth.", 503)
        headers = {"apikey": self.key, "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.auth_timeout_seconds, transport=self.transport, follow_redirects=False
            ) as client:
                response = await client.request(
                    method, self.url + "/auth/v1" + path, headers=headers, json=body, params=params
                )
        except httpx.HTTPError:
            raise AppError("AUTH_UNAVAILABLE", "Dịch vụ tài khoản chưa phản hồi; hãy thử lại.", 503) from None
        if response.status_code == 429:
            raise AppError("AUTH_RATE_LIMITED", "Quá nhiều yêu cầu tài khoản; hãy thử lại sau.", 429)
        if response.status_code in {400, 401, 403, 422}:
            code = "AUTH_INVALID_CREDENTIALS" if path == "/token" else "AUTH_REQUEST_REJECTED"
            if path == "/user" and method == "GET":
                code = "UNAUTHORIZED"
            raise AppError(
                code,
                "Thông tin tài khoản hoặc phiên không hợp lệ. Kiểm tra email, mật khẩu và xác nhận email.",
                401 if code in {"AUTH_INVALID_CREDENTIALS", "UNAUTHORIZED"} else 400,
            )
        if response.status_code not in {200, 201, 204}:
            raise AppError("AUTH_UNAVAILABLE", "Dịch vụ tài khoản chưa sẵn sàng.", 503)
        if response.status_code == 204:
            return {}
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            raise AppError(
                "AUTH_INVALID_RESPONSE", "Dịch vụ tài khoản trả dữ liệu không hợp lệ.", 502
            ) from None

    def return_url(self, value):
        try:
            u = urlsplit(value)
            origin = f"{u.scheme}://{u.netloc}"
            valid = (
                origin in self.settings.cors_origins
                and u.scheme in {"http", "https"}
                and not u.username
                and not u.password
                and u.path == "/auth"
                and not u.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise AppError("INVALID_AUTH_REDIRECT", "Địa chỉ trở về không được phép.")
        return value

    def claims(self, token, user):
        # Only called AFTER the configured Auth server has verified this exact token via GET /user.
        try:
            payload = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            userid = str(UUID(user["id"]))
            sid = str(UUID(claims["session_id"]))
            if (
                claims["sub"] != userid
                or claims["iss"].rstrip("/") != self.url + "/auth/v1"
                or claims["aud"] != "authenticated"
                or type(claims["exp"]) is not int
                or claims["exp"] <= now().timestamp()
                or user.get("is_anonymous")
            ):
                raise ValueError()
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise AppError("UNAUTHORIZED", "Phiên tài khoản không hợp lệ hoặc đã hết hạn.", 401) from None
        with self.store.engine.connect() as c:
            blocked = c.execute(
                select(revoked.c.id).where(revoked.c.id == sid, revoked.c.expires_at > now().isoformat())
            ).scalar()
        if blocked:
            raise AppError("UNAUTHORIZED", "Phiên đã đăng xuất.", 401)
        claims["session_id"] = sid
        return claims

    async def user(self, token):
        if not isinstance(token, str) or len(token) > 16000:
            raise AppError("UNAUTHORIZED", "Phiên không hợp lệ.", 401)
        user = await self.call("GET", "/user", token=token)
        claims = self.claims(token, user)
        return user, claims

    async def owner(self, token):
        user, _ = await self.user(token)
        return "user_" + UUID(user["id"]).hex

    @staticmethod
    def profile(user):
        info = user.get("user_metadata") or {}
        providers = (user.get("app_metadata") or {}).get("providers", [])
        email = str(user.get("email") or "")
        return dict(
            id=str(UUID(user["id"])),
            name=str(info.get("name") or info.get("full_name") or email.split("@")[0])[:80],
            username=email,
            email=email,
            has_password="email" in providers,
            google_email=email if "google" in providers else None,
        )

    async def session(self, data):
        token, refresh = data.get("access_token"), data.get("refresh_token")
        if not isinstance(token, str) or not isinstance(refresh, str) or not refresh:
            raise AppError("AUTH_INVALID_RESPONSE", "Dịch vụ chưa cấp phiên hợp lệ.", 502)
        user, claims = await self.user(token)
        return dict(
            access_token=token, refresh_token=refresh, expires_at=claims["exp"], user=self.profile(user)
        )

    async def config(self):
        if not self.enabled:
            return dict(enabled=False, email_enabled=False, google_enabled=False)
        data = await self.call("GET", "/settings")
        external = data.get("external") or {}
        return dict(
            enabled=True,
            email_enabled=bool(external.get("email", True)),
            google_enabled=bool(external.get("google")),
        )

    async def logout(self, token):
        _, claims = await self.user(token)
        await self.call("POST", "/logout", token=token, params={"scope": "local"})
        with self.store.transaction() as c:
            if not c.execute(select(revoked.c.id).where(revoked.c.id == claims["session_id"])).scalar():
                c.execute(
                    insert(revoked).values(
                        id=claims["session_id"],
                        expires_at=max(
                            now() + timedelta(days=30),
                            datetime.fromtimestamp(claims["exp"], UTC),
                        ).isoformat(),
                    )
                )

    async def google(self, return_url, challenge):
        if not (await self.config())["google_enabled"]:
            raise AppError("GOOGLE_NOT_CONFIGURED", "Google login chưa được cấu hình trên Supabase.", 409)
        return {
            "redirect_url": self.url
            + "/auth/v1/authorize?"
            + urlencode(
                dict(
                    provider="google",
                    redirect_to=self.return_url(return_url),
                    code_challenge=challenge,
                    code_challenge_method="s256",
                )
            )
        }
