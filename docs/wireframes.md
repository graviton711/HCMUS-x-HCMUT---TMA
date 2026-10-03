# Wireframe low-fi

**Trạng thái:** PLANNING, ngày 03/10/2026. Theo sửa đổi của user, bỏ danh sách/checkbox chọn tour; hệ thống tự đề xuất và so sánh ngay. Mẫu chỉ minh họa bố cục, chưa UI final/public response. Budget 20 và URL tham chiếu ngoài ba gợi ý cần review theo FLOW-3.

**Flow:** Input nhu cầu + URL → Review → Processing → Kết quả/so sánh tự động. Evidence là panel; không thêm màn sàng lọc ứng viên.

## 1. Nhập nhu cầu và URL tùy chọn

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Chọn tour có căn cứ                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Bạn đang muốn một chuyến đi như thế nào?                                   │
│                                                                              │
│ Nhu cầu [ Muốn đi Nhật từ TP.HCM tháng 11, khoảng 5 ngày..._______________ ] │
│         [_______________________________________________________________ ] │
│ [Điền theo hướng dẫn]                                                      │
│                                                                              │
│ Đã có tour đang cân nhắc? Thêm URL (tùy chọn)                               │
│ [ https://.../tour-tham-chieu_______________________________________ ] [Thêm URL]    │
│ [ tour-tham-chieu × ] [ tour-x × ]                                                   │
│                                                                              │
│ Hệ thống sẽ đọc các tour bạn gửi và tìm thêm lựa chọn để đối chiếu.          │
│                                              [ Xem cách hiểu nhu cầu → ]   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** Nhu cầu và URL có vùng nhập/nhãn rõ trong một draft chung. Cho nhập nhu cầu-only, URL-only hoặc cả hai; không bắt điền ngân sách/ngày/số người để xem dữ kiện công bố. Text/form là hai cách nhập nhu cầu, không gửi cả hai ghi đè nhau. “Điền theo hướng dẫn” và field survey là chi tiết thiết kế, có thể đổi sau.

## 2. Review nhu cầu và phạm vi tìm

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Kiểm tra cách hiểu trước khi tìm                                           │
│ Bắt buộc      Điểm đến Nhật Bản · xuất phát TP.HCM                          │
│ Ưu tiên       Khoảng 5 ngày                                                 │
│ Cần làm rõ    Tháng 11 năm nào? [Chọn năm]                                  │
│                                                                              │
│ Phạm vi tìm   Nhật Bản, khởi hành từ TP.HCM                   [Sửa phạm vi] │
│ Tour bạn gửi  Tour tham chiếu · Tour X                                              │
│                                                                              │
│ [Quay lại sửa đầu vào]                          [Xác nhận và tìm tour →]   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** Nội dung criteria trong ví dụ chỉ minh họa nhóm, không mặc định strength cho câu nhập. Khi chỉ có URL, đọc tour để gợi ý phạm vi; nhãn chỉ rõ phần này lấy từ tour tham chiếu và cho sửa. Giá/supplier/đặc điểm tour không tự thành ngân sách/sở thích/điều kiện bắt buộc. URL khác tuyến hoặc thiếu dữ liệu thì hỏi phạm vi tìm; chỉ làm rõ phần cần để truy vấn. URL đọc lỗi vẫn giữ input và cho bổ sung nhu cầu để tìm thêm.


## 3. Kết quả có sẵn đề xuất và bảng so sánh

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Ba tour gợi ý theo nhu cầu                     [Tìm phương án khác]          │
│ Nhật Bản · TP.HCM · nhu cầu đã xác nhận         [Sửa nhu cầu / URL]           │
│                                                                              │
│ 1. Tour A · lý do phù hợp/giới hạn       2. Tour B       3. Tour C            │
│ [Vì sao hệ thống đề xuất?]   [Xem bằng chứng theo từng dữ kiện]              │
│ Tour bạn cung cấp được giữ làm tham chiếu để đối chiếu bên dưới.            │
├──────────────────────┬──────────────────┬──────────────┬────────────┬─────────┤
│ Tiêu chí             │ Tour tham chiếu  │ Gợi ý A      │ Gợi ý B    │ Gợi ý C │
├──────────────────────┼──────────────────┼──────────────┼────────────┼─────────┤
│ Nhà cung cấp         │ Công ty R        │ Công ty A    │ Công ty B  │ Công ty C│
│ Lịch/thời lượng      │ 10/11 · 5N4Đ     │ 10/11 · 5N4Đ │11/11·6N5Đ │12/11·5N4Đ│
│ Giá công bố/người lớn│ 35,9tr           │ 32,8tr       │ 29,9tr     │ 31,2tr  │
│ Bao gồm              │ Xem nguồn        │ Bay/khách sạn│ Bay/4 đêm  │Chưa đủ  │
│ Điều kiện            │ Xem nguồn        │ Phòng đơn    │ 2 điểm mua │Chưa đủ  │
│ Nguồn/quality        │ Theo từng field  │ [3 nguồn]    │ [2 nguồn]  │[1 nguồn]│
├──────────────────────┴──────────────────┴──────────────┴────────────┴─────────┤
│ Trade-off: B có giá công bố thấp hơn A nhưng có điểm mua sắm; C thiếu dữ    │
│ kiện chính sách. Các nhận định mở được nguồn, giữ giới hạn dữ liệu.          │
│ URL chưa đọc được: Tour X [Thử lại nguồn]                                    │
│ [Tìm phương án khác]   [Sửa nhu cầu / URL]   [Mở nhà cung cấp theo tour]      │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hành vi:** BE tự chọn tối đa ba gợi ý và dựng comparison/trade-off; UI hiển thị ngay, không cần checkbox hoặc nút “So sánh các tour đã chọn”. Nhãn/phạm vi/tiêu chí/policy dùng để rank và lý do/giới hạn phải rõ. Không đủ ba tour đủ điều kiện thì hiển thị ít hơn; hard unknown/fail không lấp giả.

**Có URL — đề xuất để review:** Ba là số gợi ý mới, tour URL nằm ngoài số này và vẫn được phân tích/so chung. Không có URL thì bảng chỉ có tối đa ba gợi ý. Một URL + ba gợi ý = bốn tour; nhiều URL giữ reference/lý do của tất cả, bố cục/mobile phải review. Canonical duplicate không lặp thành gợi ý mới; không biến tour URL thành “đạt nhu cầu” nếu không đủ căn cứ.

**Tìm phương án khác:** Giữ nhu cầu/URL, BE trả nhóm mới loại đề xuất đã xem; giữ kết quả trước trong khi chờ. Hết nhóm mới thì nói rõ và cho sửa nhu cầu. Khác “Thử lại nguồn” hoặc “Cập nhật dữ liệu”, có thể vẫn trả tour cũ sau khi làm mới.

**Offer / evidence:** Chỉ rõ offer/context của giá/ngày; đổi đồng bộ snapshot/evidence, không ngầm chọn rẻ nhất. Giá người lớn công bố khác tổng nhóm đủ phụ thu. Thiếu dữ kiện/nguồn lỗi phải có lý do; không hard filter thì không gắn đạt nhu cầu. Chỉ hiển thị phase xử lý thật.

## 4. Panel bằng chứng và rủi ro

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


## Ghi chú thiết kế

- Ba bề mặt: Input, Review, Kết quả/so sánh; Evidence là panel.
- Pool đề xuất tối đa 20 ứng viên chỉ ở backend, chưa benchmark/chốt policy; không render thành danh sách hoặc phân trang để user chọn.
- Tên/giá/ngày/lý do trong mẫu đều minh họa, không dữ liệu thật; không tự dựng DTO hay điểm AI.
- Giữ G1–G10/D1–D5; review mobile, URL count và budget tại FLOW-3/P3. Design tiếp tục song song contract.
