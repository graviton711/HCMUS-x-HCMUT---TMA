# backend/agent — OpenCode travel agent

## Trách nhiệm

Điều phối hội thoại, làm rõ nhu cầu, tạo requirement draft chưa truy vấn catalog, và đánh giá mức phù hợp của từng sở thích dựa trên evidence trong tour snapshot. Agent không quyết định hard eligibility hoặc tự tính ranking cuối.

## Input/output

- Chat: owner-scoped `agent_session_id` và message; có thể trả text, choices, progress, requirement draft hoặc comparison.
- Decision run: requirement đã được người dùng review, gồm hard/soft conditions và `weight_percent` cho từng soft condition.
- Tool evaluation: verdict `pass|fail|unknown`, quote evidence nguyên văn và reason gắn với candidate/condition.
- Kết quả cuối: `ranked`, `near_miss`, `decision_views`, evidence và số candidate đã quét.

## Workflow

1. Chat tạo hoặc cập nhật Decision Brief; chưa gọi tour query cho tới khi người dùng xác nhận.
2. `POST /agent/sessions/{id}/decisions` validate lại requirement và tổng trọng số 100.
3. `query_tours` nhận `decision_run_id` do backend cấp, áp hard filter lên catalog scan và mở context chứa toàn bộ hard-pass candidates.
4. Agent gọi `score_soft` theo batch tới khi mọi candidate/soft condition trong context được đánh giá. Quote phải có trong snapshot; verdict chưa rõ là `unknown`.
5. Backend engine tính weighted view, cheapest view và Pareto view; MCP ghi Comparison cuối vào runtime store theo `decision_run_id`.
6. Sau khi OpenCode dừng, service lấy Comparison theo mã lượt, kiểm tra khớp requirement, lưu owner-scoped rồi stream kết quả. Không dựa vào model lặp lại JSON kết quả trong output.
7. SSE có progress/tool events an toàn. Không đặt deadline tổng cho agent; client disconnect sẽ hủy process. Giữ timeout riêng của tool/data call.

## Interface với module khác

`api` xác thực owner và gọi agent service. MCP gọi `input`, `workflows`, `normalize` và `decide`; `data` cung cấp catalog và runtime store. Frontend lưu draft trong transcript và gửi bản đã review qua decisions endpoint.

## Quyết định kỹ thuật

- Mỗi chat gắn một OpenCode session owner-scoped; ID OpenCode không lộ client.
- Agent đánh giá semantic fit; engine kiểm tra hard rules, evidence, trọng số và kết quả xếp hạng.
- Không gửi toàn bộ candidate evidence vào một prompt; dùng batch tuần tự trong evaluation context.
- `candidates_considered` là số tour đã quét, không phải tổng catalog.
- Không lưu hoặc hiển thị private reasoning. Tiến độ chỉ mô tả thao tác tool thực tế.

## Chạy local

Cấu hình `OPENCODE_SERVER_URL` theo `.env.example`; chạy `opencode serve` trước backend.
