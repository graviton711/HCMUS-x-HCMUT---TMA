# Crawler ↔ backend: contract v1 đề xuất

**Mẫu UI mục tiêu 07/10:** [pipeline v2](../api/backend-pipeline-v2.md) và [protocol/evidence](../../docs/frontend-protocol-v2.md) định nghĩa stage/DTO chung URL+retrieval, giá/offer/policies, locator+deep-link/fallback, source registry/admin. Xem [JSON mẫu](../../examples/protocol-v2/README.md). Đây là yêu cầu bổ sung đề xuất; v1 bên dưới vẫn là baseline code, crawler thật chưa đáp ứng.

**Trạng thái:** Backend đã có CrawlRequest/CrawlResult models, JSON Schema, fixture gateway và HTTP gateway. Crawler thật chưa có mẫu và chưa tích hợp. Ví dụ dưới chỉ là dữ liệu mô phỏng.

## Request và capability

`CrawlRequest`: schema_version `1.0`, request_id, mode `discover/compare_urls`, source_ids đã duyệt, QuerySpec, targets, deadline_at. QuerySpec có normalized conditions/party/pushdown plan; không có raw user messages hoặc API key NIM.

- Discover: targets rỗng, source phải có search capability. Nếu nguồn không hỗ trợ một filter, bỏ pushdown filter đó và backend xét lại trên snapshot; không đổi nghĩa/âm thầm bỏ hard condition.
- Compare URLs: targets gồm `{target_id, url}`; chỉ fetch đúng các target, không tìm tour thay thế. QuerySpec có thể rỗng khi chỉ so sánh dữ liệu tĩnh.
- Không tự retry quá deadline. Gateway cần contract này dù crawler gọi qua Python function hay HTTP; chưa bắt buộc thêm dịch vụ riêng.

`SourceCapability`: source_id, supplier_id, approved_domains, access_status, checked_at, modes, searchable_fields, returned_fields, pushdown_semantics và limits. Registry sở hữu mapping URL → source; nguồn chưa duyệt trả `SOURCE_NOT_APPROVED`.

## Envelope trả về

| Field | Nội dung |
|---|---|
| `schema_version`, `request_id` | Phiên bản contract và correlation đúng request |
| `origin` | `source/synthetic`; synthetic không được hiện như dữ liệu thật |
| `source_results` | Source/target id, status `ok/partial/blocked/unsupported/timeout/error`, reason code, snapshot ids và coverage/truncation |
| `suppliers`, `tours`, `offers` | Các records có stable entity id và immutable snapshot id |
| `evidence` | Evidence id, URL, publisher, snapshot ref, extraction method, locator, raw quote/value, observed_at |
| `issues` | Code, source/target/snapshot/field path, explanation, retryable; không thay field thiếu bằng dữ kiện suy đoán |

`TourSnapshot`: snapshot_id, tour_id, supplier_id, canonical_url, observed_at, fields. Fields dùng catalog ở [backend-contracts.md](../domain/backend-contracts.md), dữ liệu tĩnh như destination/origin/duration/hotel/shopping/services/policies.

`OfferSnapshot`: snapshot_id, offer_id, tour_snapshot_id, fields cho departure/return/availability, price_quotes và extra_charges. Offer id chỉ đại diện một tập điều kiện khởi hành/giá áp dụng; giá khác ngày hoặc cấu hình phải tách quote/offer, không overwrite.

## Field và giá

`SourcedField<T>` có `value`, `raw_value`, `data_state`, `verification`, `observed_at`, `evidence_ids`; có thể thêm `unit`, `scope`, `normalization_rule`, `completeness=complete/partial/unknown` (mặc định unknown). Present field cần evidence hợp lệ cùng entity/offer. Missing dùng null + reason; false/0 chỉ khi nguồn thật sự nói false/0. Freshness do backend tính, không do crawler tự gắn nhãn fresh.

Complete itinerary/services/hotel scope phải có căn cứ; lấy được một phần JSON không có nghĩa đã đủ cả lịch trình. Issue cần phân biệt acquisition error với data quality/missing field bằng code/category. Source status partial vì requested fields missing không tự làm comparison job partial; job status do coordinator xét acquisition failures và usable snapshots.

`PriceQuote` được bọc bằng SourcedField: quote_id, kind `exact/from/range`, amount (VND integer, tiền khác decimal string), upper_amount nullable, currency, basis `per_adult/per_child/per_infant/per_room/per_group`, coverage `tour_price/trip_total/unspecified`, age_min/age_max_exclusive nếu có và applicability.

- Applicability gồm party/room/date/service conditions có cấu trúc; qualifier chưa hiểu phải giữ raw và đánh dấu chưa dùng để tính giá. Không coi “từ” là exact hoặc lược bỏ điều kiện áp dụng.
- ExtraCharge cũng có amount, currency, basis, required `true/false/null`, applicability và evidence. Danh sách rỗng không chứng minh không có phụ thu.
- Coverage/completeness muốn xác nhận phải có statement từ nguồn với scope phù hợp; không suy ra complete chỉ vì parser không tìm thấy phụ thu.
- Age brackets dùng `[min, max_exclusive)` để không chồng biên. Thiếu tuổi/rooming hoặc quote không khớp party → cost unknown; không áp giá người lớn cho trẻ.

