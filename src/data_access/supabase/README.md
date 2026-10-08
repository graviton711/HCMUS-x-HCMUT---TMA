# Supabase tour catalog

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
- Evidence database_record chứa record_ref rõ ràng, không dùng deep link text fragment. Field proof website hợp lệ mới trở thành supplier_published. Chưa biết cadence → freshness unknown.

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

Price kind/basis/coverage/age/applicability không được đoán từ text. Hiện raw price_by_age được giữ trong unclassified_prices; typed adult quote chỉ dùng label adult + currency/type tour có sẵn và vẫn unverified nếu thiếu proof. Child/infant prices chưa có age brackets không dùng tính tổng. Return date/tour type/nature chưa có column/proof sẽ không tự tạo.

Xem kế hoạch và baseline chất lượng ở docs/supabase-tour-integration-plan.md. Tests dùng fake repository/engine và rows tổng hợp; CLI probe/kiểm chứng API live dùng read-only DB + application DB tạm, không nằm trong test suite offline.
