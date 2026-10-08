# Pipeline backend, crawler và kho dữ liệu — mẫu v2

**Trạng thái:** đặc tả đã được user duyệt; backend implementation ngày 07/10/2026. [Runtime/giới hạn](backend-v2-runtime.md) ghi phần đã chạy/test và phần còn cần crawler/deployment; nội dung dưới giữ mục tiêu pipeline theo [giao thức v2](frontend-protocol-v2.md). Owner: BE điều phối/giá/decision/public DTO/admin; crawler thu thập/normalization có provenance; FE state/render/review.

## 1. Quyết định kiến trúc

| Chọn | Gain | Chi phí / rủi ro | Fit / dài hạn |
|---|---|---|---|
| Một BE orchestration cho URL + discovery | Một revision/identity/offer/evidence, partial/cancel/debug nhất quán | DTO/worker adapter mới; cần immutable refs và checkpoints | Tái dùng gateway/decision domain v1; FE không ghép kết quả lệch |
| Proposal đa field riêng, atomic confirm | Chat/direct edit chung, hủy không mất committed state, xử lý nhiều tab | Proposal version/expiry/locking + full-preview validation | Tái dùng typed condition/tree validators; mạnh hơn PATCH text tự commit |
| Job + cursor events bằng polling | Replay sau mất mạng, thứ tự rõ, hạ tầng hiện có | Indexed append-only events + pagination | Không cần SSE/WebSocket để có log chính xác; có thể thêm stream dùng cùng seq sau |
| Snapshot/field evidence + locator fallback | Giá đúng offer, mở đúng đoạn nếu hỗ trợ, kiểm chứng lịch sử | Cần quote grounding/selector/anchor validation, storage retention | Không phụ thuộc website/browser phải hỗ trợ live deep link mọi lúc |
| Registry có version và admin audit | Quan sát nguồn, pause/capability/access kiểm soát được | Role/validation/audit và đồng bộ profile artifact | Một source of truth runtime, không tạo registry FE song song |

Stack production/storage engine vẫn chốt P2/backend deployment; đặc tả không bắt buộc thêm service riêng. Job/event/revision/proposal/registry state cần transaction, không dùng bộ nhớ process làm nguồn chuẩn trên hosting. Có thể giữ SQLite cho local demo; deployment multi-worker chọn transactional store phù hợp.

## 2. Các giai đoạn và input/output

Phần retrieval/evaluation/ranking mở rộng theo [structured retrieval và semantic assessment](retrieval-semantic-ranking.md), được user duyệt triển khai 08/10/2026. LLM assessment nằm giữa prepared pool và pure ranking; không thay hard eligibility.

| Stage | Input | Output / điều kiện |
|---|---|---|
| interpretation | Structured draft hoặc text/context | Canonical conditions/trees/party/preferences, diff/clarification/provenance. Text chỉ proposal; confirm riêng. Không suy ngân sách từ URL |
| reference_collection | Confirmed revision + URLs + source registry | Targets canonical/access-gated, tour/offer snapshots và evidence; URL hỏng giữ target/status/reason, không xóa cột |
| retrieval | Scope/readiness + approved searchable capabilities + exclusions | Candidate refs/source coverage/budget/truncation; chỉ pushdown filter có semantics đúng; budget khởi điểm20 đo latency/quality, không expose checkbox pool |
| normalization | CrawlResult + profile/normalization policy | Typed canonical values/snapshot/offer/quote refs, issues + missing/conflicting; giữ raw quote. Validate before persistence/decision |
| evaluation | Confirmed trees + party + selected offer + Facts | Per-condition pass/fail/unknown, eligibility/cost_bounds/quality/reasons; không hard constraints → eligibility=null |
| ranking | Evaluations + preferences + candidates + coverage | Tối đa3 tour khác nhau đủ hard conditions, rank/lý do theo policy version; hard unknown nhóm riêng, thiếu3 không lấp fail. URL-only nhóm tương tự |
| comparison | Ranked/group refs + references + row schema | columns/rows/cells/evaluation refs, offer options/prices/policies ngay cả không Budget; reference fail vẫn xem được |
| analysis | Comparison + grounded evaluations/calculations | Claims/metrics/operands/evidence/limitations; không fabricate unknown, không raw reasoning |
| publication | Complete validated envelope + job/revision guard | Immutable comparison + terminal event/status; transaction kiểm tra cancellation/ownership/binding trước publish |

