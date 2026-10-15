# backend/normalize — rows catalog thành ngôn ngữ chung

## Trách nhiệm

Đổi rows catalog thô (TourRow mappings hoặc rows Supabase) thành `TourSnapshot` và typed metric source fields theo [data-contract](../../../docs/data-contract.md). Hàm thuần, không I/O, không LLM.

## Input/output

Vào: `TourRow` (fields tour + offers + evidence + `field_meta` + timestamps). Ra: `TourSnapshot` với từng `OfferSnapshot`, giữ giá/basis theo offer, `price_by_age`, phụ thu và raw source text cần phân tích. Giá trị thiếu/không parse được thành `None`/`unknown` nhưng giữ evidence, không bịa.

## Workflow

Map fields vô hướng (enums transport/accommodation, durations, destinations) → tách offers (mỗi offer một ngày/giá/availability/metadata basis/giá theo tuổi/phụ thu) → giữ riêng raw itinerary, inclusions, exclusions, surcharges, cancellation, child policy và field metadata → gắn evidence/freshness. `price_type` được giữ làm metadata nguồn, không quyết định lọc/xếp hạng. Không tạo alias địa danh. Extraction/metric cache nằm ngoài normalizer.

## Interface với module khác

`decide` gọi sau khi `data` trả rows. Chỉ phụ thuộc `models.py`. Không chạm network hay database.

## Quyết định kỹ thuật

- Cơ học như `src/ingest`: không branch theo nguồn, không heuristic.
- Một offer = một ngày khởi hành + basis giá riêng. Gộp cross-offer là bug, không phải tối ưu.
- Giá quyết định dùng `offers.price` và currency; metadata basis không chặn numeric price. Giá thiếu hoặc currency thiếu là unknown.
- Giữ `price_by_age` và từng phụ thu theo nguyên dạng có cấu trúc để code tính tổng nhóm khi có đủ thành phần.
- `exclusions` là nguồn trọng yếu để phát hiện chi phí chưa bao gồm; việc phân loại bắt buộc/tùy chọn/có điều kiện cần evidence và không do normalizer suy diễn.
- `observed_at` là bằng chứng thời điểm crawl, không phải điều kiện so khớp ngày. Ngày khởi hành có trong offer được đối chiếu với khoảng người dùng yêu cầu bất kể timestamp; thiếu ngày là unknown. TTL chỉ ảnh hưởng nhãn freshness hiển thị. Ngày khớp không xác nhận tồn chỗ live.
- Chuẩn hóa chữ chỉ phục vụ so khớp cùng một nhãn; ánh xạ quốc gia/vùng sang destination catalog thuộc agent.
