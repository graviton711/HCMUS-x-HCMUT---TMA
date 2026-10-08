# Tour Decision Support

Hệ thống hỗ trợ người Việt so sánh tour và nhà cung cấp dựa trên dữ liệu có nguồn gốc, độ mới và trade-off rõ ràng. Người dùng tự quyết định; sản phẩm không tự lập lịch trình hay đặt tour.

```mermaid
flowchart LR
    U[Người dùng nhập nhu cầu hoặc URL tour] --> Q[Chuẩn hóa yêu cầu]
    Q --> S[Truy vấn các nguồn đã kiểm tra]
    S --> E[Trích xuất dữ liệu có cấu trúc]
    E --> V[Kiểm tra field, nguồn và thời điểm]
    V --> C[Lọc và so sánh minh bạch]
    C --> R[Bảng so sánh, bằng chứng và trade-off]
    R --> U
```

Idea, kiến trúc và wireframe đã chốt. Backend có `/v1` và `/v2`: hiểu nhu cầu qua NVIDIA NIM, proposal đa field chờ xác nhận, form/URL/hybrid, so sánh/ranking/evidence, durable jobs/events và admin/contact. Xem [runtime v2](docs/backend-v2-runtime.md) và [hướng dẫn nối frontend](examples/backend-v2.md). Package `tourcrawl` chạy độc lập; chưa có adapter nối output crawler vào backend. API mặc định dùng dữ liệu mô phỏng; frontend prototype đang review, chưa gọi API thật.

- [Proposal và phân tích bài toán](docs/idea.md)
- [Kiến trúc hệ thống](docs/system-architecture.md)
- [Wireframe](docs/wireframes.md)
- [Kế hoạch backend để thảo luận](docs/backend-plan.md)
- [Contract dữ liệu backend — bản nháp](docs/backend-contracts.md)
- [Module hiểu yêu cầu — bản nháp](src/requirements/README.md)
- [Contract crawler và mẫu JSON — bản nháp](docs/crawler-contract.md)
- [Contract API cho frontend — bản nháp](docs/api-contract.md)
- [Bộ tình huống đánh giá tiếng Việt](docs/requirements-evaluation.md)
- [Phân công/quy ước Git](docs/team-workflow.md), [registry nguồn](docs/provider-registry.md)

## Chạy backend

Python >= 3.12 và uv. Chạy từ thư mục repo:

```powershell
uv sync
uv run tour-backend serve
```

Trang chào backend: `http://127.0.0.1:8000/`; tài liệu tương tác: `http://127.0.0.1:8000/docs`. Sau khi sửa code, dừng server bằng Ctrl+C rồi chạy lại để nạp thay đổi.
NIM đọc `NVIDIA_NIM_API` và `NVIDIA_NIM_MODEL` từ `.env` hiện có. Ngân sách chưa nói phạm vi mặc định là **giá tour**, có provenance `system_default`; currency/basis chưa rõ vẫn được hỏi lại.

Đọc kho tour thật bằng `DATA_PROVIDER=supabase` và `SUPABASE_TOUR_DB_URL`. Dùng API **v2**; [khởi động và test Supabase từng bước](examples/backend-supabase-v2.md). `uv run tour-backend probe-supabase` kiểm tra kết nối/counts bằng transaction chỉ đọc. SQLite vẫn lưu phiên, nhu cầu và kết quả; Supabase lưu catalog do crawler cập nhật.

Semantic extraction v2 (`requirements-v2.2`) giữ ghép đoàn, tuyến đường, các ưu tiên định tính và khoảng lịch âm; hỏi năm/ý nghĩa khoảng trước khi quy đổi. [Test ca Tết từng bước](examples/backend-semantic-v2.md), [contract frontend/crawler](docs/requirements-semantics.md), [kết quả kiểm chứng](docs/requirements-evaluation.md). Cần tạo request mới sau khi restart để thử parser mới; lịch sử không tự được trích xuất lại.

Pipeline v2 lọc structured hard conditions trước khi cắt pool, kiểm tra toàn bộ yêu cầu trên từng offer; LLM đánh giá ưu tiên ngữ nghĩa bằng trích dẫn, backend tính ranking với coverage/khoảng điểm. Hard/soft độc lập kiểu dữ liệu. [Hướng dẫn test và đọc output](examples/backend-retrieval-semantic-v2.md), [kết quả và phần dữ liệu còn thiếu](docs/backend-retrieval-assessment-results.md).

