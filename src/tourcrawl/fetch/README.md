# fetch — transport an toàn, không LLM, không browser

## Trách nhiệm

GET tĩnh có giới hạn: chặn SSRF/IP non-public, ép same-origin, tôn trọng
robots.txt, delay lịch sự, giới hạn bytes/timeout. Mọi fetch thất bại trả
`FetchResult` lỗi thay vì raise — pipeline quyết định retry/bỏ qua.

## Input / Output

- Input: URL tuyệt đối + origin host suy từ URL + `RateLimiter` dùng chung.
- Output: `FetchResult(url, status_code, content_type, body, error)` (dataclass).

## Workflow

`validate_public_url` → chờ `RateLimiter` → GET (không theo redirect tự động;
redirect xử lý ở pipeline để kiểm tra origin lại) → kiểm tra byte limit.

## Interface

- `crawler.fetch.SafeFetcher` cũ đã xóa; module này thay thế, API tương đương.
- `pipeline` gọi duy nhất qua đây cho mọi HTTP tĩnh (HTML, robots, sitemap).
- Không gọi browser, không parse HTML.

## Quyết định kỹ thuật

- Stdlib `urllib` thuần, 0 dependency mới — fetch tĩnh không cần gì hơn.
- `RateLimiter` là 1 trong 2 class OOP của package (giữ delay dùng chung
  giữa các luồng fetch/API).
