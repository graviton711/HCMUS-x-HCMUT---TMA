# backend/input — validate điều kiện có cấu trúc

## Trách nhiệm

Chuẩn hóa và kiểm tra `Requirement` có cấu trúc do agent tools gửi. Không trích điều kiện từ câu tự do, không đọc catalog và không so sánh.

## Input/output

Vào: điều kiện JSON có field/operator/value/strength/quote đã được agent xác định, cùng điều kiện chung, các nhóm lựa chọn OR và date assumptions (nếu có). Ra: `Requirement` hợp lệ. Tiền chỉ là integer VND; ngày chỉ là ISO dương lịch; dữ liệu lỗi định dạng bị từ chối hoặc trở thành `unknown`, không tự quy đổi/đoán. Lunar date được chuyển đổi riêng qua tool `clarify_date`.

## Workflow

Agent gửi điều kiện đã cấu trúc tới tool; validator kiểm tra field/operator/value và giữ quote làm chứng cứ cho nguồn user. `conditions` là điều kiện dùng chung (AND); mỗi `alternative` là một nhánh AND và các nhánh được OR với nhau. Các chiều lựa chọn độc lập được group theo `(duration,date_window)`, destination linh hoạt gộp bằng `destination any [...]` thay vì cross-product. Điều kiện nhiều giá trị tương đương trong cùng một field vẫn có thể dùng operator `any`. `date_from`/`date_to` là hai biên bao gồm của khoảng ngày khởi hành trong catalog; ngày khởi hành đơn lẻ dùng cùng một ngày cho cả hai biên. Các trường này không xác minh ngày về. Một date assumption dùng chung cho một `(quote,date_from,date_to)` distinct và có thể link nhiều cặp ngày ở các nhánh khác nhau; UI gộp hiển thị theo tuple này. `clarify_date` dùng `vi_lunaire` và kiểm tra round-trip trước khi trả ISO. Date assumptions phải có quote, khoảng ISO cụ thể và múi giờ; chúng hiển thị cho người dùng sửa trong Brief. Sửa một nhánh trong shared assumption thì split assumption: tách cặp vừa sửa thành assumption riêng, giữ nguyên các cặp còn lại. Thay đổi điều kiện tạo requirement draft mới; chỉ endpoint decision sau khi người dùng review mới chạy hard filter.

## Interface với module khác

Agent MCP tools gọi validator trước `decide`; không có keyword parser hoặc NIM extraction fallback. Chỉ phụ thuộc `models.py` và lunar calendar helper.

## Quyết định kỹ thuật

- Không trích xuất điều kiện bằng regex, từ khóa hoặc LLM phụ; agent là hội thoại và công cụ là ranh giới dữ liệu có cấu trúc.
- Chỉ chấp nhận tiền VND dạng integer và ngày ISO; không có heuristic đổi đơn vị/định dạng.
- Lịch âm được tính bằng thư viện xác định và kiểm tra round-trip.
- Nhiều giá trị đồng nghĩa trong một field dùng condition OR (`any`); các tổ hợp lựa chọn được ghép cặp rõ ràng phải nằm trong các alternative branch riêng để tránh tạo tổ hợp sai.
- `alternatives=[]` giữ tương thích: mọi hard condition trong `conditions` tiếp tục được AND như trước.
