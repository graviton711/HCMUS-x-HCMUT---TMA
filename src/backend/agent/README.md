# backend/agent — OpenCode travel agent

## Trách nhiệm

Điều phối hội thoại, làm rõ nhu cầu, kiểm tra trước tính khả thi của hard conditions, tạo requirement draft và trích structured facts/evidence từ các trường tour. Agent phân tích ngữ nghĩa; code kiểm chứng quote, chuẩn hóa giá trị, tính toán metric, eligibility và ranking cuối.

## Input/output

- Chat: owner-scoped `agent_session_id` và message; có thể trả text, choices, progress, requirement draft hoặc comparison.
- Decision run: requirement đã được người dùng review, gồm hard/soft conditions và `weight_percent` cho từng soft condition.
- Tool evaluation: mức phù hợp `0|0.5|1|unknown` cho từng ưu tiên, quote khớp snapshot và structured facts cho itinerary, inclusions, exclusions, surcharges, cancellation, child policy.
- Kết quả cuối: metric profiles, các decision options, `ranked`, `near_miss`, evidence và số candidate đã quét.

## Workflow

1. Agent trích hard condition từ yêu cầu. Khi cần chọn hoặc xác nhận địa danh, agent đối chiếu các giá trị với `catalog_facets` (nhãn thực trong scan), rồi gửi hard condition đã chuẩn hóa cho `discover_destinations`.
2. `discover_destinations` lọc catalog theo các hard condition đã biết, chỉ trả địa điểm có candidate qua hết điều kiện và đánh dấu riêng candidate chưa xác minh. Đây là preflight chỉ đọc, không tạo comparison hoặc ranking cuối, và không xác nhận chỗ còn trống hay sức chứa nhóm. Nếu không có candidate xác minh được, agent nêu điều kiện chặn thay vì gợi ý điểm đến đoán theo địa lý.
3. Agent hỏi người dùng chọn trong các địa điểm có candidate rồi tạo hoặc cập nhật Decision Brief; chưa chạy comparison cho tới khi người dùng xác nhận.
4. `POST /agent/sessions/{id}/decisions` validate lại requirement và tổng trọng số 100.
5. `query_tours` nhận `decision_run_id` do backend cấp, áp hard filter lên catalog scan và mở context chứa toàn bộ hard-pass candidates.
6. Agent trích metric facts theo field và đánh giá từng soft condition cho mọi candidate trong context. Quote phải xuất hiện nguyên văn trong đúng snapshot field. Nội dung dài được chia theo field/chunk; không gộp thành một payload ngắn bị cắt.
7. Backend xác thực quote, chuẩn hóa facts và tính metric vector: cost (gồm exclusions), preference fit, experience density, route complexity, inclusion coverage, cancellation flexibility, family suitability và evidence coverage. Engine tạo các objective views/Pareto; MCP lưu Comparison cuối theo `decision_run_id`.
8. Sau khi OpenCode dừng, service lấy Comparison theo mã lượt, kiểm tra khớp requirement, lưu owner-scoped rồi stream kết quả. Không dựa vào model lặp lại JSON kết quả trong output.
9. SSE có progress/tool events an toàn, gắn mô tả cụ thể cho từng thao tác nghiệp vụ đã hỗ trợ. Trước khi lập nhãn, service chuẩn hóa MCP tool ID theo tên nghiệp vụ; OpenCode ghép tool ID từ tên server đã sanitize và tên tool. Trạng thái lỗi áp dụng cho từng lần gọi tool; lượt chat có thể hoàn tất nếu agent sửa lỗi và gọi lại thành công. Không đặt deadline tổng cho agent; client disconnect sẽ hủy process. Giữ timeout riêng của tool/data call.

## Interface với module khác

`api` xác thực owner và gọi agent service. MCP gọi `input`, `workflows`, `normalize` và `decide`; `data` cung cấp catalog và runtime store. Frontend lưu draft trong transcript và gửi bản đã review qua decisions endpoint.

## Quyết định kỹ thuật

- Mỗi chat gắn một OpenCode session owner-scoped; ID OpenCode không lộ client.
- Agent chỉ đề xuất địa điểm sau preflight hard filter. Semantic extraction/fit luôn có quote từ field gốc; backend kiểm tra quote, tính toán số liệu và xếp hạng.
- Không gửi toàn bộ candidate evidence vào một prompt; dùng batch tuần tự trong evaluation context.
- `candidates_considered` là số tour đã quét, không phải tổng catalog.
- Mục tiêu đầu ra là ít nhất ba tour khác nhau qua hard filter khi dữ liệu hỗ trợ. Nếu không đủ, báo số thực có và kịch bản nới điều kiện chờ người dùng duyệt.
- Exclusions được phân loại bắt buộc/tùy chọn/có điều kiện; chỉ cộng chi phí khi có amount, unit và applicability rõ. Lợi ích thêm được nêu kèm quote, không quy thành tiền.
- Không lưu hoặc hiển thị private reasoning. Tiến độ chỉ mô tả thao tác tool thực tế; không dùng nhãn tra cứu chung cho bước tạo Decision Brief. Lỗi của một lần gọi tool không đồng nghĩa lượt agent thất bại nếu có kết quả cuối hợp lệ.

## OpenCode event adapter

OpenCode's JSON stream can wrap MCP calls in a `tool_use` event for the Code Mode `execute` tool. Current output places logical calls at `part.state.metadata.metadata.toolCalls`; older output uses `part.state.metadata.toolCalls`. The adapter accepts both shapes, then reads results from `state.output` or `state.content`. It also accepts direct MCP tool events. User-facing progress reports logical MCP operations, not the `execute` wrapper. Only a validated `draft_requirement` result creates a Decision Brief.

## Chạy local

Cấu hình model dùng chung tại `configs/settings.yaml` (`opencode.model`). Backend truyền chính giá trị đó bằng `--model`; agent profile và biến môi trường không khai báo model riêng. Cấu hình `OPENCODE_SERVER_URL`, `OPENCODE_SERVER_PASSWORD`, `OPENCODE_AGENT` và `OPENCODE_PROJECT_DIR` trong `.env`. Backend truyền mật khẩu cho mỗi tiến trình `opencode run --server <URL>`. CLI dùng thư mục làm việc làm project context; mặc định là root repo:

```powershell
# Terminal 1
uv run tour-opencode serve
# Terminal 2
uv run tour-backend serve
```

Có thể override địa chỉ bind bằng `--hostname`. Cổng luôn lấy từ URL để tránh lệch với backend. Trên Windows, launcher theo npm shim tới native executable. Lệnh này dùng cho OpenCode local; server remote tiếp tục được quản lý bởi nền tảng deploy.

Không ghi mật khẩu vào log hoặc commit giá trị thật.