Reference collection và retrieval có thể song song sau prerequisites; seq là thứ tự phát event, không giả toàn bộ pipeline tuần tự. Stage lỗi ghi failed/partial/skipped theo dependency; không đánh check cho stage chưa chạy. Acquisition lỗi một phần với usable snapshot → partial; field thiếu → succeeded+unknown; toàn bộ acquisition lỗi/không snapshot → failed; access từ chối trước acquisition → business empty NO_SUPPORTED_TARGETS.

Event `{seq,job_id,stage,status:started|completed|partial|failed|cancelled|skipped,occurred_at,source_id?,summary,counts?,error_code?}`. Counts chỉ giá trị thật, không % giả. Khi cancel, không mark các stage còn lại completed; job terminal gate bảo vệ kết quả bất kể upstream vẫn chạy. Retry dùng checkpoint/snapshot còn freshness/access hợp lệ; không âm thầm thay offer người dùng đã chọn.

## 3. Hợp đồng crawler cụ thể

Transport mục tiêu `POST /internal/v2/crawl` từ BE gateway; local Python adapter dùng **cùng DTO**, không buộc mở port riêng. BE tạo request_id/deadline, source_ids approved, reference_targets, query_spec, requested_fields, excluded_tour_ids, candidate_limit và trace_id. Crawler không nhận session token, raw chat hoặc NIM key. V2 batch gộp URL + discovery nhưng từng nguồn có mode/task rõ; v1 adapter có thể chia nội bộ rồi canonical-merge tại BE.

CrawlResult: schema_version/request_id/origin/source_results/suppliers/tours/offers/evidence/issues. Tái dùng Fact/PriceQuote/ExtraCharge v1; bổ sung public identity/policies/text services/locator. source_result có task reference/discovery/source_id/target_id/status/reason/snapshot_ids/coverage/truncated/checked_at. Stable tour ID gắn supplier+canonical identity; immutable tour/offer snapshot, mỗi offer có departure_date/return_date/rooming/availability/quotes/charges/pricing_complete.

Crawler cung cấp raw structured value và quote từ **source response gốc** (JSON-LD/API/DOM theo policy đã duyệt), method/locator/timestamp/content_digest. Không lấy JSON do extractor vừa dựng để kiểm chứng chính nó. Không thấy trường → null+missing; conflicting giá → giữ conflicting/issues; lịch khởi hành không chứng minh còn chỗ; số chỗ chỉ khi nguồn nêu rõ. `verified` extraction nội bộ không thành independently_verified.

Locator gửi element_id/section_title/css_selector/text_quote. BE build/validate safe deep_link và freshness; crawler không tự quyết định giá tổng/đạt nhu cầu/rank/unknown pass. Evidence giá phải thuộc selected offer snapshot, evidence tour thuộc tour snapshot; server reject refs sai/type sai hoặc giữ valid portion với issues.

Access gate kiểm tra source approval/robots/terms theo policy và redirects; khi không kiểm tra được → access_status=unchecked, không crawl nguồn thật. Pause ngăn acquisition mới; job đang chạy tuân cancel/access checkpoint. Cache không làm nguồn blocked được fetch lại hoặc hiển thị như freshly acquired. Gold fixtures có expected values và locators trước bật nguồn.

## 4. Kho dữ liệu và nguồn chuẩn

