# Frontend ↔ backend: giao thức v2 mẫu

**Trạng thái:** mẫu đã được user duyệt, PLANNING, 07/10/2026. [Prototype](../prototypes/frontend-design/README.md) dùng mẫu để review UI. Chưa endpoint thật; không gửi payload này vào `/v1`. JSON trao đổi tại [examples/protocol-v2](../examples/protocol-v2/README.md); pipeline tại [backend-pipeline-v2](backend-pipeline-v2.md).

## 1. Quy ước chung

- Public prefix `/v2`; crawler `/internal/v2` chỉ BE gọi. Giữ `/v1` hiện hữu đến khi adapter/contract tests cho v2 đạt. FE gọi một orchestration API, không ghép hai comparison hoặc gọi crawler.
- JSON UTF-8, `schema_version="2.0-draft"`, IDs opaque/stable, timestamp UTC RFC3339; UI ngày/giờ `Asia/Ho_Chi_Minh`. VND integer đồng; tiền khác decimal string; date-only `YYYY-MM-DD`. Null là chưa biết, không phải 0/false.
- Response `{schema_version, request_id, data}`; request_id do server trả/correlation, không chứa token. List `data={items,next_cursor}`; cursor opaque, stable ordering có ID tie-break. Error giữ `{error:{code,message,retryable,field_path,trace_id,details}}` cùng schema_version/request_id.
- Anonymous Bearer session với ownership bắt buộc cho mọi resource; admin dùng danh tính/role riêng. Token không ở URL/log/storage demo. Mutation dùng `Idempotency-Key`: cùng principal/route/key/body trả cùng resource, nội dung khác 409; giữ ít nhất 24 giờ. Khi mất response, retry cùng key, không tạo search/crawl mới.
- Body tối đa 64 KiB; 1–5 URL HTTP(S), canonical/dedup bởi BE; text chat tối đa 2.000 ký tự, contact 4.000; paging default 25/max100. FE limits theo catalog/config API, không dựa maxlength prototype làm chuẩn. Nguồn URL phải qua access check kể cả redirect.

## 2. Endpoint và lifecycle

| Endpoint mẫu | Request → data / hành vi |
|---|---|
| `POST /v2/sessions` | Tạo session → id/token/expires_at; không cần Bearer |
| `GET /v2/catalog` | Canonical destinations/origins, field/operator/control/default/required_by_input_kind, preference dimensions, limits; default có origin |
| `POST /v2/requirements` | `input.kind=structured|text|urls`, `reference_urls` → Requirement hoặc resource + parse job (202). Structured input đã được user xác nhận → revision1; raw text/URL parse tạo revision0 và proposal, chưa commit inferred criteria |
| `GET /v2/requirements/{id}` | Current committed snapshot, readiness, active proposal ref, latest job/comparison refs |
| `GET /v2/requirements/{id}/revisions/{revision}` | Snapshot bất biến đúng revision; hết retention trả410, không thay bằng current |
| `POST /v2/requirements/{id}/proposals` | `expected_revision`, optional proposal_id/expected_proposal_version, input structured edits hoặc message + context → Proposal (200) hoặc parse job (202) |
| `GET /v2/proposals/{id}` | Pending normalized snapshot, diff và clarification; preview không tăng committed revision |
| `POST /v2/proposals/{id}/discard-changes` | expected_revision/proposal_version + change_ids → bỏ từng diff và validate lại snapshot nháp |
| `POST /v2/proposals/{id}/confirm` | expected_revision/proposal_version → atomic Requirement revision mới. Toàn bộ proposal hoặc không gì; không partial commit |
| `POST /v2/proposals/{id}/cancel` | expected_proposal_version → cancelled; committed snapshot giữ nguyên |
| `POST /v2/conversations/{requirement_id}/messages` | text/client_message_id/context → message + intent `answer|edit|search|next_group|clarify`; edit tạo/merge proposal, search trả requested_action chờ user/confirm; không ngầm commit |
| `POST /v2/comparisons` | requirement_id/revision, round_intent `initial|next_group|offer_change`, previous_comparison_id, exclusions, offer_selections → comparison_id/job_id/status202 |
| `GET /v2/jobs/{id}` | queued/running/succeeded/partial/failed/cancelled, stage, timestamps/deadline, error/resource_ref |
| `GET /v2/jobs/{id}/events?after_seq=0&limit=50` | items có seq/stage/status/timestamp/source_id/summary + next_seq/has_more; terminal job có thể còn events cần đọc |
| `POST /v2/jobs/{id}/cancel` | Terminal cancellation gate; nếu đã terminal trả state hiện có; worker không publish kết quả muộn |
| `GET /v2/comparisons/{id}` | status/result nullable; succeeded/partial có Comparison; failed đọc job.error; không coi null là empty |
| `GET /v2/evidence/{id}` | Quote/locator/live deep link/quality/snapshot binding; ownership theo comparison |
| `POST /v2/contacts` | category/message/reply_to tùy chọn/context.session_id → ticket_id/status=new/created_at (201); chưa gửi email |
| `GET /v2/admin/*` và mutation | Xem phần admin bên dưới; Bearer session user không có quyền admin |

