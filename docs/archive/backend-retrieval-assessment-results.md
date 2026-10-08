# Kiểm chứng structured retrieval và semantic assessment — 08/10/2026

Triển khai trên `feature/minh-phu`, theo [policy đã chốt](../../src/decision/retrieval-semantic-ranking.md). Không thay schema hoặc ghi vào Supabase; application DB của live smoke là SQLite in-memory. [Hướng dẫn test](../../examples/backend-retrieval-semantic-v2.md).

## Hai input thật với NVIDIA NIM và Supabase

| Input | Extraction / confirm | Comparison |
|---|---|---|
| Nhật Bản từ TP.HCM ngày 03/11/2026, 1 adult, giá tour tối đa 30 triệu VND/adult | Parse succeeded, 4 hard conditions đúng destination/origin/date/budget; party.adults=1, không có condition số người thừa. Không clarification, confirm 200. | Succeeded, 20 preview columns; 0 recommendations, ONLY_UNVERIFIED. |
| Câu Tết nguyên bản Hải Phòng → Đà Nẵng hoặc Tây Nguyên | Parse succeeded, giữ 11 conditions gồm tour_type/transport/route và 4 soft qualitative priorities. Hỏi strength của route, ý nghĩa khoảng ngày và năm Tết. Confirm 409 vì còn clarification blocking. | Chưa chạy search trên draft chưa rõ, đúng state gate. |

Nhật: đọc 234 tours trong bounded scan, không scan_truncated; pool_truncated và offer_truncated được báo. 20 tour giữ unknown, hard_pass=0 do field proof/freshness chưa đủ. Assessment skipped `NO_ELIGIBLE_SEMANTIC_INPUT`. Không dùng raw catalog value để tự xác nhận phù hợp.

NIM semantic assessment được thử riêng trên **snapshot mô phỏng có itinerary proof**: completed, 1 nature assessment có nguyên văn dẫn chứng, usable_for_ranking=true, không cần repair. Đây là kiểm tra schema/citation/gateway; không chứng minh kho thật đã có tour phù hợp hoặc chất lượng tour.

Artifacts local không có session token: `data/live-tests/retrieval-semantic-20261008T060759Z/` (ignored). Parse job metrics: Nhật không repair; Tết cần một bounded repair trước output hợp lệ. Một lần chạy cho mỗi input không là accuracy tổng quát.

## Phần dữ liệu còn cần

- Crawler bổ sung CatalogFieldProof đúng value/record_key/URL/quote/locator/observed_at, price qualifiers/applicability và coverage có bằng chứng.
- Chốt cadence thực tế rồi cấu hình freshness_seconds cho price/date/availability; không đặt TTL tùy ý để làm kết quả xanh.
- Field proof cho itinerary/inclusions/exclusions để semantic interpretation tham gia ranking. Reputation/service/value cần nguồn đánh giá phù hợp; chưa được suy từ quảng cáo.
- Chưa có full indexed SQL predicate pushdown; filter chạy normalized evaluator trước pool, SQL chỉ thu hẹp offer IDs. Khi catalog lớn cần đo recall/latency/truncation để thiết kế trusted indexes.

## Kiểm tra cuối cùng

`pytest -q`: **311 passed**, gồm 35 checks mới và 276 baseline; một Starlette TestClient deprecation warning hiện hữu. Ruff và diff whitespace đạt. Export 24 schemas v2 (thêm AssessmentBatch/SemanticReport); JSON schemas v1 không đổi.

Các counterexample bao gồm ghép ngày/giá khác offer, thiếu coverage offers, pool filter/unknown, thứ tự ranking khi score chỉ phủ 20% ưu tiên, giá khác currency, citation sai/trùng/thiếu/incomplete negative, repair/timeout/replay/input budget, cancel/source pause và hết freshness trong NIM wait. API không publish snapshot sau cancel/pause; hết TTL đưa về unknown.

Offline tests dùng fake NIM/crawler/SQL và application DB tạm, tách khỏi smoke mạng thật. [Runtime hiện tại](../../src/api/backend-v2-runtime.md#nghiệm-thu).
