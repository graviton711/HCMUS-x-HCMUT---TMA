# Kết quả và activity

- Trách nhiệm: hiển thị snapshot so sánh và events thật của backend, độc lập code prototype. Không tự tìm, xếp hạng, tính giá hoặc tạo nhận định.
- Input: `Comparison | null`, `busy`, callbacks chọn offer/mở evidence; activity nhận `Job | null`, `JobEvent[]`, callback hủy.
- Output: tối đa ba cards theo `recommendations.candidate_ids`; mọi cột backend (tham chiếu/thiếu dữ kiện vẫn giữ), bảng theo `rows.order`, tab phân tích và nhật ký.
- Workflow: form/chat do workspace quản lý → backend comparison → render nguyên snapshot. Đổi offer chỉ gọi workspace để tạo comparison mới; control giữ offer của snapshot đang xem khi chờ. Evidence theo từng ô/phép tính/đánh giá gọi modal của workspace.
- Dữ kiện: phân biệt data state, độ đầy đủ, xác minh và freshness; không dùng timestamp để tự suy ra mới/xác minh. Giá giữ currency, kind, basis, coverage, nhóm tuổi và điều kiện áp dụng do backend cấp.
- Card: làm nổi bật quote `per_adult` đầu tiên theo thứ tự nguồn; nếu không có thì dùng quote đầu tiên với basis thật. Các quote khác nằm trong phần mở rộng chữ nhỏ, không bị bỏ; bảng luôn giữ toàn bộ giá. Không chọn giá thấp nhất hoặc tự tính giá nhóm.
- Phân tích: chỉ claims, metrics (operands/result/limitations), semantic assessments và ranking contributions từ backend. Không tạo trade-off khi backend chưa có claim tương ứng. Unknown/blocked hiển thị rõ.
- Accessibility: tabs hỗ trợ mũi tên/Home/End; bảng semantic, cuộn ngang và cột tiêu chí/header sticky; evidence button có tên tiêu chí và tour; trạng thái có chữ. Nhãn UI Việt/Anh, giữ nguyên nội dung nguồn.
- Bố cục bảng: `minWidth = 168 + số cột tour × 230` px, tính từ metadata đã nhận; giữ cột đọc được khi có tối đa 5 URL tham chiếu + 3 gợi ý (8 cột). Bảng cuộn riêng, không làm tràn trang.
- Trạng thái: chưa tìm, đang chờ, kết quả rỗng/một phần, lỗi/hủy; workspace giữ snapshot cũ khi lần tìm mới chưa xong. Không fixture runtime, tour photo suy đoán hay thanh progress giả.