## Ví dụ response tối thiểu

Ví dụ chỉ có giá người lớn; query có trẻ em sẽ chưa tính đủ tổng giá. Domain `.invalid` không đại diện nhà cung cấp thật.

```json
{
  "schema_version": "1.0",
  "request_id": "crawl_demo_1",
  "origin": "synthetic",
  "source_results": [
    {"source_id": "demo", "target_id": "target_a", "status": "partial", "reason_code": "REQUESTED_FIELDS_MISSING", "tour_snapshot_ids": ["tour_snap_a"], "offer_snapshot_ids": ["offer_snap_a"], "truncated": false}
  ],
  "suppliers": [{"supplier_id": "supplier_demo", "display_name": "Nhà cung cấp mô phỏng"}],
  "tours": [{
    "snapshot_id": "tour_snap_a",
    "tour_id": "tour_a",
    "supplier_id": "supplier_demo",
    "canonical_url": "https://tour-demo.invalid/tour-a",
    "observed_at": "2026-10-01T03:00:00Z",
    "fields": {
      "destinations": {"value": ["country:jp"], "raw_value": "Nhật Bản", "data_state": "present", "verification": "supplier_published", "observed_at": "2026-10-01T03:00:00Z", "evidence_ids": ["ev_route_a"]},
      "departure_origin": {"value": "city:vn:hcmc", "raw_value": "TP.HCM", "data_state": "present", "verification": "supplier_published", "observed_at": "2026-10-01T03:00:00Z", "evidence_ids": ["ev_route_a"]}
    }
  }],
  "offers": [{
    "snapshot_id": "offer_snap_a",
    "offer_id": "offer_a_2026_11_10",
    "tour_snapshot_id": "tour_snap_a",
    "fields": {
      "departure_date": {"value": "2026-11-10", "raw_value": "10/11/2026", "data_state": "present", "verification": "supplier_published", "observed_at": "2026-10-01T03:00:00Z", "evidence_ids": ["ev_price_a"]}
    },
    "price_quotes": [{"value": {"quote_id": "adult_a", "kind": "exact", "amount": 10000000, "upper_amount": null, "currency": "VND", "basis": "per_adult", "coverage": "tour_price", "age_min": null, "age_max_exclusive": null, "applicability": []}, "raw_value": "Giá tour người lớn: 10.000.000 VND", "data_state": "present", "verification": "supplier_published", "observed_at": "2026-10-01T03:00:00Z", "evidence_ids": ["ev_price_a"]}],
    "extra_charges": []
  }],
  "evidence": [
    {"id": "ev_route_a", "snapshot_id": "tour_snap_a", "url": "https://tour-demo.invalid/tour-a", "publisher": "supplier_demo", "method": "synthetic_fixture", "locator": "/itinerary", "raw_quote": "Nhật Bản, khởi hành từ TP.HCM", "observed_at": "2026-10-01T03:00:00Z"},
    {"id": "ev_price_a", "snapshot_id": "offer_snap_a", "url": "https://tour-demo.invalid/tour-a", "publisher": "supplier_demo", "method": "synthetic_fixture", "locator": "/offers/0", "raw_quote": "10/11/2026; giá tour người lớn: 10.000.000 VND", "observed_at": "2026-10-01T03:00:00Z"}
  ],
  "issues": [
    {"code": "CHILD_PRICE_MISSING", "source_id": "demo", "target_id": "target_a", "snapshot_id": "offer_snap_a", "field_path": "price_quotes", "explanation": "Chưa có giá cho trẻ em", "retryable": false},
    {"code": "PRICE_COVERAGE_UNCONFIRMED", "source_id": "demo", "target_id": "target_a", "snapshot_id": "offer_snap_a", "field_path": "extra_charges", "explanation": "Chưa có bằng chứng giá bao gồm mọi phụ thu bắt buộc", "retryable": false}
  ]
}
```

Trong data thật, method chỉ nhận phương pháp đã duyệt như JSON-LD/JSON/API; `synthetic_fixture` chỉ dùng origin synthetic. Crawler gửi được dữ liệu một phần; backend quyết định field/candidate nào đủ để đánh giá.

## Điều backend kiểm tra trước lưu

Version/request id, unique ids, references tồn tại, field types/units, timestamp, source ownership/access, amount/age ranges và applicability. Evidence không thuộc đúng offer không được dùng chứng minh giá đó. Invalid field tạo issue và bị loại khỏi decision input; giữ phần hợp lệ của source nếu còn dùng được.

Snapshot bất biến; refresh tạo snapshot mới. Ngừng nguồn khi access status thay đổi; cache không làm nguồn bị chặn thành nguồn được phép fetch. Coverage limit/truncation phải đến frontend để kết quả không bị hiểu là tìm toàn bộ thị trường.
