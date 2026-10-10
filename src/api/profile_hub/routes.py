import json
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Header, Request

from api.v2.routes import envelope
from domain.common import AppError, now

from .models import DeleteItem, EditTour, PreferencesWrite, SavedTour, SaveTour, TemplateWrite
from .repository import Repository


def router(identity, store, limits, transport=None):
    api = APIRouter(prefix="/v2/profile-hub", tags=["Profile Hub"])
    repo = Repository(identity, transport)

    async def account(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer "):
            raise AppError("UNAUTHORIZED", "Đăng nhập để lưu dữ liệu cá nhân.", 401)
        bearer = authorization[7:]
        user, _ = await identity.user(bearer)
        limits.check("hub:" + user["id"], 120)
        return bearer, user["id"]

    def mutation_key(value):
        if not value or len(value) > 128 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise AppError("IDEMPOTENCY_KEY_REQUIRED", "Cần khóa lưu hợp lệ.", 422)
        return value

    async def mutate(account, request, key, body, kind, item_id, make_payload):
        token, owner = account
        key = mutation_key(key)
        action = {"path": request.url.path, "body": body.model_dump(mode="json")}
        prior = await repo.receipt(token, owner, key, action)
        if prior is not None:
            return envelope(request, prior)
        payload = await make_payload(token, owner)
        return envelope(
            request, await repo.write(token, key, action, kind, item_id, body.expected_version, payload)
        )

    @api.get("")
    async def read(request: Request, actor: Annotated[tuple, Depends(account)]):
        return envelope(request, await repo.read(*actor))

    @api.post("/preferences")
    async def preferences(
        request: Request,
        body: PreferencesWrite,
        actor: Annotated[tuple, Depends(account)],
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        async def payload(token, owner):
            return body.preferences.model_dump(mode="json")

        return await mutate(actor, request, idempotency_key, body, "preferences", "preferences", payload)

    @api.post("/templates")
    async def template(
        request: Request,
        body: TemplateWrite,
        actor: Annotated[tuple, Depends(account)],
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        async def payload(token, owner):
            return body.template.model_dump(mode="json")

        return await mutate(actor, request, idempotency_key, body, "template", body.item_id, payload)

    @api.post("/saved-tours")
    async def save(
        request: Request,
        body: SaveTour,
        actor: Annotated[tuple, Depends(account)],
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        token, owner = actor
        key = mutation_key(idempotency_key)
        action = {"path": request.url.path, "body": body.model_dump(mode="json")}
        prior = await repo.receipt(token, owner, key, action)
        if prior is not None:
            return envelope(request, prior)
        account_owner = "user_" + owner.replace("-", "")
        resource = store.resource(account_owner, body.comparison_id, kind="comparison_v2")
        comparison = json.loads(resource["payload"])
        result = comparison.get("result")
        if not result or result.get("origin") != "source":
            raise AppError(
                "TOUR_SNAPSHOT_REQUIRED", "Chỉ lưu tour có dữ liệu nguồn từ lượt đối chiếu đã hoàn tất.", 422
            )
        column = next((c for c in result["columns"] if c["id"] == body.column_id), None)
        if not column or not column.get("tour_snapshot_id"):
            raise AppError("NOT_FOUND", "Không tìm thấy tour trong lượt đối chiếu này.", 404)
        rows = {r["id"]: r["field"] for r in result["rows"]}
        cells = {
            rows.get(c["row_id"]): c
            for c in result["cells"]
            if c["column_id"] == body.column_id and c["data_state"] == "present"
        }
        date = cells.get("departure_date", {}).get("value")
        price = cells.get("listed_price_quotes", {}).get("value")
        quotes = price if isinstance(price, list) else []
        quote = next((q for q in quotes if isinstance(q, dict) and q.get("basis") == "per_adult"), None)
        label = None
        if quote:
            label = (
                ("Từ " if quote.get("kind") == "from" else "")
                + str(quote.get("amount"))
                + " "
                + str(quote.get("currency"))
                + " / người lớn · giá tour niêm yết"
            )
        snapshot = SavedTour(
            title=(column.get("title") or "Tour chưa có tên")[:500],
            supplier=(column.get("supplier") or {}).get("display_name"),
            url=column["canonical_url"],
            comparison_id=body.comparison_id,
            column_id=body.column_id,
            offer_snapshot_id=column.get("selected_offer_snapshot_id"),
            departure_date=date if isinstance(date, str) else None,
            price_label=label,
            evaluated_at=result["evaluated_at"],
            saved_at=now().isoformat(),
            status_at_save="recommended"
            if body.column_id in result["recommendations"]["candidate_ids"]
            else "needs_verification"
            if body.column_id in result["recommendations"]["needs_verification"]
            else "reference",
        )
        item_id = str(uuid5(NAMESPACE_URL, snapshot.url))
        # Re-saving updates the observation but preserves personal annotations.
        state = await repo.read(token, owner)
        old = next((i for i in state["saved_tours"] if i["id"] == item_id), None)
        expected = body.expected_version
        if old:
            snapshot.note, snapshot.collection = old["value"]["note"], old["value"]["collection"]
        elif expected == 0:
            tombstone = await repo.call(
                token,
                "profile_hub_items",
                params={
                    "owner_id": "eq." + owner,
                    "kind": "eq.saved_tour",
                    "item_id": "eq." + item_id,
                    "deleted": "eq.true",
                    "select": "version",
                },
            )
            if tombstone:
                expected = tombstone[0]["version"]
        return envelope(
            request,
            await repo.write(
                token, key, action, "saved_tour", item_id, expected, snapshot.model_dump(mode="json")
            ),
        )

    @api.post("/saved-tours/{item_id}/edit")
    async def edit(
        request: Request,
        item_id: str,
        body: EditTour,
        actor: Annotated[tuple, Depends(account)],
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        async def payload(token, owner):
            state = await repo.read(token, owner)
            old = next((i for i in state["saved_tours"] if i["id"] == item_id), None)
            if not old:
                raise AppError("NOT_FOUND", "Không tìm thấy tour lưu.", 404)
            return {**old["value"], "note": body.note, "collection": body.collection}

        return await mutate(actor, request, idempotency_key, body, "saved_tour", item_id, payload)

    @api.post("/items/delete")
    async def delete(
        request: Request,
        body: DeleteItem,
        actor: Annotated[tuple, Depends(account)],
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        async def payload(token, owner):
            return None

        return await mutate(actor, request, idempotency_key, body, body.kind, body.item_id, payload)

    return api
