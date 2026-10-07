# Contracts generated from backend models

V2 contracts xuất vào [v2](v2/) từ models/runtime, giữ schemas v1 tại thư mục này. `schema_version=2.0-draft` theo mẫu đã duyệt. Schema validation không thay kiểm tra ownership/reference/version/expiry/AST/offer/evidence ở service.

Run `uv run tour-backend export-schemas` after model changes. Do not edit generated JSON by hand.
Export không đọc `.env`, mở application DB hoặc chạy server.

- Frontend: `CreateRequirement`, `PatchRequirement`, `CreateComparison`, `Requirement`.
- Crawler: `CrawlRequest`, `CrawlResult`, `SourceCapability`.
- Internal LLM adapter: `Extraction` (not the public frontend request).

Các schema trên là v1 (`schema_version=1.0`). V2 gồm:

- Public: `CreateRequirementV2`, `RequirementV2`, `CreateProposal`, `Proposal`, `ConfirmProposal`, `ProposalVersion`, `DiscardChanges`, `CreateComparisonV2`, `ComparisonV2`, `ConversationMessage`, `JobEvent`.
- Contacts/admin: `ContactCreate`, `ContactPatch`, `SourceCreate`, `SourcePatch`, `ExpectedVersion`, `SourceApproval`, `SourceRefresh`.
- Internal NIM: `InitialExtractionV2`, `UpdateExtractionV2`; không gửi extraction DTO như request frontend.

HTTP response có envelope `{schema_version,request_id,data}`, lỗi dùng `error`; GET comparison đặt ComparisonV2 trong `data.result`. [Request walkthrough](../examples/backend-v2.md), [runtime limitations](../docs/backend-v2-runtime.md). Fixtures prototype trong `examples/protocol-v2` là mẫu thiết kế, không phải generated server responses.
