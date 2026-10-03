# shared — tiện ích dùng chung cho crawl, backend, frontend

## Trách nhiệm

Chứa helper hạ tầng mọi tầng đều cần (hiện tại: logging), không chứa logic
nghiệp vụ nào của crawl hay domain tour. Backend/frontend import trực tiếp
từ đây; cấm import ngược vào `tourcrawl` hay module nghiệp vụ khác.

## Quy tắc thêm mới

- Chỉ nhận code cross-cutting thật sự (dùng ở ≥2 tầng).
- Không dependency nặng, stdlib là đủ thì dùng stdlib.
- Secret không bao giờ vào log (xem `redact` trong `logging`).
