# Nghiệm thu recovery gợi ý tour — 10/10/2026

Đã triển khai theo [plan](recommendation-recovery-plan.md) và policy user chốt: trần **giá tour niêm yết**, báo riêng phụ thu/tiền thực trả. [Khởi động và test từng bước](../examples/backend-recommendation-recovery.md).

## Phần đã sửa

- BudgetV2 có measure listed/payable. Form/text mới mặc định listed cho giá tour; tổng chi phí/thực trả dùng payable. Payload lịch sử thiếu measure vẫn payable; sửa riêng số tiền giữ nghĩa cũ. API v1 giữ contract.
- Listed adult price thuộc đúng offer, giữ kind from/exact và nguồn. Không cần pricing_complete=true để kiểm giá niêm yết; metadata mâu thuẫn, giá thiếu, stale hoặc nguồn không hợp lệ vẫn unknown. Không suy upper bound thực trả từ giá từ.
- Mở rộng catalog địa danh/alias/quan hệ, tách chuỗi quốc gia có dấu phân cách được kiểm soát. User yêu cầu thành phố vẫn cần đúng thành phố; không tự nới thành quốc gia.
- PostgreSQL ưu tiên raw địa danh/date tree/listed budget trước scan có phân trang. Date và price dùng cùng offer; evaluator sau validation mới quyết định hard status. Các cap và truncation vẫn công khai.
- Chặn tìm mới với toàn bộ khoảng hard đã qua; OR còn nhánh tương lai vẫn cho tìm. Offer đã khởi hành có dữ kiện usable không được gợi ý, kể cả trong tháng hiện tại. URL-only và history giữ khả năng xem snapshot cũ.
- Frontend gửi đúng measure, chặn thêm tháng quá khứ, giữ khả năng bỏ tháng lịch sử và sửa phần khác. Giá giữ chữ “Từ”; hiển thị ngân sách niêm yết và chú thích phụ thu/thực trả.
- Audit có listed_prices riêng với prices/payable; comparison có budget_measures và cost_disclosures, giữ nguyên policies/evidence. Không tự sinh số phụ thu từ đoạn văn thiếu dữ liệu.

Các lỗi tương thích bắt được trong nghiệm thu đã sửa: timeout PostgreSQL set_config nhận chuỗi; audit không có mode vẫn chạy được; model dump không làm mất budget measure; form giữ dấu vết coverage mặc định.

## Kiểm tra tự động

| Phần | Kết quả |
|---|---|
| Backend `uv run pytest -q` | **510 passed**, 1 cảnh báo deprecation Starlette/TestClient |
| Recovery regression riêng | **32 passed** |
| Ruff lint toàn src/tests | Passed |
| Ruff format các 25 Python files thay đổi | Passed; không sửa format các file baseline ngoài phạm vi |
| JSON schemas | Export lại v2; schema v1 không đổi |
| Frontend unit/integration | **81 passed**, 10 files |
| Frontend lint/build/format files thay đổi | Passed; build có TypeScript check |
| Playwright trên FE worktree + backend root mới | **3 passed**: responsive 1440/1280/390/320, structured review/edit/confirm, bảng 8 cột và evidence |
| Git diff whitespace, cả hai checkout | Passed |

Positive regression: dữ kiện catalog mới/hợp lệ, Nhật Bản từ TP.HCM, giá từ 10 triệu dưới trần listed 12 triệu → 1 recommendation; có listed matrix row, nguyên văn surcharge và trạng thái tiền thực trả chưa tính. Negative kiểm vượt trần, payable chưa đủ upper bound, source không tin cậy, stale, thiếu giá, metadata/proof sai, binding sai.

Các ca khác: tháng 11 OR tháng 1 không lấy tháng 12; historical budget không bị đổi nghĩa; API tìm thời gian đã qua trả 422; đọc requirement cũ còn được; audit phân biệt usable/stale/unverified; date và budget priority cùng offer. Tests dùng dữ liệu tổng hợp có kiểm soát, không chứng minh website còn bán giá đó.

Playwright dùng fixture server tạm ở 8001, FE ở 5175. Luồng structured kiểm API backend mới; ca bảng dùng DTO fixture. Không gọi NIM, không đăng nhập Google hoặc gửi email thật trong bộ nghiệm thu này. Lần chạy trình duyệt đầu bị server Vite thử nghiệm đóng; chạy lại máy chủ trực tiếp đã qua cả 3 ca.

## Supabase thật, chỉ đọc

- Probe: 3 providers, 1.210 tours, 3.319 offers; read-only.
- Lượt Nhật Bản/TP.HCM/tháng 11/2026/listed <=40 triệu: scan 1.000 dòng, 5 trang; static rejected 608; giữ 20 tour/38 offers; **0 recommendation**. Mã lý do có FIELD_STALE và MULTIPLE_OFFERS_UNSELECTED. Scan/pool/offer coverage còn bị cắt.
- Audit production sau sửa: 100 tours/190 offers; 190 listed quotes kind from, verification catalog_validated. **190/190 FIELD_STALE**, không có listed quote usable trong mẫu. Payable pricing_complete vẫn 0.
- Audit saved ở `artifacts/recommendation-recovery-audit.json`; file local bị gitignore. Đây là bounded sample, không là audit mọi record.
- Cả truy vấn mới và PostgreSQL pagination đã chạy với DB thật; không sửa catalog, RLS, giá, timestamp hoặc TTL để tạo positive giả.

**Vì vậy chưa thể hứa có gợi ý từ dữ liệu live hiện tại.** Crawler cần đọc lại lịch/giá từ nguồn rồi cập nhật đúng offer. Cập nhật timestamp provider/tour hoặc refresh trình duyệt không làm giá/offer cũ mới lên. TTL 24 giờ không tự chạy crawler.

## Checkout và bàn giao

- Kiểm lại sau khi gộp tại checkout chính `backend`: **510 backend tests**, **84 frontend unit/integration tests** và **2 browser footer/help tests** đều passed. FE build/TypeScript, lint, BE Ruff và Git whitespace checks passed. Browser chạy trên FE local 5173, chặn auth/v2 để không tạo ticket hoặc gọi nguồn thật.
- BE: `C:\Users\Admin\Desktop\HCMUS-x-HCMUT---TMA`, branch backend.
- FE được implement/test tại `C:\Users\Admin\Desktop\HCMUS-x-HCMUT---TMA-frontend-recovery`, branch feature/minh-phu, baseline 4721773. Theo yêu cầu bàn giao gộp ngày 10/10, code FE recovery và footer/support đã được chuyển vào checkout `backend` cùng BE; worktree nguồn vẫn giữ bản làm việc.
- User đã yêu cầu commit và push một lần lên `origin/backend`. File untracked tên lệnh PowerShell không liên quan được giữ nguyên, ngoài commit. Không đưa `.env`, database hoặc artifacts vào Git.
- Không cần migration Supabase cho listed measure/quotes: đây là contract API/snapshot mới. Không tạo scheduler khi crawler refresh contract chưa có.
- Crawler handoff và các ca positive/negative: [hướng dẫn](../examples/backend-recommendation-recovery.md). Sau recrawl/restart, tạo phiên tìm mới; snapshot comparison cũ không tự thay đổi.
- Giới hạn còn lại: catalog địa danh chưa bao phủ mọi tên; acquisition vẫn bounded; chưa đánh giá live NIM cho prompt mới; chưa bóc tách/tính mọi chi phí ẩn từ prose. Policy payable và việc giữ unknown tiếp tục áp dụng khi dữ liệu chưa đủ.
