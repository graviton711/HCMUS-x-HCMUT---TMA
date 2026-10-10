# Hợp đồng backend

API HTTP cho requirements và comparisons. JSON only. Schema live ở `/openapi.json`; models trong `src/backend/models.py` là nguồn chuẩn duy nhất.

NIM extraction nhận ngày tham chiếu theo giờ Việt Nam. Ngày âm lịch chỉ được đưa vào condition sau khi backend resolve và kiểm tra hợp lệ thành ngày ISO dương lịch; OR trong cùng field được biểu diễn bằng operator `any`. Ngân sách do LLM suy ra cần có con số trong câu nhập, còn giá trị từ form là explicit.

## Endpoints

- `GET /health` → `{status, version}`.
- `POST /requirements` — body `{text?, form?}` → `{requirement}` gồm điều kiện cứng/mềm. Slot thiếu trả về trong `missing`, không đoán.
- `GET /requirements/{id}` → requirement đã lưu.
- `POST /comparisons` — body `{requirement_id?, text?, form?, candidate_limit?}` → `{comparison}` gồm rank ứng viên, chấm từng offer, evidence và phân tích (chi phí ẩn, điều kiện, rủi ro, quyền lợi).
- `GET /comparisons/{id}` → comparison đã lưu.

Lỗi dùng `{error: {code, message}}`. Thiếu là `unknown`, không tính là đạt. Destination không có dữ liệu cũng là `unknown`. Giá chỉ so khi cùng basis (giá exact/người lớn, cùng currency); giá "from" không bao giờ quyết định so sánh. LLM chấm soft chỉ nhận tour còn offer qua hard filter.

## Pipeline

`input` dựng điều kiện → `decide` đọc ứng viên qua `data`, chuẩn hóa qua `normalize`, lọc cứng, LLM chấm mềm kèm quote, rank, phân tích. Chi tiết: [system-architecture](system-architecture.md), [`src/backend/README.md`](../src/backend/README.md).

## Chạy tối thiểu

```powershell
uv sync
uv run tour-backend serve
```

Mặc định `DATA_PROVIDER=fixture` (catalog mẫu, không cần credentials). Đọc catalog thật bằng `DATA_PROVIDER=supabase` + `SUPABASE_TOUR_DB_URL` (chỉ đọc, không ghi). Parse LLM thật cần `NVIDIA_NIM_API`; không có thì text fallback keyword và trường mềm ở `unknown`. Trang chào: `http://127.0.0.1:8000/`, docs tương tác: `http://127.0.0.1:8000/docs`.
