# Owner-scoped conversation history

Refs hỗ trợ cả requirement_id top-level của queued payload và result.requirement_id của comparison/what-if hoàn thành; owner luôn được kiểm tra trước refs.

Trách nhiệm: list/detail/transcript, title/pinned/version và archive, nhập guest vào account. Input verified owner + pagination/CAS; output refs và transcript bounded. Không đưa toàn bộ snapshot hoặc credentials vào index.

SQL truy vấn theo owner/resource kind, cursor created_at/ID; detail kiểm owner trước khi truy vấn child refs. Metadata additive, default version0 khi chưa có; mutations dùng Store transaction và CAS. Archive chỉ ẩn index; không làm mất evidence hoặc sửa job.

Account owner stable giữa thiết bị sau provider verification. Guest giữ owner session hiện tại; link explicit chuyển tất cả owner-bearing application rows, revoke guest token và reject queued/running jobs. [Contract](../../../docs/account-history-what-if-integration.md).
