# Recommendation recovery — giao diện

Contract đã chốt: ngân sách tour mới là trần **giá niêm yết**, phụ thu/thực trả báo riêng. BE `BudgetV2.measure` phân biệt listed/payable; lịch sử thiếu measure hiểu là payable. Sửa số tiền giữ measure của nhu cầu cũ.

Form tạo mới gửi measure=listed cho tour_price. Các tháng nối OR theo từng YYYY-MM, không phủ khoảng trống. MonthPicker chặn thêm tháng quá khứ theo Asia/Ho_Chi_Minh; lựa chọn cũ vẫn xem/bỏ được. Tạo search mới kiểm ngày/tháng, sửa nhu cầu kiểm phần thời gian thay đổi.

Kết quả ưu tiên `listed_price_quotes` của đúng offer, giữ chữ “Từ”; thêm chú thích giá niêm yết và phụ thu chưa xác nhận. Khung nhu cầu ghi rõ listed/payable. Source text và evidence trong bảng giữ nguyên; không suy phụ thu=0 từ dữ liệu thiếu.

Validation: form create/edit/history, tháng OR không liền nhau, chặn tháng qua, recommendation có listed price và cảnh báo thực trả; typecheck/lint/build và tests frontend. UI giữ hệ thống thiết kế sản phẩm hiện có.
