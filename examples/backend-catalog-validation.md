# Dùng dữ liệu crawler đã kiểm tra

Trong `.env`, opt-in đúng nhà cung cấp nhóm đang crawl:

```dotenv
DATA_PROVIDER=supabase
SUPABASE_TOUR_TRUSTED_DOMAINS=["dulichviet.com.vn","saigontourist.net","travel.com.vn"]
SUPABASE_TOUR_FRESHNESS_SECONDS={}
```

TTL rỗng giữ ngày/giá/availability chưa rõ freshness. Nhóm chốt chu kỳ cập nhật và thời gian chấp nhận dữ liệu cũ rồi mới điền seconds theo departure_date/return_date/price/availability; không dùng một con số tùy tiện để tạo pass.

Ba hostname trên là các nguồn đang có trong catalog nhóm ở lần kiểm tra 08/10/2026, đã cấu hình trong `.env` local. Code default allowlist vẫn `[]`; khi có provider mới cần thêm domain rõ ràng sau khi nhóm nhận nguồn đó. Config không được commit credentials.

Sau khi restart `uv run tour-backend serve`, flow requirement/proposal/confirm/comparison/what-if giữ nguyên. `catalog_validated` là dữ liệu crawler đã kiểm tra theo [policy](../src/data_access/supabase/catalog-validation-policy.md). `supplier_published` vẫn là proof website. Không trạng thái nào khẳng định chất lượng/uy tín độc lập.

Kiểm kho không tạo session hoặc ghi catalog:

```powershell
uv run tour-backend audit-supabase --output data/catalog-validation.local.json
uv run python examples/check-what-if-v2.py --skip-nim
```

Script what-if dùng hai ca structured tương đương, có thông tin Tết bổ sung synthetic được ghi trong artifact; không chứng minh extraction NIM. Static field rõ thuộc nguồn opt-in không còn FIELD_UNVERIFIED. Ngày thiếu TTL, cap giá thiếu coverage, mixed transport/main_journey, ngày về/loại tour thiếu vẫn unknown. Không hứa có tour phù hợp với tuyến Hải Phòng.

Crawler hiện giữ values/link/record_key/observed_at; bổ sung quote có chọn lọc khi debug. Supabase không cần thêm column cho policy này; field_meta chưa được dùng để nhận price qualifiers.
