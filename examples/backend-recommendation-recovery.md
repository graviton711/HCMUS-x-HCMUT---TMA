# Test gợi ý tour với policy giá niêm yết

Ngày 10/10/2026. Backend ở nhánh `backend`, frontend ở worktree nhánh `feature/minh-phu`. Không cần migration Supabase cho thay đổi này. Catalog vẫn read-only; application state nằm ở `data/backend.db`.

## 1. Khởi động hai phần đã sửa

Dừng các server cũ bằng Ctrl+C để chạy code mới. PowerShell thứ nhất:

```powershell
cd C:\Users\Admin\Desktop\HCMUS-x-HCMUT---TMA
uv sync
uv run tour-backend probe-supabase
uv run tour-backend serve
```

`.env` dùng `DATA_PROVIDER=supabase`. Kiểm tra `/health` phải có `data_provider=supabase`. Probe phải có `transaction_read_only=on`. Biến môi trường PowerShell được ưu tiên hơn `.env`; kiểm tra/gỡ override fixture cũ nếu có. Giữ connection string và key riêng tư.

PowerShell thứ hai chạy frontend từ **worktree đã sửa**, không chạy bản FE cũ trong checkout backend:

```powershell
cd C:\Users\Admin\Desktop\HCMUS-x-HCMUT---TMA-frontend-recovery
corepack pnpm --dir src/frontend install --frozen-lockfile
$env:BACKEND_URL='http://127.0.0.1:8000'
corepack pnpm --dir src/frontend dev
```

Mở URL Vite in trong terminal, thường là http://127.0.0.1:5173. `BACKEND_URL` ở đây trỏ proxy frontend tới backend. Không cần chép secret backend sang frontend.

## 2. Ca positive sau khi crawler đọc lại nguồn

Tạo **phiên tìm mới** và nhập:

- Điểm đến: Nhật Bản; nơi khởi hành: TP.HCM.
- Tháng khởi hành: 11/2026; người lớn: 1.
- Giá tour niêm yết/người lớn: tối đa 40.000.000 VND.
- Bỏ các ưu tiên tùy chọn khi kiểm bước lọc hard đầu tiên.

Review nhu cầu: ngân sách có `kind=budget`, `measure=listed`, `basis=per_adult`, `coverage=tour_price`; tháng là khoảng 01–30/11. Chỉ bấm tìm sau khi đã xác nhận.

Kho được đọc ngày 10/10 có lịch TP.HCM ngày 05/11 với giá từ 33.999.000 hoặc 34.999.000 VND. Đây là **giá lưu tại lần quan sát trước**, cần crawler xác nhận lại trước khi dùng làm positive. Nếu lịch/giá còn đúng, nguồn opt-in hợp lệ và các điều kiện còn lại đạt, tour vào pool hard. Thiếu dữ kiện vẫn phải unknown, không hứa tự động có gợi ý.

Khi có recommendation, kiểm tra đúng lịch khởi hành, giá thuộc cùng offer, nhãn **Từ**, nguồn giá và chú thích phụ thu/thực trả. Giá niêm yết dưới trần không có nghĩa tổng tiền chắc chắn dưới trần.

## 3. Các ca negative và biên

| Thử nghiệm | Kỳ vọng |
|---|---|
| Cùng nhu cầu nhưng tối đa 30 triệu | Với kho đã kiểm tra, không có lịch raw phù hợp; không tự tăng trần |
| Chọn tháng 2/2026 khi đang là 10/2026 | FE chặn; API tìm mới trả 422 `DEPARTURE_WINDOW_PAST` |
| Chọn 11/2026 và 01/2027 | OR từng tháng, không bao gồm 12/2026 |
| Chọn ngày cụ thể 03/11/2026 | Giữ đúng ngày, không tự đổi thành cả tháng |
| Offer đã khởi hành trong tháng hiện tại, ngày vẫn usable | Không gợi ý: `DEPARTURE_ALREADY_PASSED` |
| Giá/lịch quá TTL 24 giờ | `FIELD_STALE`, giữ tour để kiểm tra; không gọi đó là tour đạt |
| User yêu cầu trần tiền thực trả/tổng chi phí | `measure=payable`; cần bounds và đầy đủ phí bắt buộc, giá từ không đủ chứng minh |
| Đọc comparison cũ | Giữ snapshot/policy cũ, không tính lại âm thầm |

