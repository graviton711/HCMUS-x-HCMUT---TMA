# Domain

Khôi phục recommendation theo [contract ngày 10/10](../../docs/recommendation-recovery-plan.md): BudgetV2.measure tách listed/payable, default payable cho snapshots cũ; optional listed_price_quotes không thay payable facts. V1 models giữ nguyên.

`what_if.py` cung cấp DTO và invariants cho baseline/scenarios/groups/metrics có mẫu số, witness và ranking sensitivity. [Policy](../../docs/what-if-analysis.md); không gọi network hoặc sửa requirement.

V2 bổ sung retrieval diagnostics/offer coverage; hai trục strength và processing độc lập. Xem [structured retrieval](../../docs/retrieval-semantic-ranking.md).

Supabase import v2 bổ sung record provenance riêng, catalog preview fields và CatalogFieldProof; raw database values chưa có website field proof giữ unverified. V1 models/schema không đổi. Xem [contract adapter](../data_access/supabase/README.md).

`semantic.py` mở rộng Condition/Value riêng cho v2 (entity members, temporal intents, qualitative preferences, issues/trace); `crawl_v2.py` thêm semantic facts với binding evidence. Models v1 giữ riêng; v2 đọc legacy values và snapshot. Xem [semantic contract](../../docs/requirements-semantics.md).

V2 triển khai shared requirement invariants và 1–5 URL/hybrid riêng với input policy v1; snapshot bổ sung optional title/policies, giữ tương thích payload cũ. Xem [backend-v2-runtime](../../docs/backend-v2-runtime.md).

**Trạng thái:** Đã có implementation v1/v2; phạm vi v1 ở [backend-runtime.md](../../docs/backend-runtime.md), v2 ở tài liệu trên.

## Trách nhiệm / input-output

Cung cấp typed DTO/value objects và invariants cho requirements, QuerySpec, supplier/tour/offer/evidence, cost/evaluation/result. Input là payload/normalized values; output là object hợp lệ hoặc lỗi có path. Không gọi NIM, network, database hoặc phụ thuộc FastAPI.

## Workflow và interfaces

1. Validate schema version/types, enum, extra fields và limits.
2. Validate references/condition tree, money/ranges/timestamp và entity bindings.
3. Cung cấp models/field catalog cho requirements, data_access, decision và api; xuất JSON Schema/OpenAPI qua lớp API sau.

## Quyết định kỹ thuật

- Model input strict, extra fields forbidden; coercion chỉ ở normalizer có rule rõ. Raw extraction DTO tách normalized domain; crawler DTO tách storage model.
- Condition field/operator/value phải tương thích. AST có leaf/group, unique IDs, giới hạn depth/size cấu hình và không cycle. Soft operator không được dùng trong hard tree.
- Canonical place/service IDs dùng catalog versioned; aliases/hierarchy có nguồn hoặc mapping được team review, không do model tự tạo ID ngoài catalog.
- VND integer, currency khác decimal string; ngày ISO, timestamp có timezone. Null/unknown không bằng false/0.
- Snapshot bất biến và provenance references kiểm tra được; `schema_version`, normalization/policy version đi cùng record.
- Eligibility/evaluation, data state, verification và freshness là các trục độc lập. Empty hard tree không tạo tuyên bố đã phù hợp.

Acceptance: reject condition/operator sai, references chéo offer, duplicate IDs, amount/range sai và unknown fields; giữ được payload partial hợp lệ mà không bịa defaults nghiệp vụ.
# Catalog validation v2

Theo [policy](../../docs/catalog-validation-policy.md), `FactV2` nhận thêm `catalog_validated`, evidence database_record có receipt bound source/record. Đây là kiểm tra dữ liệu crawler, không độc lập xác minh website. Snapshot/cell v2 giữ trạng thái này; models/schema v1 không đổi.
