# backend/normalize — rows catalog thành ngôn ngữ chung

## Trách nhiệm

Đổi rows catalog thô (dicts fixture hoặc rows Supabase) thành `TourSnapshot` và typed metric source fields theo [data-contract](../../../docs/data-contract.md). Hàm thuần, không I/O, không LLM.

## Input/output

Vào: `TourRow` (fields tour + offers + evidence + `field_meta` + timestamps). Ra: `TourSnapshot` với từng `OfferSnapshot`, giữ giá/basis theo offer, `price_by_age`, phụ thu và raw source text cần phân tích. Giá trị thiếu/không parse được thành `None`/`unknown` nhưng giữ evidence, không bịa.

## Workflow

Map fields vô hướng (enums transport/accommodation, durations, destinations) → tách offers (mỗi offer một ngày/giá/availability/basis/giá theo tuổi/phụ thu) → giữ riêng raw itinerary, inclusions, exclusions, surcharges, cancellation, child policy và field metadata → gắn evidence/freshness. Không kế thừa `price_type` cấp tour xuống offer và không tạo alias địa danh. Extraction/metric cache nằm ngoài normalizer.

## Interface với module khác

`decide` gọi sau khi `data` trả rows. Chỉ phụ thuộc `models.py`. Không chạm network hay database.

## Quyết định kỹ thuật

- Cơ học như `src/ingest`: không branch theo nguồn, không heuristic.
- Một offer = một ngày khởi hành + basis giá riêng. Gộp cross-offer là bug, không phải tối ưu.
- Giá chỉ dùng `offers.price_type`; thiếu basis là `unknown`, không fallback từ tour.
- Giữ `price_by_age` và từng phụ thu theo nguyên dạng có cấu trúc để code tính tổng nhóm khi có đủ thành phần.
- `exclusions` là nguồn trọng yếu để phát hiện chi phí chưa bao gồm; việc phân loại bắt buộc/tùy chọn/có điều kiện cần evidence và không do normalizer suy diễn.
- `observed_at` là bằng chứng thời điểm crawl. Demo đặt TTL ngày khởi hành là `null`: snapshot có timestamp là bản mới nhất hiện có trong catalog, không phải xác nhận tồn chỗ live. TTL dương bật lại trạng thái stale theo tuổi dữ liệu.
- Chuẩn hóa chữ chỉ phục vụ so khớp cùng một nhãn; ánh xạ quốc gia/vùng sang destination catalog thuộc agent.
