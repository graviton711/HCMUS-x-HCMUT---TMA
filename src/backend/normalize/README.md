# backend/normalize — rows catalog thành ngôn ngữ chung

## Trách nhiệm

Đổi rows catalog thô (dicts fixture hoặc rows Supabase) thành `TourSnapshot` theo [data-contract](../../../docs/data-contract.md). Hàm thuần, không I/O, không LLM.

## Input/output

Vào: `TourRow` (fields tour + offers + evidence + `field_meta` + timestamps). Ra: `TourSnapshot` với từng `OfferSnapshot`; giá trị không parse được thành `None`/`unknown` nhưng giữ evidence, không bịa.

## Workflow

Map fields vô hướng (enums transport/accommodation, durations, destinations) → tách offers (mỗi offer một ngày/giá/availability; giá "from" gắn cờ `price_type="from"`, không tính là exact) → gắn evidence từng snapshot → giữ `observed_at` (giờ VN) và verification.

## Interface với module khác

`decide` gọi sau khi `data` trả rows. Chỉ phụ thuộc `models.py`. Không chạm network hay database.

## Quyết định kỹ thuật

- Cơ học như `src/ingest`: không branch theo nguồn, không heuristic.
- Một offer = một ngày khởi hành + một basis giá. Gộp cross-offer là bug, không phải tối ưu.
