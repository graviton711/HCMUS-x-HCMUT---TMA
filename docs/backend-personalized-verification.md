# Nghiệm thu personalized core — 08/10/2026

Triển khai trên `backend` theo [policy](personalized-requirement-policy.md), ngân sách form là trần bắt buộc. Không sửa frontend, catalog Supabase hoặc application DB đang dùng; smoke dùng SQLite trong memory. Credentials vẫn nằm trong `.env`, artifacts chỉ lưu public responses.

## Offline

**358 passed**: 311 baseline + 47 checks bổ sung. Ruff lint và diff whitespace đạt. Export 24 schemas v2; chỉ RequirementV2/Proposal/ComparisonV2 thêm completeness/readiness, JSON schemas v1 không đổi. Cảnh báo Starlette TestClient deprecation hiện hữu; không thay dependency trong việc này.

Phạm vi: từng core missing/ambiguous/negative-only, hard cap/zero/lower-bound/OR bypass, form/text parity, typed core answers, preservation/atomicity/stale CAS, remove/downgrade/discard, URL/hybrid, legacy readiness bị stale. NIM guard kiểm phân loại địa danh/loại tour, budget strength, quote/duplicates/polarity/control mức ưu tiên; mixed reply bổ sung core và trả lời semantics trong cùng lượt. Audit tests dùng fake SQL, không network.

## Hai input thật qua API/NIM/Supabase

Script: `uv run python examples/check-personalized-v2.py`; prompt `vi-semantic-v2.8`, model `.env` `nvidia/nemotron-3-super-120b-a12b`. Lượt cuối lưu tại `data/live-tests/personalized-20261008T084433Z/`, **15/15 assertions đạt**; một lượt cho mỗi bước không chứng minh accuracy tổng quát.

| Input | Extraction và gate | Comparison thật |
|---|---|---|
| Nhật nguyên bản | 4 hard conditions; Nhật/HCM, ngày 2026-11-03, cap 30 triệu VND/người lớn/giá tour; adults=1; không condition số người thừa; confirm200 | succeeded, 20 columns, 0 recommendations, ONLY_UNVERIFIED |
| Tết nguyên bản | 11 conditions, OR Đà Nẵng/Tây Nguyên, Hải Phòng, ghép đoàn/ô tô, route chưa rõ strength, 4 soft priorities; adults/cap chưa có; hỏi năm/ý nghĩa khoảng/route + 2 core questions; confirm409 | Không enqueue comparison |
| Tết + follow-up minh họa | **Input test bổ sung**, không là thông tin suy từ câu gốc: 2 người lớn, cap 10 triệu/người lớn, Tết2027, khoảng có thể đi, route soft; giữ địa danh/priorities; departure gte2027-02-03, return lte2027-02-09; confirm200 | succeeded, 20 columns, 0 recommendations, ONLY_UNVERIFIED |

Hai comparison scan 234 records, giữ pool20 unknown; pool/offers bị cắt, scan không bị cắt. Semantic assessment skipped do không có pool hard-pass dùng được. Đây là kết quả xử lý thành công với bằng chứng chưa đủ, không là khẳng định các tour trong pool phù hợp user.

## Hồi quy NIM ngữ nghĩa

`uv run tour-backend evaluate-nim-v2 --repeat 1 --output data/evaluation-personalized-v2-acceptance.local.json`: **5/5 curated cases đạt**, gồm original Tết + update, clarified availability, paraphrase năm đã biết, partial OR và hard metric unsupported. Đây là SemanticRequirement tests, tách khỏi business gate API.

Các lượt trước có lỗi và không bị xóa khỏi artifacts: thêm loại tour từ từ “tour”, gán Nhật Bản sai field, thiếu answers trong mixed reply, duplicate ngày/quote không chứa raw value, tạo slider không được nói. Đã bổ sung regression/grounding/schema/prompt checks rồi chạy lại. Các reports trước ở `data/evaluation-personalized-v2.local.json` và `data/evaluation-personalized-v2-final.local.json` đều 4/5; không dùng lượt đạt sau cùng để hứa model hiểu mọi câu.

Parser vẫn một bounded repair; output còn sai trả lỗi kỹ thuật, không confirm bản đoán. Frontend cần cho sửa/retry hoặc dùng typed answers. Gold 50 câu/15 chuỗi vẫn chưa nghiệm thu.

## Audit dữ liệu thật

`uv run tour-backend audit-supabase --output data/catalog-audit.local.json`: chỉ đọc Supabase qua production adapter. **Mẫu 100 tours / 258 offers**, scan234; pool/offer truncation bật. Không là audit đầy đủ mọi records/offers.

- Origin/duration/itinerary có values trong 100/100 mẫu, nhưng unverified; destinations có 37 present/63 unsupported, transport 2 present/98 unsupported sau normalization.
- Ngày đi 258 present/unverified; ngày về và numeric availability thiếu 258/258.
- 258 giá dạng `from`, coverage unspecified, unverified; pricing_complete=0. Child prices chưa có age brackets được giữ unclassified.
- Volatile TTL của bootstrap chưa cấu hình; audit không đọc registry đã persisted của server. Record provenance không thay field website proof.

Việc dữ liệu tiếp theo: mở catalog địa danh/transport theo records thật; crawler xuất field proof/value/quote/scope; thống nhất pricing qualifiers/applicability và adapter import; bổ sung ngày về/chỗ/tour type có bằng chứng; chốt cadence trước cấu hình TTL. Không suy giá exact/coverage/số chỗ hoặc nâng verification để tăng số recommendations.

## Frontend sử dụng

Đọc `completeness.fields`, `readiness.can_confirm/can_search`, semantic issues/questions để tự điền và hỏi đúng phần thiếu. 201 có thể là confirmed Requirement hoặc draft với proposal_id. Giữ revision/version thật; form budget hard lte VND/per_adult/tour_price. Chưa tích hợp prototype UI; [hướng dẫn từng bước](../examples/backend-personalized-v2.md), [contract frontend](frontend-protocol-v2.md).
