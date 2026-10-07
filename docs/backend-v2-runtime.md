# Backend v2 — implementation

User yêu cầu implementation ngày 07/10/2026. Thực hiện trên `feature/minh-phu`, giữ `/v1`. Thiết kế gốc: [protocol](frontend-protocol-v2.md), [pipeline](backend-pipeline-v2.md). Tài liệu này phân biệt khả năng runtime với mẫu UI.

## Phạm vi và thứ tự

1. DTO/OpenAPI v2 và catalog; structured form commit revision 1, text tạo draft revision 0 và parse proposal.
2. Proposal durable, multi-field/direct/message edits, full preview, discard/cancel/expiry, version CAS, atomic confirm và idempotency. Không tự search khi confirm.
3. Một orchestration cho nhu cầu/1–5 URL/hybrid; append-only job events, immutable comparisons, public prices/evidence, hard gating, tối đa 3 tour distinct, next-group exclusions.
4. Migration SQLite additive, snapshot indexes và runtime registry. Contacts/admin role checks/audit; không gửi email.

## Quyết định triển khai

- Shared requirement invariants được tách khỏi policy input v1: v1 giữ 2–5 URL; v2 cho 1–5 và hybrid. Parser NIM tái dùng grounding/normalization/AND-OR; không thay bằng regex lấy condition.
- Extraction v2 bổ sung preference_updates/reference_urls/notes có quote gốc; mọi slot phải grounding trước dựng preview. Chat answer chỉ chọn metric/evaluation refs có sẵn, prose từ template BE; chưa có câu trả lời mở bằng LLM.
- Proposal preview là revision kế tiếp nhưng chưa vào `requirement_revisions`. Parse dựa preview hiện tại; commit kiểm tra job lease/deadline/proposal version/base revision trong cùng transaction. Pending parse chặn confirm. Discard dựa change ID và dựng lại preview, không rollback revision đã commit.
- Job events có seq tăng trong transaction; polling có cursor, owner isolation và terminal gate. Không báo phần trăm giả. Restart kết thúc running jobs bằng JOB_INTERRUPTED.
- Gateway v2 chia acquisition thành reference/discovery qua DTO v1 hiện có, cùng deadline và kiểm tra binding; HTTP crawler vẫn theo contract v1 đến khi crawler owner cung cấp v2. Lỗi task được giữ trong coverage nếu task khác dùng được. Source blocked/paused ngăn acquisition và reuse.
- Rank policy `rank-v2.1`: hard pass trước, unknown tách riêng; utility soft predicate được tính xác định (near theo khoảng cách tương đối, prefer_low/high theo miền candidates, predicate theo pass/fail). AND dùng trung bình có trọng số, OR dùng utility tốt nhất; missing không được coi pass. Cost/comfort sliders điều chỉnh các điều kiện liên quan; pace/culture chưa có metric nên công bố unsupported, không tạo điểm giả. Điểm/coverage/contributions công khai; stable tour identity theo supplier + tour ID.
- Giá công bố luôn được trả kể cả không Budget. Metric chênh lệch chỉ dùng exact quote cùng currency/basis/coverage, applicability phù hợp, evidence đủ và freshness usable; nêu giới hạn ngày/fees, không gọi là tổng chuyến đi.
- SQLite schema 2 thêm bảng, không sửa/xóa dữ liệu v1; một process như runtime cũ. Snapshot refs theo comparison/owner được lưu transaction, không tạo catalog thị trường giả. Hosting nhiều worker/PostgreSQL là phần deployment riêng.
- Admin dùng Bearer riêng cấu hình bằng secrets, role viewer/operator/admin phía server. Không có token mặc định. Registry bootstrap từ cấu hình đã duyệt; source mới unchecked/paused. Check/approval mới phải có access proof từ checker được cấu hình; chưa có proof thì không kích hoạt. Pause/refresh/contact xử lý có CAS/audit; không tự gửi email.
- Source active phải có modes/returned fields hợp lệ và không trùng domain nguồn active khác. Proof/interval normalize UTC; refresh kiểm tra expiry cả trước và sau acquisition. Admin lists có cursor, filter trước paging; sessions/activity chỉ trả metadata/counts, giữ metadata phiên hết hạn đến retention cutoff nhưng token bị chặn ngay khi hết hạn.
- Check trả blocked/unchecked sẽ pause nguồn và thu hồi approval ngay trong transaction; lỗi checker giữ lịch sử lỗi, không sinh approval mới.
- Registry routing ưu tiên domain của nguồn active/approved; draft paused cùng domain không chặn nguồn đang chạy. Không cho hai nguồn active claim cùng domain. Contact ID top-level và context nếu cùng xuất hiện phải khớp nhau.
- Text/chat tối đa 2.000 ký tự, contact 4.000, paging mặc định 25/tối đa 100; schema v2 được xuất vào `contracts/v2`. Giá người lớn có thể tạm tính từ exact usable quote × party.adults với operand revision/evidence; không cộng giả trẻ em/phụ thu.
- GET requirement trả latest comparison/job refs để FE phục hồi sau refresh. Error v2 gồm schema_version/request_id cả khi body quá lớn hoặc route không tồn tại. DB schema chưa hỗ trợ bị từ chối trước khi tạo bảng mới.
- Conversation client_message_id dedup cả job và activity count; retry cùng message không tăng user_messages. Worker phân loại validation lỗi parse/message v2 thành LLM_INVALID_OUTPUT.

