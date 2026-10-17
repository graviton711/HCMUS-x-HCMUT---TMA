# backend/agent — TourLens decision agent

## Trách nhiệm

Điều phối hội thoại, làm rõ nhu cầu, kiểm tra trước tính khả thi của hard conditions, tạo requirement draft và trích structured facts/evidence từ các trường tour. Agent phân tích ngữ nghĩa; code kiểm chứng quote, chuẩn hóa giá trị, tính toán metric, eligibility và ranking cuối.

## Input/output

- Chat: owner-scoped `agent_session_id` và message; có thể trả text, choices, progress, requirement draft hoặc comparison.
- Decision run: requirement đã được người dùng review, gồm hard/soft conditions và `weight_percent` cho từng soft condition.
- Tool evaluation: mức phù hợp `0|0.5|1|unknown` cho từng ưu tiên, quote khớp snapshot và structured facts cho itinerary, inclusions, exclusions, surcharges, cancellation, child policy.
- Kết quả cuối: metric profiles, các decision options, `ranked`, `near_miss`, evidence và số candidate đã quét.

## Workflow

1. Agent trích hard condition và soft preference. Nếu location cần resolve, agent dùng `catalog_facets` để chọn nhãn có thật trong scan.
2. `discover_destinations` chạy một lần cho cùng bộ điều kiện đã biết, trả ứng viên theo từng nhánh/điểm đến cùng blocker. Đây là preflight chỉ đọc, không tạo comparison, không xác nhận chỗ còn trống hay sức chứa nhóm. Không hỏi người dùng chọn một giá trị họ đã nói là linh hoạt; dùng các lựa chọn catalog-backed để tạo Brief. Không gọi “gần” nếu dữ liệu không chứng minh khoảng cách. `date_from`/`date_to` giới hạn ngày khởi hành ghi nhận; ngày đơn lẻ dùng cùng giá trị cho hai biên. Chúng không xác minh ngày về; một khoảng ngày distinct là một date assumption dùng chung cho mọi nhánh cùng range.
3. Agent tạo Decision Brief với điều kiện chung, ít nhất các lựa chọn khả thi được hỗ trợ bởi preflight, và giả định ngày mơ hồ có thể sửa. Không bắt buộc người dùng chốt một điểm đến trước khi review; chỉ hỏi khi thiếu dữ liệu thiết yếu mà catalog không thể giải quyết. Comparison chỉ chạy sau khi người dùng duyệt Brief.
4. `POST /agent/sessions/{id}/decisions` validate lại requirement và tổng trọng số 100.
5. `query_tours` nhận `decision_run_id` do backend cấp và hard-filter toàn bộ snapshot trên index nhẹ. Context đầu tiên chỉ gồm tối đa 15 tour đạt điều kiện được chọn mẫu đa dạng; detail chỉ hydrate cho mẫu và near-miss hiển thị.
6. Agent trích metric facts theo field và đánh giá từng soft condition trong nhóm hiện tại. Quote phải xuất hiện nguyên văn trong đúng snapshot field. Nội dung dài được chia theo field/chunk; không gộp thành một payload ngắn bị cắt. `soft_review` báo số đủ điều kiện, đã đánh giá, còn lại và giới hạn nhóm.
7. Backend xác thực quote, chuẩn hóa facts và tính metric vector: cost (gồm exclusions), preference fit, experience density, route complexity, inclusion coverage, cancellation flexibility, family suitability và evidence coverage. Engine tạo các objective views/Pareto; MCP lưu Comparison cuối theo `decision_run_id`.
8. Sau khi provider dừng, service lấy Comparison theo mã lượt, kiểm tra khớp requirement, lưu owner-scoped rồi stream kết quả. Không dựa vào model lặp lại JSON kết quả trong output.
9. SSE có progress/tool events an toàn, gắn mô tả cụ thể cho từng thao tác nghiệp vụ đã hỗ trợ. Adapter chuẩn hóa Codex JSONL hoặc OpenCode event về cùng event nghiệp vụ. Trạng thái lỗi áp dụng cho từng lần gọi tool; lượt chat có thể hoàn tất nếu agent sửa lỗi và gọi lại thành công. Không đặt deadline tổng cho agent; client disconnect sẽ hủy process. Giữ timeout riêng của tool/data call.

## Interface với module khác

`api` xác thực owner và gọi agent service. MCP gọi `input`, `workflows`, `normalize` và `decide`; `data` cung cấp catalog và runtime store. Frontend lưu draft trong transcript và gửi bản đã review qua decisions endpoint.

## Quyết định kỹ thuật

