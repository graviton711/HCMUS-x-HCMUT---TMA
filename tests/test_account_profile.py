"""Real account routes and image validation, isolated from hosted users and Storage."""

import base64
import json
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_auth_history import OTHER, URL, USER, token

from api.app import create_app
from api.auth.avatar import normalize_image, provider_avatar
from api.settings import Settings


class Photos:
    def __init__(self):
        self.meta = {USER: {"name": "Tester", "provider_value": "preserve"}, OTHER: {"name": "Other"}}
        self.files = {}
        self.calls = []
        self.available = True

    def handle(self, request):
        self.calls.append(request)
        assert request.headers["apikey"] == "public-test"
        raw = request.headers.get("authorization", "").removeprefix("Bearer ")
        try:
            uid = json.loads(base64.urlsafe_b64decode(raw.split(".")[1] + "=="))["sub"]
        except Exception:
            return httpx.Response(401, json={})
        if request.url.path == "/auth/v1/user":
            if request.method == "PUT":
                self.meta[uid] = json.loads(request.content)["data"]
            return httpx.Response(
                200,
                json={
                    "id": uid,
                    "email": "test@example.test",
                    "user_metadata": self.meta[uid],
                    "app_metadata": {"providers": ["email"]},
                },
            )
        assert request.url.path.startswith("/storage/v1/object/")
        if not self.available:
            return httpx.Response(403, json={"error": "PRIVATE PROVIDER DETAIL"})
        if request.method == "DELETE":
            assert json.loads(request.content) == {"prefixes": [f"{uid}/avatar.jpg"]}
            self.files.pop(uid, None)
        elif "/sign/" in request.url.path:
            assert request.url.path.endswith(f"/{uid}/avatar.jpg")
            return httpx.Response(
                200, json={"signedURL": f"/object/sign/profile-avatars/{uid}/avatar.jpg?token=test"}
            )
        else:
            assert request.url.path == f"/storage/v1/object/profile-avatars/{uid}/avatar.jpg"
            assert request.headers["content-type"] == "image/jpeg"
            self.files[uid] = request.content
        return httpx.Response(200, json={})


@pytest.fixture
def account(tmp_path):
    hosted = Photos()
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'account.db'}",
            worker_enabled=False,
            data_provider="fixture",
            supabase_auth_url=URL,
            supabase_auth_publishable_key="public-test",
        ),
        auth_transport=httpx.MockTransport(hosted.handle),
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token()
        yield client, hosted


def image():
    output = BytesIO()
    im = Image.new("RGB", (320, 240), (50, 90, 60))
    exif = im.getexif()
    exif[270] = "private camera metadata"
    im.save(output, format="PNG", exif=exif)
    return base64.b64encode(output.getvalue()).decode()


def test_profile_edits_preserve_provider_data_and_omitted_fields(account):
    client, hosted = account
    response = client.patch(
        "/auth/me",
        json={
            "name": "  New name ",
            "phone": "+84 123456",
            "home_city": "Hà Nội",
            "bio": "Thích thiên nhiên",
        },
    )
    assert response.status_code == 200
    profile = response.json()["user"]
    assert profile["name"] == "New name" and profile["phone"] == "+84 123456"
    assert hosted.meta[USER]["provider_value"] == "preserve"
    assert client.patch("/auth/me", json={"name": "Changed"}).json()["user"]["home_city"] == "Hà Nội"
    assert (
        client.patch("/auth/me", json={"name": "Changed", "phone": "", "bio": ""}).json()["user"]["phone"]
        == ""
    )
    for patch in [
        {"name": " "},
        {"name": "X", "phone": "wrong"},
        {"name": "X", "bio": "x" * 281},
        {"name": "X", "role": "admin"},
    ]:
        assert client.patch("/auth/me", json=patch).status_code == 422


def test_avatar_owned_normalized_and_remove_persists(account):
    client, hosted = account
    response = client.post("/auth/me/avatar", json={"image": image()})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["avatar_kind"] == "uploaded"
    assert f"/{USER}/avatar.jpg" in response.json()["user"]["avatar_url"]
    photo = Image.open(BytesIO(hosted.files[USER]))
    assert photo.size == (256, 256) and photo.format == "JPEG" and not photo.getexif()
    client.headers["Authorization"] = "Bearer " + token(OTHER)
    assert client.get("/auth/me").json()["user"]["avatar_url"] is None
    assert client.post("/auth/me/avatar", json={"image": image(), "owner": USER}).status_code == 422
    assert client.post("/auth/me/avatar", json={"image": image()}).status_code == 200
    assert len(hosted.files) == 2
    client.headers["Authorization"] = "Bearer " + token()
    assert client.delete("/auth/me/avatar").json()["user"]["avatar_kind"] == "initials"
    assert USER not in hosted.files and OTHER in hosted.files
    assert client.get("/auth/me").json()["user"]["avatar_url"] is None


def test_bad_images_and_unauthenticated_uploads_never_reach_storage(account):
    client, hosted = account
    for encoded in [
        "not base64",
        base64.b64encode(b"<svg>fake</svg>").decode(),
        base64.b64encode(b"x" * 45001).decode(),
    ]:
        assert client.post("/auth/me/avatar", json={"image": encoded}).status_code == 422
    assert not hosted.files
    client.headers.clear()
    assert client.post("/auth/me/avatar", json={"image": image()}).status_code == 401


def test_storage_failure_keeps_profile_and_tolerates_missing_photo(account):
    client, hosted = account
    hosted.available = False
    response = client.post("/auth/me/avatar", json={"image": image()})
    assert response.status_code == 503 and "002_profile_avatars.sql" in response.text
    assert "PRIVATE PROVIDER" not in response.text and "profile_avatar" not in hosted.meta[USER]
    hosted.meta[USER]["profile_avatar"] = "uploaded"
    assert client.get("/auth/me").status_code == 200
    assert client.get("/auth/me").json()["user"]["avatar_url"] is None


def test_provider_url_validation_and_pixel_limits():
    assert provider_avatar("https://lh3.googleusercontent.com/a/photo")
    for value in [
        "javascript:alert(1)",
        "https://googleusercontent.com.evil.test/a",
        "https://x:secret@lh3.googleusercontent.com/a",
        "https://lh3.googleusercontent.com:444/a",
    ]:
        assert provider_avatar(value) is None
    output = BytesIO()
    Image.new("1", (3000, 2000)).save(output, format="PNG")
    with pytest.raises(Exception, match="Ảnh không hợp lệ"):
        normalize_image(base64.b64encode(output.getvalue()).decode())
