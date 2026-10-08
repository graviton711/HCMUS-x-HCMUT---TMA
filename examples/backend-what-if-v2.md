# Test phân tích “nếu đổi điều kiện thì sao?” — v2

Flow: **nhu cầu đã xác nhận → comparison → what-if job → xem kết quả giả định → proposal → xác nhận → comparison mới**. Phân tích giữ nhu cầu gốc; chỉ khi xác nhận proposal mới tăng revision.

## 1. Khởi động và chuẩn bị comparison

Tại repo root, dừng server cũ bằng Ctrl+C rồi chạy:

```powershell
uv sync
uv run tour-backend serve
```

Mở `http://127.0.0.1:8000/docs`. Tạo `POST /v2/sessions`, bấm **Authorize**, dán `data.token` (không thêm `Bearer`). Giữ cùng session cho toàn bộ flow.

Với Supabase, dùng [hướng dẫn tạo nhu cầu/comparison](backend-supabase-v2.md). Text phải parse → đọc proposal → trả lời phần còn thiếu → confirm trước. Nhớ giữ `requirement_id`, revision và `comparison_id` thật từ response. Chờ `GET /v2/jobs/{job_id}` thành `succeeded` hoặc `partial`, rồi đọc `GET /v2/comparisons/{comparison_id}` có `result`.

Ca Nhật có đủ năm core fields. Câu Tết gốc thiếu số người, trần giá và năm/ý nghĩa khoảng thời gian; xử lý theo [flow bổ sung thông tin](backend-personalized-v2.md). Không dùng các con số của ca minh họa làm câu trả lời thay người dùng.

## 2. Tạo phân tích

Trong `POST /v2/comparisons/{cid}/what-if`, điền `cid` bằng comparison vừa hoàn tất. Thay toàn bộ body ví dụ Swagger bằng:

```json
{
  "expected_revision": 1,
  "candidate_limit": 100,
  "max_scenarios": 32,
  "include_soft": true,
  "include_pairs": true,
  "max_budget_increase_ratio": 0.25,
  "max_date_shift_days": 7
}
```

`expected_revision` phải là revision hiện tại đã xác nhận. Hai giới hạn cuối cho phép thử tăng trần giá tối đa 25%, mở ngày tối đa 7 ngày để đo tác động; chúng không tự sửa yêu cầu. Backend chỉ tạo mức nới cụ thể khi có giá/ngày xác minh được. Không tự suy ngày âm hoặc tạo giá từ thông tin chưa đủ.

`candidate_limit` tối đa500; `max_scenarios` tối đa64 là số lần thử, gồm cả cặp bị bỏ vì dư thừa. Muốn tập trung một điều kiện, thêm `condition_ids: ["ID từ requirement"]`; cả nhóm OR/cùng field/khoảng đi-về sẽ được giữ nguyên.

Header `Idempotency-Key` có thể để trống khi thử lần đầu; nếu dùng thì chọn chuỗi riêng. Lặp cùng key/body trả cùng job, không tạo thêm job; body khác cần key khác.

Response 202 chứa `analysis_id`, `job_id`. Chờ job kết thúc qua `GET /v2/jobs/{job_id}`. Nếu `failed`, đọc `error.code`; nếu còn `queued/running`, chưa đọc đó thành kết quả cuối.

## 3. Đọc kết quả

Gọi `GET /v2/what-if/{aid}` bằng `analysis_id`. Phần chính nằm ở `data.result`:

| Field | Ý nghĩa |
| --- | --- |
| `baseline` | Số tour đạt, không đạt, chưa rõ trước khi đổi điều kiện |
| `scope` | Snapshot, thời điểm, giới hạn đọc tour/offer, policy nguồn, exclusions |
| `scope.condition_diagnostics` | Pass/fail/unknown và lý do cho từng điều kiện trên candidate summaries; dùng để tìm phần dữ liệu cần bổ sung |
| `groups` | Các điều kiện được thay cùng nhau để giữ đúng AND/OR và bounds |
| `scenarios` | Từng giả định bỏ nhóm hard/soft, nới giá/ngày, bỏ cặp hard |
| `additional_candidate_ids` | Tour mới đủ các hard còn lại trong kịch bản |
| `proven_blocked_candidate_ids` | Tour mới mà yêu cầu gốc đã loại có bằng chứng |
| `previously_unknown_candidate_ids` | Tour mới mà yêu cầu gốc chưa xác minh đủ |
| `joint_only_candidate_ids` | Tour chỉ mở khi thay cả hai nhóm, vượt thay từng nhóm riêng |
| `witnesses` | Tour, offer cụ thể và đánh giá/bằng chứng trước-sau |
| `top_before/top_after`, `rank_changes` | Biến động thứ hạng khi thay ưu tiên, cùng policy xếp hạng |
| `restriction_ratio` | Tử số, mẫu số và tỷ lệ quan sát trên snapshot; `null` nếu chưa đủ cơ sở |
| `explanation` | Các insight đã tính được LLM chọn hoặc fallback; câu chữ do backend dựng |
| `limits` | Số lần thử, cặp dư thừa, truncation; tối đa3 witnesses và10 rank changes/kịch bản |

