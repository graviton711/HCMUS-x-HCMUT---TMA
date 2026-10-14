# backend/decide — hard filter, soft verdicts, ranking

## Trách nhiệm

Áp hard rules xác định trên từng offer, freshness ngày khởi hành, near-miss và phân tích dữ kiện tour. Giá catalog dùng trực tiếp price, price_type và currency. Sau hard pass, engine sắp theo ranking.order_by nhiều khóa; soft_fit là số soft verdict pass đã được xác thực, còn giá xếp theo số tiền niêm yết và giữ nguyên basis.

## Input/output

Vào: `Requirement`, snapshots đã normalize và verdict map `(offer_id, condition_id) → (pass|unknown|fail, quote, reason)`. Ra: `Comparison` gồm hard/soft evaluations, ranked hard-pass offers, near-miss, snapshots và analysis. `unknown` không bao giờ được tính là hard pass.

## Workflow

hard_filter đánh giá mọi hard condition. Destination được so với nhãn tường minh sau chuẩn hóa chuỗi tổng quát; có nhãn nhưng không khớp là fail, thiếu nhãn là unknown. passing_offers chỉ giữ offer khi mọi hard condition đều pass. Agent hiểu yêu cầu và gửi ranking.order_by; score_soft chỉ nhận verdict có quote khớp nguyên văn với snapshot. Engine áp dụng ranking theo thứ tự, xếp dữ liệu thiếu cuối và dùng ID làm tie-break ổn định. Mặc định là soft_fit giảm dần rồi price tăng dần nếu có soft condition; không có soft condition thì price tăng dần. near_miss giữ riêng; analyze tóm tắt phụ phí, điều khoản, rủi ro và quyền lợi.

## Interface với module khác

`workflows.py` cung cấp snapshots từ `data` qua `normalize`. MCP `query_tours`, `score_soft` và `relax_criterion` gọi engine; engine không truy cập HTTP, catalog, storage hay LLM.

## Quyết định kỹ thuật

- Không còn 0–1 score hoặc LLM callback trong engine.
- Engine không suy luận country/place aliases; `contains` và `any` áp dụng trên nhãn destination tường minh trong requirement.
- Không chấm mềm cho offer có bất kỳ hard condition nào chưa được chứng minh là pass.
- Near-miss không trộn vào ranked; mọi kết quả giữ condition state, reason code và source quote.
