# Workspace

Trách nhiệm: orchestrate form/criteria, proposal/chat, search jobs và snapshots từ API v2; không tự parse ngôn ngữ, rank, tính giá hoặc sinh activity.

Input: catalog API, draft người dùng, requirement/proposal/comparison/job/evidence từ client. Output: form review → structured commit hoặc text/URL proposal → confirm → explicit search; edits/chat merge vào proposal thật; next group/offer tạo comparison mới.

Local history lưu IDs, draft, messages đã nhận và metadata của lượt tìm; bearer chỉ sessionStorage. Refresh lấy lại resource qua API, không xem local IDs là access. State theo từng phiên; AbortSignal và guard ngăn response trễ ghi đè, job không bị cancel khi đổi màn. Poll job/events theo thứ tự, drain events terminal; cancel job có thao tác riêng. Kết quả cũ giữ khi criteria khác/pending/failure, không tự gắn vào revision mới.

Form lấy canonical options/sliders từ catalog; URL/text không ép các field structured. Sửa giữ condition IDs và cây BE; diff có version, confirm/cancel/discard atomic. 409 giữ draft và cho đọc lại BE. Transcript chỉ hiển thị response BE; source quotes không dịch.

Field bị khóa khi mutation chạy để response không ghi đè input mới. Proposal có local edits chưa gửi thì phải Review trước confirm/discard/clarify; Hủy tất cả là thao tác explicit bỏ cả local draft. URL-only vẫn sửa URLs/notes/partial fields mà không ép destination/budget/party. Initial text/URL notes merge vào pending proposal bằng set_notes, vẫn chờ user confirm. History local được scope theo identity khi adapter được cấu hình; không tự gán owner V2 sang user.

Interfaces: `useWorkspace` quản lý resources; `CriteriaForm` thu input và review; `Results` render DTO immutable; shell quản lý route/phiên; API client sở hữu HTTP và errors. Các điểm BE thiếu ở ../../BACKEND-GAPS.md.
