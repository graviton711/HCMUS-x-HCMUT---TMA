# pipeline — điều phối batch, resume, exit code rõ ràng

## Trách nhiệm

Chạy end-to-end từng tour (fetch → blocks → browser nếu cần → clean →
validate → ghi CSV/JSON) và điều phối batch nhiều URL: resume (skip URL đã
có), failure budget (10 lỗi liên tiếp thì dừng), delay lịch sự.
Không chứa logic parse hay site-specific nào.

## Input / Output

- Input: 1 URL, CSV URLs, hoặc sitemap + tên profile.
- Output: append CSV (cột ổn định: url, observed_at, profile, status, title,
  departures, notes_keys, error) và JSON chi tiết từng tour; exit code theo
  taxonomy (`blocked` dừng nguồn, `fetch_fail` retry 1 lần, `parse_fail`
  đi tiếp).

## Workflow

Load profile+settings → với mỗi URL: kiểm tra resume → fetch → blocks →
browser (nếu flow yêu cầu) → clean → validate → ghi ngay (flush từng dòng,
crash không mất batch) → cập nhật failure budget.

## Interface

- Gọi `fetch`, `browser`, `blocks`, `clean`, `validate`, `profiles` theo đúng
  thứ tự; là module duy nhất biết toàn bộ luồng.
- Không parse HTML, không quyết định evidence, không hardcode nguồn.

## Quyết định kỹ thuật

- Chạy tuần tự từng tour (mỗi tour đã tối ưu ~60s); song song để phase sau
  khi có số liệu ổn định — không config chết cho thứ chưa implement.
- V1 deterministic 100%, không LLM.
