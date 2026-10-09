# Crawler bổ sung giá có thể đánh giá

Backend chỉ đọc Supabase. JSON dưới đây là **ví dụ tổng hợp**, không copy giá/complete vào tour thật khi chưa xác nhận nội dung nguồn. Cột `offers.field_meta` JSONB hiện có nhận object `pricing`; metadata quan sát cùng thời điểm với offer. `evidence` hiện có được giữ nguyên.

```json
{
  "pricing": {
    "observed_at": "2026-10-09T14:00:00Z",
    "quotes": [
      {
        "quote_id": "adult",
        "kind": "from",
        "amount": 10000000,
        "currency": "VND",
        "basis": "per_adult",
        "coverage": "tour_price",
        "applicability": []
      }
    ],
    "extra_charges": [],
    "complete": false
  }
}
```

- `amount` khớp `offers.price_by_age.adult/child/infant` theo basis; currency/kind khớp tour tương ứng. Metadata không được tự đổi giá from thành exact. `quote_id` là nhãn trong input; backend tạo ID gắn snapshot.
- `coverage`: phần tiền được báo giá (`tour_price` hoặc `trip_total`), do crawler xác nhận từ nội dung. `applicability` giữ điều kiện nhóm/phòng nếu có; không thêm giả định.
- `extra_charges` phải được khai báo rõ (schema ExtraCharge), gồm amount/currency/basis/required/applicability. Mảng rỗng không tự chứng minh không có phụ thu.
- `complete=true` là assertion của nguồn rằng các khoản bắt buộc/điều chỉnh ảnh hưởng phép tính đã được biểu diễn đầy đủ. Chỉ đặt true khi crawler có đủ nội dung để xác nhận; chưa đủ giữ false. Tuổi trẻ em/infant cần age_min/age_max_exclusive nếu dùng tính tổng.
- Nguồn phải được cấu hình opt-in và approved. Metadata sai, timestamp lệch, amount/kind/currency mâu thuẫn hoặc nguồn không được tin → không hard pass. Có metadata vẫn cần TTL price còn mới.
- Giá from 10 triệu dưới trần 30 triệu vẫn unknown vì không biết giá tối đa; from 40 triệu có thể fail trần 30 triệu khi các prerequisites đầy đủ. Exact có thể pass khi đủ scope/terms/freshness; không dùng exact cho trang chỉ ghi “từ”.

User chốt cadence dự kiến 1 ngày: local `.env` đã cấu hình `SUPABASE_TOUR_FRESHNESS_SECONDS={"departure_date":86400,"price":86400}`. Đây là thời hạn chấp nhận dữ liệu, **không phải lịch tự động crawl**. Dữ liệu cũ cần crawler đọc lại trang và cập nhật observed_at khi thực sự quan sát lại; không sửa timestamp để né stale.
