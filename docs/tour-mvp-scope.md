# Tour MVP scope

Bài toán gốc ở `idea.md` (không sửa). Demo Day 17/10/2026.

## Phạm vi

- Nguồn: 3–5 site lữ hành, bắt đầu từ `dulichviet`. Thêm site mới chỉ bằng `python -m ingest.survey --source <source> --promote` kèm selftest PASS và `audit` PASS; cấm parser viết tay per-site ngoài profile YAML, cấm sửa profile tay (resurvey để tái sinh).
- Demo: query tự do trên Supabase thật qua chat agent, không khóa tuyến cố định. `fixture-catalog.yaml` chỉ phục vụ dev/test offline, không dùng demo. Trước demo kiểm tra freshness/TTL và rehearsal 2–3 query (tránh budget/date cứng khi giá stale hoặc `price_basis=from`, vì policy ép các trường hợp này về `unknown`).
- Không điểm số bí mật: mọi thứ tự hiển thị đều kèm lý do tính bằng code từ field có nguồn. Không "học preference", chỉ lưu lựa chọn đã chốt. Không nhận thời gian thực.

## Pipeline hiện tại

`survey` (agent vẽ map → `artifacts/`) → `discover` (liệt kê link theo khối `discovery`: `search_pages` hoặc `sitemap`) → `batch` (crawl → CSV + JSON) → `audit` (evidence gate) → `publish` (Supabase tour). Lệnh chạy ở `README.md`; hợp đồng profile/discovery ở `src/ingest/README.md`.

## Quyết định kỹ thuật

- Generic crawler + profile khai báo; thêm site = thêm YAML, không thêm code.
- "Tổng chi phí thực" (niêm yết + phụ thu bắt buộc) là metric so sánh chính, không phải giá bìa.
- Browser flow chỉ chạy khi profile khai báo (`uv sync --extra browser`); không dùng thì không tốn gì.
- Mọi timestamp quan sát là giờ Việt Nam; mọi thông số vận hành nằm ở `configs/settings.yaml`.

## Điều kiện xong

- So được ≥1 nhóm tour cùng tiêu chí qua chat tự do, mỗi số có nguồn + thời điểm lấy.
- `pytest` xanh (trừ test playwright nếu máy chưa cài extra).
