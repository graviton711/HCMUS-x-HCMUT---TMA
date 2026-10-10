"""Bounded account photos; storage paths are derived from the verified identity."""

import base64
import binascii
import warnings
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from domain.common import AppError

BUCKET = "profile-avatars"


def normalize_image(encoded):
    try:
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > 45000:
            raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 4_000_000:
                    raise ValueError()
                source.load()
                photo = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (256, 256))
                output = BytesIO()
                photo.save(output, format="JPEG", quality=80, optimize=True)
                return output.getvalue()
    except (
        ValueError,
        binascii.Error,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise AppError("INVALID_AVATAR", "Ảnh không hợp lệ. Chọn ảnh JPG, PNG hoặc WebP khác.") from None


def provider_avatar(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme == "https"
            and not url.username
            and not url.password
            and url.port in {None, 443}
            and url.hostname
            and (url.hostname == "googleusercontent.com" or url.hostname.endswith(".googleusercontent.com"))
        ):
            return value
    except ValueError:
        pass
    return None


async def storage(identity, bearer, method, path, *, body=None, content=None):
    headers = {"apikey": identity.key, "Authorization": f"Bearer {bearer}"}
    if content is not None:
        headers.update({"Content-Type": "image/jpeg", "x-upsert": "true", "cache-control": "0"})
    try:
        async with httpx.AsyncClient(
            timeout=identity.settings.auth_timeout_seconds,
            transport=identity.transport,
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method, identity.url + "/storage/v1" + path, headers=headers, json=body, content=content
            )
    except httpx.HTTPError:
        raise AppError("AVATAR_UNAVAILABLE", "Chưa lưu được ảnh đại diện; hãy thử lại.", 503) from None
    if response.status_code not in {200, 201, 204}:
        raise AppError(
            "AVATAR_STORAGE_UNAVAILABLE",
            "Kho ảnh chưa sẵn sàng. Chạy migration 002_profile_avatars.sql trong project Supabase Auth, rồi thử lại.",
            503,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        raise AppError("AVATAR_UNAVAILABLE", "Kho ảnh trả dữ liệu không hợp lệ.", 502) from None


def path_for(user):
    return f"{UUID(user['id'])}/avatar.jpg"


async def public_profile(identity, user, bearer):
    profile = identity.profile(user)
    info = user.get("user_metadata") or {}
    choice = info.get("profile_avatar")
    profile["avatar_url"] = None
    profile["avatar_kind"] = "initials"
    if choice == "uploaded":
        profile["avatar_kind"] = "uploaded"
        try:
            result = await storage(
                identity, bearer, "POST", f"/object/sign/{BUCKET}/{path_for(user)}", body={"expiresIn": 3600}
            )
            signed = result.get("signedURL") if isinstance(result, dict) else None
            # Only accept the expected relative Storage path, never a provider-selected host.
            prefix = f"/object/sign/{BUCKET}/{path_for(user)}?"
            if isinstance(signed, str) and signed.startswith(prefix):
                profile["avatar_url"] = identity.url + "/storage/v1" + signed
        except AppError:
            pass  # A missing image/bucket must never prevent account login.
    elif choice != "initials":
        profile["avatar_url"] = provider_avatar(info.get("avatar_url") or info.get("picture"))
        if profile["avatar_url"]:
            profile["avatar_kind"] = "google"
    return profile
