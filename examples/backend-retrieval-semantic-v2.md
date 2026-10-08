# Test structured retrieval và semantic assessment

Từ repo root: dừng server cũ, `uv sync`, `uv run tour-backend serve`. Không cần đổi `.env` nếu đã có DATA_PROVIDER=supabase, SUPABASE_TOUR_DB_URL, NVIDIA_NIM_API và NVIDIA_NIM_MODEL. Bản fixture tự bỏ qua NIM assessment để tránh trộn dữ liệu mô phỏng với đánh giá thật.

## Flow API

1. POST /v2/sessions → Authorize bằng token. GET /v2/catalog xem processing_methods và strength_choices: hai trục độc lập.
2. POST /v2/requirements bằng input Nhật hoặc Tết ở [Supabase guide](backend-supabase-v2.md). Đợi parse job, GET proposal, trả lời clarification nếu có; POST confirm đúng revision/version.
3. POST /v2/comparisons với requirement_id + revision vừa confirm. Theo dõi job/events: reference_collection → normalization → hard_filter → semantic_assessment → evaluation/ranking/comparison/analysis → publication. Stage skipped/partial có lý do, không giả đã đánh giá.
4. GET comparison kiểm tra:
   - `analysis.retrieval.runs`: scanned_count/static_rejected/offer_rejected/retained_count, scan/pool/offer_truncated.
   - `columns[].offer_assessments`, `eligible_offer_snapshot_ids`, `offers_complete`: cả hard tree kiểm tra trên cùng offer. Nhiều offer đạt vẫn phải chọn offer để xem giá/ngày cụ thể.
   - `analysis.semantic_assessment`: state, reason_code, model/policy, items/status/citations/evidence_ids/usable_for_ranking, limited. hard unknown hoặc không có semantic input → skipped; NIM timeout/schema lỗi → partial nhưng structured comparison còn dùng được.
   - `recommendations.items[]`: score trên phần đã biết, coverage, score_interval, ranking_basis, rank_status và contributions. Bounds không phải xác suất; interval chồng nhau không chứng minh tour nào tốt hơn.
   - `analysis.metric_availability`: lý do thiếu metric giá, không chỉ metrics rỗng.
5. Đổi offer: gửi round_intent=offer_change, previous_comparison_id, offer_selections theo IDs trong comparison. Giữ revision; assessment snapshot cùng requirement được replay, không gọi NIM lại. Thay requirement/snapshot làm fingerprint thay đổi.

## Data cần crawler bổ sung

- `evidence.fields.<column>` theo CatalogFieldProof, value/record_key/URL/observed_at và quote/locator đúng field. Metadata `verified` chung không đủ.
- Giá: kind/currency/basis/coverage/applicability, nhóm tuổi và pricing_complete/phụ thu có bằng chứng. Giá from không được coi là exact hoặc là tổng chi phí.
- Registry source: freshness_seconds cho date/price/availability theo cadence thực tế; mặc định vẫn unknown, không tự đặt TTL.
- itinerary/inclusions/exclusions có field proof để semantic interpretation có thể tham gia ranking. Reputation/service quality/value for money hiện chưa có metric độc lập.

Database thiếu proof/TTL vẫn có thể trả preview thật + unknown và không có recommendation. Đây không phải lỗi NIM; có DATA_PROVIDER=supabase không đồng nghĩa mọi row đã đủ điều kiện để hard filter.

## Giới hạn hiện tại

SQL chỉ thu hẹp offer IDs sau static hard filter đã kiểm chứng. Các predicates phức tạp vẫn chạy normalized evaluator trong bounded scan trước pool; chưa có migration/index trusted để filter toàn catalog bằng SQL. Unknown không bị loại chỉ vì raw database value khác yêu cầu. Bounded scan phải đọc cả các tour có thể unknown, do đó cần theo dõi recall/truncation khi dữ liệu lớn lên.

Assessment mặc định enabled, tối đa 12 candidates/24 criteria pairs, 60.000 ký tự JSON input (pairs + excerpts), 6.000 mỗi excerpt, 45 giây tổng (cả một repair). Biến cấu hình: SEMANTIC_ASSESSMENT_ENABLED, SEMANTIC_MAX_CANDIDATES, SEMANTIC_MAX_PAIRS, SEMANTIC_MAX_INPUT_CHARS, SEMANTIC_EXCERPT_CHARS, SEMANTIC_TIMEOUT_SECONDS. Giới hạn phải công khai, không gọi LLM toàn database. [Kết quả kiểm tra và giới hạn dữ liệu thật](../docs/backend-retrieval-assessment-results.md).
