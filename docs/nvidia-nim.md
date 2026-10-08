# NVIDIA NIM — cấu hình và probe

**Trạng thái:** Đã có NIM gateway, grounded parser, giới hạn một repair và runner smoke. Các probe lịch sử dưới đây không thay kết quả kiểm tra hiện tại ở [backend-runtime.md](backend-runtime.md).

## Cấu hình đã xác nhận

| Mục | Giá trị / vai trò |
|---|---|
| Provider | NVIDIA hosted NIM |
| `NVIDIA_NIM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |
| `NVIDIA_NIM_API` | Credential dùng cho Bearer authentication; không đưa giá trị vào docs/log |
| File hiện có | `.env` ở root; có cả hai biến, được Git bỏ qua và không tracked. Lần probe đầu file nằm tại `docs/.env`; đường dẫn hiện tại đã được kiểm tra lại |
| Base URL | `https://integrate.api.nvidia.com/v1` |
| Endpoint | `POST /chat/completions` |

Khi viết settings, đề xuất ưu tiên environment variables rồi `.env` ở root; có explicit env-file override cho dev nếu cần. Validate cả credential/model trước gửi request và fail fast nếu thiếu, không gửi request rỗng do đường dẫn cũ. Deployment truyền secrets qua môi trường; không tự đổi tên các biến user đã dùng.

## Điều đã kiểm tra trong tài liệu NVIDIA

- [API reference của model](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b-infer) mô tả Chat Completions, `reasoning_effort=none/low/high`, `reasoning_budget`, `max_tokens`, `stream` và response 200/202/422/500.
- [Model card](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard) khuyến nghị `temperature=1.0`, `top_p=0.95`. Danh sách ngôn ngữ hỗ trợ không liệt kê tiếng Việt; điều này không chứng minh model không hiểu tiếng Việt, nhưng cần đánh giá riêng.
- API reference được đọc chưa mô tả `response_format`. Không lấy tài liệu structured generation của NIM self-hosted làm bằng chứng hosted endpoint này bảo đảm constrained decoding.

## Probe quan sát được

Một request chứa ba câu giả lập, không gửi dữ liệu thật của khách hàng. Dùng schema JSON nhỏ cho experiment, không phải contract parser cuối cùng; gửi `response_format.type=json_schema`, `strict=true`, `stream=false`, reasoning `none`, temperature 1.0, top_p 0.95 và max_tokens 1536.

- HTTP 200, finish reason `stop`, content parse được thành JSON và có các field theo schema thử nghiệm.
- Khoảng 5,37 giây cho request này; usage 382 prompt + 439 completion = 821 tokens, reasoning tokens 0. Đây là một quan sát, chưa phải latency/cost benchmark.
- Request chứa schema được endpoint chấp nhận; chưa chứng minh tham số schema được enforced. Backend vẫn cần reject extra fields, kiểm tra kiểu/enum, completeness và semantic rules.

| Ca giả lập | Quan sát đúng | Vấn đề |
|---|---|---|
| Nhật hoặc Hàn; từ Sài Gòn; tối đa 30tr VND cả nhà; ưu tiên hotel 4 sao | OR, amount 30.000.000, group_total, hard budget và soft hotel | Đưa ghi chú về nhóm khách đã rõ vào clarifications; scope “tổng chi phí” rộng hơn coverage chưa được xác định |
| Ngân sách 30 triệu; 5 ngày; tháng sau | Amount và duration; budget basis unknown | Tự thêm VND trong hard condition; danh sách clarification gồm nhiều field chưa chắc cần cho luồng tìm kiếm |
| Bỏ hotel 4 sao bắt buộc, giữ không shopping | Remove đúng hotel; giữ shopping hard | Dùng clarifications để ghi lại thay đổi, không phải câu hỏi cần trả lời |

Không gán tỷ lệ accuracy từ ba ca này. Probe không kiểm tra normalize ngày tương đối theo reference timestamp, nguồn quote, tính giá nhóm, consistency giữa các lượt API hoặc chống instruction injection đầy đủ.

## Điều chỉnh thiết kế từ kết quả

1. Backend kiểm tra raw value/quote và derivation; không chấp nhận VND, budget coverage hay điều kiện mới không có nguồn hoặc default policy công khai.
2. Validator quyết định readiness và tạo câu hỏi có target; không dùng nguyên danh sách clarifications do LLM tự sinh.
3. Parser nhận final content, kiểm tra finish reason/truncation và schema trước semantic validation. Không đưa reasoning trace vào yêu cầu, response frontend hoặc log mặc định.
4. Gold evaluation so sánh `none/low/high`, prompt và sampling trên cùng bộ tiếng Việt. Chọn cấu hình theo semantic accuracy, false-ready, latency và token usage; không chọn `none` chỉ vì probe nhanh.
5. Khi implement gateway, phân biệt lỗi credential, rate limit, timeout, upstream/202 pending và malformed/truncated content. Retry/repair có giới hạn và nằm trong tổng deadline; không trả draft giả khi model lỗi.

Các quyết định schema/backend khác vẫn là bản nháp ở [backend-plan.md](archive/backend-plan.md) và [requirements README](../src/requirements/README.md).

## Probe tiếp theo: sáu ca, ba mức reasoning

Một request cho mỗi `none/low/high`, chạy độc lập đồng thời trên cùng sáu câu giả lập; mỗi request chứa cả sáu case. Temperature 1.0, top_p 0.95, max_tokens 2048; riêng high có reasoning_budget 512. Probe label nhỏ, chưa có quote/semantic validators của backend.

| Profile | Quan sát | Giới hạn/lỗi ngữ nghĩa |
|---|---|---|
| none | 200, JSON parse được; 10,75 giây; 1.228 total tokens | Case “30tr cả nhà” bị gán trip_total dù coverage chưa rõ |
| low | Client timeout ở khoảng 35,03 giây | Không có output để đánh giá; không kết luận model luôn chậm từ một lượt |
| high | 200, JSON parse được; 15,33 giây; 1.743 total tokens, 511 reasoning | Một case không nói điểm đến bị thêm Nhật/Hàn từ case khác; hotel đã remove vẫn có strength soft |

Field `hotel_action` trong prompt thử chưa định nghĩa đủ semantics cho initial creation nên không dùng nó chấm điểm. Không công bố accuracy/winner từ thử nghiệm này; batch case cũng khác cách gọi production.

Hệ quả: một request production chỉ có context của một requirement; gold chạy từng case riêng. Vẫn cần evidence-grounding và invariant cho patch/removal. Async parse job giữ UI theo dõi được, timeout thành terminal error; không tự hạ model/profile để che lỗi. Chọn profile sau bộ [gold](archive/requirements-evaluation.md), không chỉ theo latency của probe.

## Gateway hiện tại (02/10/2026)

`src/requirements/nim.py` dùng schema riêng cho initial/update, đưa schema vào prompt và kiểm tra lại ở backend. Native response_format được gửi nhưng không được coi là bảo đảm schema enforcement. Prompt `vi-conditions-v5`, raw quotes/values, operator whitelist, source spans và condition-tree references đều được kiểm tra; tối đa một repair có feedback cụ thể.

Sau khi sửa normalization chuỗi tiền kèm currency/basis và schema update, smoke 8 ca + 2 patch đạt ở lần chạy cuối. Các thử trước từng bị chặn vì field/operator sai, reference thiếu và raw amount chưa được normalize. Full gold và held-out vẫn chưa chạy. Báo cáo local tại `data/evaluation-final.local.json`, phạm vi xác minh ở [runtime](backend-runtime.md).
