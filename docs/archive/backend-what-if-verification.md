# Kiểm chứng phân tích thay đổi điều kiện — 08/10/2026

Implementation trên nhánh `backend`, policy `what-if-v1`. [Thiết kế](../../src/api/what-if-analysis.md), [test từng bước](../../examples/backend-what-if-v2.md). Không commit/push, không sửa frontend hoặc catalog Supabase trong lần triển khai này.

## Kết quả offline

`uv run pytest -q`: **401 passed**, gồm **43 tests what-if** và358 tests trước đó. Ruff check đạt. Có một deprecation warning từ FastAPI/Starlette TestClient; không phải lỗi API. Export/parse đủ **27 schemas v2**, so sánh JSON schemas v1 với HEAD không có thay đổi.

Đã kiểm: tour mở ngoài pool gốc; bỏ nhóm hard/soft; nhóm OR/cùng field/đi-về; joint blockers; không ghép ngày/giá của hai offers; mức nới budget/date theo dữ liệu verified; không đề xuất giá từ/from/khác currency/unverified/stale; null khi mẫu số0 hoặc original eligibility unknown; rank/interval/ties; giới hạn lần thử và cặp dư thừa; empty universe; diagnostics; DTO từ chối metrics sai binding/số học.

API kiểm owner, idempotency, proposal không đổi revision trước confirm, removal core không vượt completeness gate, stale revision/pending proposal, URL-only không thành personalized eligibility, cancel trước/chờ model, source pause/policy đổi trong lúc chờ, freshness hết hạn sau model và recompute trước publish. Supabase fake engine kiểm broad acquisition không hard loại trước, bỏ date anchor, analysis limit lớn hơn100 trong khi comparison giữ giới hạn cũ.

Ví dụ synthetic qua API: cap11 triệu VND/người lớn/giá tour giữ1 tour; nâng cap12 triệu giữ2 tour, có1 tour mới đã bị yêu cầu gốc loại. Tỷ lệ1/2=50% có witness offer/evidence. Đây là tỷ lệ hạn chế lựa chọn trong cohort, không là contribution% chất lượng. Chọn scenario tạo proposal; confirm mới tăng revision1→2.

## Đọc Supabase thật

Lệnh cuối: `uv run python examples/check-what-if-v2.py --skip-nim`; artifact `data/live-tests/what-if-20261008T101834Z/summary.json`. Toàn bộ18 assertions của hai ca đạt. Application SQLite in-memory riêng; reader PostgreSQL đặt `REPEATABLE READ` và `default_transaction_read_only=on`, không ghi catalog. Không lưu session tokens/credentials trong artifacts.

Inputs là structured equivalents để kiểm analysis/API, **không chạy lại extraction NIM**:

- Nhật: Hồ Chí Minh → Nhật, ngày03/11/2026,1 người lớn, trần giá tour30 triệu VND/người lớn.
- Tết: Hải Phòng → Đà Nẵng hoặc Tây Nguyên, ghép đoàn/xe ô tô; minh họa **synthetic answers**2 người lớn, trần giá10 triệu và khoảng03–09/02/2027, tuyến miền Trung và bốn ưu tiên mềm. Các câu trả lời thêm không được suy từ câu Tết gốc hoặc coi là nhu cầu thật của user.

| Kết quả | Nhật | Tết đã bổ sung minh họa |
| --- | ---: | ---: |
| Job | succeeded | succeeded |
| Tours trong snapshot | 234 | 234 |
| Offers đọc trong giới hạn | 1000 | 1000 |
| Baseline pass / fail / unknown | 0 / 0 /234 | 0 /0 /234 |
| Kịch bản giữ lại | 4 | 11 |
| Số lần thử / cặp dư thừa bỏ | 10 /6 | 26 /15 |
| Mức nới giá/ngày actionable | 0 | 0 |
| Mở lựa chọn có chứng minh | 0 | 0 |
| Toàn flow, giây gần đúng | 6.20 | 14.25 |

