# backend/normalize — rows catalog thành ngôn ngữ chung

## Trách nhiệm

Đổi rows catalog thô (dicts fixture hoặc rows Supabase) thành `TourSnapshot` theo [data-contract](../../../docs/data-contract.md). Hàm thuần, không I/O, không LLM.

## Input/output

Vào: `TourRow` (fields tour + offers + evidence + `field_meta` + timestamps). Ra: `TourSnapshot` với từng `OfferSnapshot`; giá trị không parse được thành `None`/`unknown` nhưng giữ evidence, không bịa.

## Workflow

Map fields vô hướng (enums transport/accommodation, durations, destinations) → loại endpoint xuất phát chỉ khi nhãn trùng sau chuẩn hóa chữ tổng quát → tách offers (mỗi offer một ngày/giá/availability; giá "from" gắn cờ `price_type="from"`, không tính là exact) → ánh xạ giá và loại giá từ cột catalog → gắn evidence và freshness cho ngày khởi hành. Không tạo alias địa danh, country code hay completeness metadata. Metadata giá cấu trúc được giữ như thông tin phụ; không xác minh domain, không ràng buộc quote với raw fields và không ghi đè giá catalog.

## Interface với module khác

`decide` gọi sau khi `data` trả rows. Chỉ phụ thuộc `models.py`. Không chạm network hay database.

## Quyết định kỹ thuật

- Cơ học như `src/ingest`: không branch theo nguồn, không heuristic.
- Một offer = một ngày khởi hành + một basis giá. Gộp cross-offer là bug, không phải tối ưu.
- Giá ngân sách lấy từ `offers.price`, `tours.price_type` và currency; tuổi giá không chặn eligibility.
- `observed_at` là bằng chứng thời điểm ghi nhận. Freshness TTL chỉ áp dụng cho ngày khởi hành.
- Chuẩn hóa chữ chỉ phục vụ so khớp cùng một nhãn; ánh xạ quốc gia/vùng sang destination catalog thuộc agent.
