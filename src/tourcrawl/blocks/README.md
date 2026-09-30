# blocks — tách khối data thô, function thuần, không đoán mò

## Trách nhiệm

Biến HTML/XHR thành các khối dữ liệu nguyên vẹn: JSON-LD, object JSON nhúng
(unescape + balanced-parse), prose đã decode, panel detail theo snapshot,
lịch departures từ payload. Không suy diễn, không điền khuyết, không ép schema.

## Input / Output

- Input: HTML tĩnh và/hoặc `CapturedTraffic` từ browser + alias key từ profile.
- Output: dict các khối (`json_ld`, `tour_info`, `page_prose`, `departures`,
  `notes`, `panels`) — full fidelity, key giữ nguyên tên nguồn.

## Workflow

JSON-LD parse trực tiếp → tìm object theo alias key trong HTML đã unescape
→ decode prose (unescape, strip tag, giữ dòng chữ) → panel detail theo
snapshot đã ghi → departures = mọi dict có `departureDate`.

## Interface

- Nhận alias key (`tourInfoData`, ...) từ profile, không hardcode tên nguồn.
- Output thô chuyển cho `clean` (lọc rác) rồi `validate` (evidence).
- Không fetch, không gọi browser, không LLM.

## Quyết định kỹ thuật

- Function thuần 100%: cùng input cho cùng output, test offline bằng fixture
  HTML thật đã lưu — đây là module được test nặng nhất package.
- `unescape một pass duy nhất` (không replace nối chuỗi gây decode 2 lần).
