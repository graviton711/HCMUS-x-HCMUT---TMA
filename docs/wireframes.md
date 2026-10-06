# Wireframe low-fi

**Trạng thái:** PLANNING, sửa ngày 06/10/2026 theo [review nhóm](frontend-review-2026-10-06.md). Giấy & Mực đã chốt style; token và ba màn mới còn P3.3–P3.7. Mẫu chỉ minh họa bố cục/hành vi, chưa public response hoặc frontend production.

**Bổ sung mới:** [Review điều khiển/navigation](frontend-review-controls.md): navbar Giới thiệu/Tìm tour/Liên hệ/Hỗ trợ, form và kết quả đều thuộc Tìm tour. Heading kết quả có Tìm kiếm + trạng thái bằng chữ; bỏ số revision trên UI. Cột yêu cầu có slider sở thích; Sửa tự cuộn tới xác nhận, confirm chỉ cập nhật, nút/chat mới tìm. Chữ nội dung 14–16px, mobile giữ bảng cuộn riêng. Bố cục thấp dưới đây giữ vai trò nền, không mô tả token chi tiết mới.

**Flow:** Giới thiệu → form nhu cầu và xác nhận tại chỗ → Kết quả/so sánh có trạng thái xử lý. Evidence là panel. Bỏ stepper và màn Review riêng; không thêm màn chọn tour từ pool.

## 1. Giới thiệu

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Đi cùng                                      Hướng dẫn · Demo         │
├───────────────────────────────────────────────────────────────────────┤
│ Chọn chuyến đi có căn cứ                    [Ảnh du lịch]             │
│ So sánh tour, hiểu đánh đổi, kiểm tra nguồn.                           │
│ [Tìm tour →]           [Xem hướng dẫn/demo]                           │
│                                                                       │
│ [Vị trí · minh họa]      [Thời tiết · minh họa]                        │
│ Tour minh họa:       [Ảnh · Tour A] [Ảnh · Tour B] [Ảnh · Tour C]      │
│ Cách dùng: điền nhu cầu → xác nhận → đối chiếu và hỏi thêm.            │
└───────────────────────────────────────────────────────────────────────┘
```

Widget và tour có nhãn minh họa. Prototype dùng walkthrough tương tác; video thật chưa có. Mô phỏng loading/từ chối quyền/lỗi và fallback, không gọi API ngoài hoặc geolocation thật. Provider/quyền/API là enhancement cần chốt, không chặn Tìm tour. Đi cùng vẫn là tên tạm.

## 2. Form nhu cầu + xác nhận

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Chuyến đi bạn đang tìm                                                │
├─────────────────────────────────────┬─────────────────────────────────┤
│ Bắt buộc trong tìm cá nhân hóa       │ Nhu cầu trước khi xác nhận     │
│ Điểm đến *      [Nhật Bản]          │ Nhật Bản · từ TP.HCM           │
│ Khởi hành *     [TP.HCM]            │ Tháng 11/2026 · 2 người lớn    │
│ Ngày dự kiến *  [11/2026]           │ 35 triệu / người lớn          │
│ Người lớn *     [2]                │ Coverage: giá tour             │
│ Ngân sách *     [35 triệu/người lớn]│ Ưu tiên 5 ngày · trẻ em 0       │
│                                     │ [Cần làm rõ / lỗi theo field]   │
│ Tùy chọn và mặc định rõ             │                                 │
│ 5 ngày (ưu tiên) · trẻ em 0         │ Chat ghi chú                    │
│ Khách sạn / mua sắm [Chưa chọn]     │ [Thêm lưu ý khác…] [Gửi]       │
│ URL tham chiếu [________________]  │                                 │
├─────────────────────────────────────┴─────────────────────────────────┤
│ [Về giới thiệu]                         [Xác nhận và tìm tour →]      │
└───────────────────────────────────────────────────────────────────────┘
```

Field/default là mẫu để review C1/G4, chưa thay API contract; ngân sách mẫu là ưu tiên với basis per_adult/coverage giá tour, không tự coi là tổng nhóm. Trẻ em >0 cần tuổi để đánh giá giá; unknown giữ blocker. Chat ghi chú sửa cùng draft, không tự suy hard/soft. Validation giữ input và focus tới field lỗi; xác nhận/review nằm ngay form.

URL-only vẫn trong kế hoạch: review phạm vi có nguồn, không ép bộ field cá nhân hóa hoặc suy ngân sách/sở thích từ tour. V1 hiện tách mode và URL 2–5 (G9). Fixture prototype Nhật Bản không giả có retrieval cho đầu vào khác.

## 3. Kết quả, so sánh và chat

