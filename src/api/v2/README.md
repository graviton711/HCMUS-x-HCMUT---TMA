# API v2

Trách nhiệm: HTTP DTO/envelope/catalog, proposal/conversation/comparison services và admin. Input: Bearer session/admin, typed form/message/edits/version/idempotency. Output: draft/proposal/full requirement, jobs/events và bảng có evidence.

Workflow: route validate → repository transaction → async worker gọi NIM/gateway → validate domain/decision → terminal publish atomically. Network không nằm trong DB transaction. v1 routes vẫn hoạt động.

Interfaces: `api.store` sở hữu SQLite/leases; `requirements` normalize/ground; `data_access.v2` acquisition; `decision.v2` public comparison/rank/analysis. API không trả token trong refs/logs, không cho chat model tự mutation.

Chi tiết và acceptance: [backend-v2-runtime](../../../docs/backend-v2-runtime.md). Modules `models`, `state`, `service`, `routes`, `admin` tách contract/business/storage/auth để tránh thêm toàn bộ vào app.py.
