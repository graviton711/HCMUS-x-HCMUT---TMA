# Supabase tour catalog

Sửa tìm tour 09/10 theo [quy tắc và nghiệm thu](../../../docs/search-correctness-repair.md): loại origin endpoints khỏi destinations, giữ raw/route; pricing metadata tùy chọn, không suy qualifiers; freshness local được cấu hình theo cadence một ngày đã được user chốt.

`pricing.py` validate optional `offers.field_meta.pricing` trước khi tạo catalog quote/charge/completeness facts. [JSON cho crawler](../../../examples/catalog-price-metadata.md); thiếu metadata giữ preview như trước. `CatalogPricing` được export cùng schemas v2.

Policy hiện hành: [catalog-validation-v1](../../../docs/catalog-validation-policy.md). Nguồn opt-in qua `SUPABASE_TOUR_TRUSTED_DOMAINS` được dùng field đã kiểm tra dưới trạng thái `catalog_validated`, giữ provenance database_record; website proof là đường bổ sung. Giá thiếu qualifiers, mixed transport, field thiếu và freshness chưa cấu hình vẫn unknown. Không cần backfill proof mọi field. Các đoạn proof bên dưới mô tả đường website proof, không là prerequisite cho catalog opt-in.

`audit.py` tạo báo cáo aggregate từ **pool retrieval có giới hạn** qua đúng reader/adapter/validator, không claim audit toàn kho nếu scan/pool/offers bị cắt. `uv run tour-backend audit-supabase --output data/catalog-audit.local.json` chỉ đọc catalog, không tạo application DB, không gọi NIM/crawler. Report công bố counts/coverage, catalog_validated/proof/value, thiếu qualifiers và các field adapter chưa hỗ trợ. TTL audit lấy config bootstrap tường minh, không đại diện toàn bộ registry persisted/admin của app; không tự đặt TTL hoặc nâng independent verification. [Policy](../../../docs/catalog-validation-policy.md).

## Trách nhiệm và interface

Reader PostgreSQL read-only + adapter records providers/tours/offers → CrawlResultV2. Input là registry nguồn, normalized conditions, URL targets, deadline, candidate limit và excluded stable tour IDs; không gửi raw user text/NIM key đến database. Output là immutable snapshots, evidence, source coverage và issues. Store/publish thuộc API; evaluator không được coi imported unverified values là hard pass.

## Workflow

1. Validate cấu hình/schema, load provider metadata để bootstrap namespace catalog; registry persisted có quyền pause.
2. Trong repeatable-read transaction, normalize bounded tour scan, loại static hard fail có bằng chứng trước SQL lookup offers. Đánh giá toàn bộ hard tree cho từng offer rồi mới cắt pool; ưu tiên pass/unknown/relevance. Unknown không bị loại. Lookup URL giữ nguyên kể cả không đạt hard.
3. Lấy offers với thứ tự công bằng giữa tours, ưu tiên ngày gần mốc departure đã biết; giới hạn và truncation công khai.
4. Adapter chuẩn hóa bằng catalog chung, giữ raw/missing/conflict/scope. Hash toàn bộ record + observed_at để tạo snapshot bất biến.
5. Gateway validate toàn bộ references/domain/time rồi API lưu snapshots cùng comparison. DB row update không sửa comparison cũ.

Retrieval/per-offer coverage theo [contract](../../../docs/retrieval-semantic-ranking.md). SQL dùng IDs sau evidence validation; chưa có raw-field trusted index. Registry persisted truyền vào reader để freshness theo đúng policy hiện hành.

## Quyết định

- Không fallback fixture, không ghi Supabase, không sửa RLS, không suy return date, số chỗ, tuổi trẻ em hoặc zero fee. Raw price vẫn có thể xem khi chưa đủ qualifiers/evidence.
- DATABASE_URL vẫn là SQLite application store. SUPABASE_TOUR_DB_URL là SecretStr của reader; REST URL/publishable key được nhận nhưng không dùng để bypass RLS.
- PostgreSQL pool/deadline có giới hạn; connection/statement lỗi được chuyển thành mã public, không serialize exception/DSN. Đóng pool khi app shutdown và CLI probe kết thúc.
- Catalog sources chỉ dùng cho đọc DB. Crawler refresh chưa được nối; URL không có trong kho trả CATALOG_URL_NOT_FOUND.
- Evidence database_record chứa record_ref rõ ràng, không dùng deep link text fragment. Receipt validation của nguồn opt-in cho phép catalog_validated; field proof website hợp lệ trở thành supplier_published. Chưa biết cadence → freshness unknown.

## Field proof để crawler bổ sung

JSONB evidence giữ metadata hiện hữu và có thể thêm fields map theo **tên column hoặc dotted price path**. Mỗi entry theo CatalogFieldProof schema:

```json
{
  "record_key": "stable_record_key",
  "field": "departure_city",
  "value": "Hồ Chí Minh",
  "url": "https://dulichviet.com.vn/example-tour",
  "raw_value": "Hồ Chí Minh",
  "raw_quote": "Khởi hành từ Hồ Chí Minh",
  "locator": "#departure-city",
  "method": "html",
  "observed_at": "2026-10-07T15:00:00Z",
  "scope": null,
  "completeness": "unknown"
}
```

Value phải khớp column/path của đúng record, time khớp observed_at của row, raw_value nằm nguyên văn trong raw_quote, URL cùng source/path của tour. Transport/route/nature cần scope phù hợp; không suy scope từ bus/mixed. Extra fields/invalid proof bị từ chối riêng field, giữ record như unverified + issue.

Raw_value còn phải chứng minh value: scalar text khớp hoặc dùng alias catalog đã duyệt; địa danh list phải có đủ tên nguyên văn; ngày chỉ ISO/dd-mm-yyyy/dd/mm/yyyy có năm; số phải parse đúng giá trị. Không nhận proof có value đúng DB nhưng quote/raw_value nói địa danh hoặc con số khác.

Price kind/basis/coverage/age/applicability không được đoán từ text. Raw price_by_age được giữ trong unclassified_prices. Nếu chưa có field_meta.pricing, typed adult preview chỉ dùng label adult + currency/type tour có sẵn và vẫn unverified nếu thiếu proof; metadata hợp lệ dùng đường validation ở đầu tài liệu. Child/infant prices chưa có age brackets không dùng tính tổng. Return date/tour type/nature chưa có column/proof sẽ không tự tạo.

Xem kế hoạch và baseline chất lượng ở docs/supabase-tour-integration-plan.md. Tests dùng fake repository/engine và rows tổng hợp; CLI probe/kiểm chứng API live dùng read-only DB + application DB tạm, không nằm trong test suite offline.
# What-if acquisition

Theo [policy](../../../docs/what-if-analysis.md), analysis đọc bounded tối đa500 tours trong một transaction; không loại hard fail hoặc cắt pool20, không dùng date anchor khi chọn offers. Scan/offer limits và proof validation vẫn áp dụng, báo coverage/truncation; không ghi catalog. Comparison bình thường giữ retrieval policy hiện tại.
