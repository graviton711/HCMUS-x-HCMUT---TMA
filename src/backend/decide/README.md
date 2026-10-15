# backend/decide — eligibility, metric vectors và decision views

## Trách nhiệm

Áp hard filter xác định; tiêu thụ metric facts đã chuẩn hóa và evidence; tính preference fit có khoảng khi thiếu dữ kiện; tạo objective views từ cùng một metric vector. Không tạo điểm chất lượng tổng hợp.

## Input/output

Vào: requirement đã validate, tour/offer snapshots, metric facts và preference evaluations `(offer_id, condition_id) -> score/unknown + quote`. Ra: hard evaluations, metric profiles, decision options, `ranked`, `near_miss`, snapshots, evidence, decision trace theo offer/tour và số lượng đã quét.

## Workflow

1. Hard filter chạy trước; chỉ offers pass toàn bộ hard conditions vào soft evaluation.
2. Metric facts chỉ hợp lệ khi evidence quote khớp đúng source field. Numeric/categorical normalization và phép tính do code thực hiện.
3. Preference fit cộng trọng số theo mức `0`, `0.5`, `1`; unknown tạo khoảng điểm min/max và evidence coverage riêng.
4. Cost view tách exact/from/contact, group total, khoản bắt buộc đã định giá và exclusions chưa định giá. Exclusion chỉ thành cost khi obligation, amount, unit và applicability có evidence.
5. Objective views gồm cheapest, best-fit, experience-rich, fewest-legs, cancellation-flexible, family-friendly, included-value và balanced Pareto. Chỉ xếp trên metric có thể so sánh; unknown không được ép thành 0 hoặc pass.
6. Mỗi view trả tối đa 5 lựa chọn, nhưng engine giữ đủ profile/evaluation cho explanations. Nếu có đủ candidates, kết quả có tối thiểu ba tour khác nhau; thiếu thì trả số thực có và relaxation scenarios riêng.
7. Decision trace đếm riêng scan, điều kiện và blocker đầu tiên. Tổng theo condition có thể chồng lấp; unknown được đếm riêng. Mỗi option so metric với nhóm hard-pass cùng đơn vị/phạm vi, giữ evidence và trạng thái thiếu dữ liệu.

## Interface với module khác

`workflows.py` truyền snapshots đã normalize; MCP/service điều phối batch và gọi engine. Engine không truy cập HTTP, storage, catalog trực tiếp hay LLM.

## Quyết định kỹ thuật

- Trọng số chỉ đổi thứ tự/view, không thay eligibility.
- Mỗi metric giữ đơn vị và thang đo riêng; evidence coverage mô tả dữ liệu, không phải độ tốt của tour hay xác suất.
- Unknown tạo khoảng hoặc trạng thái unavailable, không bị biến thành điểm 0 hay đạt.
- Không cộng giá trị tiền cho lợi ích hoặc exclusions không có giá/đơn vị/điều kiện áp dụng rõ.
- Multi-currency không quy đổi; cheapest/Pareto được nhóm currency-wise.
- Tie-break dùng khóa xác định để kết quả ổn định.
- `ranked`/`near_miss` được giữ cho consumer cũ.
- Scenario gọi lại engine thuần trên cùng snapshot; tiêu chí mới không tự nhận soft verdict nếu chưa được enrichment.
