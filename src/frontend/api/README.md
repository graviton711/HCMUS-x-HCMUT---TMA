# API boundary

DTO lấy từ `src/api/v2/models.py`, `routes.py`, `service.py` và domain BE; không import prototype/fixture. Client kiểm envelope và cấu trúc response trước khi trả typed data, dùng bearer và AbortSignal. `/health` có contract riêng. Mutation tạo một idempotency key cho một body, chỉ retry lỗi network/502/503/504 bằng đúng body/key; 409/422 không retry.

`form.ts` serialize structured/text/URLs và tạo typed edits dựa requirement thật. ID của condition/child có sẵn được giữ; cập nhật condition không làm phẳng cây AND/OR hoặc xóa field không có control. Empty optional field chỉ xóa condition tương ứng. Giá/ranking/phân tích do BE cung cấp; FE chỉ định dạng.

Shopping: “không có” = `shopping_stops eq 0 hard`; “ưu tiên ít” = `prefer_low 0 soft`, không tự đặt ngưỡng một điểm. Form không thể biểu diễn nhiều predicates của cùng field: sửa trực tiếp trường này bị chặn, dùng chat/proposal để giữ cây. Các giá trị mặc định slider có origin từ catalog; không tự điền số người/ngân sách từ URL.

Control ngân sách structured hiện có phạm vi VND/người lớn/giá tour và một mức tiền. Budget ngoại tệ, cả nhóm, tổng chuyến hoặc range đã parse được giữ nguyên khi sửa trường khác; sửa trực tiếp budget đó bị chặn và hướng về chat để không đổi currency/basis/coverage/range ngầm.

Kiểm chứng: Vitest cho JSON/envelope/binding, mutation retry và form/edit preservation. Runtime chỉ gọi API thật; fixture chỉ tồn tại trong test.

`backend-runtime.test.ts` chạy `verify_backend.py` bằng Python `.venv` của repo: FastAPI thật/SQLite memory/FakeNim + fixture provider chỉ trong test. Nó kiểm payload actual routes bằng validators FE; không gọi server production, không NIM/network. Cần `uv sync` trước test integration này.


Account/history/what-if: client thêm PATCH metadata, list/detail/archive/link và analysis/apply; account transport refresh single-flight với owner guard. Runtime validators kiểm ratio cohorts, IDs, population, rank bindings. Default budget form hard theo personalized policy; explicit strength cũ được giữ. `needs_clarification` là response hợp lệ, không là lỗi transport. Current readiness can_confirm/can_search được ưu tiên khi BE cấp.
