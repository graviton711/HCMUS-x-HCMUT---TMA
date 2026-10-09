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

Một test layout kết quả dùng response actual từ `api/verify_backend.py`, sao chép trong test và đổi origin source để render contract; thêm năm cột URL chưa đọc được để kiểm giới hạn tám cột. Transport bị intercept chỉ trong Playwright; không có fixture/mock trong runtime/build. Ảnh `comparison-contract-test-*` là **dữ liệu kiểm thử**, không bằng chứng nguồn live. Gate production synthetic được kiểm riêng bằng backend thật. Test layout kiểm bảng cuộn riêng, facts/AI/evidence drawer trên 1440/1280/390/320px.
