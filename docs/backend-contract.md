# Hợp đồng backend

API HTTP cho frontend và các consumer; JSON only. Schema live ở `/openapi.json`; models trong `src/backend/models.py` là nguồn chuẩn duy nhất. Frontend gọi contract này, không gọi `/v2` legacy và không đọc database trực tiếp.

NIM extraction nhận ngày tham chiếu theo giờ Việt Nam. Ngày âm lịch chỉ được đưa vào condition sau khi backend resolve và kiểm tra hợp lệ thành ngày ISO dương lịch; OR trong cùng field được biểu diễn bằng operator `any`. Ngân sách do LLM suy ra cần có con số trong câu nhập, còn giá trị từ form là explicit.

## Endpoints

- `GET /health` → `{status, version}`.
- `POST /requirements` — body `{text?, form?}` → `{requirement}` gồm điều kiện cứng/mềm. Slot thiếu trả về trong `missing`, không đoán.
- `GET /requirements/{id}` → requirement đã lưu.
- `POST /comparisons` — body `{requirement_id?, text?, form?, candidate_limit?}` → `{comparison}` gồm rank ứng viên, chấm từng offer, evidence và phân tích (chi phí ẩn, điều kiện, rủi ro, quyền lợi).
- `GET /comparisons/{id}` → comparison đã lưu.
- `POST /sessions`, `GET /catalog` → guest/account session và lựa chọn canonical cho UI.
- `/auth/*` → Supabase Auth adapter; backend verify identity với đúng provider project, không tin owner ID từ client.
- `/requirements/{id}/revisions/{revision}`, `/requirements/{id}/proposals`, `/proposals/{id}/*` → revision, draft proposal, confirm/cancel/discard explicit.
- `POST /comparison-jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel` → progress có thứ tự và trạng thái terminal; không đổi kết quả comparison đồng bộ hiện có.
- `/history/*` → owner-scoped pagination/detail/metadata/archive và guest-session link explicit.
- `POST /comparisons/{id}/what-if`, `GET /what-if/{id}`, `POST /what-if/{id}/scenarios/{scenario}/proposals` → phân tích bound với comparison, apply chỉ tạo proposal; cần confirm trước lần tìm kế tiếp.
- `/evidence/*`, `/requirements/{id}/messages/*`, `/contacts` → evidence lookup, conversation follow-up và contact ticket.

Lỗi dùng `{error: {code, message}}`. Thiếu là `unknown`, không tính là đạt. Destination không có dữ liệu cũng là `unknown`. Giá chỉ so khi cùng basis (giá exact/người lớn, cùng currency); giá "from" không bao giờ quyết định so sánh. LLM chấm soft chỉ nhận tour còn offer qua hard filter. New account/history/jobs do SQLite application store sở hữu; Supabase catalog vẫn chỉ đọc.

## Pipeline

`input` dựng điều kiện → `decide` đọc ứng viên qua `data`, chuẩn hóa qua `normalize`, lọc cứng, LLM chấm mềm kèm quote, rank, phân tích. Chi tiết: [system-architecture](system-architecture.md), [`src/backend/README.md`](../src/backend/README.md).

## Chạy tối thiểu

```powershell
uv sync
uv run tour-backend serve
```

Mặc định `DATA_PROVIDER=fixture` (catalog mẫu, không cần credentials). Đọc catalog thật bằng `DATA_PROVIDER=supabase` + `SUPABASE_TOUR_DB_URL` (chỉ đọc, không ghi). Parse LLM thật cần `NVIDIA_NIM_API`; không có thì text fallback keyword và trường mềm ở `unknown`. Trang chào: `http://127.0.0.1:8000/`, docs tương tác: `http://127.0.0.1:8000/docs`.