- Mỗi chat gắn ID thread của provider owner-scoped; ID provider không lộ client. Mapping lưu riêng `opencode_session_id` và `codex_thread_id` để giữ phiên OpenCode cũ trên Render khi chưa cutover.
- Agent chỉ đề xuất địa điểm sau preflight hard filter; nhiều lựa chọn được giữ trong brief dưới dạng nhánh OR thay vì tự chọn một nhánh. Semantic extraction/fit luôn có quote từ field gốc; backend kiểm tra quote, tính toán số liệu và xếp hạng.
- Không gửi toàn bộ candidate evidence vào một prompt; dùng batch tuần tự trong evaluation context.
- `catalog_facets(fields=[...])` chỉ trả các facet được yêu cầu; agent chỉ hỏi điểm đến hoặc nơi khởi hành cần xác nhận. Dùng `discover_destinations` để kiểm tra điều kiện giá/ngày và tránh đưa toàn bộ facet vào model context.
- `candidates_considered` là số tour đã quét, không phải tổng catalog.
- Snapshot giữ index của mọi offer và detail đầy đủ của ứng viên đã tải; scenario chỉ hydrate record còn thiếu theo khóa nguồn/timestamp trong snapshot, không quét lại catalog.
- Mỗi nhóm soft-review tối đa 15 tour duy nhất, chọn ổn định theo thứ tự ranking có thể tính trước và độ đa dạng nhà cung cấp, tuyến/điểm đến, tháng khởi hành, thời lượng, quartile giá theo currency. `POST /comparisons/{id}/expand` đánh giá nhóm tiếp theo trên cùng snapshot, không lặp tour; tạo comparison phiên bản mới và giữ phiên bản cũ bất biến.
- Mục tiêu đầu ra là ít nhất ba tour khác nhau qua hard filter khi dữ liệu hỗ trợ. Nếu không đủ, báo số thực có và kịch bản nới điều kiện chờ người dùng duyệt.
- Exclusions được phân loại bắt buộc/tùy chọn/có điều kiện; chỉ cộng chi phí khi có amount, unit và applicability rõ. Lợi ích thêm được nêu kèm quote, không quy thành tiền.
- Không lưu hoặc hiển thị private reasoning. Tiến độ chỉ mô tả thao tác tool thực tế; không dùng nhãn tra cứu chung cho bước tạo Decision Brief. Lỗi của một lần gọi tool không đồng nghĩa lượt agent thất bại nếu có kết quả cuối hợp lệ.

## Provider event adapters

Codex emits JSONL events. The adapter maps thread IDs, MCP call lifecycle/results, assistant messages, usage and terminal errors to the shared agent event shape. The gateway loads the system instructions from `configs/prompts/backend-agent.yaml` into an isolated Codex workspace. It enables only the `tour-catalog` MCP server, launches it with the gateway's Python interpreter so startup does not write to the uv cache outside the read-only workspace, pre-approves only the allow-listed MCP tools for non-interactive turns, disables the shell and multi-agent tools, and runs with the read-only sandbox. `AGENT_PROVIDER=opencode` retains the legacy OpenCode event adapter during Render eligibility review.

OpenCode's JSON stream can wrap MCP calls in a `tool_use` event for the Code Mode `execute` tool. Current output places logical calls at `part.state.metadata.metadata.toolCalls`; older output uses `part.state.metadata.toolCalls`. The adapter accepts both shapes, then reads results from `state.output` or `state.content`. It also accepts direct MCP tool events. User-facing progress reports logical MCP operations, not the `execute` wrapper. Only a validated `draft_requirement` result creates a Decision Brief.

For assistant text, group completed parts by OpenCode `messageID` and part ID, ignore repeated events and parts marked `synthetic` or `ignored`, and exclude commentary. Return only the final user-facing assistant message; separate distinct text parts within it with a paragraph boundary. Log aggregate message/part counts only, never the text itself.

## Chạy local

Cấu hình local chat dùng `codex.model=gpt-6-luna`, `codex.reasoning_effort=medium`; `opencode.model` giữ cho survey và chat legacy trên Render. Backend chọn provider qua `AGENT_PROVIDER` và lưu thread ID theo provider. Codex gateway chạy riêng, chỉ mở MCP `tour-catalog`, tắt shell/multi-agent và giữ workspace chỉ đọc. Gateway đặt working directory tiến trình ở workspace cho cả lượt đầu lẫn `exec resume`; không truyền `--cd` vào resume vì Codex CLI 0.162.1 không hỗ trợ cờ đó ở subcommand này. Nếu CLI chưa đăng nhập, gateway khởi tạo device-code flow nền và ghi URL/mã xác thực vào log. Sau Render free spin down/redeploy cần xác thực lại; nếu thread ID cũ không còn, backend xóa mapping cũ và lần gửi lại kế tiếp mở thread mới.

```powershell
corepack pnpm --dir src/frontend dev:all
```

Lệnh này chạy backend, Codex gateway và web; OpenCode CLI/config vẫn được giữ cho `src/ingest/survey.py`. Render tiếp tục dùng OpenCode cho đến khi xác nhận điều kiện dùng ChatGPT plan trên app remote-hosted.

Không ghi mật khẩu vào log hoặc commit giá trị thật.
