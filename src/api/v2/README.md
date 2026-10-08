# API v2

Comparison chuẩn bị candidates/per-offer trước semantic assessment; NIM lỗi chỉ làm assessment partial, publication/cancel/source gates vẫn giữ. DTO thêm offer eligibility và analysis.semantic_assessment. [Contract](../../../docs/retrieval-semantic-ranking.md).

GET catalog công bố hai trục processing/strength, assessment policy và giới hạn candidate/pair/input/excerpt/timeout để frontend giải thích phạm vi đánh giá.

Provider Supabase dùng catalog read-only qua data_access; Evidence database_record trả record_ref và page fallback, không tạo text fragment giả. SQLite vẫn lưu history/snapshots; [kế hoạch](../../../docs/supabase-tour-integration-plan.md) và [adapter](../../data_access/supabase/README.md).

Trách nhiệm: HTTP DTO/envelope/catalog, proposal/conversation/comparison services và admin. Input: Bearer session/admin, typed form/message/edits/version/idempotency. Output: draft/proposal/full requirement, jobs/events và bảng có evidence.

Workflow: route validate → repository transaction → async worker gọi NIM/gateway → validate domain/decision → terminal publish atomically. Network không nằm trong DB transaction. v1 routes vẫn hoạt động.

Interfaces: `api.store` sở hữu SQLite/leases; `requirements` normalize/ground; `data_access.v2` acquisition; `decision.v2` public comparison/rank/analysis. API không trả token trong refs/logs, không cho chat model tự mutation.

Chi tiết và acceptance: [backend-v2-runtime](../../../docs/backend-v2-runtime.md). Modules `models`, `state`, `service`, `routes`, `admin` tách contract/business/storage/auth để tránh thêm toàn bộ vào app.py.
## Semantic requirements

Form/edit v2 nhận values mới và `answer_clarification`, giữ CAS/expiry/cancel. Worker normalize/finalize v2, lưu trace/issues cùng proposal/revision; confirm chặn issue blocking và user clarification, soft unsupported không block. [Contract](../../../docs/requirements-semantics.md).
