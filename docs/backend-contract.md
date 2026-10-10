# Hợp đồng backend

API HTTP cho frontend và các consumer; JSON only. Schema live ở `/openapi.json`; models trong `src/backend/models.py` là nguồn chuẩn duy nhất. Frontend gọi contract này, không gọi `/v2` legacy và không đọc database trực tiếp.

NIM extraction nhận ngày tham chiếu theo giờ Việt Nam. Ngày âm lịch chỉ được đưa vào condition sau khi backend resolve và kiểm tra hợp lệ thành ngày ISO dương lịch; OR trong cùng field được biểu diễn bằng operator `any`. Ngân sách do LLM suy ra cần có con số trong câu nhập, còn giá trị từ form là explicit.

## Current runtime

- `GET /health` → `{status, version}`.
- `POST /sessions` → guest session Bearer token with expiry. Only a SHA-256 token hash is persisted.
- `GET /catalog` → `{destinations}` from the active read-only catalog provider; this is a basic lookup, not the richer frontend catalog contract.
- `POST /requirements` — body `{text?, form?}` → `{requirement}` gồm điều kiện cứng/mềm. Slot thiếu trả về trong `missing`, không đoán.
- `GET /requirements/{id}` → requirement đã lưu.
- `POST /comparisons` — body `{requirement_id?, text?, form?, candidate_limit?}` → `{comparison}` gồm rank ứng viên, chấm từng offer, evidence, phân tích và snapshot candidate tự chứa để kết quả đã lưu vẫn render được.
- `GET /comparisons/{id}` → comparison đã lưu.
- `GET /history?limit=&cursor=` and `GET /history/{id}` → cursor pagination and owner-scoped requirement/comparison detail for guest sessions.

Requirements/comparisons created without a Bearer token remain unowned for backward compatibility. When a guest Bearer token is supplied, reads and history are restricted to that session. Existing unowned records are preserved by the schema migration. `POST /comparisons` runs synchronously.

Guest frontend vertical slice supports destination, departure city/date, maximum budget and duration via `form`. Other criteria are not silently treated as evaluated; unsupported criteria remain outside this runtime contract.

## Remaining integration target (not yet runtime)

- `/auth/*` → Supabase Auth adapter; backend verify identity với đúng provider project, không tin owner ID từ client.
- `/requirements/{id}/revisions/{revision}`, `/requirements/{id}/proposals`, `/proposals/{id}/*` → revision, draft proposal, confirm/cancel/discard explicit.
- `POST /comparison-jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel` → progress có thứ tự và trạng thái terminal; không đổi kết quả comparison đồng bộ hiện có.
- `/history/*` → rename/pin/archive, transcript, metadata CAS và guest-session linking explicit (basic list/detail are runtime).
- `POST /comparisons/{id}/what-if`, `GET /what-if/{id}`, `POST /what-if/{id}/scenarios/{scenario}/proposals` → phân tích bound với comparison, apply chỉ tạo proposal; cần confirm trước lần tìm kế tiếp.
- `/evidence/*`, `/requirements/{id}/messages/*`, `/contacts` → evidence lookup, conversation follow-up và contact ticket.

Lỗi dùng `{error: {code, message}}`. Thiếu là `unknown`, không tính là đạt. Destination chỉ gồm nơi tham quan đã bỏ origin endpoint; route/raw vẫn được giữ. Giá hard chỉ so khi fresh, trusted, exact, cùng currency/basis; giá `from` dưới trần là unknown, lower bound đã vượt trần có thể fail. LLM chấm soft chỉ nhận tour còn offer qua hard filter.

## Pipeline

`input` dựng điều kiện → `decide` đọc ứng viên qua `data`, chuẩn hóa qua `normalize`, lọc cứng, LLM chấm mềm kèm quote, rank, phân tích. Chi tiết: [system-architecture](system-architecture.md), [`src/backend/README.md`](../src/backend/README.md).

## Chạy tối thiểu

```powershell
uv sync
uv run tour-backend serve
```

Mặc định `DATA_PROVIDER=fixture` (catalog mẫu, không cần credentials). Đọc catalog thật bằng `DATA_PROVIDER=supabase` + `SUPABASE_TOUR_DB_URL` (chỉ đọc, không ghi). Parse LLM thật cần `NVIDIA_NIM_API`; không có thì text fallback keyword và trường mềm ở `unknown`. Trang chào: `http://127.0.0.1:8000/`, docs tương tác: `http://127.0.0.1:8000/docs`.
