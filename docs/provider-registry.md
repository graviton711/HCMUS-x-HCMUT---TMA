# Danh mục nhà cung cấp

**Trạng thái:** Đặc tả kết quả khảo sát nguồn trong Git. Config crawler hiện ở `configs/profiles/*.yaml`; capability runtime backend dùng [SourceCapability](../src/data_access/crawler-contract.md). Chưa có mapping đầy đủ profile → capability/approval/TTL; không tạo lại `data/providers.toml` thành nguồn chuẩn song song.

## Mục đích

Registry ghi kết quả khảo sát khả năng lấy dữ liệu theo từng nhà cung cấp. Đây là danh sách nguồn đã kiểm tra, không phải danh sách đã có crawler adapter production. `reviewed_at` cho biết lần kiểm tra gần nhất; khi dữ liệu/robots thay đổi phải kiểm tra lại trước khi crawl.

Profiles `vietravel` và `dulichviet` có flow/alias/anchor nhưng không chứa đầy đủ access_status/checked_at/freshness_seconds của BE. Có profile không đồng nghĩa approved; phần survey artifacts đang ignore cũng không thay hồ sơ nguồn/fixture đã review trong repo.

## Trường dữ liệu

| Trường | Ý nghĩa |
|---|---|
| `id`, `name`, `homepage` | Định danh ổn định, tên hiển thị và trang gốc. |
| `status` | `candidate`: có dữ liệu cấu trúc hữu ích; `limited`: chỉ có một phần; `excluded`: hiện chưa có đường lấy dữ liệu sạch, được phép. |
| `reviewed_at`, `robots_url`, `sample_tour_urls` | Thời điểm, chính sách truy cập và URL đã dùng để kiểm tra. |
| `structured_formats`, `schema_types` | Định dạng/schema quan sát được trên trang đã kiểm tra. |
| `available_fields`, `missing_fields` | Field đọc được/không thấy trong structured data tại mẫu; không đảm bảo bao phủ mọi tour. |
| `blocked_paths`, `notes`, `next_step` | Endpoint/luồng không được gọi, giới hạn và hành động tiếp theo. |

## Quy tắc cập nhật

1. Kiểm tra robots và điều khoản nguồn trước khi thử endpoint; ghi rõ endpoint bị chặn, tuyệt đối không gọi để “xác minh”.
2. Ghi URL bằng chứng cụ thể, ngày kiểm tra, field quan sát được và giới hạn của mẫu.
3. Chỉ đặt `candidate` khi trang mẫu có structured data hữu ích; adapter và field validation vẫn cần test riêng trước khi dùng kết quả ra quyết định.
4. Nếu cấu trúc thay đổi hoặc dữ liệu không sạch, cập nhật status/`reviewed_at`; không giữ trạng thái cũ như cam kết crawlability.
