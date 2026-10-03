# validate — evidence và fail-loud, không bao giờ bịa

## Trách nhiệm

Mọi fact xuất ra phải có bằng chứng nguyên văn trong nguồn đã thu thập.
Field quyết định (giá/ngày/chính sách/mã) yêu cầu khớp strict; field mô tả
chấp nhận fuzzy overlap. Không đạt → `null` + ghi `dropped`, không suy diễn.

## Input / Output

- Input: field cần kiểm + context nguồn, hoặc 1 departure + context
  (qua `departure_evidence` mà `pipeline` gọi cho mỗi đợt).
- Output: `EvidenceReport(fields, populated, evidence_match, dropped)` cho
  field lẻ; `"verified" | "partial" | "unverified"` cho mỗi departure; và
  error taxonomy: `ok | blocked | fetch_fail | parse_fail`.

## Workflow

Chuẩn hóa quote/context (casefold, bỏ dấu câu) → strict: substring nguyên
văn; fuzzy: overlap token ≥ ngưỡng → fail field nào null field đó, đếm
`populated`/`evidence_match` để pipeline đánh giá chất lượng nguồn.

## Interface

- `pipeline` dùng metrics để quyết định pass/fail nguồn và exit code batch.
- Không fetch, không parse HTML, không LLM.

## Quyết định kỹ thuật

- Function thuần, test bằng fixture quote đúng/sai/chắp nối — đặc biệt
  regression case `tour_code` suy từ slug URL và quote chắp nhiều đoạn.