## Nghiệm thu

Tests deterministic với temporary DB/FakeNim/mock crawler: atomic multi-edit, OR preservation, stale parse/version/revision, ownership, idempotency, expiry, cancel/restart/late publication, replay events, URL-only/hybrid, unknown/fail ranking, distinct/exclusions, wrong-offer evidence, exact price without Budget, additive migration, admin permissions/audit/contact. Không gọi NIM/crawl live trong test; độ chính xác NIM và chất lượng nguồn thật cần gold evaluation riêng.

Nghiệm thu 07/10/2026: `pytest -q` **155 passed** (45 ca v2 + 110 ca hiện hữu); Ruff và diff whitespace đạt. Worker tự chạy đã publish luồng URL fixture; sáu JSON request trong walkthrough validate bằng runtime DTO; 20 schemas v2 xuất thành công. Design fixtures riêng đạt 258 checks/8 files, không thay kiểm thử server hoặc nguồn thật.

## Chạy và tích hợp

`uv sync` → `uv run tour-backend serve`; sau sửa code cần dừng/chạy lại server. `/docs` có nhóm v2/admin, `/v2/catalog` công bố limits/controls. [Hướng dẫn request thật](../examples/backend-v2.md), [schemas](../contracts/README.md). Frontend origin 4173/5173 được cấu hình CORS cho localhost/127.0.0.1.

`uv run pytest -q`, `uv run ruff check src tests`, `uv run tour-backend export-schemas`. Tests dùng DB tạm/FakeNim/mock HTTP. NIM v2 live smoke đã nhận đúng destination Nhật và cost=4 với quote gốc; không thay gold evaluation toàn bộ tiếng Việt.

Database mặc định `data/backend.db`: session/revision/proposal/job lưu ngay khi request hợp lệ; snapshots chỉ lưu khi comparison/refresh publish thành công. SQLite viewer cần refresh đúng file; không cần crawler để có session/job. Migration 1→2 tự thêm bảng, giữ dữ liệu cũ; schema khác bị từ chối.

Admin mặc định tắt: cấu hình `ADMIN_TOKEN`, `ADMIN_OPERATOR_TOKEN`, `ADMIN_VIEWER_TOKEN` tùy role, mỗi secret khác nhau và ít nhất 32 ký tự. Dùng AdminBearer riêng. Check nguồn cần trusted callable `access_checker` truyền vào `create_app`; CLI hiện chưa có checker robots/terms thật. Source bootstrap dùng registry cấu hình đã duyệt, không tự suy quyền từ profile. Contacts không gửi mail; resolved giữ thêm `CONTACT_RESOLVED_RETENTION_DAYS` (30 ngày).

## Trạng thái và giới hạn

Đã implement backend v2: proposal/confirm, text/form/URL/hybrid, comparisons/rank/analysis/evidence, events/cancel, SQLite migration, registry/admin/contact. `/v1` tiếp tục hoạt động. Frontend prototype vẫn dùng dữ liệu mẫu; team frontend cần nối endpoints theo hướng dẫn.

- Provider mặc định `fixture`, dữ liệu mô phỏng có nhãn `synthetic`; chưa nối output `tourcrawl` JSON/CSV vào runtime và chưa nghiệm thu giá/evidence từ nguồn thật. HTTP gateway vẫn gửi DTO v1, chưa có transport `/internal/v2/crawl`.
- Candidate budget 20 giới hạn pool sau acquisition/normalization; chưa giới hạn lượng fetch của crawler v1, không cam kết cải thiện latency upstream. Logs acquisition tổng hợp sau response, không có progress từng trang khi crawler đang chạy.
- Cost/comfort chỉ reweight các soft conditions liên quan; pace/culture chưa có metric. Không suy party/preferences từ URL. Text phải đủ slot rõ hoặc trả clarification; chưa nghiệm thu bộ gold 50 câu/15 chuỗi. Chat trả facts/metrics và template, chưa prose mở bằng LLM.
- Evidence live link chỉ best_effort/page fallback; không có endpoint HTML excerpt/anchor đã verify. Resource hết retention trả 404 theo ownership, chưa có tombstone 410. Source metadata theo SourceCapability v1; source draft cần gửi capabilities đầy đủ khi tạo để được duyệt. Profile artifacts không bị ghi lại bởi UI.
- Session/admin counts chỉ gồm activity v2 kể từ triển khai; activity cursor theo timestamp/ID, không transcript. Audit metadata append-only chưa có cleanup riêng. SQLite một process; PostgreSQL/multiworker là việc deployment tiếp theo.