Revision, proposal version và job generation là ba khóa khác nhau. GET current không thay snapshot của comparison cũ. Confirm không tự search; chỉ khi user đã nói sửa+kèm tìm, FE gửi **POST comparison riêng** sau confirm thành công, đúng revision trả về. Không tiếp tục requested_action khi confirm lỗi/hủy/409.

## 3. Requirement, draft và chat nhiều thay đổi

Requirement: `id,revision,input_kind,conditions,hard_tree,preference_tree,party,preference_levels,reference_urls,notes,readiness,provenance,created_at`. Condition có `id,field,operator,value,strength=hard|soft|unresolved,sources`; chưa rõ strength phải hỏi, không tự thành soft. Tái dùng typed Value/budget/AND-OR trong domain v1. Party `{adults,children:[{id,age}]}`; tuổi chưa biết null tạo blocker giá, không áp giá người lớn. URL-only không tự tạo budget/party/preferences. Catalog/normalized snapshot dùng canonical IDs, labels chỉ cho UI.

Preference dimension `cost|comfort|pace|culture` có level0–5 và origin `user|system_default`; level là mức ưu tiên, không phải điểm tour. BE trả ranking_policy_version và explanation dùng actuals/evidence; mapping/normalization nằm trong policy có version, không FE tự nhân slider làm rank.

| Control mẫu | Mapping mục tiêu khi structured form được xác nhận |
|---|---|
| Điểm đến / nơi đi | destinations contains canonical IDs / departure_origin in IDs, hard |
| Ngày dự kiến | departure_date eq `{kind:"date",value:"YYYY-MM-DD"}`, hard. Nếu user chọn khoảng ngày rõ ràng mới dùng between/value/upper; không ngầm mở rộng ngày. JSON bundle chọn khoảng 10–17/11 tường minh, khác form prototype một ngày |
| Ngân sách | estimated_cost lte Budget per_adult/VND/tour_price, soft; coverage_origin=explicit; nguồn giá thiếu phụ thu → unknown cost, vẫn hiện published quote |
| Thời lượng | duration_days near NumberValue, soft; để trống không tạo condition |
| Người lớn/trẻ em/tuổi | party adults + stable child IDs/age; không đi qua conditions; thiếu tuổi có blocker giá |
| Khách sạn | hotel_stars_min gte NumberValue3/4/5, soft; để trống không tạo condition |
| Ít điểm / không mua sắm | shopping_stops prefer_low NumberValue0, soft / eq0, hard; hard_tree cập nhật cùng proposal |
| Slider | preference_levels.dimension level0–5 + origin; policy BE giải thích ảnh hưởng xếp hạng, không hard constraint |
| Lưu ý / URL | notes nguyên văn chưa tự hard/soft; reference_urls canonical dedup/access-gated. Chat suy condition từ notes phải tạo proposal và giải thích |

Personalized structured form yêu cầu destination/origin/date/adults/budget theo catalog; URL-only giữ các field null nếu chưa user xác nhận. BE trả sources/provenance theo từng condition (form field_path hoặc text message/quote/span), giữ origin/default; crawler QuerySpec không nhận raw chat/provenance user nhạy cảm.

