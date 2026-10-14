# features/chat

Chat UI và các thành phần của decision workspace. Page layer sở hữu API orchestration/session state; feature render dữ liệu đã validate, không tự quyết eligibility.

- **Input/output:** `ChatMsg`, Decision Brief draft/review state, thread, composer, tool progress, quick replies, tour cards, comparison controls, saved tours.
- **Workflow:** Chat draft hiển thị trong thread nhưng chưa query catalog. Người dùng sửa hard/soft conditions, phân bổ 100 điểm và xác nhận. Decision run gửi requirement qua `/agent/sessions/{id}/decisions`; result message chứa ba decision views. Reload khôi phục draft, trọng số và kết quả từ local session state.
- **Views:** Cheapest (exact price theo currency), Best fit (tổng weight của soft pass), Balanced (Pareto alternatives). Mỗi view nêu số candidates scanned, hiển thị tối đa năm tour, evidence và unknown riêng.
- **Compatibility:** Giữ `ranked`/`near_miss` cho consumers hiện tại; `decision_views=[]` hợp lệ với dữ liệu comparison cũ. Saved tours và suggestions hiện có tiếp tục hoạt động như công cụ phụ trợ.
- **Interaction:** Sửa giá trị trong brief cập nhật quote và ngữ cảnh đã review; tổng trọng số khác 100 khóa nút chạy; “Chia đều” phân phối remainder xác định. Hard conditions không bị trọng số ảnh hưởng. Kết quả không tuyên bố “rẻ nhất” xuyên currency hoặc từ giá `from`.
- **Visual:** Dùng shared tokens trong light/dark mode, semantic status và progressive disclosure. Workspace ưu tiên lựa chọn/đánh đổi/evidence thay vì bubble chat đơn; responsive và dùng được bàn phím.