```text
┌───────────────────────────────┬────────────────────────────────────────┐
│ Yêu cầu của bạn · revision 2 │ Tour theo nhu cầu · Dữ liệu minh họa    │
│ ~340–380px / 30% desktop     │ [Gợi ý A]    [Gợi ý B]    [Gợi ý C]    │
├───────────────────────────────┤                                        │
│ Điểm đến      [Nhật Bản]     │ [Bảng kiểm chứng] [Phân tích AI]       │
│ Khởi hành     [TP.HCM]       ├──────────────┬─────────┬─────────┬───────┤
│ Ngày          [11/2026]      │ Tiêu chí     │ A       │ B       │ C     │
│ Người lớn     [2]           │ Giá/người lớn│ 32,8tr  │ 29,9tr  │31,2tr │
│ Trẻ em        [0]           │ Ngày/offer   │ 10/11   │ 11/11   │12/11  │
│ Ngân sách     [35tr/adult]   │ Bao gồm      │ [Nguồn] │ [Nguồn] │Thiếu  │
│ Thời lượng    [5 ngày ưu tiên]│ Điều kiện    │ [Nguồn] │ [Nguồn] │Thiếu  │
│ Coverage giá tour · ưu tiên  │ ...          │ ...     │ ...     │...    │
├───────────────────────────────┤                                        │
│ Chat về chuyến đi            │ Tab Phân tích AI:                      │
│ “Giảm ngân sách còn 30tr”    │ Kết luận/đánh đổi · evidence theo ý     │
│ Đề xuất: 35tr → 30tr         │ A−B = 2,9tr/người lớn · basis/offer    │
│ [Xác nhận thay đổi] [Hủy]    │ Giới hạn phụ thu/trẻ em/dữ kiện thiếu │
│ [Hỏi hoặc đổi yêu cầu…] [Gửi]│                                        │
└───────────────────────────────┴────────────────────────────────────────┘
```

- Criteria hiển thị đủ hàng/default và blocker; sửa trực tiếp từng field và chat ngay dưới. Diff trước → sau chưa đổi bảng cho tới xác nhận; Hủy/làm rõ/conflict giữ revision. Atomic commit/expected revision và preview không commit còn G11; PATCH text v1 không dùng làm preview.
- Bỏ Sửa yêu cầu/Lưu bản nháp/Tìm lại/Tìm phương án khác; yêu cầu nhóm khác qua chat giữ criteria và loại tour đã xem. Retry lỗi tác vụ/nguồn là hành động riêng. Không tự nới hard constraints hoặc lấp giả đủ ba.
- Kết quả gắn revision đã dùng; còn xem được khi lượt mới chờ/lỗi/hủy. Response muộn không ghi đè lượt mới, pending proposal mất hiệu lực khi context đổi.
- Bảng kiểm chứng giữ cùng hàng/evidence theo field. Tab Phân tích AI là giải thích có căn cứ/phép tính/đánh đổi/unknown, không suy nghĩ nội bộ/điểm AI. So giá cùng basis/coverage/currency/offer; giá người lớn chưa phải tổng cuối đủ phụ thu. G3/G10/G12 cần dữ liệu runtime.
- Đổi offer cập nhật ngày/giá/evidence/phép tính đồng bộ; không ngầm chọn rẻ nhất. Hard unknown không gọi là đạt nhu cầu.

**Có URL — đề xuất cần review FLOW-3:** tối đa ba gợi ý mới cộng tour URL tham chiếu ngoài số này; một URL + ba gợi ý = bốn cột. Canonical duplicate không lặp, tham chiếu lỗi vẫn có lý do. Nhiều URL/mobile cần review; budget 20 chỉ ở backend.

**Processing ngay màn 3:** skeleton + nhật ký hiểu nhu cầu/đọc nguồn/tìm/đánh giá/so sánh có nhãn mock; mô phỏng success/chậm/partial/empty/error/cancel. Runtime chỉ phase/activity thật, chưa có stream từng bước v1 (G13), không phần trăm giả. Giữ kết quả cũ và thao tác Hủy/Retry thích hợp.

## 4. Panel bằng chứng

```text
┌──────────────────────── Bằng chứng: Giá Tour A ────────────────────────┐
│ 32.800.000 VND / người lớn · offer ngày 10/11/2026 · minh họa          │
│ Nhà cung cấp công bố · thời điểm quan sát                             │
│ URL nguồn [Mở nguồn ↗] · raw quote / snapshot / giới hạn               │
│ Chưa có nguồn độc lập xác nhận tình trạng chỗ.                        │
│ [Đóng]                                                                │
└───────────────────────────────────────────────────────────────────────┘
```

Evidence mở đúng field/nhận định/offer, đóng trả focus. Phân biệt tự công bố với xác minh độc lập; timestamp không thay freshness hoặc verification. Không gán uy tín/rủi ro nếu không có tiêu chí và nguồn.

## Visual và kiểm tra

- Giấy ấm, Newsreader + Be Vietnam Pro; xanh sâu/đất nung/nền nhạt và ảnh tạo điểm nhấn, không chỉ tăng chữ đậm. Màu trạng thái có nhãn riêng với thương hiệu.
- Motion transform/opacity 220–360ms, ảnh hover nhẹ, tour xuất hiện nối tiếp, skeleton/log; tôn trọng reduced-motion.
- Kiểm tra 1440/1280/768/390/320px, form/validation, chat diff–confirm–cancel, sửa trực tiếp, tab/evidence/offer, mọi loading/error/partial/empty/cancel và Back. Mobile xếp dọc, bảng cuộn riêng.
- Tour/giá/ngày/lý do/log/chat/widget đều có nhãn minh họa. Giữ G1–G13/D1–D5, không tự dựng API DTO hoặc gọi crawler từ FE.
