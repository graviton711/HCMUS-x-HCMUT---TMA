# Kiểm chứng frontend

- `Results.test.tsx`: giá giữ kind/basis/coverage/điều kiện; dữ kiện mâu thuẫn không là giá trị hợp lệ; quality không suy từ timestamp; chặn nguồn synthetic; giữ tham chiếu lỗi; dùng kết quả phép tính BE; nhật ký đúng job/seq.
- `Workspace.test.tsx`: hook thật với transport chỉ mock trong test. Kiểm tra chuyển phiên/request cũ, giữ bảng cũ khi tìm lỗi, resume tin nhắn/job, bảo toàn draft chưa gửi, version khi xác nhận và hủy.
- `storage.test.ts`: history theo owner không đọc nhầm lịch sử anonymous/owner khác; restore loại draft hỏng ở dữ liệu lồng nhau; bearer nằm ngoài history/export; access hết hạn bị từ chối; tìm nhiều từ có dấu và Đ/đ. Chỉ dùng browser storage của test, không dữ liệu hay token người dùng.
- API/form tests: serialization, contract và idempotency; integration harness gọi backend source thật khi dependencies sẵn sàng.
- Fixtures/mock chỉ nằm trong test, không import vào runtime/build. Dùng deferred promise để kiểm tra race thay vì timeout dài hoặc simulate trong sản phẩm.
- Chạy `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`; browser integration kiểm tra luồng thật và responsive sau các kiểm tra module.

## Browser integration

`e2e.spec.ts` dùng Playwright + Chrome headless, frontend 127.0.0.1:5173 và backend 127.0.0.1:8000 đã chạy riêng. Không inject mock vào app; tạo nhu cầu structured/proposal/confirm và contact thật qua UI. Backend fixture chỉ kiểm gate: không POST comparison hoặc hiển thị tour synthetic. Không gọi NIM/email. Các record kiểm thử có nội dung E2E.

Kiểm 1440/390/320px, không overflow toàn trang; VI/EN + theme persistence, auth khi chưa adapter, phiên ẩn danh/draft/switch/reload, xác nhận/sửa nhu cầu và gửi ticket. Ảnh/report ở `artifacts/frontend/` (Git ignore). Chạy `npm run test:e2e`; biến `E2E_BASE_URL`/`PLAYWRIGHT_CHROME_PATH` cho host khác. Test chỉ dùng state/query đã có, không tạo dữ liệu tour để lấp backend.

Control hiển thị: dropdown ngôn ngữ và nút theme độc lập; browser kiểm đổi ngôn ngữ không đổi theme, đổi theme không đổi ngôn ngữ, Escape/focus/đóng ngoài, persistence và bố cục header/dropdown ở 1440/1280/390/320px.

Một test layout kết quả dùng response actual từ `api/verify_backend.py`, sao chép trong test và đổi origin source để render contract; thêm năm cột URL chưa đọc được để kiểm giới hạn tám cột. Transport bị intercept chỉ trong Playwright; không có fixture/mock trong runtime/build. Ảnh `comparison-contract-test-*` là **dữ liệu kiểm thử**, không bằng chứng nguồn live. Gate production synthetic được kiểm riêng bằng backend thật. Test layout kiểm bảng cuộn riêng, facts/AI/evidence drawer trên 1440/1280/390/320px.


## Account/history/what-if (09/10)

- `auth.test.ts`: rotation single-flight, 401 refresh retry giữ mutation key, account switch, PKCE one-shot/state/corrupt storage và clear expiry.
- `WhatIf.test.tsx`: ratio với unknown phải null, cohort/ID/witness binding; không mở unsafe URL. Fixture ở tests/fixtures, không runtime.
- Workspace test account hydrate không tạo guest; analysis/apply chỉ review, chưa confirm/search. Runtime contract capture thêm hard-group what-if/ratio và proposal actual của backend.
- `SearchResults.test.tsx`: sự kiện started đã lưu không là trạng thái đang chạy; blockers đếm tour duy nhất và ưu tiên per-offer; diagnostics giới hạn retrieval/AI skipped được dịch VI/EN. Browser layout contract thêm scope retrieval test để kiểm panel tại 1440/1280/390/320px.
- `tests/test_auth_history.py`: provider HTTP stub + app/SQLite thật cho account ownership, signup confirmation, bad claims/redirect/provider flags, refresh/logout, history pagination/CAS/archive/link/transcript/purge.

Browser harness repo root (memory DB, fixture, FakeNim; **không dùng .env thật hoặc Supabase real account**):

```powershell
uv run python tests/frontend_server.py --port 18000
```

Terminal frontend: `$env:BACKEND_URL='http://127.0.0.1:18000'; pnpm --dir src/frontend dev --port 15173`. Terminal test: `$env:E2E_BASE_URL='http://127.0.0.1:15173'; pnpm --dir src/frontend test:e2e --grep-invert 'hosted identity'`.

Account harness riêng: `uv run python tests/frontend_server.py --port 18001 --auth`; FE `$env:BACKEND_URL='http://127.0.0.1:18001'; pnpm --dir src/frontend dev --port 15174`; test `$env:E2E_BASE_URL='http://127.0.0.1:15174'; $env:E2E_AUTH_STUB='1'; pnpm --dir src/frontend test:e2e --grep 'hosted identity'`. Credentials test-only: browser@example.test / test-password. Không dùng credentials này với Supabase thật.

Account browser kiểm xác nhận email chưa login, login, hydrate ở context sạch khác, rename/profile và archive đồng bộ. What-if browser lấy hard comparison/analysis/proposal actual từ isolated backend capture, intercept test-only và đổi origin trên bản test để qua gate synthetic; xác nhận không POST confirm/search. Screenshot `what-if-contract-test-*`, `account-auth-stub-*` là bằng chứng UI/test, không chứng minh nguồn tour/Google/email live.

Ảnh riêng panel what-if tạm ẩn header/toolbar/skip link chỉ trong lúc chụp để các phần sticky không che nội dung ảnh dài; kiểm overflow và tương tác vẫn dùng giao diện đầy đủ.
