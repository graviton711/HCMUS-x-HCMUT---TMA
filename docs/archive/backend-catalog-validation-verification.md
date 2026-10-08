# Nghiệm thu catalog validation — 08/10/2026

Backend trên `backend`, theo [policy](../../src/data_access/supabase/catalog-validation-policy.md). Supabase chỉ đọc, test API live dùng SQLite `:memory:`. Không sửa schema/rows/RLS, frontend, credentials hoặc commit/push. `.env` local bật đúng ba domain catalog hiện có; code default allowlist vẫn rỗng. TTL volatile giữ rỗng vì nhóm chưa chốt cadence.

## Đã triển khai

- FactV2/cell nhận `catalog_validated`; database evidence giữ receipt/checks/source/table/key/field/hash/time, không giả website quote. Receipt binding và source/capability hiện hành được kiểm tra, HTTP/fixture không tự khai catalog trust.
- Reader kiểm trước static hard filter và dùng chung evaluator cho comparison/what-if. Invalid proof không fallback; nguồn ngoài allowlist/paused/revoked, field thiếu/sai/mơ hồ vẫn unknown. Policy đổi sau await không publish kết quả cũ.
- Source registry persisted giao với cấu hình hiện hành; explicit TTL config overlay, admin pause giữ hiệu lực. `/v2/catalog`, `/v2/sources`, cells và evidence công bố policy/trạng thái. V1 JSON schemas không đổi; v2 có 28 schemas (thêm CatalogValidation).
- Itinerary/policies đã làm sạch có thể hỗ trợ soft matched bằng quote đúng snapshot sau hard-pass; text completeness unknown không cho kết luận absence. Giá thiếu coverage, mixed/main_journey, return_date/tour_type/seat capacity vẫn giữ giới hạn.

## Kiểm chứng

- **443 tests passed**, gồm 42 tests mới ở `tests/test_catalog_validation.py`: nguồn/receipt/schema/URL/time/field/raw binding, invalid proof/no fallback, partial địa danh, TTL độc lập, revocation/HTTP spoof, soft quote/absence, API/what-if và publication sau policy change. Ruff check/format các file sửa, diff whitespace và schema JSON đạt; schemas v1 bằng HEAD theo nội dung JSON. Một warning deprecation TestClient/httpx hiện hữu.
- Probe tại lần kiểm tra: **3 providers, 1.210 tours, 3.319 offers**, transaction_read_only=on. Đây là thời điểm kiểm tra; kho đang tiếp tục được crawl.
- Audit `data/catalog-validation.local.json`: sample 100 tours/190 offers, scan 1.000 có truncation. 100 origins, 100 durations, 100 itinerary và 190 departure_dates được catalog_validated. Địa danh còn thiếu mapping: 37 tours có một phần destination được chuẩn hóa, 63 unsupported; 98 mixed/unsupported transports. Toàn bộ 190 adult quotes là from/coverage unspecified, pricing_complete=0. Không dùng sample để khẳng định toàn kho.
- Live NIM input Nhật và Tết nguyên bản: `data/live-tests/personalized-20261008T124333Z/summary.json`, **15 checks đạt**. Nhật đúng bốn hard predicates + adults=1, confirm200/search succeeded nhưng chưa có recommendation. Tết không tự điền người/ngân sách/năm: confirm409 hỏi đúng thông tin. Follow-up dùng đáp án synthetic (năm2027, cửa sổ có thể đi, adults2/cap10 triệu/route soft) → confirm200/search succeeded. Đây là một lần live, không là accuracy benchmark.
- Live what-if với ba domain: `data/live-tests/what-if-20261008T124610Z/summary.json`, **18 checks đạt**. Inputs structured tương đương, ca Tết có bổ sung synthetic đã ghi trong artifact; không đo extraction lần này. Mỗi analysis giữ 500 tour trong scan1.000, offers/truncation công khai, baseline và scenarios cùng snapshot, requirement không đổi.

| Ca | Baseline pass/fail/unknown | Riêng điều kiện nơi đi |
|---|---|---|
| Nhật | 0 / 65 / 435 | 490 pass, 10 fail; không còn FIELD_UNVERIFIED |
| Tết đã làm rõ | 0 / 480 / 20 | 3 pass Hải Phòng, 470 fail, 27 unsupported |

Kho mới đã có một số record Hải Phòng, nên kết luận “không có tour Hải Phòng” trong báo cáo cũ không còn đại diện dữ liệu hiện tại. Nơi đi được đánh giá theo catalog đã kiểm tra; fail tổng thể còn có thể do các hard khác. Địa danh partial/unsupported, ngày chưa có TTL, nhiều/missing offers, ngân sách chưa có coverage và field thiếu vẫn làm kết quả unknown. Không có actionable price/date bounds; unknown→pass không được tính là đóng góp đã xác định. Có thể xuất hiện mở rộng pool khi bỏ nhiều nhóm, nhưng chưa đủ chứng minh các tour đạt yêu cầu gốc.

## Việc tiếp theo về dữ liệu

1. Thống nhất cadence/TTL, ghi rõ giá tour người lớn theo từng offer (from/exact, coverage, qualifiers/phụ thu/applicability); chốt contract pricing rồi cập nhật adapter. Không chuyển from thành exact.
2. Mở rộng catalog địa danh dựa trên mẫu raw thực tế; giữ OR/hierarchy và partial khi chưa nhận đủ.
3. Làm rõ phương tiện chính, loại tour, ngày về và số chỗ nếu nguồn có. Không suy từ mixed/available/duration một cách ngầm định.
4. Frontend chỉ cần nhận enum catalog_validated và nhãn “Dữ liệu crawler đã qua kiểm tra”, đọc reason_code và link nguồn; chưa sửa frontend trong đợt này.

Khởi động/test: [hướng dẫn](../../examples/backend-catalog-validation.md).