Không bị cắt tours/scan trong hai ca; **offers bị cắt theo tổng giới hạn1000**, không hứa đọc toàn bộ departures. Các kịch bản không đủ cơ sở đo giữ tỷ lệ `null`, explanation có `NO_MEASURED_CHANGE`; requirement values/revision giữ nguyên. `succeeded` nghĩa là job phân tích hoàn tất đúng contract, không phải có tour đã xác minh phù hợp.

`scope.condition_diagnostics` phân biệt candidate summary với đánh giá từng offer. Ví dụ `MULTIPLE_OFFERS_UNSELECTED` không che mất lý do trên offers:

| Field | Lý do quan sát trong snapshot |
| --- | --- |
| Nơi khởi hành | 234/234 candidate summaries,1000/1000 offer evaluations `FIELD_UNVERIFIED` |
| Điểm đến | 90 tours `FIELD_UNVERIFIED`,144 `FIELD_UNSUPPORTED`; trên offers423/577 tương ứng |
| Ngày khởi hành | 1000/1000 offers `FIELD_UNVERIFIED` |
| Trần giá | 1000/1000 offers `PRICE_COVERAGE_UNCONFIRMED` |
| Ngày về và loại tour — Tết | 1000/1000 offers `FIELD_MISSING` cho từng field |
| Phương tiện — Tết | 318 offer evaluations unverified,682 unsupported |
| Bốn ưu tiên định tính — Tết | `METRIC_UNSUPPORTED`; không tự tạo rating/utility từ quảng cáo |

Đây là thiếu/chưa hỗ trợ dữ liệu, không đủ bằng chứng để nói tour thật vi phạm điều kiện. Bỏ một hoặc hai nhóm không làm các hard còn lại tự được xác minh.

## Probe NIM cuối pipeline

Lần chạy đầy đủ trước đó: `data/live-tests/what-if-20261008T101334Z/nim-selection.json`. NIM thật `nvidia/nemotron-3-super-120b-a12b` trên **computed synthetic metrics**, state `completed`: chọn insight tăng cap11→12 triệu và bỏ nhóm ngân sách. Tất cả IDs thuộc enum đã gửi; câu output khớp template backend, không dùng prose/số do model tạo. Đây là probe schema/grounding riêng, không là kết quả recommendation trên Supabase hoặc đo accuracy tổng quát. Test offline còn kiểm invalid IDs/timeout/disabled → fallback/skipped có lý do.

## Việc nhóm cần bổ sung dữ liệu

1. Policy mới [catalog-validation-v1](../../src/data_access/supabase/catalog-validation-policy.md) thay yêu cầu bulk field proof bằng nguồn opt-in + validation, giữ record provenance/link. Quote website bổ sung có chọn lọc; mở rộng mapping địa danh đúng phạm vi. Số liệu bên trên là baseline trước policy mới; xem [kết quả hiện hành](backend-catalog-validation-verification.md).
2. Ghi rõ price coverage/basis/qualifiers: giá cho người lớn, giá từ hoặc chính xác, bao gồm phần nào. Không chuyển giá `from` thành exact hoặc mặc định đã bao mọi phụ thu để đạt hard cap.
3. Bổ sung return_date có bằng chứng/policy derivation được duyệt, tour_type và main_journey transport; không coi `mixed` tự động là đi ô tô từ nơi xuất phát.
4. Uy tín/dịch vụ/đáng tiền cần nguồn đánh giá và metric policy được thống nhất; giữ unsupported khi chưa có. Thiên nhiên cần các nội dung/tags có evidence đủ kiểm chứng.

Backend đã công khai lý do để phân chia việc này; không tự backfill/nâng verification của catalog. Scenarios có giới hạn32 attempts mặc định, cặp tối đa2 nhóm, witness3 và rank changes10; minimal chỉ trong subset đã kiểm. Hybrid analysis dùng broad discovery snapshot, reference ngoài universe bounded có thể vắng; URL-only giữ URL scope. Frontend nối ba APIs trong hướng dẫn để hiển thị baseline/scenarios/tradeoffs và review proposal trước confirm.
