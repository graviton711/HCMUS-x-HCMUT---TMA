# Tour MVP scope

Bài toán gốc ở `idea.md` (không sửa). Demo Day 17/10/2026.

## Phạm vi

- Nguồn: 3–5 site lữ hành, bắt đầu từ `dulichviet`. Thêm site mới chỉ bằng `python -m ingest.survey --promote` kèm selftest PASS; cấm parser viết tay per-site ngoài profile YAML.
- Demo: 1 tuyến khóa cứng (Đà Nẵng 4 ngày) chạy canned data. Live crawl là đường phụ — fail thì fallback canned, không fail demo.
- Không điểm số bí mật: mọi thứ tự hiển thị đều kèm lý do tính bằng code từ field có nguồn. Không "học preference", chỉ lưu lựa chọn đã chốt. Không nhận thời gian thực.

## Pipeline hiện tại

`survey` (agent vẽ map → `artifacts/`) → `discover` (liệt kê link theo khối `discovery`: `search_pages` hoặc `sitemap`) → `batch` (crawl → CSV + JSON) → `audit` (evidence gate) → `publish` (Supabase tour). Lệnh chạy ở `README.md`; hợp đồng profile/discovery ở `src/ingest/README.md`.

## Quyết định kỹ thuật

- Generic crawler + profile khai báo; thêm site = thêm YAML, không thêm code.
- "Tổng chi phí thực" (niêm yết + phụ thu bắt buộc) là metric so sánh chính, không phải giá bìa.
- What-if là re-rank trên ràng buộc đổi, không phải mô hình mới.
- Browser flow chỉ chạy khi profile khai báo (`uv sync --extra browser`); không dùng thì không tốn gì.
- Mọi timestamp quan sát là giờ Việt Nam; mọi thông số vận hành nằm ở `configs/settings.yaml`.

## Điều kiện xong

- So được ≥1 nhóm tour cùng tuyến theo cùng tiêu chí, mỗi số có nguồn + thời điểm lấy.
- Demo canned chạy offline 100%, gồm 1 ca what-if lật thứ hạng và 1 ca thiếu data hiển thị trung thực.
- `pytest` xanh (trừ test playwright nếu máy chưa cài extra).
