# Domain

**Trạng thái:** Đã có implementation v1; phạm vi kiểm tra và giới hạn ở [backend-runtime.md](../../docs/backend-runtime.md).

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
