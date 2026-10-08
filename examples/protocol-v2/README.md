# Trao đổi JSON — v2 mẫu cho prototype

**Design fixtures, 07/10/2026.** Theo [protocol](../../docs/frontend-protocol-v2.md) và [pipeline/crawler/admin](../../src/api/backend-pipeline-v2.md). Backend v2 đã có runtime/schema riêng: [giới hạn thực tế](../../src/api/backend-v2-runtime.md), [request walkthrough](../backend-v2.md). Mọi tour, giá, nguồn, timestamp và ID ở đây là synthetic, không phải kết quả server. Không gửi các request này vào `/v1` hoặc dùng ID mẫu làm ID resource thật.

| File | Nội dung / dùng để nghiệm thu |
|---|---|
| requirements.json | Form normalized/canonical IDs, conditions/trees/party/preference levels/defaults/readiness và revision1 |
| batch-edit.json | Direct edit + chat nhiều field merge proposal/version, discard một diff, confirm revision2, cancel lượt sau giữ revision2 |
| comparison.json | Search revision2, public identity/offer/price/policies, metadata row×column, evaluations/quality, ranked refs/analysis/coverage; giá không phụ thuộc có Budget |
| activity.json | Job/events seq/cursor/stages, field missing ở normalization, succeeded và cancelled terminal; không % giả |
| evidence.json | Offer binding + quote/element anchor/text quote/deep_link+fallback; live link không cam kết thông tin độc lập đúng |
| crawler.json | BE gateway request/CrawlResult typed source snapshots/offer/quote/locator/issue; không raw chat/token |
| admin.json | Overview metric definitions/interval, source add/check/pause, contact create/process/internal note, session counts/activity |
| errors.json | Atomic validation, revision/proposal conflict, expiry, admin403, async source failure |

Mỗi file chứa `scenario`, `origin="synthetic"` và `exchanges[]`: `{method,path,request?,response:{status,body}}`. Body response dùng envelope schema_version2.0-draft/request_id/data; lỗi dùng error. Examples chia sẻ req_demo/revision2/offer_a/evidence refs. Ví dụ chỉ vài rows/candidates để đọc nhanh; runtime phải trả đủ metadata/row×column theo protocol, không dựng thiếu fields ở FE.

Các invariant phải kiểm tra ngoài parse JSON: before từ revision1, confirm một lần ra revision2, cancel giữ revision2; cùng revision/offer/evidence; giá integer VND; missing=null; seq tăng; analysis tính đúng operands/basis/coverage; approved-only source activation; contact note không được gửi ra ngoài. Runtime có tests v2 riêng trong `tests/test_v2.py`/`tests/test_v2_edges.py`; fixtures này tiếp tục dùng để review thiết kế và không thay contract tests server.

**Đã kiểm tra:** `validate.py` đạt **258 checks / 8 JSON files**; kiểm tra binding/calculations/state và typed Value/Condition/Tree/Party/PriceQuote theo models v1. Chạy từ repo root: `uv run python -B examples/protocol-v2/validate.py`. Không gọi NIM/crawl/API. Stage normalization partial trong activity sample do missing fields, job vẫn succeeded; cancellation là resource khác và không publish.
