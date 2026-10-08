# Nhật ký nghiệm thu — 08/10/2026

Số liệu theo ngày, giữ để đối chiếu lịch sử và lấy số pitch. **Không phải chuẩn hiện hành.** Chuẩn sống nằm ở docs module tương ứng (`src/api/`, `src/data_access/`, `src/requirements/`).

## Backend runtime (từ `src/api/backend-v2-runtime.md`)

- Nghiệm thu 07/10/2026: `pytest -q` **155 passed** (45 ca v2 + 110 ca hiện hữu); Ruff và diff whitespace đạt. Worker tự chạy đã publish luồng URL fixture; sáu JSON request trong walkthrough validate bằng runtime DTO; 20 schemas v2 xuất thành công. Design fixtures riêng đạt 258 checks/8 files, không thay kiểm thử server hoặc nguồn thật.
- Nghiệm thu semantic 08/10/2026: `pytest -q` **240 passed**, gồm 85 semantic checks và toàn bộ 155 ca baseline; Ruff/diff whitespace đạt. Có API test create → text year answer → typed strength → stale CAS → confirm → persisted revision → HTTP mock comparison → reuse, cùng hard unsupported confirm/removal và legacy reads. Export 21 schema v2; v1 schemas không đổi.
- Nghiệm thu Supabase 08/10/2026: **276 passed** (155 baseline + 89 semantic + 32 Supabase), Ruff/diff whitespace đạt, 22 schemas v2 và v1 không đổi. Probe/live API read-only đạt discover/URL/hybrid và NIM → confirm → comparison; giá/field thiếu proof giữ unknown.
- Nghiệm thu structured retrieval/assessment 08/10/2026: **311 passed** (276 baseline + 35 checks mới), Ruff/diff whitespace đạt; 24 schemas v2, JSON schemas v1 không đổi. Có counterexamples cross-offer, truncated offers, partial perfect-score ranking, foreign-price metric availability, invalid citations, bounded repair/timeout/replay/input, cancel/source pause/freshness sau NIM wait.
- Nghiệm thu personalized core 08/10/2026: **358 passed** (311 baseline + 47 checks bổ sung), Ruff/diff đạt; 24 schemas v2, JSON schemas v1 không đổi. Form/text/edit/read legacy dùng cùng business gate trước confirm/search/worker; hard cap áp dụng toàn bộ branches, URL-only miễn core. Live Nhật/Tết/follow-up đạt 15 assertions, semantic smoke 5/5; comparisons thật ONLY_UNVERIFIED.
- Catalog validation 08/10/2026: **443 passed**, Ruff/diff whitespace đạt, 28 schemas v2 và schemas v1 không đổi. Nguồn opt-in dùng catalog_validated với receipt/record binding; website proof bổ sung, TTL/price qualifiers độc lập.

## Supabase baseline + nghiệm thu (từ `src/data_access/supabase-tour-integration-plan.md`)

Baseline trước implementation — 08/10/2026 (kho lúc đó: 1 provider `dulichviet`, 234 tours, 2.373 offers):

- Settings chỉ hỗ trợ `DATA_PROVIDER=fixture/http`, bỏ qua ba biến `SUPABASE_TOUR_*`. HTTP vẫn gọi crawler, chưa đọc kho tour. Server đang chạy báo `synthetic`, trong khi `.env` khai báo `http`; cấu hình process đang chạy có thể khác file.
- PostgreSQL kết nối được: 1 provider (`dulichviet`), 234 tours, 2.373 offers; không có offer mồ côi. Migrations hiện có: `001_tour_schema.sql`, `002_tour_evidence.sql`.
- Cả bốn bảng bật RLS, không có policy. GET bằng publishable key trả 200 và zero visible rows; không có nghĩa database trống.
- Registry cấu hình vẫn là `replace_with_real_source`, unchecked. Registry SQLite có nguồn demo active và placeholder paused. Crawler endpoint hiện không kết nối được.
- SQLite là application store (sessions/requirements/proposals/jobs/comparisons/snapshots); Supabase hiện là catalog nguồn (providers/tours/offers). `DATABASE_URL` của app chưa hỗ trợ PostgreSQL; không thay nó bằng tour DB URL.

Chất lượng catalog tại thời điểm đó (số phản ánh giá trị được lưu, nay đã cũ — kho hiện ~1200 tour/3 nguồn):

- 234 tour ghi khởi hành Hồ Chí Minh; 0 Hải Phòng; 9 tour có chuỗi Đà Nẵng/Tây Nguyên trong destinations.
- 234 tour có `price_type=from`, currency VND; offers có giá theo adult/child/infant/small_child nhưng thiếu kind/basis/coverage/age brackets riêng.
- `evidence` tour chỉ có observed_at/record_missing/record_evidence; offer chỉ có observed_at, trên toàn bộ records.
- 234 canonical_url rỗng; 33 destinations chứa alias điểm xuất phát; 31 chứa chuỗi ghép nhiều địa danh.
- Transport: 194 mixed, 39 bus, 1 flight. Availability: 2.296 available, 77 sold_out; không có số chỗ.
- 2.373 offers thiếu flights/pickup_point/conditions; 488 single_supplement bằng 0.
- Không có return_date; có tour days/nights không theo days=nights+1.
- Tour observed_at từ 07/10/2026 12:41:51 đến 15:50:34 UTC; lịch khởi hành 07/10/2026–03/08/2027.

Nghiệm thu Supabase — 08/10/2026:

- Offline: **276 tests passed** (155 baseline + 89 semantic + 32 Supabase). Ruff và diff whitespace đạt; export 22 v2 schemas, hash schemas v1 giữ nguyên.
- PostgreSQL live: probe `transaction_read_only=on`, 1 provider/234 tours/2.373 offers. Dùng application SQLite tạm trong các API smoke, không sửa catalog/RLS hoặc dữ liệu phiên thật.
- URL-only hai URL có thật → job succeeded, 2 columns/3 offers, 2 recommendations dạng similar, không có personalized evaluations. Discovery structured → 20 columns/48 offers, hybrid cũng chạy; raw prices hiện được, hard evaluations unknown và không có recommendation cá nhân hóa do thiếu proof.
- NIM text → proposal → confirm → Supabase comparison: giữ đúng Nhật Bản/TP.HCM/ngày 03-11-2026/budget 30 triệu VND per_adult tour_price, party 1 người lớn; comparison succeeded, origin source, 20 preview giá và ONLY_UNVERIFIED.
- `DATA_PROVIDER=supabase` là cấu hình local để sử dụng reader mới. Server cũ phải dừng/restart; frontend prototype vẫn dùng mock.

Field proofs/price qualifiers/cadence và dữ liệu provider/origin khác vẫn cần crawler bổ sung; freshness chưa tự được đặt. URL-only còn usable để xem/đối chiếu raw data, không phải chứng minh tour phù hợp hoặc giá cuối cùng.
