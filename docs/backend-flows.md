# Hai luồng backend và chính sách hiểu yêu cầu

**Trạng thái:** Đang triển khai cả hai luồng. User chốt ngày 01/10/2026: budget coverage mặc định tour_price.

## Discover: nhập nhu cầu

1. Nhận text/form, lưu mode và timestamp của lượt nhập; tạo job extraction nếu cần NIM.
2. Normalize/validate, trả cách hiểu có thể sửa và câu hỏi có target. Chỉ hỏi field ảnh hưởng bước đang làm.
3. Cần scope tìm đủ cụ thể theo source capability: đề xuất ít nhất điểm đến hoặc nhà cung cấp được nhận diện. Budget/date không bắt buộc khi user không ràng buộc và nguồn cho tìm rộng.
4. Compile QuerySpec, chọn source đã duyệt có khả năng search; ghi rõ hạn chế coverage. Filter nguồn chỉ là prefilter, không thay đánh giá trên snapshot.
5. Nhận candidates theo từng offer; xét hard tree rồi trình bày ba nhóm và trade-off của nhóm có dữ liệu đủ.
6. Khi không có eligible, phân biệt no candidates / tất cả fail / chỉ có unknown / upstream không dùng được. Có thể nêu điều kiện gây loại và gợi ý sửa; không tự nới.

URL được tìm thấy phải đi qua cùng access/fetch policy như URL user nhập. Không tìm nguồn ngoài registry để “đủ kết quả”.

## Compare URLs: giữ lựa chọn của user

1. Nhận 2–5 URL từ input riêng; giữ thứ tự user nhập và tạo stable `target_id`. Đây là giới hạn demo đề xuất, có thể cấu hình.
2. Validate URL/source; target không hỗ trợ vẫn có trạng thái/ lý do trong kết quả. URL lỗi cú pháp không được gửi đi fetch.
3. Nhu cầu là tùy chọn. Không ép nhập điểm đến/date/budget/party nếu user chỉ muốn đối chiếu dữ liệu công bố.
4. Đọc từng target, giữ source status riêng. Tour fail hard condition hoặc nguồn lỗi vẫn giữ cột, không thay bằng tour khác.
5. Có một offer phù hợp và đủ cụ thể → có thể đánh giá offer đó. Có nhiều offer → trả lựa chọn offer; khi chưa chọn, các ô phụ thuộc offer ghi `MULTIPLE_OFFERS_UNSELECTED`, không ghép giá/ngày/chỗ.
6. Cho user chọn offer bằng `target_id + offer_snapshot_id` từ kết quả đã sở hữu; tạo comparison mới dùng lại snapshot khi policy cho phép. Không tự chọn offer rẻ nhất.

Đối chiếu tour tĩnh không đồng nghĩa xác nhận giá/chỗ cho một ngày cụ thể. Candidate có `assessment_level=tour_only/offer_specific`; readiness cho acquisition tách khỏi readiness cho hard evaluation.

## Quy tắc ngôn ngữ đề xuất

| Cách nói | Xử lý |
|---|---|
| “Đi Nhật”, “muốn đi Nhật”, “từ Sài Gòn”, “5 ngày” | Scope tìm kiếm/condition theo field đã nói; mặc định hard và hiển thị cho sửa |
| “Bắt buộc”, “chỉ chọn nếu”, “không”, “tối đa”, “ít nhất” | Hard predicate đúng operator/scope; không bỏ qualifier |
| “Ưu tiên”, “nếu được”, “thích”, “ít/rẻ hơn”, “tầm” | Soft; target gần đúng không tự thành giới hạn số |
| “Muốn khách sạn 4 sao” | Đề xuất soft khi không có tín hiệu bắt buộc; hard/soft hiện rõ để sửa |
| “Không cần X nữa” với X đang tồn tại | Remove X; không thêm cấm X |
| “Không cần X” nhưng chưa có X | Không tạo condition X; không coi là `not X` |
| “Nhật hoặc Hàn” | OR; “cả Tokyo và Kyoto trong cùng tour” là AND/contains_all |
| Câu tự sửa “Nhật hoặc Hàn… à chỉ Hàn thôi” | Thay phần được sửa, giữ phần không liên quan; hỏi nếu scope sửa không xác định |

Unsupported hard condition vẫn là decision blocker. Source thiếu field là data unknown; không hỏi user đoán dữ kiện nhà cung cấp.

## Tiền, thời gian và nhóm khách

- Text không nói currency: giữ unresolved; có thể hỏi gộp currency/basis/coverage. Form có currency VND hiển thị trước và user submit thì là evidence từ form, không phải LLM tự thêm.
- “Cả nhà/nhóm” xác định basis, không xác định coverage. “Giá tour” = tour_price; “tổng chi phí chuyến đi” = trip_total. Khi không nói coverage, backend dùng tour_price với provenance system_default, hiển thị cho sửa; không hỏi coverage lại. Không cộng chi phí tự ước lượng ngoài nguồn để lấp trip_total.
- Date tương đối normalize bằng timestamp của lượt nói + timezone ứng dụng (đề xuất `Asia/Ho_Chi_Minh`). “Tháng sau” là tháng lịch tiếp theo; “cuối tháng” chưa có ngày biên thì hỏi nếu dùng làm hard filter.
- Date không có năm không tự chọn năm tương lai; lấy từ context rõ hoặc hỏi. Form datepicker gửi ISO date đầy đủ.
- Party là context tính giá, không tự biến thành sở thích. Thiếu tuổi/rooming chỉ block phép tính cần dữ liệu đó; không ngăn đối chiếu tour tĩnh.

## Hợp nhất nhiều lượt

Text extraction trả patch intent và quote; backend resolve target từ revision đang dùng. Chỉ `add/replace/remove` condition/party fields được cho phép; không thao tác JSON tùy ý hay đặt lại toàn bộ state từ response LLM.

Structured edit/clarification trả lời trực tiếp theo target và expected revision; giá trị mới cũng validate. Hai update cùng revision: chỉ một được commit; update còn lại conflict và không ghi đè. Compare job khóa vào revision được yêu cầu, không tự đổi theo lượt user sửa tiếp.

“Giữ nguyên” không làm refresh timestamp hoặc mất evidence của conditions cũ. Budget increment chỉ áp dụng khi có đúng một target phù hợp và basis/currency đã rõ; nếu có hai budget thì hỏi tăng cái nào.
