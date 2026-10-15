# backend/agent — OpenCode travel agent

## Trách nhiệm

Điều phối hội thoại, làm rõ nhu cầu, kiểm tra trước tính khả thi của hard condition đã biết, tạo requirement draft và đánh giá mức phù hợp của sở thích dựa trên evidence trong tour snapshot. Agent không quyết định hard eligibility hoặc tự tính ranking cuối.

## Input/output

- Chat: owner-scoped `agent_session_id` và message; có thể trả text, choices, progress, requirement draft hoặc comparison.
- Decision run: requirement đã được người dùng review, gồm hard/soft conditions và `weight_percent` cho từng soft condition.
- Tool evaluation: verdict `pass|fail|unknown`, quote evidence nguyên văn và reason gắn với candidate/condition.
- Kết quả cuối: `ranked`, `near_miss`, `decision_views`, evidence và số candidate đã quét.

## Workflow

1. Agent trích hard condition từ yêu cầu. Khi cần chọn hoặc xác nhận địa danh, agent đối chiếu các giá trị với `catalog_facets` (nhãn thực trong scan), rồi gửi hard condition đã chuẩn hóa cho `discover_destinations`.
2. `discover_destinations` lọc catalog theo các hard condition đã biết, chỉ trả địa điểm có candidate qua hết điều kiện và đánh dấu riêng candidate chưa xác minh. Đây là preflight chỉ đọc, không tạo comparison hoặc ranking cuối, và không xác nhận chỗ còn trống hay sức chứa nhóm. Nếu không có candidate xác minh được, agent nêu điều kiện chặn thay vì gợi ý điểm đến đoán theo địa lý.
3. Agent hỏi người dùng chọn trong các địa điểm có candidate rồi tạo hoặc cập nhật Decision Brief; chưa chạy comparison cho tới khi người dùng xác nhận.
4. `POST /agent/sessions/{id}/decisions` validate lại requirement và tổng trọng số 100.
5. `query_tours` nhận `decision_run_id` do backend cấp, áp hard filter lên catalog scan và mở context chứa toàn bộ hard-pass candidates.
6. Agent gọi `score_soft` theo batch tới khi mọi candidate/soft condition trong context được đánh giá. Quote phải có trong snapshot; verdict chưa rõ là `unknown`.
7. Backend engine tính weighted view, cheapest view và Pareto view; MCP ghi Comparison cuối vào runtime store theo `decision_run_id`.
8. Sau khi OpenCode dừng, service lấy Comparison theo mã lượt, kiểm tra khớp requirement, lưu owner-scoped rồi stream kết quả. Không dựa vào model lặp lại JSON kết quả trong output.
9. SSE có progress/tool events an toàn, gắn mô tả cụ thể cho từng thao tác nghiệp vụ đã hỗ trợ. Trước khi lập nhãn, service chuẩn hóa MCP tool ID theo tên nghiệp vụ; OpenCode ghép tool ID từ tên server đã sanitize và tên tool. Trạng thái lỗi áp dụng cho từng lần gọi tool; lượt chat có thể hoàn tất nếu agent sửa lỗi và gọi lại thành công. Không đặt deadline tổng cho agent; client disconnect sẽ hủy process. Giữ timeout riêng của tool/data call.

## Interface với module khác

`api` xác thực owner và gọi agent service. MCP gọi `input`, `workflows`, `normalize` và `decide`; `data` cung cấp catalog và runtime store. Frontend lưu draft trong transcript và gửi bản đã review qua decisions endpoint.

## Quyết định kỹ thuật

- Mỗi chat gắn một OpenCode session owner-scoped; ID OpenCode không lộ client.
- Agent đánh giá semantic fit; engine kiểm tra hard rules, evidence, trọng số và kết quả xếp hạng. Mọi đề xuất trước brief đều lấy từ candidate thực qua hard filter; địa danh được đối chiếu với nhãn catalog thay vì danh sách alias viết cứng.
- Không gửi toàn bộ candidate evidence vào một prompt; dùng batch tuần tự trong evaluation context.
- `candidates_considered` là số tour đã quét, không phải tổng catalog.
- Mục tiêu đầu ra là ít nhất ba phương án khác nhau có dữ liệu, theo các mục tiêu phù hợp với yêu cầu và field catalog hiện có. Chỉ dùng candidate qua hard filter; nếu catalog có dưới ba candidate, báo đúng số hiện có thay vì nới điều kiện hoặc tự sinh tour.
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
