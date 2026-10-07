# Scope MVP tour — chốt để team cùng làm

**Trạng thái:** Đề xuất chờ 3 người chốt. Bài toán gốc ở `idea.md` (không sửa). Demo Day 17/10/2026.

## Cắt phạm vi

- 3–5 site lữ hành, bắt đầu từ profile `dulichviet`, thêm site mới chỉ qua `python -m ingest.survey --promote` + selftest, cấm parser viết tay per-site ngoài profile.
- 1 tuyến demo khóa cứng (ví dụ Đà Nẵng 4 ngày) chạy canned data; live crawl là đường phụ, fail thì fallback canned chứ không fail demo.
- Không điểm số bí mật (`idea.md` đã cấm): thứ tự hiển thị phải kèm lý do tính bằng code từ field có nguồn. Không chữ "học preference", chỉ lưu lựa chọn đã chốt. Không nhận thời gian thực.

## Module

| Module | Trách nhiệm | Input / Output | Giao diện |
|---|---|---|---|
| Crawl (`src/ingest` + profile YAML) | Lấy field tour theo tọa độ khai báo (DSL strict cho trang tĩnh, browser flow cho site động), tôn trọng robots, lưu `observed_at` | HTML/JSON-LD → record thô + provenance | Profile mới phải kèm selftest PASS mới merge |
| Normalize | Giá tổng thực (niêm yết + phụ thu bắt buộc − bữa tự túc quy đổi), bao gồm/không bao gồm, lịch trình, phí ẩn | Record thô → bản ghi so sánh được | Thiếu field quyết định → ghi thiếu, cấm đoán |
| Decide | Ràng buộc cứng loại thẳng, slider ưu tiên sắp lại, what-if chạy lại trên ràng buộc đổi, lý do giải thích toàn số đã tính | Nhu cầu + bản ghi → bảng so sánh + trade-off + what-if | Không gọi LLM để bịa field; LLM chỉ diễn đạt lại số đã có |
| App (1 màn hình) | Nhập nhu cầu, hiện bảng so sánh, panel what-if, chip provenance | API/local JSON → UI | Mọi con số click ra được nguồn + thời điểm lấy |
| Preference | Lưu lựa chọn đã chốt để lần sau gợi ý trước | Feedback → profile người dùng local | Không gọi là learning khi chưa có dữ liệu nhiều kỳ |

## Quyết định kỹ thuật chốt sẵn

- Generic crawler + profile khai báo đã có, giữ nguyên kiến trúc; thêm site = thêm YAML, không thêm code.
- "Tổng chi phí thực" là metric so sánh chính, không phải giá niêm yết.
- What-if là re-rank đơn giản trên ràng buộc đổi, không phải mô hình mới.
- Render flow (browser/XHR cho site động) giữ lại đúng cho profile khai báo, không dùng thì không tốn gì; ai cần thì `uv sync --extra browser`.

## Điều kiện xong

- So được ≥1 nhóm tour cùng tuyến theo cùng tiêu chí, mỗi số có nguồn + thời điểm.
- Demo canned chạy offline 100%, có 1 ca what-if lật thứ hạng và 1 ca thiếu data hiển thị trung thực.
- pytest xanh (trừ test playwright nếu máy chưa cài extra).
