# browser — phiên visitor thật, không đụng credential

## Trách nhiệm

Render trang bằng Chromium headless, tương tác generic (tab/accordion/dòng
ngày theo role + text pattern từ profile), bắt XHR JSON, chụp snapshot DOM
theo từng bước. Browser tự gắn credential của chính web (nếu có); code không
bao giờ đọc, lưu hay gửi token/cookie đi đâu.

## Input / Output

- Input: URL + profile (pattern tab/dòng, budget click/scroll/wait).
- Output: `CapturedTraffic(html_snapshots, json_payloads, interactions_log)`.

## Workflow

Mở trang → đợi mốc text chính → click tab theo pattern → với mỗi tab, tìm
dòng ngày còn ẩn → click → đợi response mới (event-driven, không sleep cứng)
→ snapshot sau mỗi bước → đóng browser.

## Interface

- `BrowserSession` là context manager (1 trong 2 class OOP): giữ browser,
  page, listener; dọn sạch khi thoát kể cả khi lỗi giữa chừng.
- `pipeline` chỉ gọi browser khi profile yêu cầu flow `browser` (Vietravel
  combo); flow static-only không chạm tới module này.
- Không parse dữ liệu — chỉ thu thập nguyên liệu thô cho `blocks`.

## Quyết định kỹ thuật

- Playwright sync API (optional extra `browser`), chặn tài nguyên nặng
  (image/font/media) để tăng tốc.
- Mọi tương tác đều generic (role ARIA + text pattern); selector riêng của
  site bị cấm. Thất bại ở bước nào log rõ bước đó, không fail cả phiên.
