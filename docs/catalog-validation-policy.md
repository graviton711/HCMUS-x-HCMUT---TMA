# Dữ liệu crawler được kiểm tra — catalog-validation-v1

Phạm vi: backend trên `backend`, Supabase chỉ đọc. Thay policy bắt buộc website proof từng field bằng hai đường độc lập: proof website hợp lệ → `supplier_published`; dữ liệu catalog thuộc nguồn được cấu hình, qua validation → `catalog_validated`. V1 giữ nguyên. Không coi hai trạng thái này là kiểm chứng độc lập chất lượng tour.

## Nguồn và kiểm tra

- Opt-in bằng `SUPABASE_TOUR_TRUSTED_DOMAINS` (JSON array hostname chính xác, mặc định `[]`). Không tin nguồn chỉ vì `DATA_PROVIDER=supabase` hoặc `record_evidence=verified`.
- Registry phải approved, provider/supplier đúng, URL tour và evidence thuộc cùng domain được cấu hình; không wildcard/subdomain ngầm. Capability hiệu dụng công bố `limits.catalog_validated=1`; config hiện hành là trần quyền, không cho registry cũ hoặc HTTP crawler tự nâng quyền.
- Backend tạo receipt `catalog_validation` trên evidence database_record: policy/source/checks. Giữ record_key/table/field/content_hash/observed_at và giá trị nguyên gốc; không tạo quote website/selector giả. Receipt không thay freshness hoặc completeness.
- Check schema/type, binding record và offer→tour, URL/domain, timestamp hợp lệ/không ở tương lai, timestamp metadata nếu có phải khớp row, chuẩn hóa field được hỗ trợ. Invalid website proof không được fallback sang catalog trust để che lỗi.
- `catalog_validated` chỉ hợp lệ khi receipt có nguồn và record binding đúng; evaluator còn kiểm capability hiện hành. HTTP/fixture không được gửi trạng thái này như nguồn tin cậy.

## Các field dùng được

- Nơi xuất phát, điểm đến, thời lượng, transport enum rõ, ngày khởi hành, route và nội dung itinerary/policies hiện có. Giá/availability text/single supplement vẫn là preview khi thiếu qualifiers/capacity/applicability.
- Scalar được nhận là complete cho giá trị catalog đó; destinations/route là danh sách khai báo trong catalog, chỉ complete khi toàn bộ tên được chuẩn hóa, danh sách không rỗng. Có tên chưa biết → partial, không dùng absence làm fail. Transport mixed không được nhận là coach, không tự gán main_journey scope.
- Nội dung đã làm sạch được giữ như excerpt của catalog; completeness unknown (hoặc partial khi bị cắt), không dùng để kết luận không có một dịch vụ chỉ vì không thấy trong đoạn. LLM phải trích đúng nội dung đã lưu, chạy sau hard-pass, chưa chấm uy tín/dịch vụ tốt/đáng tiền từ quảng cáo.
- Ngày/giá/availability vẫn cần TTL được nhóm thống nhất. `SUPABASE_TOUR_FRESHNESS_SECONDS` là JSON map chỉ cho departure_date/return_date/price/availability, positive seconds, mặc định `{}`; chưa cấu hình thì unknown. Không tự chọn TTL chỉ để test pass; config tường minh áp dụng cả registry đã persisted, admin pause vẫn giữ hiệu lực.
- Không đổi from thành exact; không suy coverage/phụ thu/ngày về/ghép đoàn/số chỗ/giá trẻ em. Chỉ thêm evidence.fields không giải quyết các qualifiers này.
- Optional price metadata theo [contract crawler](../examples/catalog-price-metadata.md) được validate và ràng buộc với row trước catalog validation. Thiếu metadata vẫn giữ giá preview unverified; `complete` phải tường minh, không suy từ mảng phụ thu rỗng. Local cadence 1 ngày đã được user chốt ngày 09/10, được cấu hình trong `.env`, không đổi default của deployment khác.

## API, what-if và tương thích

Fact/cell v2 thêm verification `catalog_validated`. Evidence endpoint công bố receipt và quality tương ứng, link về trang tour, không text fragment cho database_record. FE có thể ghi “Dữ liệu crawler đã qua kiểm tra”; đây là bổ sung enum, không đổi flow requirement→proposal→confirm→comparison.

Comparison/what-if dùng cùng evaluator, nguồn/capability, snapshot và bound hiện hành. What-if vẫn tách fail→pass khỏi unknown→pass; phần trăm là thay đổi lựa chọn theo catalog đã kiểm tra, không là xác suất/độ uy tín. Lưu policy version để truy lại; đổi policy không sửa kết quả lịch sử. Khi source policy đổi trong lúc chờ LLM, không publish kết quả dựa trên policy cũ.

## Triển khai và nghiệm thu

1. Cập nhật domain v2/adapter/settings/registry/evaluator/evidence endpoint và schemas; giữ proof path, v1, guards và remote read-only.
2. Test trusted/untrusted/paused/revoked/HTTP spoof; malformed type/URL/time/proof/list, partial semantics, stale/unknown TTL, same-offer pricing, source-policy change khi await, soft quote và what-if.
3. Chạy regression/Ruff/schema export; audit và chạy lại ca Nhật/Tết qua Supabase read-only, application DB tạm. Không hứa có recommendation nếu ngân sách/ngày/phạm vi dữ liệu còn thiếu.
4. Crawler giữ URL/record_key/observed_at, dữ liệu nguyên văn đã làm sạch; quote từng field bổ sung có chọn lọc. Chưa cần migration Supabase hoặc bulk backfill proof. Price/date/transport schema mở rộng chỉ chốt sau khi review mẫu dữ liệu thật.
