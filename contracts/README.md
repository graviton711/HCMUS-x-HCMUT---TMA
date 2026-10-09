# Contracts generated from backend models

V2 contracts xuất vào [v2](v2/) từ models/runtime, giữ schemas v1 tại thư mục này. `schema_version=2.0-draft` theo mẫu đã duyệt. Schema validation không thay kiểm tra ownership/reference/version/expiry/AST/offer/evidence ở service.

RequirementV2/Proposal/ComparisonV2 thêm `completeness` policy `personalized-core-v1` và readiness `can_confirm/can_search`. Structured DTO được phép thiếu core để tạo draft; confirm/search kiểm nội dung qua validator dùng chung. Field states liên kết conditions/questions, không tạo values để FE tự suy. GET revision cũ tính lại metadata từ values đã lưu, không gọi NIM hoặc ghi lại history. [Contract mới](../docs/personalized-requirement-policy.md).

Run `uv run tour-backend export-schemas` after model changes. Do not edit generated JSON by hand.

Supabase v2 bổ sung CatalogFieldProof schema cho crawler và record provenance trong CrawlResultV2/ComparisonV2. EvidenceV2.database_record không là website quote; catalog preview fields không thêm hard metric. V1 schemas giữ nguyên.
Export hiện có **27 schemas v2**; CatalogFieldProof là entry trong `evidence.fields` JSONB của từng record, không phải request frontend. [Reader/proof contract](../src/data_access/supabase/README.md).
Export không đọc `.env`, mở application DB hoặc chạy server.

- Frontend: `CreateRequirement`, `PatchRequirement`, `CreateComparison`, `Requirement`.
- Crawler: `CrawlRequest`, `CrawlResult`, `SourceCapability`.
- Internal LLM adapter: `Extraction` (not the public frontend request).

Các schema trên là v1 (`schema_version=1.0`). V2 gồm:

- Public: `CreateRequirementV2`, `RequirementV2`, `CreateProposal`, `Proposal`, `ConfirmProposal`, `ProposalVersion`, `DiscardChanges`, `CreateComparisonV2`, `ComparisonV2`, `ConversationMessage`, `JobEvent`.
- Contacts/admin: `ContactCreate`, `ContactPatch`, `SourceCreate`, `SourcePatch`, `ExpectedVersion`, `SourceApproval`, `SourceRefresh`.
- Internal NIM: `InitialExtractionV2`, `UpdateExtractionV2`; không gửi extraction DTO như request frontend.
- Semantic assessment: `AssessmentBatch` là NIM output; `SemanticReport` là phần backend đã kiểm tra tại `analysis.semantic_assessment`. Assessment không sửa hard evaluations. Columns thêm per-offer assessments/eligible IDs và `offers_complete`; crawler thêm retrieval diagnostics/offer coverage. [Flow và policy](../docs/retrieval-semantic-ranking.md).
- Crawler response extension: `v2/CrawlResultV2.schema.json` giữ envelope `schema_version=1.0` của transport hiện tại, thêm optional `TourSnapshotV2.semantic_fields` evidence-bound cho tour_type/route/nature. V1 response cũ vẫn đọc được. Không thêm endpoint crawler v2 giả.

Semantic v2 có policy `requirements-v2.2`: typed entities/temporal/qualitative/issue/answer; API envelope vẫn `2.0-draft`. Frontend cần render theo `value.kind` mới; server đọc được stored v2 values cũ, không tự re-parse lịch sử. [Test ca Tết](../examples/backend-semantic-v2.md), [contract/policies](../docs/requirements-semantics.md).

HTTP response có envelope `{schema_version,request_id,data}`, lỗi dùng `error`; GET comparison đặt ComparisonV2 trong `data.result`. [Request walkthrough](../examples/backend-v2.md), [runtime limitations](../docs/backend-v2-runtime.md). Fixtures prototype trong `examples/protocol-v2` là mẫu thiết kế, không phải generated server responses.
## What-if contracts

`CreateWhatIf`, `WhatIfAnalysis`, `ApplyWhatIf` bổ sung resource async có baseline/scenarios/rank changes/witnesses/explicit scope. Không thay request comparison v1/v2 hoặc tự commit requirement. [Policy](../docs/what-if-analysis.md).
# Catalog trust v2

FactV2/Cell bổ sung verification `catalog_validated`; EvidenceV2 có CatalogValidation receipt theo [policy](../docs/catalog-validation-policy.md). Website proof không đổi; schemas v1 giữ nguyên. Consumer v2 cần nhận enum mới, không hiển thị như independent verification.