Proposal: `id,version,requirement_id,base_revision,status,expires_at,preview,changes,clarifications,requested_action`. Status `pending|needs_clarification|confirmed|cancelled|superseded|expired`. Change `{id,path,condition_id?,before,after,origin=user_edit|chat_inference,reason}`; before luôn từ committed base. `preview` là toàn bộ normalized snapshot, không chỉ delta.

Typed edit whitelist: `upsert_condition`, `replace_condition_value`, `remove_condition`, `replace_party`, `set_preference_level`, `replace_reference_urls`, `set_notes`, `replace_tree` (all/any/predicate, refs hợp lệ). Không arbitrary JSON Patch; `replace_tree` phải giữ nghĩa OR, references và strength consistency. Nhóm field phụ thuộc như số trẻ/tuổi validate trên **preview hợp nhất**, không commit tạm từng field.

Merge cùng proposal: edit field mới thêm vào diff; cùng path giá trị sau cùng thắng và before giữ base; trở về base xóa diff. Confirm atomically kiểm tra expected_revision + proposal_version + toàn snapshot + quyền + expiry; cùng key không tăng revision lần hai. Cancel/discard không rollback các revision đã xác nhận. Draft chưa confirm được giữ qua nav và câu hỏi; refresh lấy active proposal. Kết quả parse muộn với proposal_version/generation cũ bị superseded, không ghi đè thay đổi mới.

Chat context `{requirement_revision,proposal_id,proposal_version,comparison_id,result_revision,offer_snapshot_ids,evidence_ids}`. Answer dựa comparison đang xem; edits dựa preview hiện tại. Mơ hồ/unsupported → clarification, không tự bỏ điều kiện. Câu nhiều thay đổi trả tất cả diff cùng proposal; không sửa requirement bằng PATCH text v1. UI trình bày đề xuất cho user; raw reasoning/chain-of-thought không trả ra.

FE chat gọi conversations/messages; direct edit gọi requirements/proposals. `input.kind=message` tại proposals dành cho explicit preview nếu cần dùng riêng cùng parser; không gọi cả hai route cho cùng tin nhắn. Conversation edit validate revision/proposal_version từ context; response202 có job_id/proposal_id, poll job rồi GET proposal/version mới. Không coi queued parse là diff đã hoàn thành.

## 4. Comparison và metadata để dựng bảng

Comparison bắt buộc: `id,requirement_id,revision,requirement_snapshot,origin,evaluated_at,policy_versions,columns,rows,cells,evaluations,recommendations,analysis,source_coverage,warnings,empty_reason`.

| Nhóm | Field và invariant |
|---|---|
| Identity | Column id/candidate_id/tour_id/tour_snapshot_id/offer_snapshot_id nullable; title/supplier.id/display_name/canonical_url; origin discovery/reference/both + target_ids + source_ids. References ngoài tối đa3 recommended; canonical duplicate gộp nguồn, không gộp offers khác điều kiện |
| Offer | offer_options có id/snapshot/date/rooming/price_quotes; selected_offer_snapshot_id. Nhiều lịch chưa chọn → `MULTIPLE_OFFERS_UNSELECTED`, không tự lấy rẻ nhất. Đổi offer tạo comparison mới, giữ cũ để review |
| Row metadata | id/field/label/value_type/unit/scope `tour|offer|cost|evaluation`, order/condition_ids; BE trả giá/chính sách/tên ngay cả khi không có Budget condition; không inject budget giả |
| Cells | row_id/column_id + value/raw_value/display_hint/reason_code/evidence_ids; data_state/verification/completeness/observed_at; freshness `{state,checked_at,expires_at,policy_version}`; evaluation_ids. Mỗi row×column có cell hoặc null+reason, không lấp missing bằng 0 |
| Evaluation | id/condition_id/candidate_id/field/strength/expected/actual/status `pass|fail|unknown|not_evaluated`, reason_code/reason/evidence_ids. Hard_tree đánh giá đúng all/any; absence của hard constraints → eligibility=null |
| Giá | price_quotes và extra_charges là sourced values theo đúng offer; exact/from/range/currency/basis/coverage/applicability; pricing_complete và cost_bounds/lý do thiếu. Phụ thu chưa biết không thành tổng exact; không áp người lớn cho trẻ |
| Recommendation | ordered candidate IDs, ordinal rank nullable, reasons/evaluation/evidence refs, ranking_policy_version, coverage/candidate_limit/truncated/excluded counts. Fail không thành recommended; unknown hard nằm nhóm cần kiểm tra riêng. URL-only nhãn tương tự, không đạt nhu cầu cá nhân |
| Analysis | claims có refs/limitations; metrics `{operation,operands,result,currency,basis,coverage,comparable,limitations,evidence_ids}`. Operand có field/snapshot/value/evidence. Không comparable → result=null. Khác ngày có thể so giá công bố với giới hạn, không kết luận tổng cuối |
| Coverage | sources_attempted/usable/errors, acquisition statuses, observed snapshots, truncation và range. Partial vì acquisition lỗi; field thiếu có thể succeeded+unknown. Empty reason không phải bằng chứng không có tour ngoài thị trường |