Baseline được **tính lại trên snapshot rộng mới**, không lấy số trong comparison cũ để tính delta. Chỉ so baseline và các scenarios của cùng analysis. Catalog có thể đã thay đổi từ lúc chạy comparison.

URL-only phân tích tập URL đã đưa; hybrid dùng discovery snapshot rộng trong giới hạn. Reference URL ngoài tập được đọc có thể vắng trong hybrid analysis. Backend không trộn hai thời điểm đọc và không hứa phủ toàn thị trường/catalog offers.

Trong diagnostics, `counts`/`unknown_reason_counts` là candidate summaries; `offer_counts`/`offer_unknown_reason_counts` là từng offer thực tế. Summary có `MULTIPLE_OFFERS_UNSELECTED` chưa có nghĩa chọn một offer sẽ giải quyết được vấn đề: đọc lý do trên offers để biết còn thiếu proof/phạm vi giá hay không.

Ví dụ **synthetic**: trần giá11 triệu giữ1 tour; tăng lên12 triệu giữ2 tour. Một tour mới đã bị trần giá gốc loại: `numerator=1`, `denominator=2`, `percent=50`. Nghĩa là 50% lựa chọn đạt kịch bản đã bị yêu cầu gốc chặn trong snapshot này. Đây không phải “ngân sách đóng góp50% chất lượng”, không cộng các tỷ lệ thành100%.

Nếu có unknown→pass, tỷ lệ để `null`, có reason. Tour chưa rõ không được gọi là đã chứng minh bị chặn. Với Supabase chưa đủ evidence, số unknown lớn và không có mức nới actionable vẫn là kết quả hợp lệ; cần bổ sung chất lượng dữ liệu.

Bỏ soft không đổi hard pool; xem biến động nhóm đầu, khoảng điểm, coverage và `tied`. Thứ hạng policy thay đổi không chứng minh tour tốt hơn khi các khoảng điểm chồng nhau. `insufficient_data` nghĩa là chưa đo được, không phải ảnh hưởng bằng0.

Đọc `witnesses[].evidence_ids` bằng `GET /v2/evidence/{eid}`; cùng session. Mỗi witness dùng một offer thỏa các điều kiện còn lại, không ghép ngày offer này với giá offer khác.

## 4. Chọn kịch bản để tạo bản sửa

Sau khi đọc tradeoffs, lấy `scenarios[].id` muốn áp dụng. Gọi `POST /v2/what-if/{aid}/scenarios/{sid}/proposals` với:

```json
{
  "expected_revision": 1
}
```

Response trả proposal có `id`, `version`, `preview`. Đọc các điều kiện thay đổi và `preview.readiness.can_confirm`. Yêu cầu đã xác nhận vẫn ở revision1.

Nếu bỏ điểm đến/nơi đi/ngày/trần giá, proposal có thể thiếu core field và cần bổ sung trước khi confirm. Kịch bản tăng trần giá giữ đủ core fields thường có thể confirm; backend vẫn kiểm tra đầy đủ, không bỏ gate.

Khi đồng ý preview, gọi `POST /v2/proposals/{proposal_id}/confirm`:

```json
{
  "expected_revision": 1,
  "expected_proposal_version": 1
}
```

Thay version bằng `version` thật của proposal; tên field là **`expected_proposal_version`**. Response requirement tăng revision. Tạo `POST /v2/comparisons` bằng requirement_id và revision mới để tìm lại; lần này catalog được đọc mới nên kết quả thực tế có thể khác phân tích trước đó.

409 khi revision cũ/proposal chưa duyệt/comparison chưa sẵn sàng cần xử lý trạng thái trước. Nếu nguồn bị pause hoặc policy đổi lúc phân tích, job bị chặn publication; hủy proposal chưa cần và chạy analysis mới bằng revision hiện tại.

## Kiểm thử tự động và cấu hình

```powershell
uv run pytest tests/test_what_if.py -q
uv run python examples/check-what-if-v2.py
```

Lệnh đầu chạy offline bằng dữ liệu synthetic. Lệnh sau đọc Supabase thật và gọi NIM một lần riêng trên metrics synthetic để kiểm schema chọn insight. Nó dùng SQLite in-memory riêng, không cần server đang chạy, không ghi catalog/session token; báo cáo public ở `data/live-tests/what-if-*`. Hai nhu cầu được gửi dạng structured tương đương ca Nhật và **ca Tết đã bổ sung câu trả lời giả định**; đây là test analysis, không test lại extraction ngôn ngữ tự nhiên. [Script test extraction riêng](backend-personalized-v2.md).

`.env`: `DATA_PROVIDER=supabase` và cấu hình catalog/NIM hiện có. `WHAT_IF_EXPLANATION_ENABLED=false` tắt riêng bước chọn insight; metrics và template vẫn có. Timeout mặc định `WHAT_IF_EXPLANATION_TIMEOUT_SECONDS=15`; lỗi NIM giữ kết quả tính toán bằng fallback. Script live có `--skip-nim` để chỉ kiểm catalog/API.

Policy/giới hạn: [what-if-analysis](../docs/what-if-analysis.md). Không tìm optimum toàn cục; minimal chỉ trong các singleton/cặp đã thử.
