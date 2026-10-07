# Prototype frontend — Giấy & Mực

**Trạng thái:** PLANNING. User đã duyệt prototype hiện tại và ví dụ giao thức ngày 07/10/2026. Chỉ HTML/CSS/JS thử nghiệm và dữ liệu synthetic; chưa frontend production, backend v2 hoặc crawler thật. GitHub Pages chưa bật và không thuộc lượt bàn giao này.

## Trách nhiệm / input / output

- Input: flow đã duyệt, [giao thức FE–BE v2 mẫu](../../docs/frontend-protocol-v2.md), [pipeline/backend/crawler](../../docs/backend-pipeline-v2.md) và [JSON exchanges](../../examples/protocol-v2/README.md).
- Output: `paper.html` gồm Giới thiệu → form/xác nhận → kết quả/chat/analysis; `admin.html` gồm Tổng quan/Nguồn/Liên hệ/Phiên; `source.html` mở đúng đoạn nguồn mẫu. `index.html`/`viewer.html` là lối vào review; `coastal.html` giữ hướng visual lịch sử.
- Sửa nhiều field/slider/chat merge một nháp; xác nhận cả nhóm một lần; hủy khôi phục bản đã xác nhận gần nhất. Xác nhận chưa tự tìm, trừ khi user đã nhắn sửa+kèm tìm. Banner phân biệt pending/matched/stale; matched chỉ nói về bản yêu cầu, không chứng minh tour đạt mọi điều kiện.

## Mở và thử mẫu

Mở `paper.html`, hoặc `paper.html?demo=results` để vào thẳng bảng. Mở `admin.html` cho quản trị. Desktop/mobile trong `viewer.html`; cũng có thể mở bằng Chrome/Edge trực tiếp từ file.

Ưu tiên HTTP cùng origin. Từ repo root:

```powershell
python -m http.server 4173 --bind 127.0.0.1 --directory prototypes/frontend-design
```

1. Sửa nhiều mục hoặc nhắn “đổi ngân sách thành 32 triệu và thời lượng thành 6 ngày”; sửa tiếp/bỏ từng diff/xác nhận/hủy cả nhóm.
2. Tìm kiếm bằng nút/chat; thử loading/chậm/lỗi/hủy tại mục tình huống, giữ bảng cũ và cảnh báo theo bản yêu cầu.
3. Mở evidence/đổi offer rồi bấm “Mở đúng đoạn nguồn mẫu”; giá trị thiếu không có deep link giả.
4. Tạo liên hệ ở `paper.html#contact` rồi mở admin cùng tab để xem ticket, ghi chú nội bộ và cập nhật trạng thái. Thử thêm/sửa/pause/check/refresh nguồn mẫu, lọc và xem phiên.

## Interface và quyết định kỹ thuật

- Vanilla HTML/CSS/JS, không framework/build/API/LLM/ranking/crawl thật. Newsreader + Be Vietnam Pro, ảnh và license/provenance trong [assets/SOURCES.md](assets/SOURCES.md).
- `tour-data.js` chia sẻ fixture giữa bảng và trang nguồn; tour/offer/field quyết định URL anchor local. Miền `.example` không được fetch; ảnh chỉ minh họa điểm đến.
- `demo-store.js` dùng SessionStorage để chia sẻ contact/source state/counters giữa các trang trong một tab. Không lưu token, yêu cầu tour hoặc nội dung chat; contact user nhập chỉ ở tab. Ngày/số liệu admin là mẫu 07/10/2026, không live. Reset chỉ khôi phục dữ liệu demo.
- Điều hướng sang file khác dừng job mô phỏng đang chạy; backend thật có lifecycle riêng theo protocol. Form và bảng vẫn dùng fixture Nhật Bản/TP.HCM tháng 11, không chứng minh truy xuất hoặc xếp hạng đúng nhu cầu mới.
- Dùng đường dẫn asset tương đối để chạy local hoặc dưới project path. Asset runtime hiện có được giữ; ảnh/báo cáo QA mới trong `review/batch/` chỉ local và không thuộc commit bàn giao.

## Kiểm chứng đã có

88/88 browser checks đạt ở 1440/1280/768/390/320px; bulk edit/atomic confirm/cancel, chat/nav, evidence/offer, admin/contact, focused control khi diff dài và reduced-motion; console sạch. Chrome offline dùng asset local; đã thử file local giữ contact → admin cùng tab. Không chạy lại bộ QA trong lượt commit; chưa nghiệm thu API/auth/crawler/hosting thật.
