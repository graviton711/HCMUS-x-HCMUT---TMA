# backend/agent — OpenCode travel agent

## Trách nhiệm

Giữ một OpenCode conversation cho mỗi chat local, cung cấp MCP tools grounded vào catalog, hard-filter và evidence, và trả lời nhiều lượt tự nhiên. Agent quyết định khi cần hỏi thêm, tìm tour, xem chi tiết hoặc nới tiêu chí.

## Input/output

- Tạo session: guest owner từ Bearer token; trả `agent_session_id` local.
- Gửi tin nhắn: `agent_session_id` + nội dung lượt mới; backend gắn OpenCode session tương ứng. Hỗ trợ JSON response cho client cũ và SSE khi client gửi `Accept: text/event-stream`.
- Tool inputs là điều kiện có cấu trúc. Tiền chỉ nhận integer VND, ngày chỉ nhận ISO; giá trị sai định dạng bị loại hoặc thành `unknown`, không suy đoán.
- Trả về câu trả lời cuối của assistant (bỏ commentary trung gian), lựa chọn hỏi thêm, thông tin tour có evidence, soft verdicts và tối đa 5 tour.

## Workflow

1. `POST /agent/sessions` tạo local session cho owner.
2. `POST /agent/sessions/{id}/messages` chạy `opencode run --attach`; lượt đầu chưa có OpenCode ID, backend lấy ID từ JSON events và lưu mapping trong runtime store. Không đặt deadline tổng cho lượt agent; khi client ngắt kết nối, backend hủy tiến trình đang chạy. Khi dùng SSE, trạng thái bắt đầu và từng tool call (`running`, `completed`, `error`) được gửi ngay khi nhận từ OpenCode, kèm mô tả hành động dựng từ tên tool và input cấu trúc đã cho phép; không đưa private reasoning hay message tự do do model viết vào tiến độ. Backend và OpenCode/MCP không tự reload code, cần khởi động lại sau khi sửa.
3. Agent gọi MCP tools tùy hội thoại: `ask_choice`, `catalog_facets`, `query_tours`, `tour_detail`, `score_soft`, `relax_criterion`, `clarify_date`.
4. MCP schema của `query_tours` yêu cầu mỗi condition có ID, `field`, `operator`, `value`, `strength` và `quote`; backend kiểm tra lại điều kiện và quote theo cùng contract với API. Agent quét catalog đến `backend.data.scan_limit` (hiện là 2000 theo `configs/settings.yaml`), độc lập với `backend.api.candidate_default` (20) của endpoint comparison đồng bộ cũ. `query_tours` trả trạng thái pass/unknown/fail và reason code gọn cho mọi offer; comparison/evidence chi tiết giới hạn tối đa 5 tour duy nhất, chọn offer xếp hạng cao nhất cho mỗi tour để các ngày khởi hành không thành thẻ trùng. `score_soft` nhận nguyên requirement từ kết quả query, chỉ chấm ứng viên pass trong danh sách ranked, xác minh quote nguyên văn từ tour/evidence, rồi xếp hạng theo số verdict hợp, sau đó giá.
5. Backend lưu requirement/comparison thuộc guest owner; kết quả hiển thị tối đa 5 tour.

## Interface với module khác

`api` xác thực owner và gọi agent service. `data` cung cấp catalog và runtime store. MCP tools dùng `models`, `decide.engine`, `normalize` và `input.lunar`; không có quyền ghi catalog hoặc gọi crawler. Frontend gửi từng lượt và render text, `ask_choice`, tool progress và ResultCards.

## Quyết định kỹ thuật

- Một `opencode serve` local được giữ chạy; backend tạo tiến trình nhẹ `opencode run --attach` cho mỗi lượt, không khởi chạy daemon riêng.
- Mapping owner/local session/OpenCode session được giữ trong runtime store; client không gửi hay nhận OpenCode ID.
- Agent/model prompt không thay đổi theo destination. `catalog_facets` chỉ trả dữ liệu thực tế đã quét; `scanned_tours` là số bản ghi đã đọc, không phải tổng số tour trong catalog. `scan_limit` là trần truy xuất có cấu hình, không phải khẳng định catalog chỉ có từng ấy tour.
- Với yêu cầu quốc gia/vùng, agent dùng hiểu biết địa lý để chọn destination label thực có trong `catalog_facets`; gửi một nhãn bằng `contains`, nhiều nhãn bằng `any`. Nếu không xác định được nhãn phù hợp, agent hỏi lại; không kết luận toàn catalog không có kết quả từ facets đã quét.
- Nội dung hướng tới người dùng phải dùng tiếng Việt có dấu. `ask_choice` chuẩn hóa chính tả lựa chọn trùng khớp duy nhất với tên destination trong catalog; giá trị không khớp hoặc mơ hồ được giữ nguyên. Tiến độ tool được tạo từ loại thao tác và input an toàn, các lần gọi có cùng mô tả được gom ở UI và hiện số lần thay vì lặp dòng.
- Tên điểm đến cụ thể phải được xác nhận đúng theo `catalog_facets`; không được biến điểm đến cấp tỉnh thành xác nhận cho địa danh nhỏ hơn. Khi không có tour đạt đủ nhưng có `near_miss`, câu trả lời phải phân biệt “chưa có tour được xác minh đạt đủ điều kiện” với “không có tour ở điểm đến đó”. Lượt chat mới cập nhật điều kiện trong cùng chuyến đi, thay điều kiện mâu thuẫn thay vì giữ cả hai.
- Hard filter, evidence, freshness ngày khởi hành, near-miss và phân tích rủi ro vẫn là quy tắc xác định. Giá ngân sách dùng trường giá catalog trực tiếp, không qua domain/metadata trust gate; tuổi giá không chặn quyết định. Free-text keyword/NIM extraction và slot state machine bị loại.
- Tool responses được xác thực trước lưu/hiển thị; lỗi soft scoring trở thành `unknown`, không làm hỏng hard-filter result.
- Không lọc danh sách tool bằng `tools: { "*": false }`: cấu hình đó làm Muse Spark free trả 403 qua CLI, kể cả khi bật lại `read`. Giữ schema tool mặc định để tương thích; đặt permission `*` thành `ask` và chỉ cho phép `tour-catalog_*`. Runner không duyệt permission, nên tool hệ thống không thể chạy tự động; agent chỉ được gọi MCP catalog trong các lượt chat.
- Local-first: cùng MCP server và agent config được dùng khi triển khai server OpenCode riêng. Cùng endpoint giữ chế độ JSON mặc định và thương lượng SSE qua `Accept`, tránh đổi contract client cũ.
- Không có timeout tổng cho agent; timeout riêng của từng MCP call và kết nối dữ liệu vẫn được giữ.

## Chạy local

Đảm bảo `.env` có `OPENCODE_SERVER_URL=http://127.0.0.1:4098` như `.env.example`, rồi chạy `opencode serve --hostname 127.0.0.1 --port 4098` trước backend.
