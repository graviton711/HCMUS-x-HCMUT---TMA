# API v2

What-if là async resource riêng sau comparison, có owner/revision/idempotency/job/source guards; apply scenario chỉ tạo proposal qua typed edits/CAS, không auto-confirm/search. [Contract và limits](../what-if-analysis.md).

Create/parse/edit/discard/confirm/comparison dùng chung [personalized core policy](../../requirements/personalized-requirement-policy.md). Form chưa đủ trả draft/proposal, form đủ trả 201 confirmed. Readiness/completeness được tính lại trước mutation/search, không tin payload cũ. Catalog và lỗi 409 có thông tin để FE bổ sung field; URL-only miễn core.

Comparison chuẩn bị candidates/per-offer trước semantic assessment; NIM lỗi chỉ làm assessment partial, publication/cancel/source gates vẫn giữ. DTO thêm offer eligibility và analysis.semantic_assessment. [Contract](../../decision/retrieval-semantic-ranking.md).

GET catalog công bố hai trục processing/strength, assessment policy và giới hạn candidate/pair/input/excerpt/timeout để frontend giải thích phạm vi đánh giá.

Provider Supabase dùng catalog read-only qua data_access; Evidence database_record trả record_ref và page fallback, không tạo text fragment giả. SQLite vẫn lưu history/snapshots; [kế hoạch](../../data_access/supabase-tour-integration-plan.md) và [adapter](../../data_access/supabase/README.md).

Trách nhiệm: HTTP DTO/envelope/catalog, proposal/conversation/comparison services và admin. Input: Bearer session/admin, typed form/message/edits/version/idempotency. Output: draft/proposal/full requirement, jobs/events và bảng có evidence.

Workflow: route validate → repository transaction → async worker gọi NIM/gateway → validate domain/decision → terminal publish atomically. Network không nằm trong DB transaction. v1 routes vẫn hoạt động.

Interfaces: `api.store` sở hữu SQLite/leases; `requirements` normalize/ground; `data_access.v2` acquisition; `decision.v2` public comparison/rank/analysis. API không trả token trong refs/logs, không cho chat model tự mutation.

Chi tiết và acceptance: [backend-v2-runtime](../backend-v2-runtime.md). Modules `models`, `state`, `service`, `routes`, `admin` tách contract/business/storage/auth để tránh thêm toàn bộ vào app.py.
## Semantic requirements

Form/edit v2 nhận values mới và `answer_clarification`, giữ CAS/expiry/cancel. Worker normalize/finalize v2, lưu trace/issues cùng proposal/revision; confirm chặn issue blocking và user clarification, soft unsupported không block. [Contract](../../requirements/requirements-semantics.md).
# Catalog validation

[Policy](../../data_access/supabase/catalog-validation-policy.md): cell thêm verification `catalog_validated`; evidence endpoint trả receipt và link page database_record. Registry hiệu dụng giao với config trust hiện hành, không tự nâng quyền từ persisted capability. Freshness config tường minh overlay bootstrap/persisted registry; pause/revocation vẫn giữ hiệu lực. So sánh/what-if kiểm lại source policy trước publish sau await.