FE format/render, không rank hoặc tính cost thiếu. Kiểm tra refs/currency/offer/revision khi nhận; lỗi contract báo `CONTRACT_INVALID` tại API boundary, không hiển thị dữ kiện không có căn cứ.

Khối **đồng bộ yêu cầu** so revision/snapshot hiện tại với comparison, độc lập evaluation tour: matched xanh = đúng bản đã xác nhận; pending hổ phách = draft chưa áp dụng; stale đỏ = yêu cầu đã xác nhận thay đổi; running trung tính = đang tìm (giữ stale nếu bảng cũ). Nêu field before/after đã thay đổi và nút xem căn cứ. Green không chứng minh pass. Hủy search chỉ hủy job, không rollback yêu cầu đã xác nhận.

## 5. Evidence trỏ tới đoạn cụ thể

Evidence: `id,source_id,snapshot_id,field_path,offer_snapshot_id?,source_url,publisher,observed_at,raw_quote,raw_value,method,locator,deep_link,retained_excerpt_url?,content_digest,quality`.

- Locator có section_title, element_id nullable, css_selector nullable và text_quote `{exact,prefix,suffix}`. CSS selector giúp crawler kiểm chứng, **không** tự là link mà browser ngoài có thể cuộn tới.
- BE chọn deep_link `{url,method:element_id|text_fragment|page,status:verified|best_effort|unavailable,verified_at,reason}`. Ưu tiên anchor tồn tại; nếu không, text fragment URL-encode từ quote đủ đặc hiệu; cuối cùng page+quote để user tìm. Không tự đặt #price khi nguồn không có anchor đó.
- verified chỉ nghĩa locator khớp snapshot đã kiểm tra tại verified_at, không nghĩa thông tin đúng độc lập hoặc live page chưa đổi. Giá/đoạn lịch phải gắn offer đúng; quote tồn tại cùng snapshot, không dùng JSON do parser vừa sinh để tự chứng minh.
- Live page có thể đổi, quote lặp, bị ẩn hoặc browser không xử lý fragment. UI luôn có quote + section + nút copy; fallback label **Mở trang nguồn — có thể cần tìm trích đoạn**. Snapshot excerpt cho historical proof nếu quyền/retention cho phép; không serve raw scripts/HTML chưa sanitize.
- Nguồn/link HTTP(S) được BE validate domain/redirect, không credentials/javascript/private network. Evidence thiếu hoặc source bị blocked không có nút deep-link giả. Prototype dùng source.html local, nhãn minh họa rõ.

