# Kết nối kho tour Supabase — implementation

User yêu cầu implement ngày 08/10/2026, trên `feature/minh-phu`. Baseline kiểm tra bên dưới được giữ để đối chiếu. Không ghi URL kết nối, mật khẩu, API key vào tài liệu. Kho Supabase chỉ được đọc; không tự migrate bảng, sửa RLS hay khởi động crawler.

## Phương án đề xuất

Thêm provider đọc PostgreSQL từ `SUPABASE_TOUR_DB_URL` qua repository riêng ở data_access; tên cấu hình đề xuất `supabase` **chưa được runtime chấp nhận**. Backend giữ API v2 và application store SQLite trong lát cắt này.

- PostgreSQL reader: join providers/tours/offers, transaction nhất quán, query có tham số, deadline/pool giới hạn, quyền SELECT; đã kiểm tra đường kết nối này. Đây là phương án ưu tiên.
- REST với URL + publishable key: cần SELECT policies phù hợp; hiện không đọc được rows, thêm dependency vào RLS cho pipeline BE. Không cần mở quyền chỉ để dùng database reader.
- HTTP bridge DB → crawler DTO: tái dùng gateway hiện có nhưng thêm service phải vận hành; chưa có gain cần thiết cho catalog hiện tại. HTTP crawler vẫn dùng cho refresh/URL mới sau khi contract chạy thật.

Workflow mục tiêu:

```text
Nhu cầu → NIM → proposal/clarifications → confirmed revision
→ truy vấn catalog Supabase / lookup URL
→ chuẩn hóa + kiểm tra dữ kiện + snapshot bất biến
→ hard evaluation / soft ranking → comparison / evidence
```

URL đã có trong kho dùng cùng adapter. URL chưa có trả trạng thái chưa có dữ liệu; chỉ gọi crawler khi endpoint/capability thực sự sẵn sàng. Không fallback sang synthetic khi provider thật lỗi.

## Contract và interface cần chốt trước code

1. Repository nhận QuerySpec/targets/deadline/candidate budget; trả raw provider/tour/offer records + coverage, không nhận raw user text hoặc NIM key. SQL không loại unknown theo hard condition, không dùng lọc chuỗi quá hẹp làm mất nhánh OR. Backend đánh giá lại mọi điều kiện.
2. Adapter tạo stable entity IDs từ source + record_key; snapshot IDs/version/hash gắn nội dung + observed_at, giữ đúng offer/tour references. App lưu snapshot khóa theo comparison; việc crawler cập nhật rows không sửa comparison cũ.
3. Phân biệt provenance của **database record** với evidence của **website field**. Cần spec bổ sung record refs/raw values cho preview; không giả quote/locator website để vượt validator. Record chưa có field evidence giữ unverified/unknown trong evaluation. Đường này có thể hiển thị dữ liệu thật nhưng chưa tạo hard pass từ những field chưa đủ chứng cứ.
4. Crawler bổ sung field evidence: source URL, raw quote/value, locator, extraction method, observed_at, field/offer binding; price qualifiers, child age brackets, availability semantics, main journey transport, return date khi xác định được. Provider_claimed ánh xạ supplier_published khi field có căn cứ; không nâng thành independently_verified.
5. Registry nguồn thật: stable supplier/source ID, domain, database-read và live-refresh capability, returned/searchable fields, freshness policy theo lịch cập nhật đã chốt. Đối chiếu registry persisted của v2, không giả định sửa JSON sẽ overwrite entry cũ.
6. Canonical place IDs dùng chung cho extraction và catalog. Unknown địa danh/route giữ raw + issue; không tự gán entity ID hoặc lấy title làm bằng chứng destination. Giá/availability/policies thiếu nghĩa vẫn hiển thị giới hạn rõ.
7. Giới hạn retrieval/pagination và offers phải công khai; hiện CrawlResult tối đa 500 tours/2.000 offers, không đưa toàn bộ 2.373 offers vào một envelope. Một tour có tối đa 252 offers; giới hạn/fresh date selection không được đổi offer ngầm. Empty catalog match phân biệt lỗi kết nối/schema.

