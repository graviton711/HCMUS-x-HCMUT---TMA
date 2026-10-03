# Wireframe low-fi

**Trạng thái:** Đã chốt bố cục theo xác nhận ngày 03/10/2026, chưa phải UI final. Mục tiêu là làm rõ quyết định và bằng chứng; chi tiết hành vi/mobile/visual tiếp tục ở planning frontend.

**Phạm vi MVP:** Ưu tiên luồng “So sánh URL tour” với 2–3 URL. Luồng “Tìm theo nhu cầu” vẫn là hướng sản phẩm, nhưng chưa thuộc lát cắt tích hợp đầu tiên.

## 1. Nhập nhu cầu hoặc tour cần so sánh

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Chọn tour có căn cứ                                           [Đăng nhập: —] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Bạn muốn tìm tour hay so sánh tour đang cân nhắc?                            │
│ [ Tìm theo nhu cầu ]  [ So sánh URL tour ]                                   │
│                                                                              │
│ Điểm đến        [ Nhật Bản____________________ ]  Khởi hành từ [ TP.HCM___ ] │
│ Ngày đi         [ 10/11/2026 ] [ Linh hoạt ± 3 ngày ]                        │
│ Số người        [ 2 người lớn ] [ 1 trẻ em, 8 tuổi ]                         │
│ Ngân sách       [ Tối đa 35.000.000đ / người ]                               │
│ Ưu tiên         [ Ít mua sắm ] [ Bay thẳng ] [ Khách sạn 4 sao ]              │
│ Điều kiện bắt buộc [ Không transit______________________________ ]            │
│                                                                              │
│                                      [ Tìm tour để so sánh → ]               │
│                                                                              │
│ Hoặc dán URL tour vào tab “So sánh URL tour”.                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** Nêu rõ field bắt buộc/tuỳ chọn; điều kiện mơ hồ phải được làm rõ trước khi kết luận đạt. Tìm theo nhu cầu chờ đủ scope truy vấn; URL có thể đối chiếu dữ liệu tĩnh khi phép tính giá còn thiếu input. Hai luồng có input riêng, không trộn lẫn vào một ô không giải thích.

**Cả hai luồng được chọn cho demo:**

- Tab nhu cầu có text input hoặc form; sau khi xử lý hiển thị cách hiểu theo Bắt buộc / Ưu tiên / Cần làm rõ để sửa. Không gửi text và form cùng ghi đè một field không rõ thứ tự.
- Tab URL có danh sách 2–5 URL riêng và phần nhu cầu tùy chọn. Không bắt user điền ngân sách/ngày/số người khi chỉ muốn đối chiếu thông tin công bố.
- Tiến trình xử lý/nguồn lỗi có trạng thái rõ; user có thể tiếp tục sửa, nhưng kết quả cũ giữ nhu cầu/thời điểm của lần chạy đó.

## 2. Bảng so sánh

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Kết quả so sánh                                                              │
│ Nhật Bản · TP.HCM · 10–13/11 · 2 người lớn + 1 trẻ · tối đa 35tr/người       │
│ 2 lựa chọn đạt · 1 cần xác minh thêm            Giá/chỗ cập nhật: 27/09 10:42 │
├─────────────────────┬───────────────────┬───────────────────┬────────────────┤
│ Tiêu chí            │ Tour A            │ Tour B            │ Tour C         │
├─────────────────────┼───────────────────┼───────────────────┼────────────────┤
│ Nhà cung cấp        │ Công ty A         │ Công ty B         │ Công ty C      │
│ Lịch / thời lượng   │ 10/11 · 5N4Đ      │ 11/11 · 6N5Đ      │ Chưa xác minh  │
│ Tổng giá dự kiến    │ 32,8tr/người     │ 29,9tr/người     │ 31,2tr/người   │
│ Bao gồm             │ Vé bay, khách sạn │ Vé bay, 4 đêm    │ Thiếu dữ liệu  │
│ Điều kiện           │ Phụ thu phòng đơn │ Có 2 điểm mua sắm│ Mở chi tiết    │
│ Độ mới dữ liệu      │ Vừa kiểm tra      │ Vừa kiểm tra      │ Giá cũ 4 ngày  │
│ Nguồn               │ [3 nguồn]         │ [2 nguồn]         │ [1 nguồn]      │
├─────────────────────┴───────────────────┴───────────────────┴────────────────┤
│ Trade-off nổi bật: B rẻ hơn A nhưng có chương trình mua sắm; C thiếu xác nhận │
│ giá mới. Chưa đưa ra kết luận nếu dữ liệu quan trọng còn thiếu.               │
│ [Xem bằng chứng]   [Sửa tiêu chí]   [Mở trang nhà cung cấp]                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** Điều kiện bắt buộc được tách khỏi ưu tiên; mỗi ô có trạng thái đạt/không đạt/thiếu/cũ. Không sắp xếp theo “điểm AI” mặc định; nếu có sắp xếp, người dùng thấy tiêu chí và trọng số đang dùng. Giá cần ghi rõ tổng giá, đơn vị tính và thời điểm quan sát.

Trong tab URL, tour không đạt hoặc nguồn lỗi vẫn giữ cột tương ứng. Nhiều lượt khởi hành có lựa chọn riêng; chưa chọn thì ô giá/ngày/chỗ không ghép thành một offer. Chỉ có giá người lớn hoặc thiếu phụ thu thì không ghi là tổng giá cả nhóm đã đủ. Khi không có điều kiện bắt buộc, không gắn nhãn “đã đạt nhu cầu”.

## 3. Bằng chứng và rủi ro

```text
┌────────────────────────────── Bằng chứng: Giá Tour A ────────────────────────┐
│ Giá trị chuẩn hóa      32.800.000 VND / người                                │
│ Trạng thái             Nhà cung cấp công bố · kiểm tra lại lúc 10:42          │
│ Nguồn                  tour-page.example/tour-a  [Mở nguồn ↗]                │
│ Trích dẫn              “Giá người lớn: 32.800.000đ; khởi hành 10/11/2026”    │
│                                                                              │
│ Kiểm tra chéo          Chưa có nguồn độc lập xác nhận tình trạng chỗ.         │
│ Rủi ro liên quan       Giá có thể thay đổi; xác nhận với nhà cung cấp trước   │
│                       khi thanh toán.                                        │
│                                                                              │
│ [Đóng]                 Các field khác: lịch khởi hành · bao gồm · chính sách  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** Evidence mở theo từng field, không chỉ một danh sách link chung. Phân biệt nội dung nhà cung cấp tự công bố với xác minh độc lập; hiển thị thiếu dữ liệu và giới hạn crawl. Không hiển thị “uy tín thấp/cao” nếu không có tiêu chí và nguồn cụ thể.

## Ghi chú cho thiết kế chi tiết

- Ví dụ giá, ngày và tên công ty trong wireframe chỉ minh hoạ bố cục, không phải dữ liệu thật.
- Khi thiết kế chi tiết, kiểm tra hai tab nhập đủ rõ, bảng đối chiếu được trên mobile và nhóm evidence/rủi ro dễ kiểm chứng; giữ các trách nhiệm và bố cục chính đã chốt.
