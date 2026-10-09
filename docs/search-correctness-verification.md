# Kiểm chứng sửa tìm tour — 09/10/2026

Phạm vi theo [kế hoạch sửa](search-correctness-repair.md). Code FE/BE trên `backend` theo quyền user đã cấp; Supabase chỉ đọc. Không commit/push, không sửa dữ liệu nguồn hoặc các comparison đã lưu.

## Kết quả đã sửa

| Vấn đề | Hành vi hiện tại |
| --- | --- |
| Tour nước ngoài chứa TP.HCM ở đầu/cuối được hiểu là điểm đến Việt Nam | Bỏ origin endpoints khỏi view destinations, giữ raw/route; bổ sung alias/hierarchy Trung Quốc, Đài Loan, Brunei. Structured và semantic v2 dùng chung hierarchy. Tên chưa hiểu vẫn partial/unknown. |
| Ngày/giá đều unknown nhưng khó biết nguyên nhân | Phân biệt thiếu policy, dữ liệu stale và timestamp tương lai. Local TTL ngày/giá là 86400 giây theo xác nhận user. Lịch mới sai ngày bị loại trước pool; lịch cũ chưa chứng minh được tình trạng hiện tại. |
| Giá có trong DB nhưng không đủ điều kiện đánh giá hard cap | Nhận optional `offers.field_meta.pricing`, validate amount/basis/kind/currency/time/completeness trước dùng. Exact/from giữ bounds; phụ thu có cấu trúc đi vào phép tính. Không tự tạo qualifiers hoặc complete=true. |
| Lượt tìm hoàn thành nhưng log còn ghi đang thực hiện | Started được hiển thị “Đã bắt đầu”; trạng thái job hiện tại vẫn riêng. Orchestration/publication có nhãn VI/EN. |
| 0 gợi ý và nhiều tour đối chiếu gây hiểu nhầm | Nêu số tour cần xác nhận, blockers hard theo field/reason, scope scan/pool/offers và lý do AI chưa chạy. Đếm tour duy nhất, ưu tiên diagnostics từng offer. |
| Khôi phục lịch sử mất comparison/what-if đã hoàn thành | Đọc requirement_id ở cả payload queued và wrapper result terminal. Giữ owner guards. |

Comparison mới ghi policy `decision-v2.4-search`; catalog `tour-entities-v2.2`. V1 không đổi. JSON schema mới: `contracts/v2/CatalogPricing.schema.json`; các schema cũ giữ nguyên.

## Kiểm tra tự động

- Backend: `uv run pytest -q` — **478 passed**, 1 cảnh báo deprecation Starlette/httpx; không test lỗi. Regression mới nằm ở `tests/test_search_correctness.py` (28 cases), gồm địa danh/hierarchy, lịch fresh/stale, giá exact/from, metadata mâu thuẫn/untrusted, phụ thu và history resume. Schema export kiểm thêm nội dung CatalogPricing và đủ 29 schemas v2.
- Frontend: `npm test` — **68 passed / 9 files**. `SearchResults.test.tsx` có 4 cases cho terminal log, unique tour counts/per-offer blockers, VI/EN và bỏ panel khi không còn lý do cần hiển thị.
- Ruff, ESLint, typecheck, Prettier cho các file FE sửa và production build: pass.
- Browser: test `comparison contract example` — **1 passed**. Kiểm bảng/panel scope tại 1440/1280/390/320px, không overflow toàn trang; bảng cuộn riêng, evidence drawer hoạt động, không page errors. Dùng harness trên 18000/15173, đã dừng sau kiểm tra; không thay server user ở 8000/5173. Screenshots ở `artifacts/frontend/comparison-contract-test-*` là **DTO test**, không bằng chứng tour live.

Các test offline dùng fixtures/stubs tại test, không tạo tour giả trong runtime. Đợt này không kiểm lại Google/email OAuth hoặc gọi NIM live.

## Replay Supabase thật, chỉ đọc

Dùng requirement snapshot của comparison `comparison_8b22c066953d477a81fb2ae95660ba21`: Việt Nam, xuất phát TP.HCM, ngày 07/02/2027, trần 30 triệu VND/người lớn/giá tour; giữ party và các ưu tiên của lượt gốc. Tạo application SQLite tạm; semantic assessment/what-if prose bị tắt, không gọi NIM hoặc ghi Supabase.

- Job mới succeeded, empty_reason `ONLY_UNVERIFIED`.
- Quét 1000 records; static_rejected 395; offer_rejected 0; giữ 20 tour unknown. Scan/pool/offer coverage đều bị giới hạn; không đại diện toàn bộ catalog.
- 0 recommendations, 20 needs_verification. Reason counts trong evaluations: FIELD_STALE 88, PRICE_COVERAGE_UNCONFIRMED 88. Đây là **số evaluations**, không phải số tour.
- Năm cột đầu là các tour trong nước (Miền Bắc, Nha Trang, Đông Bắc), condition destinations Việt Nam pass. Regression riêng chứng minh các tour Thượng Hải/Đài Loan/Brunei có origin TP.HCM không pass Việt Nam.
- Lịch/giá hiện quan sát từ 07/10 đã quá 24 giờ ở thời điểm chạy. Catalog hiện thiếu metadata phạm vi/điều kiện giá; 0 gợi ý vẫn là kết quả đúng theo hard gate, không là job bị treo.

## User và crawler làm tiếp

1. Dừng backend đang chạy bằng Ctrl+C, khởi động lại từ repo root: `uv run tour-backend serve`. Reload frontend, giữ Vite đang chạy hoặc khởi động theo README frontend.
2. Tạo **lượt tìm mới** với nhu cầu đã xác nhận; comparison lịch sử không được viết lại. Kiểm nhật ký Hoàn thành, panel blockers và mục Phạm vi/giới hạn nguồn.
3. Crawler đọc lại lịch/giá thực tế và cập nhật observed_at khi đã quan sát lại. TTL 24 giờ **không tạo lịch tự động crawl**.
4. Bổ sung optional pricing metadata theo [ví dụ và quy tắc](../examples/catalog-price-metadata.md). Cột field_meta JSONB đã có; không cần migration chỉ để thêm object pricing. Chưa xác nhận complete/coverage/applicability thì giữ thiếu/false, giá from vẫn là from.

Không sửa timestamp, đổi from thành exact hoặc khai báo phụ thu bằng 0 chỉ để có recommendation. Các địa danh chưa mapping, return_date/tour_type/scoped transport và qualitative metrics chưa có đủ nguồn vẫn giữ unknown/unsupported theo policy hiện hành.
