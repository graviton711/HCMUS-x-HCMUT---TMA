# Tour MVP scope

Bài toán gốc ở `idea.md` (không sửa). Demo Day 17/10/2026.

## Phạm vi

- Nguồn: 3–5 site lữ hành, bắt đầu từ `dulichviet`. Thêm nguồn bằng `python -m ingest.survey --source <source> --promote`; nghiệm thu profile mới hoặc đã đổi bằng self-test toàn bộ inventory PASS và holdout `audit` PASS. Chỉ dùng crawler chung cùng profile YAML, không viết parser riêng theo site hoặc sửa profile tay (resurvey để tái sinh).
- Demo: query tự do trên Supabase thật qua chat agent, không khóa tuyến cố định. `fixture-catalog.yaml` chỉ phục vụ dev/test offline, không dùng demo. Ngày khởi hành dùng snapshot crawl mới nhất hiện có (`freshness_seconds.departure_date: null`), vẫn hiện thời điểm ghi nhận và không xác nhận tồn chỗ live. Giá `from` vẫn là lower bound, không được coi như giá chính xác.
- Không điểm số bí mật: mọi thứ tự hiển thị đều kèm lý do tính bằng code từ field có nguồn. Không "học preference", chỉ lưu lựa chọn đã chốt. Không nhận thời gian thực.

## Pipeline hiện tại

Runner `python -m ingest.run` thực hiện `survey` (agent tạo profile, `--promote`) → `discover` → `batch` (crawl và kiểm chứng field từng tour) → `migrate` → `publish` (Supabase tour), dừng ở bước đầu tiên có lỗi. Không có bước `audit` trong runner: self-test toàn inventory và holdout `audit` là kiểm tra thủ công khi onboarding hoặc thay đổi profile/nguồn; runner không chặn publish nếu các bước đó chưa chạy. Audit bổ sung holdout và không thay thế kiểm chứng theo từng tour trong batch. Lệnh và hợp đồng chi tiết ở `README.md` và [`src/ingest/README.md`](../src/ingest/README.md).

`docs/idea.md` là đề xuất sản phẩm đã khóa, không phải nguồn cấu hình runtime. Đề xuất ghi `scan_limit` 1000 và mô tả tối đa 3 gợi ý mới cho URL tham chiếu; hiện config đặt scan limit 2000 và agent trả tối đa 5 tour duy nhất. Hãy dùng config và backend contract làm nguồn chuẩn cho giới hạn đang chạy.

## Quyết định kỹ thuật

- Generic crawler + profile khai báo; thêm site = thêm YAML, không thêm code.
- "Tổng chi phí thực" (niêm yết + phụ thu bắt buộc) là metric so sánh chính, không phải giá bìa.
- Browser flow chỉ chạy khi profile khai báo (`uv sync --extra browser`); không dùng thì không tốn gì.
- Mọi timestamp quan sát là giờ Việt Nam; mọi thông số vận hành nằm ở `configs/settings.yaml`.

## Điều kiện xong

- So được ≥1 nhóm tour cùng tiêu chí qua chat tự do, mỗi số có nguồn + thời điểm lấy.
- `pytest` xanh (trừ test playwright nếu máy chưa cài extra).
