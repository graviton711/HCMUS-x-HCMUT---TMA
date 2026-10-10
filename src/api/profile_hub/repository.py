import json
from hashlib import sha256

import httpx
from pydantic import TypeAdapter, ValidationError

from domain.common import AppError, Identifier, instant, now

from .models import PAYLOADS

IDENTIFIER = TypeAdapter(Identifier)


def valid_version(value, minimum=1):
    if type(value) is not int or not minimum <= value <= 9007199254740991:
        raise ValueError("Invalid item version")
    return value


def fingerprint(action):
    return sha256(
        json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class Repository:
    """The verified user's JWT is also the database authorization boundary."""

    def __init__(self, identity, transport=None):
        self.identity, self.transport = identity, transport

    async def call(self, token, path, *, body=None, params=None):
        if not self.identity.enabled:
            raise AppError("PROFILE_HUB_UNAVAILABLE", "Chưa cấu hình Supabase Auth cho hồ sơ cá nhân.", 503)
        try:
            async with httpx.AsyncClient(
                timeout=self.identity.settings.auth_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    "POST" if body is not None else "GET",
                    self.identity.url + "/rest/v1/" + path,
                    headers={
                        "apikey": self.identity.key,
                        "Authorization": "Bearer " + token,
                        "Accept": "application/json",
                    },
                    json=body,
                    params=params,
                )
        except httpx.HTTPError as error:
            raise AppError(
                "PROFILE_HUB_UNAVAILABLE",
                "Chưa kết nối được kho hồ sơ. Giữ nội dung và thử lại.",
                503,
                retryable=True,
            ) from error
        try:
            data = response.json()
        except ValueError:
            data = None
        if not response.is_success:
            code = data.get("code") if isinstance(data, dict) else None
            if code in {"42P01", "PGRST202", "PGRST205", "42883"}:
                raise AppError(
                    "PROFILE_HUB_MIGRATION_REQUIRED",
                    "Kho cá nhân chưa sẵn sàng. Nhóm cần chạy migration Profile Hub trong Supabase Auth.",
                    503,
                )
            if response.status_code in {401, 403}:
                raise AppError(
                    "PROFILE_HUB_ACCESS_DENIED",
                    "Chưa có quyền truy cập kho cá nhân. Kiểm tra đăng nhập và cấu hình migration.",
                    response.status_code,
                )
            raise AppError(
                "PROFILE_HUB_UNAVAILABLE",
                "Kho cá nhân chưa phản hồi. Nội dung đang sửa vẫn được giữ.",
                503,
                retryable=True,
            )
        return data

    def item(self, row):
        try:
            kind = row["kind"]
            value = PAYLOADS[kind].model_validate(row["payload"])
            valid_version(row["version"])
            IDENTIFIER.validate_python(row["item_id"])
            if not isinstance(row["updated_at"], str):
                raise ValueError()
            instant(row["updated_at"])
            if kind == "preferences" and row["item_id"] != "preferences":
                raise ValueError()
            return {
                "id": row["item_id"],
                "kind": kind,
                "version": row["version"],
                "updated_at": row["updated_at"],
                "value": value.model_dump(mode="json"),
            }
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise AppError(
                "PROFILE_HUB_DATA_INVALID",
                "Một mục hồ sơ không đúng định dạng. Nhóm cần kiểm tra kho cá nhân.",
                502,
            ) from error

    async def read(self, token, owner):
        rows = await self.call(
            token,
            "profile_hub_items",
            params={
                "owner_id": "eq." + owner,
                "deleted": "eq.false",
                "select": "kind,item_id,version,payload,updated_at",
                "order": "updated_at.desc",
                "limit": "62",
            },
        )
        if not isinstance(rows, list) or len(rows) > 61:
            raise AppError("PROFILE_HUB_DATA_INVALID", "Kho cá nhân trả dữ liệu không hợp lệ.", 502)
        items = [self.item(row) for row in rows]
        preference = next((i for i in items if i["kind"] == "preferences"), None)
        versions = await self.call(
            token,
            "profile_hub_items",
            params={
                "owner_id": "eq." + owner,
                "kind": "eq.preferences",
                "deleted": "eq.true",
                "select": "version",
            },
        )
        try:
            if not isinstance(versions, list) or len(versions) > 1:
                raise ValueError()
            preference_version = valid_version(
                preference["version"] if preference else versions[0]["version"] if versions else 0, 0
            )
        except (KeyError, TypeError, ValueError) as error:
            raise AppError("PROFILE_HUB_DATA_INVALID", "Phiên bản hồ sơ không hợp lệ.", 502) from error
        return {
            "schema_version": "1",
            "preferences": preference,
            "preferences_version": preference_version,
            "saved_tours": [i for i in items if i["kind"] == "saved_tour"],
            "templates": [i for i in items if i["kind"] == "template"],
        }

    async def receipt(self, token, owner, key, action):
        rows = await self.call(
            token,
            "profile_hub_receipts",
            params={
                "owner_id": "eq." + owner,
                "mutation_key": "eq." + key,
                "select": "request_hash,result,expires_at",
            },
        )
        if not isinstance(rows, list) or len(rows) > 1:
            raise AppError("PROFILE_HUB_DATA_INVALID", "Response hồ sơ không hợp lệ.", 502)
        if rows:
            row = rows[0]
            try:
                if not isinstance(row["expires_at"], str):
                    raise ValueError()
                if instant(row["expires_at"]) <= now():
                    return None
                if not isinstance(row["request_hash"], str) or "result" not in row:
                    raise ValueError()
            except (KeyError, TypeError, ValueError) as error:
                raise AppError("PROFILE_HUB_DATA_INVALID", "Response lưu hồ sơ không hợp lệ.", 502) from error
            if row["request_hash"] != fingerprint(action):
                raise AppError("IDEMPOTENCY_CONFLICT", "Khóa lưu đã được dùng cho nội dung khác.", 409)
            return self.result(row["result"])
        return None

    def result(self, data):
        if not isinstance(data, dict):
            raise AppError("PROFILE_HUB_DATA_INVALID", "Response lưu hồ sơ không hợp lệ.", 502)
        code = data.get("error")
        if code is not None and not isinstance(code, str):
            raise AppError("PROFILE_HUB_DATA_INVALID", "Response lưu hồ sơ không hợp lệ.", 502)
        if code:
            messages = {
                "VERSION_CONFLICT": "Mục này đã thay đổi trên thiết bị khác. Tải lại trước khi lưu.",
                "LIMIT_REACHED": "Đã đạt giới hạn mục lưu. Xóa một mục trước khi thêm.",
                "IDEMPOTENCY_CONFLICT": "Khóa lưu đã được dùng cho nội dung khác.",
            }
            raise AppError(code, messages.get(code, "Không thể lưu hồ sơ."), 409 if code in messages else 422)
        if data.get("deleted") is True:
            try:
                item_id = IDENTIFIER.validate_python(data["item_id"])
                version = valid_version(data["version"])
                if data["kind"] not in PAYLOADS or data["payload"] is not None:
                    raise ValueError()
                return {"deleted": True, "id": item_id, "version": version}
            except (KeyError, TypeError, ValueError) as error:
                raise AppError("PROFILE_HUB_DATA_INVALID", "Response xóa hồ sơ không hợp lệ.", 502) from error
        if data.get("deleted") is not False:
            raise AppError("PROFILE_HUB_DATA_INVALID", "Response lưu hồ sơ không hợp lệ.", 502)
        return {"deleted": False, "item": self.item(data)}

    async def write(self, token, key, action, kind, item_id, expected_version, payload):
        data = await self.call(
            token,
            "rpc/profile_hub_mutate",
            body={
                "p_kind": kind,
                "p_item_id": item_id,
                "p_expected_version": expected_version,
                "p_payload": payload,
                "p_key": key,
                "p_request_hash": fingerprint(action),
            },
        )
        return self.result(data)
