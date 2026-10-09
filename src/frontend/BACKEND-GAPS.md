# Giới hạn tích hợp backend

Nguồn contract runtime là `src/api/v2/models.py`, `routes.py`, `service.py` và `/v2/catalog`. Frontend kiểm JSON tại API boundary; tài liệu mẫu/prototype không thay request/response hiện có.

| Phần             | Backend / yêu cầu còn thiếu                                                                            | Hành vi frontend                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Identity         | Có bearer ẩn danh qua `/v2/sessions`; chưa có login/register/Google/profile/logout/link theo user      | Auth adapter chỉ bật khi được cấu hình; cho tiếp tục phiên ẩn danh                     |
| Lịch sử          | Chưa có endpoint liệt kê hội thoại/chat/comparisons theo user hoặc đồng bộ đa thiết bị                 | Lưu IDs/draft/transcript đã nhận ở browser; resume GET resource theo quyền còn hạn     |
| Dữ liệu tour     | Mặc định `DATA_PROVIDER=fixture`; nguồn thật cần Supabase/HTTP và dữ liệu đủ evidence/price qualifiers | Kiểm `/health`, chặn nguồn synthetic; không tạo tour/giá giả                           |
| Worker           | Comparison/chat jobs cần worker đang chạy                                                              | `worker_enabled=false` chặn search enqueue; giữ nhu cầu và cho thử lại                 |
| Weather/location | Chưa có provider/contract                                                                              | Không hiện dữ liệu mô phỏng; ảnh giới thiệu độc lập dữ liệu tour                       |
| Locale           | Chưa có policy ngôn ngữ cho source/catalog/AI responses                                                | Dịch UI VI/EN; giữ nguyên input, quotes và response backend                            |
| Deploy           | Hosting cần SPA fallback; cross-origin cần CORS đúng origin                                            | Dev proxy `/v2` và `/health`; production dùng reverse proxy hoặc cấu hình CORS backend |

Auth endpoints/body/config dự kiến tại [AUTH-ADAPTER.md](app/AUTH-ADAPTER.md). Identity bearer không được gửi vào v2 trước khi backend xác định ownership/migration; adapter profile chỉ scope chỉ mục history local.

## Contract và lifecycle

- `/health` có JSON riêng (`schema_version:1.0`, `api_versions:[v1,v2]`), không dùng envelope v2. V2 envelope vẫn `2.0-draft`; catalog/session/job/evidence/chat/error còn response dict nên validators kiểm cấu trúc runtime.
- V2 có proposal/confirm/clarification, comparisons/next-group/offer-change, ranking/analysis/evidence, jobs/events/cancel và revision snapshots.
- Session creation chưa có idempotency: client không tự retry. Mutation khác chỉ retry transient network/502/503/504 bằng cùng body/key; `409`/`422` giữ draft.
- GET resource biết ID phục hồi current refs/snapshots; retention hết trả `404`. Phiên mới không có quyền đọc phiên cũ. Chưa có transcript/history list hoặc lifecycle delete/export theo user.
- Job events phải drain `has_more` sau terminal; acquisition chưa có progress từng trang. Frontend không suy phần trăm tiến độ.
- `offer_assessments[].hard_status` và `analysis.candidate_pool[].hard_status` có thể null khi URL-only không có hard constraints. Replay contact có thể trả status ticket hiện tại.

## Dữ kiện và controls

- Direct form biểu diễn một predicate mỗi field; nhiều predicates cần chat để giữ IDs/cây điều kiện. Budget ngoại tệ/cả nhóm/tổng chuyến/range giữ nguyên khi sửa trường khác; control không đổi currency/basis/coverage ngầm.
- Shopping: ít điểm mua sắm là `shopping_stops prefer_low 0 soft`; không mua sắm là `eq 0 hard`.
- Cost/comfort dùng soft conditions liên quan. Pace/culture và reputation/service-quality/value-for-money chưa có metric đủ căn cứ; giữ unsupported/unknown. Frontend chỉ hiển thị claims/metrics/semantic assessments do backend trả.
- Supabase là một provider; database_record chỉ xác nhận provenance database. Field proofs từ website, freshness cadence và deep links cần dữ liệu crawler; thiếu HTML excerpt vẫn giữ unverified/unknown.
- From-price/giá trẻ thiếu age brackets/phụ thu không đủ để kết luận tổng tiền. Comparison columns chưa có ảnh tour kèm provenance; UI không suy ảnh tour từ stock ảnh điểm đến.

[Test contract/browser](tests/README.md) dùng dữ liệu kiểm thử để xác nhận interfaces và workflow; nghiệm thu tour/giá/field proof live, NIM tổng quát và auth backend cần service/dữ liệu thật.
