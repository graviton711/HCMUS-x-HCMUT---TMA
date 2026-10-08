# Contracts — JSON Schema sinh từ models backend

> File `.schema.json` do `uv run tour-backend export-schemas` sinh ra. **Không sửa tay.** Sửa model Python rồi export lại. Export không đọc `.env`, không mở DB, không chạy server.

## Mục lục theo người dùng

| Nhóm | Schema | Version | Trạng thái |
|---|---|---|---|
| Frontend gọi API v1 | `CreateRequirement`, `PatchRequirement`, `Requirement`, `CreateComparison` | 1.0 | Live (`/v1`) |
| Frontend gọi API v2 | `CreateRequirementV2`, `RequirementV2`, `CreateProposal`, `ConfirmProposal`, `DiscardChanges`, `CreateComparisonV2`, `ComparisonV2`, `ConversationMessage`, `JobEvent` | 2.0-draft | Live (`/v2`) |
| Contacts/admin | `ContactCreate`, `ContactPatch`, `SourceCreate`, `SourcePatch`, `SourceApproval`, `SourceRefresh`, `ExpectedVersion` | 2.0-draft | Live (`/v2` admin) |
| Nội bộ LLM | `Extraction`, `InitialExtractionV2`, `UpdateExtractionV2`, `AssessmentBatch`, `SemanticReport` | 1.0 / 2.0-draft | Nội bộ, không phải request public |
| What-if | `CreateWhatIf`, `WhatIfAnalysis`, `ApplyWhatIf` | 2.0-draft | Live (`/v2`), xem [policy](../docs/what-if-analysis.md) |

## Cửa crawler (backend đọc Supabase catalog)

Envelope duy nhất đang dùng: **`v2/CrawlResultV2.schema.json`** (kế thừa v1, thêm `semantic_fields`, `retrieval/offer_coverage`).

| Schema | Vai trò | Trạng thái |
|---|---|---|
| `CrawlRequest`, `SourceCapability` | Backend đặt hàng crawl / khai báo nguồn | Live, dùng cho cả v1 và v2 |
| `v2/CrawlResultV2` | Envelope crawler trả qua Supabase reader (`src/data_access/supabase/adapter.py`) | **Live — theo cái này khi nối adapter** |
| `v2/CatalogFieldProof` | Object proof lẻ trong `evidence.fields` JSONB từng record (nâng `database_record` → `supplier_published`) | Live, phạm vi hẹp, không thay envelope |
| `CrawlResult` (v1 root) | Đường fixture/legacy (`DataGateway` mặc định, worker v1, decision engine) | Giữ cho tương thích, không dùng cho catalog mới |

Chi tiết: [reader/proof contract](../src/data_access/supabase/README.md), [policy catalog trust](../docs/catalog-validation-policy.md), [kế hoạch Supabase](../docs/supabase-tour-integration-plan.md).

## Ghi chú version

- V1 (`schema_version=1.0`) và V2 (`2.0-draft`) phục vụ song song (`/health` khai báo `["v1","v2"]`); v2 bổ sung, không thay v1.
- `FactV2` thêm verification `catalog_validated`; `EvidenceV2.database_record` không phải website quote. Consumer v2 nhận enum mới, không hiển thị như independent verification.
- HTTP response envelope `{schema_version,request_id,data}`, lỗi dùng `error`; GET comparison đặt ComparisonV2 trong `data.result`. [Request walkthrough](../examples/backend-v2.md), [runtime](../docs/backend-v2-runtime.md).
- Semantic v2 policy `requirements-v2.2`, typed entities/temporal/qualitative; frontend render theo `value.kind` mới; server đọc stored v2 cũ, không re-parse lịch sử. [Test ca Tết](../examples/backend-semantic-v2.md), [contract](../docs/requirements-semantics.md).
- Fixtures trong `examples/protocol-v2` là mẫu thiết kế, không phải response thật của server.
