# shared — tiện ích dùng chung cho crawl và backend

## Trách nhiệm

Chứa helper hạ tầng mọi tầng đều cần (hiện tại: logging), không chứa logic
nghiệp vụ nào của crawl hay domain tour. Backend import trực tiếp
từ đây; cấm import ngược vào `ingest` hay module nghiệp vụ khác.

## Quy tắc thêm mới

- Chỉ nhận code cross-cutting thật sự (dùng ở ≥2 tầng).
- Không dependency nặng, stdlib là đủ thì dùng stdlib.
- Secret không bao giờ vào log (xem `redact` trong `logging`).

## Logging

`get_logger()` writes to `stderr` for local terminals and hosted log collectors. Locally it defaults to `.local/logs/backend.log`; `LOG_FILE` can override the path or be set to an empty value to disable the file sink. File logs use UTF-8 rotation (10 MiB per file, five backups). Render is detected through its `RENDER=true` environment variable, so it uses the Dashboard stream without creating container log files.

Request context adds a correlation ID to each record. Logs may include operation names, safe error codes, process exit status, logical tool names/status, and whether a validated decision draft was returned. Never log prompts, chat text, tool inputs/results, credentials, environment variables, or exception messages.