## 4. Test ngôn ngữ tự nhiên qua Swagger

Ở http://127.0.0.1:8000/docs, làm theo session → requirement → proposal → confirm → comparison của [walkthrough](backend-supabase-v2.md). Payload requirement:

```json
{
  "input": {
    "kind": "text",
    "text": "Tôi muốn tìm tour Nhật Bản khởi hành từ Hồ Chí Minh trong tháng 11/2026, đi 1 người lớn, giá tour niêm yết tối đa 40 triệu VND mỗi người lớn. Phụ thu báo riêng."
  },
  "timezone": "Asia/Ho_Chi_Minh"
}
```

Kiểm `data.preview` sau khi job extraction hoàn thành: nơi đi/đến đúng, ngày between đúng tháng, party có 1 người lớn, budget listed. Nếu model hiểu sai thì sửa draft trước khi confirm. Dùng ID/version/revision thực của response, không dùng ID mẫu Swagger.

Sau comparison đọc `data.result.recommendations.items`, `evaluations` và `analysis.budget_measures`. `analysis.cost_disclosures` giữ nguyên nội dung inclusion/exclusion/surcharge và evidence; với luồng listed, tiền thực trả chưa được tính. Response `queued` chỉ là nhận tác vụ, chưa phải kết quả.

Test text này gọi NIM; các regression offline của recovery không gọi NIM thật. Positive kiểm adapter/evaluator đã có regression riêng, tránh coi model parse thành công là đã kiểm đủ chất lượng dữ liệu tour.

## 5. Crawler cần làm gì

1. Chọn URL tour thật có lịch tương lai phù hợp ca test. Đọc lại website và panel lịch/giá của **từng offer**.
2. Upsert các giá trị thực sự quan sát: `departure_date`, `price_by_age.adult`, availability nếu nguồn có; giữ `tour_id`, record_key và URL ràng buộc đúng tour. `tours.currency`/`price_type` phải đúng nguồn; giá từ vẫn `from`, liên hệ vẫn `contact`.
3. Đặt `offers.observed_at` và `evidence.observed_at` thành thời điểm thực sự đọc offer. Tour/provider timestamp mới không làm offer cũ mới theo. Không chỉ sửa timestamp bằng tay.
4. Giữ provenance/source hợp lệ. Nguồn đã opt-in theo [catalog policy](../docs/catalog-validation-policy.md) không cần proof từng field để kiểm listed adult. Nếu metadata pricing đã có nhưng sai, sửa từ nguồn hoặc bỏ assertion sai; không đặt complete=true để ép đạt.
5. Với tiền thực trả/nhóm trẻ em: bổ sung [pricing metadata](catalog-price-metadata.md) có basis/age/applicability/phí đủ căn cứ. Không suy phí thiếu thành 0.
6. Chạy lại audit rồi tạo comparison mới. Nhóm tự triển khai chu kỳ crawler nếu chọn cập nhật hằng ngày; backend hiện không có scheduler tự recrawl.

Audit ở repo backend:

```powershell
uv run tour-backend audit-supabase --output data/catalog-audit.local.json
```

Đọc `listed_prices.eligibility_reasons`: `usable` khi hợp lệ/còn mới, `FIELD_STALE` khi cũ. `prices.pricing_complete` dành cho payable. Audit là mẫu bounded, phải đọc scan/pool/offer truncation trước khi suy ra toàn kho. TTL 86400 giây là giới hạn độ mới, không phải tác vụ tự cập nhật dữ liệu.

Kết quả đã chạy và giới hạn: [báo cáo nghiệm thu](../docs/recommendation-recovery-verification.md).
