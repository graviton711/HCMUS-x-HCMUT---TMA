# Prototype frontend — Giấy & Mực

HTML/CSS/JS tham khảo giao diện, dùng dữ liệu synthetic. Prototype không kết nối auth, API v2 hoặc crawler thật; frontend React độc lập tại [src/frontend](../../src/frontend/README.md).

## Trách nhiệm và input/output

- Input: fixtures tour/offer/source, [protocol v2 mẫu](../../docs/frontend-protocol-v2.md) và thao tác UI.
- `index.html`: dẫn đến prototype workspace và admin.
- `paper.html`: giới thiệu, auth/account demo, sidebar phiên, form/kết quả/chat. `viewer.html` đổi viewport của cùng prototype.
- `admin.html`: Tổng quan/Nguồn/Liên hệ/Phiên. `source.html`: section nguồn mẫu theo tour/offer/field.
- Output: trạng thái/DOM/local demo history; không tạo tài khoản, ticket hoặc job server thật.

## Chạy

Từ repo root:

```powershell
python -m http.server 4173 --bind 127.0.0.1 --directory prototypes/frontend-design
```

Mở `http://127.0.0.1:4173/`. `paper.html#auth` mở đăng nhập; `paper.html?auth=register#auth` mở đăng ký. Tài khoản mẫu và Google chooser chỉ mô phỏng identity; đăng nhập demo không kiểm tra mật khẩu thật.

## Workflow

1. Vào tài khoản mẫu hoặc auth demo, chọn phiên hoặc tạo lượt tìm mới.
2. Nhập form/URLs/notes/chat; direct edit/slider/chat dùng chung proposal, review diff rồi confirm; Tìm kiếm là thao tác riêng.
3. Xem cards/bảng/phân tích/evidence/offer theo fixtures; giữ snapshot cũ và draft khi đổi phiên/lượt.
4. Sidebar hỗ trợ tìm, ghim, đổi tên/xóa và drawer mobile. Account demo có profile/link/export/delete local theo identity mẫu.
5. VIE/ENG và sáng/tối dùng chung trên các trang, giữ qua reload/đổi trang và độc lập account/history.

## Interfaces và lưu trữ

- Vanilla JS/CSS; Newsreader + Be Vietnam Pro và local assets/license tại [assets/SOURCES.md](assets/SOURCES.md).
- `workspace.js`/`workspace.css`: auth/account/sidebar/run history. localStorage versioned lưu profile/phiên theo ID; sessionStorage chỉ giữ ID login demo. Không lưu mật khẩu, token hoặc OAuth secret; email `.example` không có quyền truy cập thư.
- `presentation.js`/`locales-en.js`/`presentation.css`: preferences, UI copy và dark roles; giữ nguyên user text, quotes và draft/job state.
- `journey.js`: capture/restore/blank/pause và change/run lifecycle. Tách committed criteria, draft/proposal, snapshots và request/câu hỏi đang dở; restore text/DOM/evidence refs, không HTML từ storage.
- `tour-data.js`: fixture dùng chung với source; `demo-store.js`: counters/source/contact trong tab admin, độc lập workspace history.
- Rời prototype tạm dừng timer demo. Runtime React tiếp tục đọc job/message backend; không dùng timer/fixture prototype.

Kiểm tra asset/font, responsive, bàn phím và form/chat/evidence bằng dữ liệu demo. Báo cáo/ảnh kiểm chứng chỉ giữ local tại `review/` (ignored), không là dependency của prototype hoặc frontend React.
