# Luồng và trạng thái frontend

**Trạng thái:** Chi tiết hành vi đề xuất để review ở P1. Bám wireframe đã chốt; chưa thay đổi API contract.
**Liên quan:** [planning](frontend-plan.md), [wireframe](wireframes.md), [checklist FE–BE](frontend-backend-checklist.md).

## Màn hình và hai luồng

| Bề mặt | Người dùng làm gì | Frontend cần gì |
|---|---|---|
| Input: tìm theo nhu cầu | Nhập điểm đi/đến, ngày, nhóm khách, ngân sách, điều kiện và ưu tiên | Field rules, schema criteria, lỗi theo field |
| Input: so sánh URL | Dán/chỉnh danh sách tour đang cân nhắc | Rule URL/số lượng, lỗi theo URL, dedup/canonicalization từ BE |
| Làm rõ / xác nhận | Bổ sung phần mơ hồ hoặc xác nhận yêu cầu đã chuẩn hóa | Criteria chuẩn hóa, câu hỏi/field cần bổ sung từ BE nếu có |
| Đang xử lý | Nhìn thấy yêu cầu đang chạy; có thể quay lại/sửa/hủy theo policy | Request/job state thật, timeout và ý nghĩa hủy |
| Kết quả | Đối chiếu tour/offer, trạng thái ràng buộc và trade-off | Tour/offer, evaluation, evidence và lý do thiếu/loại |
| Panel evidence | Kiểm tra một nhận định hoặc field, mở nguồn | Reference chính xác, dữ kiện nguồn, thời điểm, trạng thái xác minh |

Đề xuất tổ chức Input và Results là hai màn; Processing là trạng thái chuyển tiếp, Evidence là panel trong Results. Route cụ thể và khôi phục khi refresh chốt ở P2; không tự thêm dashboard/profile/booking.

**Luồng nhu cầu:** Nhập → kiểm tra input → làm rõ khi cần → xác nhận criteria → xử lý → so sánh → mở evidence hoặc sửa criteria/mở nhà cung cấp.

**Luồng URL:** Nhập danh sách → kiểm tra định dạng/trùng → xử lý → so sánh dữ liệu và ưu tiên nếu có → evidence hoặc sửa/thử lại URL lỗi. Thiếu ưu tiên thì chỉ đối chiếu dữ kiện, không gọi kết quả là mức phù hợp cá nhân.

Frontend không tự hiểu điều kiện như “không transit” thành kết luận đạt nếu backend chưa có cách đánh giá có căn cứ. Việc chuyển dữ liệu người dùng thành criteria và hỏi lại phải có trách nhiệm rõ ở C1–C3.

## Quy tắc thao tác đề xuất

- Đổi tab giữ draft riêng cho từng kiểu nhập; không âm thầm chuyển dữ liệu giữa hai kiểu.
- Validation hiện ngay tại field; lỗi một URL chỉ ra URL đó. Giữ input để sửa, không reset toàn bộ form khi request lỗi.
- Criteria đã submit và draft đang sửa là hai snapshot khác nhau; kết quả luôn ghi rõ criteria dùng để tạo nó.
- Submit mới vô hiệu kết quả request cũ. Chốt hủy phía BE riêng; hủy chờ ở trình duyệt không mặc định là BE đã dừng xử lý.
- Sửa tiêu chí làm rõ kết quả cũ chưa ứng với draft mới; chạy lại các bước cần BE tính/lọc. Sắp xếp chỉ ở FE nếu đã nhận đủ tập kết quả và quy tắc cho phép.
- Giữ cùng tiêu chí giữa các tour; khi một tour có nhiều offer, chỉ rõ offer đang đối chiếu và đổi đúng giá/ngày/evidence cùng nhau.
- Evidence đóng về đúng phần tử mở nó; panel trên mobile không che lối quay lại và giữ được nhãn tour/field.
- Mở trang nhà cung cấp/nguồn bằng URL từ dữ liệu đã kiểm tra; không biến thao tác này thành đặt tour.

## Ma trận trạng thái

Các tên UI dưới đây là mô tả trạng thái local, **không phải enum mới của API**.

| Tình huống | UI / hành động tiếp theo |
|---|---|
| Input thiếu/sai | Lỗi theo field/URL, focus tới lỗi; giữ các giá trị hợp lệ |
| Criteria mơ hồ | Hiển thị phần cần làm rõ và lý do; chưa coi request đủ điều kiện |
| Đang xử lý | Skeleton/progress theo stage thật nếu BE hỗ trợ; không hiển thị phần trăm giả |
| Thành công | So sánh dữ kiện cùng tiêu chí; mọi trade-off mở được evidence |
| Một phần nguồn thất bại | Giữ tour thành công, nêu URL/nguồn lỗi và cách thử lại; không giấu lỗi |
| Không có tour phù hợp | Nêu lý do đã biết và cho sửa criteria; phân biệt với nguồn không lấy được dữ liệu |
| Chỉ có 1 tour | Hiển thị dữ kiện và giới hạn so sánh; không tạo trade-off giữa nhiều lựa chọn |
| Toàn bộ nguồn thất bại | Lỗi truy xuất, cho chỉnh URL/thử lại; không nói “không có tour phù hợp” |
| Mất mạng/timeout | Giữ input; thông báo có thể thử lại. Nếu có job, kiểm tra trạng thái trước khi tạo job trùng |
| Dữ liệu thiếu/một phần | Nhãn chữ và chi tiết field; không suy ra giá trị hoặc bỏ hàng tiêu chí |
| Dữ liệu cũ/chưa có policy freshness | Hiển thị timestamp; chỉ gắn “cũ” khi có policy đã chốt |
| Nguồn tự công bố/chưa xác minh độc lập | Nêu đúng trạng thái bằng chứng; không đổi thành dấu “đã xác minh” chung cho tour |

## Điểm review ở P1

- [ ] FLOW-1 — Field bắt buộc/tùy chọn, lựa chọn ngày linh hoạt và ngân sách theo người/nhóm.
- [ ] FLOW-2 — Đầu vào URL có dùng criteria cá nhân hay chỉ so sánh thông tin; số URL và số cột tối đa.
- [ ] FLOW-3 — Cách chọn offer, điều kiện đạt/không đạt/chưa biết và tour bị loại có được xem lý do hay không.
- [ ] FLOW-4 — Sửa criteria cần request mới khi nào; trạng thái chờ/hủy/thử lại và giữ draft.
- [ ] FLOW-5 — Route/back/refresh: chỉ giữ phiên hiện tại hay khôi phục kết quả; dữ liệu nào được lưu và thời hạn.
- [ ] FLOW-6 — Phạm vi đăng nhập; phương án mobile cho comparison/evidence.

## Tiêu chí walkthrough

Người dùng có thể nhập một nhu cầu hoặc nhóm URL, biết kết quả dựa trên criteria nào, đối chiếu đúng giá/ngày, tìm một trade-off và kiểm tra nguồn tương ứng. Khi dữ liệu thiếu/cũ/nguồn lỗi, họ hiểu hạn chế và biết thao tác tiếp theo.
