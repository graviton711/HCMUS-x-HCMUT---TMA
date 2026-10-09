from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import Field, SecretStr, model_validator

from domain.common import AppError, Model


class Login(Model):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: SecretStr

    @model_validator(mode="after")
    def size(self):
        if not 1 <= len(self.password.get_secret_value()) <= 1024:
            raise ValueError("Invalid password length")
        return self


class Register(Login):
    name: str = Field(min_length=1, max_length=80)
    password_confirmation: SecretStr
    return_url: str

    @model_validator(mode="after")
    def confirmation(self):
        if len(self.password.get_secret_value()) < 8 or self.password != self.password_confirmation:
            raise ValueError("Password confirmation mismatch or too short")
        return self


class Refresh(Model):
    refresh_token: SecretStr = Field(min_length=1, max_length=4096)


class ProfileEdit(Model):
    name: str = Field(min_length=1, max_length=80)


class GoogleStart(Model):
    return_url: str
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class GoogleExchange(Model):
    code: str = Field(min_length=1, max_length=1024)
    code_verifier: SecretStr

    @model_validator(mode="after")
    def verifier(self):
        import re

        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", self.code_verifier.get_secret_value()):
            raise ValueError("Invalid PKCE verifier")
        return self


def router(identity, limits):
    routes = APIRouter(prefix="/auth", tags=["account"])

    def token(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer "):
            raise AppError("UNAUTHORIZED", "Cần đăng nhập tài khoản.", 401)
        return authorization[7:]

    def rate(request):
        limits.check(f"auth:{request.client.host if request.client else 'local'}", 30)

    @routes.get("/config")
    async def config():
        return await identity.config()

    @routes.post("/login")
    async def login(body: Login, request: Request):
        rate(request)
        data = await identity.call(
            "POST",
            "/token",
            params={"grant_type": "password"},
            body={"email": body.email, "password": body.password.get_secret_value()},
        )
        return await identity.session(data)

    @routes.post("/register")
    async def register(body: Register, request: Request):
        rate(request)
        data = await identity.call(
            "POST",
            "/signup",
            params={"redirect_to": identity.return_url(body.return_url)},
            body={
                "email": body.email,
                "password": body.password.get_secret_value(),
                "data": {"name": body.name},
            },
        )
        if not data.get("access_token"):
            return {
                "status": "confirmation_required",
                "message": "Kiểm tra email để xác nhận tài khoản, rồi đăng nhập.",
            }
        return await identity.session(data)

    @routes.post("/refresh")
    async def refresh(body: Refresh, request: Request):
        rate(request)
        data = await identity.call(
            "POST",
            "/token",
            params={"grant_type": "refresh_token"},
            body={"refresh_token": body.refresh_token.get_secret_value()},
        )
        return await identity.session(data)

    @routes.get("/me")
    async def me(authorization: Annotated[str | None, Header()] = None):
        user, _ = await identity.user(token(authorization))
        return {"user": identity.profile(user)}

    @routes.patch("/me")
    async def update(body: ProfileEdit, authorization: Annotated[str | None, Header()] = None):
        bearer = token(authorization)
        user, _ = await identity.user(bearer)
        await identity.call(
            "PUT",
            "/user",
            token=bearer,
            body={"data": {**(user.get("user_metadata") or {}), "name": body.name}},
        )
        user, _ = await identity.user(bearer)
        return {"user": identity.profile(user)}

    @routes.post("/logout")
    async def logout(authorization: Annotated[str | None, Header()] = None):
        await identity.logout(token(authorization))
        return {"status": "signed_out"}

    @routes.post("/google/start")
    async def google_start(body: GoogleStart, request: Request):
        rate(request)
        return await identity.google(body.return_url, body.code_challenge)

    @routes.post("/google/exchange")
    async def google_exchange(body: GoogleExchange, request: Request):
        rate(request)
        data = await identity.call(
            "POST",
            "/token",
            params={"grant_type": "pkce"},
            body={"auth_code": body.code, "code_verifier": body.code_verifier.get_secret_value()},
        )
        return await identity.session(data)

    return routes