Text fragment là progressive enhancement, có giới hạn với nội dung ẩn; xem [Chrome: hidden-until-found](https://developer.chrome.com/docs/css-ui/hidden-until-found). Cam kết locator/snapshot + fallback mạnh hơn hứa mọi website đều mở đúng đoạn live.

## 6. Admin và contacts

| Endpoint | Data / mutation |
|---|---|
| `GET /v2/admin/overview?from=&to=&timezone=Asia/Ho_Chi_Minh` | distinct_sessions/user_messages/comparison_runs + terminal breakdown/active_jobs/source_health/contact_counts; metric_definition_version, interval `[from,to)`, timezone, updated_at, origin |
| `GET /v2/admin/sources?status=&cursor=` | Source records có version; display_name/domain/state/access_status/checked_at/capabilities/freshness/profile_version/last_run/health/data_counts |
| `GET /v2/admin/sources/{id}` | Record cùng last_check/job refs/audit refs để review khả năng approval; không tự active sau check |
| `POST /v2/admin/sources` | domain/display_name/profile_ref/capabilities → draft unchecked; không tự kích hoạt/crawl |
| `PATCH /v2/admin/sources/{id}` | expected_version + whitelist display_name/state active/paused/notes/policy_ref; active chỉ khi access approved/capabilities hợp lệ; không rewrite profile từ FE |
| `POST /v2/admin/sources/{id}/checks` | expected_version → source_check job202; kiểm tra policy/capabilities rồi mới approval; lỗi/unchecked không crawl |
| `POST /v2/admin/sources/{id}/approvals` | admin + expected_version/check_job_id → approved + paused chỉ khi check thành công còn hiệu lực/capabilities hợp lệ; bật bằng PATCH riêng |
| `POST /v2/admin/sources/{id}/refreshes` | expected_version + scope → crawl job202 nếu approved/active, deadline/limits/audit. Poll job, không refresh on focus |
| `GET /v2/admin/sources/{id}/runs` | Job history/status/acquisition errors/field coverage; không raw secrets |
| `GET /v2/admin/contacts?status=&category=&cursor=` | ticket_id/version/category/message/created_at/session_ref/reply_to nếu có quyền/status/assignee/internal_notes |
| `PATCH /v2/admin/contacts/{id}` | expected_version/status new/in_progress/resolved/assignee/internal_note → record mới; không gửi message/email |
| `GET /v2/admin/sessions?from=&to=&status=&cursor=` | id/started_at/last_active_at/user_message_count/comparison_count/state/last_job_ref; counts aggregate, không raw personal query |
| `GET /v2/admin/sessions/{id}/activity` | Timeline job/message metadata theo seq; transcript riêng cần quyền/retention/consent đã chốt, không default dump chat |
| `GET /v2/admin/audit?resource_id=&cursor=` | actor_id/action/resource_id/before/after/timestamp/trace_id; PII redacted |

Roles: viewer read metrics/redacted summaries; operator thêm xử lý contact/pause/refresh nguồn đã duyệt; admin thêm nguồn/sửa policy/phê duyệt sau check. Server enforce role từng route/field, không dựa link nav. Contact form không cần marketing consent; reply_to chỉ để người dùng tự chọn cách liên hệ, không tự gửi mail.

## 7. Lỗi, phục hồi và nghiệm thu

422 INVALID_INPUT có fields/path/message, giữ draft; 409 REVISION_CONFLICT/PROPOSAL_CONFLICT/OFFER_SELECTION_INVALID/IDEMPOTENCY_CONFLICT trả current refs để review, không auto overwrite;410 PROPOSAL_EXPIRED/RESOURCE_EXPIRED giữ draft local và cho tạo proposal mới. 401 hết phiên cần re-auth/phiên mới;403 FORBIDDEN admin;404 không tồn tại/không owned;429 Retry-After. SOURCE_BLOCKED/SOURCES_UNAVAILABLE/LLM_TIMEOUT/CONTRACT_INVALID nằm job.error khi đã202.

Poll visible khởi điểm1s, backoff tối đa5s + jitter, GET immediate khi quay lại; ngừng job polling terminal, drain events theo has_more. Mất mạng không tự POST. Seq dedup/events có thể out-of-order network; chỉ apply result có đúng job/comparison/revision/generation. Pending validation/conflict không commit một phần. Cancel gate chặn terminal result muộn. Retention/expiry theo server config và trường expires_at.

Nghiệm thu: JSON samples parse; binding refs/offer/revision/diff/math/status khớp; backend export schema cho DTO v2 và tests domain/ownership/atomicity/cancel; crawler adapter đáp ứng source/evidence/pricing. Mẫu và UI đẹp không đóng G1–G16/D1–D5 runtime.