Form/text v2 dùng chung năm core fields trước confirm/search; draft được phép thiếu, ngân sách form là hard cap giá tour/người lớn. Xem [flow mới và typed answers](examples/backend-personalized-v2.md), [nghiệm thu](docs/backend-personalized-verification.md). `uv run tour-backend audit-supabase` đọc catalog và xuất báo cáo chất lượng có giới hạn; không cập nhật rows hoặc tạo dữ liệu tour.

Sau comparison, v2 có phân tích nếu bỏ/nới điều kiện: đọc snapshot rộng, giữ hard/soft và AND/OR, đo lựa chọn/thứ hạng thay đổi, công khai bằng chứng và tỷ lệ có mẫu số. Kịch bản tạo proposal để review; chưa tự đổi nhu cầu. [Hướng dẫn test](examples/backend-what-if-v2.md), [policy](docs/what-if-analysis.md), [kết quả kiểm chứng](docs/backend-what-if-verification.md).

- [Hướng dẫn frontend, payload và cấu hình](examples/README.md)
- [Runtime, lệnh kiểm tra và giới hạn](docs/backend-runtime.md)
- [JSON Schema đã xuất cho team](contracts/README.md)

## Planning frontend

Frontend đang PLANNING; chưa production UI hoặc chốt stack. Ngày 06/10/2026 user chốt **Giấy & Mực**, Newsreader + Be Vietnam Pro; flow mới **Giới thiệu → form + xác nhận → Kết quả**, criteria rộng/sửa trực tiếp/chat có diff xác nhận, bảng kiểm chứng + Phân tích AI, log/loading mock và accent/motion. Token/màn chi tiết còn review; G1–G13/D1–D5 giữ phần backend cần chốt.

- [Roadmap 7 phase và todo frontend](docs/frontend-plan.md)
- [Quyết định review nhóm 06/10/2026](docs/frontend-review-2026-10-06.md), [prototype minh họa](prototypes/frontend-design/README.md)
- [Flow và trạng thái UI](docs/frontend-flows.md)
- [Hướng tích hợp API v1 theo code](docs/frontend-api-integration.md)
- [Checklist contract và khoảng thiếu cần trao đổi với BE](docs/frontend-backend-checklist.md)
- [Đối chiếu crawler/backend và công việc tích hợp dữ liệu](docs/frontend-crawler-integration.md)
- [Chuẩn bị skill/thiết kế](docs/frontend-design-preparation.md), [module frontend](src/frontend/README.md)

## Kiểm tra backend

Mặc định của code là `DATA_PROVIDER=fixture`: ba tour giả lập tại `tour-demo.invalid`, `origin=synthetic`. Cấu hình `supabase` đọc catalog thật và trả `origin=source`, không fallback sang dữ liệu giả. [Catalog validation](docs/catalog-validation-policy.md) cho phép field qua kiểm tra thuộc domain opt-in được dùng với trạng thái `catalog_validated`; website proof là bổ sung. Giá thiếu qualifiers, field mơ hồ hoặc freshness chưa rõ vẫn `unknown`. Local runtime dùng SQLite và một worker; không chạy nhiều process trên cùng application database.

```powershell
uv run pytest -q
uv run ruff check src tests
uv run tour-backend export-schemas
```

Gọi NIM thật (tách khỏi tests offline): `uv run tour-backend probe-nim`; bộ smoke tiếng Việt: `uv run tour-backend evaluate-nim`. Kết quả smoke không thay bộ gold 50 câu + 15 chuỗi hội thoại đầy đủ.

## Crawler và dữ liệu

[tourcrawl pipeline](src/tourcrawl/pipeline/README.md) chạy CLI độc lập, output CSV/JSON detail; profiles tại `configs/profiles/`. Browser flow cần `uv sync --extra browser` và Chromium của Playwright. Các script khảo sát/profile nằm tại `scripts/`, đọc/ghi artifacts được ignore; không có bộ dữ liệu tour thật đã nghiệm thu trong Git.

HTTP crawler giữ [contract v1](docs/crawler-contract.md); Supabase có [reader/adapter v2](src/data_access/supabase/README.md). Không cần bulk backfill proof: crawler cần làm rõ price qualifiers/cadence và các field mơ hồ; quote bổ sung có chọn lọc. Backend chưa tự đặt TTL hoặc gọi live crawler khi URL vắng trong kho. [Hướng dẫn cấu hình](examples/backend-catalog-validation.md), [nghiệm thu hiện hành](docs/backend-catalog-validation-verification.md); [baseline trước policy mới](docs/supabase-tour-integration-plan.md).