| Record | Nội dung / bất biến |
|---|---|
| sessions | owner/created_at/expires_at/retention; token hash, không token plaintext trong logs |
| requirement_revisions | requirement_id/revision + full snapshot; immutable sau commit |
| proposals | base revision/version/preview/diff/status/expiry; confirm và revision commit cùng transaction |
| jobs + job_events | state/deadline/generation/cancellation + unique(job_id,seq); append-only events, checkpoint refs |
| comparisons | requirement revision/full snapshot + tour/offer/evidence refs + policy versions/origin; immutable published result |
| source_registry | source_id/version/domain/state/access checks/capabilities/policy/profile artifact refs; runtime source of truth |
| tour/offer/evidence snapshots | Stable entity IDs, immutable snapshots/raw structured fields/sanitized excerpts/content_digest/observed_at; retention bound refs |
| contacts | ticket/version/message/reply_to optional/status/assignee/internal notes; tách khỏi crawl/query dataset |
| admin_audit | actor/action/resource/version/before-after redacted/timestamp/trace_id; append-only |

Git `configs/profiles` là versioned extraction artifacts; import vào registry bằng profile_ref/version, **không** ghi YAML bằng thao tác admin browser. Metadata state/approval/capabilities runtime do registry giữ; nguồn mới draft/unchecked, chỉ active sau check+admin approve. Không coi file profile tồn tại là nguồn được duyệt.

Freshness do BE áp field-specific policy; price/availability khác policy/itinerary. API trả freshness state + checked/expires/policy version cho **từng cell**, observed_at không tự thành fresh. Chính sách có version; TTL giá trị thật chốt sau khảo sát/đo nguồn, không chế thời hạn để tô xanh mock.

Local runtime: session24h/retention7ngày như v1; hosting config công bố expires_at. Contact giữ đến resolved+30ngày qua cấu hình; admin metrics chỉ aggregate/minimal session activity. Mục tiêu evidence tombstone410 chưa implement: hiện resource đã purge trả404 theo ownership. Không đổi thành chứng cứ nguồn mới. Log/metrics không chứa token/email/raw message; contact reply_to chỉ endpoint có quyền.

## 5. Admin, quan sát và contacts

- Distinct sessions = số session_id có activity user trong interval, không page view/requests. user_messages = tin user đã accepted, không assistant/tool/log. comparison_runs = comparisons đã accepted, retry cùng idempotency key không tăng; breakdown theo terminal state, active riêng. From/to `[from,to)` được normalize timezone rõ.
- Overview có updated_at/metric_definition_version/source health/contact backlog/active jobs; null cho metric chưa thu thập. Không tạo token/cost estimate nếu không có usage thật. Session detail chỉ timestamps/counts/job stage/status/trace metadata mặc định.
- New contact có idempotency/client submission id, text escaped/sanitized, category `feedback|data_issue|support`, reply_to optional/email validate, context session/comparison refs owned. Xử lý `new → in_progress → resolved`, có thể reopen; version check và audit. Internal note không xuất cho user, không tự gửi email.
- Admin production phải auth/roles phía server; role viewer/operator/admin theo [protocol](frontend-protocol-v2.md). Demo admin chỉ mô phỏng quyền; không được dùng trang static làm bảo vệ dữ liệu thật.
- Source detail hiển thị access approval/last checked/capability/field coverage/profile version/last run+error. Pause/refresh/check đều có version/audit/job; source bị blocked/unchecked không bật bằng UI.

## 6. Điều kiện bàn giao cho BE/crawler

1. BE export request/response/error schema v2 riêng và adapter v1; mọi UI field có metadata/default/null/reason chính xác. Validate samples và binding ngoài JSON Schema.
2. Proposal nhiều field/direct+chat, cancel/discard/atomic commit/409/expiry/idempotency và response đảo thứ tự có tests; giữ cây AND/OR, children/offer dependencies.
3. Crawl adapter HTTP/Python cùng DTO; gold fixtures định danh/giá/ngày/phụ thu/availability/policies/quote+locator; access failure và wrong-offer evidence bị chặn.
4. Pipeline stage events có cursor/dedup/replay/terminal/cancel; price public không Budget; URL+retrieval/common comparison/dedup/reference/Top3/unknown/round exclusions đúng policy.
5. Admin metrics definitions/filters/paging, role403/ownership404, source version/audit/access, contact ticket lifecycle/PII minimization; UI mock không nghiệm thu endpoint thật.

Theo dõi bằng G1–G16/D1–D5 ở checklist. Không bắt FE đổi wireframe theo thiếu field của v1; phản hồi BE được ghi thành spec version mới trước khi thay implementation.
