# Kết nối kho tour Supabase — implementation

User yêu cầu implement ngày 08/10/2026, trên `feature/minh-phu`. Baseline kiểm tra bên dưới được giữ để đối chiếu. Không ghi URL kết nối, mật khẩu, API key vào tài liệu. Kho Supabase chỉ được đọc; không tự migrate bảng, sửa RLS hay khởi động crawler.

## Baseline trước implementation — 08/10/2026

- Settings chỉ hỗ trợ `DATA_PROVIDER=fixture/http`, bỏ qua ba biến `SUPABASE_TOUR_*`. HTTP vẫn gọi crawler, chưa đọc kho tour. Server đang chạy báo `synthetic`, trong khi `.env` khai báo `http`; cấu hình process đang chạy có thể khác file.
- PostgreSQL kết nối được: 1 provider (`dulichviet`), 234 tours, 2.373 offers; không có offer mồ côi. Migrations hiện có: `001_tour_schema.sql`, `002_tour_evidence.sql`.
- Cả bốn bảng bật RLS, không có policy. GET bằng publishable key trả 200 và zero visible rows; không có nghĩa database trống.
- Registry cấu hình vẫn là `replace_with_real_source`, unchecked. Registry SQLite có nguồn demo active và placeholder paused. Crawler endpoint hiện không kết nối được.
- SQLite là application store (sessions/requirements/proposals/jobs/comparisons/snapshots); Supabase hiện là catalog nguồn (providers/tours/offers). `DATABASE_URL` của app chưa hỗ trợ PostgreSQL; không thay nó bằng tour DB URL.

## Chất lượng catalog

Các số dưới phản ánh giá trị được lưu, chưa xác minh lại trang nhà cung cấp.

| Quan sát | Hệ quả với adapter/evaluator |
|---|---|
| 234 tour ghi khởi hành Hồ Chí Minh; 0 Hải Phòng; 9 tour có chuỗi Đà Nẵng/Tây Nguyên trong destinations | Ca Tết Hải Phòng có thể không có ứng viên phù hợp; không tự nới origin hoặc thêm tour giả. Kiểm tra cả chất lượng field xuất phát. |
| 234 tour có `price_type=from`, currency VND; offers có giá theo adult/child/infant/small_child nhưng thiếu kind/basis/coverage/age brackets riêng | Giữ nghĩa giá từ; chưa chứng minh giá đủ nhóm hoặc áp giá trẻ em đúng tuổi. Không giả định giá offer là exact từ một con số. |
| `evidence` tour chỉ có observed_at/record_missing/record_evidence; offer chỉ có observed_at, trên toàn bộ records | Có provenance của record, chưa có quote/locator/method/binding cho từng field theo runtime. `record_evidence=verified` không là xác minh độc lập. |
| 234 canonical_url rỗng; 33 destinations chứa alias điểm xuất phát; 31 chứa chuỗi ghép nhiều địa danh | Dùng URL gốc làm locator khi cần, giữ canonicalization rule; chuẩn hóa alias/route nhưng không suy canonical hoặc điểm đến chỉ từ tiêu đề. |
| Transport: 194 mixed, 39 bus, 1 flight | mixed chưa chứng minh main_journey bằng ô tô; scope phải có bằng chứng riêng. |
| Availability: 2.296 available, 77 sold_out; không có số chỗ | Không ánh xạ available thành số chỗ tùy ý; cần thống nhất policy cho trạng thái đặt chỗ trong contract. |
| 2.373 offers thiếu flights/pickup_point/conditions; 488 single_supplement bằng 0 | Null/rỗng/0 chưa tự chứng minh không có chuyến bay, điều kiện hoặc phụ thu. |
| Không có return_date; có tour days/nights không theo days=nights+1 | Không tự tính ngày về theo công thức chung; cần lịch trình/giờ và rule có provenance. |
| Tour observed_at từ 07/10/2026 12:41:51 đến 15:50:34 UTC; lịch khởi hành 07/10/2026–03/08/2027 | Giữ observed_at thật khi đọc DB, không đổi thành thời điểm truy vấn. TTL/cadence còn cần chốt; không coi available là hiện thời. |

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

## Nghiệm thu — 08/10/2026

- Offline: **276 tests passed** (155 baseline + 89 semantic + 32 Supabase). Ruff và diff whitespace đạt; export 22 v2 schemas, hash schemas v1 giữ nguyên. Có cases budget/party omission + duplicate dates repair, URL lỗi isolation, fair offer budget/truncation, provider domain đổi, bad proofs, deadline/errors, record binding, owner isolation và registry pause.
- PostgreSQL live: probe `transaction_read_only=on`, 1 provider/234 tours/2.373 offers. Dùng application SQLite tạm trong các API smoke, không sửa catalog/RLS hoặc dữ liệu phiên thật.
- URL-only hai URL có thật → job succeeded, 2 columns/3 offers, 2 recommendations dạng similar, không có personalized evaluations. Discovery structured → 20 columns/48 offers, hybrid cũng chạy; raw prices hiện được, hard evaluations unknown và không có recommendation cá nhân hóa do thiếu proof.
- NIM text → proposal → confirm → Supabase comparison: giữ đúng Nhật Bản/TP.HCM/ngày 03-11-2026/budget 30 triệu VND per_adult tour_price, party 1 người lớn; comparison succeeded, origin source, 20 preview giá và ONLY_UNVERIFIED. Một lượt smoke đầu phát hiện date duplicates thay budget/party; đã thêm guard/prompt và regression, lượt live sau sửa đúng. Không dùng kết quả này làm chỉ số accuracy tổng quát.
- `DATA_PROVIDER=supabase` là cấu hình local để sử dụng reader mới. Server cũ phải dừng/restart; frontend prototype vẫn dùng mock. [Hướng dẫn khởi động/test](../examples/backend-supabase-v2.md).

Field proofs/price qualifiers/cadence và dữ liệu provider/origin khác vẫn cần crawler bổ sung; freshness chưa tự được đặt. URL-only còn usable để xem/đối chiếu raw data, không phải chứng minh tour phù hợp hoặc giá cuối cùng.
# Policy hiện hành và baseline lịch sử

[catalog-validation-v1](catalog-validation-policy.md) thay yêu cầu proof từng field bằng nguồn opt-in + validation; v1 giữ nguyên, Supabase chỉ đọc. [Nghiệm thu hiện hành](archive/backend-catalog-validation-verification.md). Các số liệu/verification và kế hoạch bên dưới lưu baseline trước policy mới, không mô tả counts hay quyền trust hiện tại.