## Thứ tự và nghiệm thu

1. Reader + config/preflight: đọc thật, schema/count kiểm tra được; application DB và secrets riêng; timeout/schema/permission error rõ, zero rows không giả thành outage.
2. Adapter + public preview: đủ title/source/URL/dates/raw prices/policies; chuẩn hóa và provenance trung thực. Khi evidence chưa đủ, comparison giải thích unknown thay vì recommendation giả.
3. Crawler evidence/pricing + registry/TTL: bổ sung theo contract; chạy mẫu gold khởi hành/giá/age/available/sold_out/mixed/overnight. Không nới validator chỉ để dữ liệu nhập được.
4. API create → clarify → confirm → comparison thật cho discover, URL và hybrid. Kiểm tra đúng offer/partial sources, snapshots không đổi khi catalog update; ca Hải Phòng zero match được giải thích đúng.
5. FE nối API v2; gỡ mock khỏi flow thật, hiển thị giá từ, tuổi dữ liệu, unknown, nguồn và giới hạn chỉ một provider. Chưa cần redesign.

Reader/normalizer/adapter/public facts thuộc BE; crawl/cadence/field evidence và sửa extraction nguồn thuộc crawler; FE render API và trạng thái dữ liệu. Cadence còn đang hỏi user; chưa đặt TTL hoặc tự tạo automation.

Acquisition chuyển sang catalog sẵn có theo yêu cầu user. Thực hiện BE reader/adapter/API; crawler bổ sung field evidence/cadence và FE nối API là công việc của các owner tương ứng, không tự tạo bằng chứng hoặc sửa frontend prototype.

## Quyết định cho lát cắt hiện tại

- Provider mới `supabase`, chỉ dùng API v2; v1 trả lỗi rõ khi yêu cầu thu thập bằng provider này, contract v1 không mở rộng. PostgreSQL có pool nhỏ, transaction repeatable read + read only, connect/statement/deadline timeout. Có CLI probe riêng không tạo application DB.
- Registry catalog bootstrap từ providers website/source_key; approval chỉ là đọc kho đã cấu hình, namespace `catalog_`, limits `catalog_read_only=1/live_refresh=0`. HTTP không nhận sources catalog. Admin pause vẫn chặn đọc/publish/reuse; các record registry đã có không bị ghi đè khi restart. Không tự fetch website.
- Mặc định không đặt TTL khi cadence chưa được xác nhận. Fact volatile được hiển thị với freshness unknown; TTL sau này cấu hình qua registry có chủ đích.
- V2 có EvidenceV2.method=database_record và record_ref (table/record_key/field/content_hash). Raw quote là giá trị **trong DB**, không được tạo text fragment đến trang nhà cung cấp. Mọi giá trị import chưa có field proof giữ verification=unverified.
- Tour/offer v2 có catalog_fields cho published_price/itinerary/availability_status/unclassified_prices/single_supplement; đây là dữ kiện để xem, không thêm metric hard tự động. Published_price cho thấy giá tour kể cả nhiều offers chưa chọn. Không suy số chỗ từ available.
- Field proof tùy chọn theo contract cạnh adapter; chỉ nâng thành supplier_published khi field/record/value/time/URL/quote/scope khớp. Không nâng record_evidence=verified, không nhận independently_verified từ self-claim.
- Discovery dùng positive canonical matches để ưu tiên retrieval, không lọc SQL loại các field unverified/unknown; giới hạn pool/truncation được công bố. URL lookup bỏ fragment/UTM thông dụng, không đoán canonical hoặc bỏ query chức năng. Stable IDs/hash, exclusions và fairness giữa tours trong offer pagination.
- Ca Hải Phòng không có origin matching được lưu; do dữ kiện chưa có proof, evaluator có thể trả unknown thay vì fail. Không khẳng định không có tour trên thị trường hoặc thay đổi origin.

