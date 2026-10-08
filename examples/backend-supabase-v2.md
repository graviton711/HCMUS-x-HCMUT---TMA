# Test backend v2 với kho tour Supabase thật

Ngày 08/10/2026: reader đã đọc được 1 provider, 234 tours và 2.373 offers. Đây là dữ liệu crawler trong Supabase. Session/requirement/proposal/job/comparison vẫn ở `data/backend.db`; backend không ghi vào ba bảng catalog.

## 1. Khởi động

Dừng server cũ bằng **Ctrl+C** trước; Windows có thể khóa file CLI khi server còn chạy. Trong PowerShell ở repo root:

```powershell
Remove-Item Env:DATA_PROVIDER -ErrorAction SilentlyContinue
uv sync
uv run tour-backend probe-supabase
uv run tour-backend serve
```

`.env` dùng `DATA_PROVIDER=supabase`, `SUPABASE_TOUR_DB_URL` giữ connection string hiện có. Biến môi trường PowerShell được ưu tiên hơn `.env`, vì vậy cần gỡ override fixture/http cũ. Không thay `DATABASE_URL` thành PostgreSQL: đó là application store SQLite.

Probe phải trả `status=ok`, `transaction_read_only=on` và counts. Mở `/health`: cần thấy `data_provider=supabase`. Mở [Swagger](http://127.0.0.1:8000/docs) và reload để nhận schema mới. Provider này dùng nhóm **v2**, không dùng ví dụ v1/URL `.invalid`.

`SUPABASE_TOUR_URL`/publishable key được nhận nhưng reader hiện dùng PostgreSQL URL. Các bảng hiện có RLS và chưa có policy cho publishable role; backend không tự sửa RLS. `CRAWLER_URL`/`CRAWLER_REGISTRY_PATH` dành cho mode http, không cần gọi crawler để đọc dữ liệu đã có.

## 2. Session

Execute `POST /v2/sessions`, lấy riêng `data.token`. Bấm **Authorize**, điền token vào **SessionBearer**; không thêm chữ Bearer. Giữ session này cho toàn bộ flow. Không dùng token session trong AdminBearer.

## 3. Test nhu cầu bằng text

Ở `POST /v2/requirements`, thay **Edit Value/request body** bằng:

```json
{
  "input": {
    "kind": "text",
    "text": "Tôi muốn tìm tour Nhật Bản khởi hành từ Hồ Chí Minh ngày 03/11/2026, đi 1 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour."
  },
  "timezone": "Asia/Ho_Chi_Minh"
}
```

Response 202 trả `requirement_id`, `proposal_id`, `job_id`. Điền `job_id` vào `GET /v2/jobs/{jid}` và Execute lại đến `succeeded` hoặc `failed`. Nếu failed, đọc `data.error`; không confirm bản chưa parse.

`GET /v2/proposals/{pid}` bằng proposal_id. Trong `data.preview`, kỳ vọng có destination Nhật, origin TP.HCM, ngày đi 2026-11-03, budget lte 30.000.000 VND/per_adult/tour_price; `party.adults=1`. Ngày chỉ một condition. Đọc `clarifications`, `issues`, `readiness`; nếu model còn hiểu thiếu/sai, sửa qua proposal trước xác nhận. Ca smoke đúng không chứng minh mọi câu đều đúng.

Ở `POST /v2/proposals/{pid}/confirm`, dùng ID proposal thật và body:

```json
{
  "expected_revision": 0,
  "expected_proposal_version": 2
}
```

**Lấy hai số từ `data.base_revision` và `data.version` của proposal vừa GET**, không mặc định 0/2 sau các lần sửa. Confirm trả requirement có `data.id`, `data.revision`; bước này mới lưu revision đã xác nhận.

## 4. Chạy comparison

`POST /v2/comparisons`, body chỉ cần:

```json
{
  "requirement_id": "ID_requirement_vừa_confirm",
  "revision": 1
}
```

Thay ID/revision bằng `data.id`/`data.revision` thật; không dán cả envelope response. Lần đầu bỏ offer_selections/reuse_comparison_id. Response 202 là queued: lấy job_id để poll, sau succeeded lấy comparison_id cho `GET /v2/comparisons/{cid}`.

Kết quả nằm ở **`data.result`**:

| Phần | Cách đọc |
|---|---|
| `origin` | `source` là catalog thật |
| `columns` | Tour và `offer_options` cho các lịch khởi hành |
| `cells`, row `published_price` | Giá công bố; `kind=from` là giá từ, basis/coverage chưa xác nhận |
| `evaluations` | `unknown` khi thiếu bằng chứng/freshness; không kết luận đạt budget |
| `recommendations.items`, `empty_reason` | Có thể rỗng dù có tour để tham khảo; ONLY_UNVERIFIED khi chưa chứng minh được điều kiện |
| `source_coverage`, `warnings` | Partial, unresolved places, dữ liệu thiếu proof, truncation |

Với kho hiện tại, smoke text sau sửa trả 20 tour, 20 preview giá, evaluations unknown và không có recommendation cá nhân hóa. SQL ưu tiên địa danh match nhưng không loại hàng chưa kiểm chứng như hard fail. Do vậy cột tham khảo có thể chưa khớp tất cả nhu cầu; đọc evaluations trước quyết định.

## 5. Test URL và hybrid

Trong Supabase Table Editor → `tours`, copy **toàn bộ giá trị cột url** của 1–2 tour. Không copy URL trang dashboard Supabase. `POST /v2/requirements`:

```json
{
  "input": {"kind": "urls"},
  "reference_urls": ["URL_tour_thật_đã_có_trong_bảng_tours"],
  "timezone": "Asia/Ho_Chi_Minh"
}
```

URL-only không cần NIM: GET proposal → confirm theo version thật → comparison như trên. Có thể dùng 1–5 URL. Recommendations ở mode này là tour tương tự để xem, không kết luận phù hợp nhu cầu cá nhân chưa nhập.

Hybrid: dùng input text của bước 3 và thêm `reference_urls` với các URL thật. Structured form đủ core/rõ nghĩa tạo revision 1 trực tiếp; thiếu/chưa rõ trả draft/proposal201. Payload ở [walkthrough v2](backend-v2.md), [quy tắc core](backend-personalized-v2.md). URL vắng trong catalog trả `CATALOG_URL_NOT_FOUND`; domain chưa có provider được phép trả source unsupported. Không có fallback mock/live crawl.

## 6. Bằng chứng và các lỗi thường gặp

Lấy một evidence_id trong cell → `GET /v2/evidence/{eid}`. `method=database_record` có `record_ref` gồm bảng/record_key/field/content_hash. Raw quote là giá trị trong DB; `deep_link.method=page` chỉ mở trang nguồn, không cam kết highlight quote website. Field website proof hợp lệ mới được đánh dấu supplier_published.

- 401: token/session hết hạn hoặc điền sai authorization; tạo session mới thì phải tạo lại flow trong session mới.
- 404: sai ID hoặc khác session; không dùng ID mẫu Swagger.
- 409: revision/proposal version đã đổi; GET lại trước khi gửi.
- SUPABASE_SCHEMA_MISMATCH/PERMISSION_DENIED/UNAVAILABLE: đọc thông báo probe, kiểm tra connection/quyền/schema. Không tự đổi RLS để sửa backend.
- Unknown/stale offer không được nâng thành usable bằng cách chọn lại; cần freshness policy có căn cứ và field evidence. App vẫn cho xem raw offer options/giá.

## Việc team cần bổ sung tiếp

Crawler: field proofs theo [CatalogFieldProof](../src/data_access/supabase/README.md), price kind/basis/coverage/age brackets, scope transport, cadence từng field. Hiện chỉ có một provider và mọi origin là TP.HCM; ca Hải Phòng chưa có dữ liệu phù hợp để chứng minh.

Frontend: nối API v2, hiển thị from-price/raw provenance/unknown/partial/truncation, proposal confirm và job polling. Prototype hiện vẫn dùng dữ liệu mẫu; thay DATA_PROVIDER chỉ chuyển nguồn backend.
# Policy dữ liệu hiện hành

[catalog-validation-v1](../docs/catalog-validation-policy.md) cho phép field đã kiểm tra thuộc nguồn opt-in tham gia lọc, không cần proof từng field. [Cấu hình](backend-catalog-validation.md) và [nghiệm thu](../docs/archive/backend-catalog-validation-verification.md). Các ví dụ/baseline `unverified` bên dưới áp dụng cho nguồn chưa opt-in hoặc field thiếu nghĩa dữ liệu, không là trạng thái mặc định của mọi field catalog.
