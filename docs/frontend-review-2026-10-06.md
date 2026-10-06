# Điều chỉnh frontend sau review nhóm — 06/10/2026

**Trạng thái:** PLANNING. User chốt Giấy & Mực và yêu cầu chỉnh prototype; chưa frontend production hoặc chốt stack. Bản này thay baseline bố cục Input → Review → Kết quả cũ; các contract backend hiện hành không tự đổi.

**Review bổ sung:** [Điều khiển/navigation](frontend-review-controls.md) thay hành vi tự chạy sau confirm bằng nút Tìm kiếm/chat; bỏ revision trên UI, thêm slider sở thích, chữ lớn và nav Liên hệ/Hỗ trợ. Quyết định mới ưu tiên khi khác phần mô tả ban đầu dưới đây.

## Quyết định đã chốt

- Giữ nền giấy ấm, Newsreader cho tiêu đề và Be Vietnam Pro cho UI. Thêm accent xanh sâu, điểm nhấn đất nung và nền nhạt có chủ đích; ảnh du lịch nổi bật hơn, không tăng mật độ chữ.
- Ba màn: **Giới thiệu → Điền nhu cầu và xác nhận → Kết quả/so sánh**. Review nằm ngay màn form; bỏ thanh “1 nhu cầu / 2 xác nhận / 3 so sánh”.
- Màn giới thiệu có giới thiệu dự án, tour minh họa, hướng dẫn/demo tương tác, vị trí và thời tiết. Prototype mô phỏng widget, có nhãn; provider/API thật chưa chốt.
- Màn form phân biệt bắt buộc/tùy chọn, có chat ghi chú nhỏ và xác nhận trước khi tìm. URL vẫn tùy chọn; luồng URL-only giữ trong kế hoạch, không ép suy ra ngân sách/sở thích từ tour.
- Màn kết quả: cột yêu cầu khoảng **340–380px / 30% desktop**, rộng hơn 222px cũ; criteria mặc định đầy đủ, sửa trực tiếp từng field và chat ngay dưới. Mobile xếp dọc, bảng vẫn cuộn riêng.
- Bỏ nút Sửa yêu cầu, Lưu bản nháp, Tìm lại/Tìm phương án khác. Trao đổi, đổi criteria và yêu cầu nhóm khác qua chat; Retry cho lỗi tác vụ vẫn là hành động riêng.
- Giữ bảng kiểm chứng và evidence theo field; thêm tab **Phân tích AI** với kết luận có căn cứ, phép tính, đánh đổi, điều kiện áp dụng và dữ kiện chưa biết.
- Loading có skeleton và nhật ký bước xử lý; mock success/chậm/partial/empty/error/cancel. Mỗi log/tour/chat/thời tiết giả có nhãn minh họa; runtime chỉ dùng progress thật.

## Field mẫu để review (chưa thay contract C1/G4)

| Nhóm | Field |
|---|---|
| Bắt buộc trong tìm cá nhân hóa | Điểm đến, nơi khởi hành, ngày dự kiến, số người lớn, ngân sách/người lớn |
| Lựa chọn mặc định hiển thị rõ | Thời lượng 5 ngày (ưu tiên), trẻ em 0, ngân sách là ưu tiên với phạm vi giá tour; không tự coi là tổng nhóm |
| Tùy chọn | Thời lượng khác, số/tuổi trẻ em, khách sạn, điểm mua sắm, URL tham chiếu, ghi chú |

Prototype dùng bộ Nhật Bản / TP.HCM / tháng 11/2026 có sẵn để kiểm tra bố cục; nhập khác vẫn phải thấy giới hạn fixture, không giả retrieval đã tìm đúng. Chưa có API catalog. URL-only cần phạm vi có nguồn và review, không áp bộ field cá nhân hóa bắt buộc. Trẻ em >0 cần tuổi để đánh giá giá; unknown giữ blocker, không tự quy tuổi.

## Chat và thay đổi yêu cầu

1. Phân biệt câu hỏi về tour, đề nghị đổi criteria và yêu cầu nhóm khác. Prototype nhận một số câu mẫu, không giả có LLM thật.
2. Đề nghị sửa tạo **diff trước → sau**, giữ nguyên bảng cho tới khi user xác nhận; có Hủy và làm rõ khi mơ hồ. Không gửi PATCH text để lấy preview vì v1 commit sau parse.
3. Sau xác nhận, commit atomic theo expected revision rồi chạy lại phần phụ thuộc. Criteria hiện tại có revision riêng; kết quả cũ ghi rõ revision đã dùng trong khi chờ hoặc khi lượt mới lỗi/hủy.
4. Sửa trực tiếp dùng cùng diff/xác nhận. Response muộn không ghi đè lượt mới; pending proposal hết hiệu lực khi context đổi. Không tự nới ràng buộc để đủ 3 tour.
5. Nhóm khác giữ criteria, loại tour đã xem; mock có hai nhóm cố định và báo hết mẫu. Chat về kết quả chỉ dùng snapshot/evidence đang xem.

## Phân tích và phép tính

- Tóm tắt giải thích có căn cứ, không trình bày suy nghĩ nội bộ hoặc tạo điểm AI/trọng số chưa chốt.
- So sánh chênh lệch giá cùng basis/coverage/offer; minh họa A–B = 2.900.000đ/người lớn. Ước tính giá tour cho số người lớn ghi rõ chưa gồm phụ thu/trẻ em, không gọi tổng cuối.
- Đổi offer cập nhật giá/ngày/evidence/phép tính đồng bộ. Criteria sửa không biến kết quả revision cũ thành đã đánh giá lại.
- Mỗi nhận định mở evidence tương ứng; dữ kiện thiếu giữ unknown. G3/G10/G12 phải có dữ liệu backend trước runtime.

## Motion và kiểm tra prototype

- Chuyển màn fade/translate 220–360ms, ảnh hover nhẹ, tour xuất hiện nối tiếp, skeleton và log từng bước; chỉ animate transform/opacity, tôn trọng reduced-motion.
- Kiểm tra 1440/1280/768/390/320px, input/validation, chat đề xuất–xác nhận–hủy, sửa trực tiếp, tab/evidence/offer, loading chậm/lỗi/partial/empty/cancel, giữ kết quả cũ và Back.
- Không gọi API ngoài hoặc đọc geolocation thật trong lượt prototype; widget mô phỏng cả loading và từ chối quyền. Demo là walkthrough tương tác; video thật chưa được cung cấp.

**Kết quả 06/10:** prototype đã mở rộng, [61/61 kiểm tra](../prototypes/frontend-design/review/v2/qa-summary.json) đạt trên trang/asset local; không tràn ngang ở năm kích thước trên, console sạch. HTTP preview chưa xác minh vì kết nối localhost bị chặn trong sandbox. Token/accent, form và các màn mới vẫn cần user review; chưa nghiệm thu backend hoặc production.

## Khoảng thiếu cần FE–BE chốt

- **G11:** chat có context + preview proposal không commit → diff → confirm atomic/revision conflict; chưa endpoint/DTO, v1 PATCH text không đáp ứng preview.
- **G12:** phân tích có evidence, operands/basis/coverage/offer snapshot và giới hạn; không suy từ thứ tự candidates v1.
- **G13:** job activity có thứ tự, thời điểm, phase/source status và terminal; v1 chưa stream các bước rank/analysis. Polling v1 giữ làm nền.
- G1–G10 và D1–D5 giữ nguyên. Widget location/weather và video là enhancement độc lập, không chặn tìm tour; API/provider/quyền/fallback chưa chốt.
