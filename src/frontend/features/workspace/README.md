# Workspace

Theo [sửa tìm tour](../../../../docs/search-correctness-repair.md), Activity hiển thị sự kiện lịch sử bằng quá khứ; Results nêu blockers bắt buộc, số tour cần xác nhận và giới hạn dữ liệu từ DTO, không tự tạo eligibility. Đếm tour duy nhất cho mỗi field/reason, dùng đánh giá per-offer khi có.

What-if: create/poll/read trên comparison hiện tại, kiểm binding/late-response; apply tạo proposal để review/confirm/search riêng. History account được hydrate từ refs server; anonymous flow giữ nguyên. [Integration contract](../../../../docs/account-history-what-if-integration.md).

Trách nhiệm: orchestrate form/criteria, proposal/chat, search jobs và snapshots từ API v2; không tự parse ngôn ngữ, rank, tính giá hoặc sinh activity.

Input: catalog API, draft người dùng, requirement/proposal/comparison/job/evidence từ client. Output: form review → structured commit hoặc text/URL proposal → confirm → explicit search; edits/chat merge vào proposal thật; next group/offer tạo comparison mới.

Local history lưu IDs, draft, messages đã nhận và metadata của lượt tìm; bearer chỉ sessionStorage. Refresh lấy lại resource qua API, không xem local IDs là access. State theo từng phiên; AbortSignal và guard ngăn response trễ ghi đè, job không bị cancel khi đổi màn. Poll job/events theo thứ tự, drain events terminal; cancel job có thao tác riêng. Kết quả cũ giữ khi criteria khác/pending/failure, không tự gắn vào revision mới.

Form lấy canonical options/sliders từ catalog; URL/text không ép các field structured. Sửa giữ condition IDs và cây BE; diff có version, confirm/cancel/discard atomic. 409 giữ draft và cho đọc lại BE. Transcript chỉ hiển thị response BE; source quotes không dịch.

Field bị khóa khi mutation chạy để response không ghi đè input mới. Proposal có local edits chưa gửi thì phải Review trước confirm/discard/clarify; Hủy tất cả là thao tác explicit bỏ cả local draft. URL-only vẫn sửa URLs/notes/partial fields mà không ép destination/budget/party. Initial text/URL notes merge vào pending proposal bằng set_notes, vẫn chờ user confirm. Account history/hydration theo backend owner đã verify; guest import explicit. what-if chỉ tạo proposal, confirm/search riêng.

Interfaces: `useWorkspace` quản lý resources; `CriteriaForm` thu input và review; `Results` render DTO immutable; shell quản lý route/phiên; API client sở hữu HTTP và errors. Các điểm BE thiếu ở ../../BACKEND-GAPS.md.

## Tháng và khoảng ngân sách

- Lịch đi chọn một hoặc nhiều tháng dương lịch kèm năm, tối đa 12 tháng; tháng rời nhau có nghĩa OR. Mỗi tháng là khoảng ngày đầu/cuối tháng, không gồm các tháng nằm giữa hai lựa chọn. Thời lượng vẫn là ưu tiên `duration_days near` độc lập; chọn Bắt buộc thì dùng số ngày chính xác `eq`, không gửi `near hard`. Nhãn số ngày và control strength được gắn riêng để đọc đúng bằng screen reader.
- Ngân sách có hai đầu kéo và ô nhập chính xác, VND/người lớn/giá tour; khoảng mới được gửi bằng `estimated_cost between hard` để lọc đúng range. Giữ strength đã có khi sửa nhu cầu cũ. Chưa thao tác thì chưa có ngân sách, không ngầm nhận giá mặc định trên slider. Hai đầu không vượt nhau; ô số cho phép nhập giá ngoài thang ban đầu.
- Review ban đầu hiển thị đầy đủ các tháng, hai đầu giá và thời lượng. Lịch/ngân sách khác định dạng control được giữ nguyên khi sửa mục khác; nhóm ngày phức tạp sửa qua chat để bảo toàn cây.
# Recommendation recovery

Giá card/offer picker ưu tiên listed_price_quotes, giữ kind=from và ghi rõ niêm yết/phụ thu chưa xác nhận. Khung yêu cầu phân biệt measure listed/payable. [Contract](../../../../docs/recommendation-recovery-ui.md).
