# Backend: kế hoạch phát triển

**Trạng thái:** Backend v1 đã triển khai cho discover/compare_urls. User chốt ngân sách mặc định là giá tour. Crawler thật chưa có mẫu; phạm vi kiểm tra và lệnh chạy ở [backend-runtime.md](../../src/api/backend-runtime.md).

## Kết luận từ docs hiện tại

- Sản phẩm hỗ trợ chọn tour: nhận nhu cầu/URL → thu thập dữ liệu → lọc điều kiện cứng → so sánh và giải thích có bằng chứng. Không tự tạo lịch trình hoặc đặt tour.
- AI hiểu yêu cầu và có thể diễn đạt kết quả; dữ kiện tour và việc đạt ràng buộc phải được kiểm tra bằng dữ liệu, không giao cho LLM tự phán đoán.
- Tour ổn định, offer biến động và thông tin nhà cung cấp phải tách nhau; evidence nằm ở từng field.
- Checkout có backend v1 và fixture gateway; chưa có crawler thật. Không coi fixture là dữ liệu đã crawl.
- Kết quả tách `eligible`, `ineligible`, `needs_verification`; chỉ gắn nhãn đã đạt khi dữ liệu đủ cho điều kiện được xét.
- Docs hiện yêu cầu lấy tour/offer theo nhu cầu hoặc URL. Nếu crawler dự định crawl trước toàn bộ catalog, đây là thay đổi cần team review; chưa mặc định thay kiến trúc.

## Pipeline và ranh giới giữa ba người

`Input → RequirementDraft → validation/clarification → QuerySpec → crawler/cache → snapshot validation → hard filtering → comparison/evidence → API result`

| Phần | Backend | Crawler | Frontend |
|---|---|---|---|
| Yêu cầu | Hiểu tiếng Việt, chuẩn hóa, phát hiện mơ hồ/mâu thuẫn, lưu revision | Nhận QuerySpec có cấu trúc | Nhập text/form; hiển thị cách hiểu và sửa field |
| Dữ liệu | Chốt contract, kiểm tra, lưu snapshot và provenance | Source registry, quyền truy cập, tìm URL phù hợp, adapters, trả dữ liệu có nguồn | Hiển thị tiến độ, nguồn không hỗ trợ và dữ liệu thiếu |
| Quyết định | Xét từng condition, giá theo nhóm khách, trade-off có căn cứ | Cung cấp field đúng nghĩa và capability theo nguồn | Bảng so sánh, evidence từng ô, tiêu chí sắp xếp |

Crawler phải cung cấp cả khả năng **tìm ứng viên theo nhu cầu**, không chỉ đọc một URL. Nếu nguồn chỉ hỗ trợ URL, backend trả giới hạn capability rõ ràng; không hứa tìm toàn bộ tour.

Hai luồng dùng chung domain/decision engine nhưng khác acquisition và presentation; xem [backend-flows.md](../../src/api/backend-flows.md). Trong so sánh URL, giữ mọi target user đã chọn, kể cả target không đạt hoặc nguồn lỗi. Không tự tìm tour khác để thay target đó.

## Các module dự kiến

| Module | Trách nhiệm, input → output | Workflow/interface | Quyết định quan trọng |
|---|---|---|---|
| `domain` | Kiểu dữ liệu chung: yêu cầu, điều kiện, tour, offer, evidence, kết quả | Schema version → validation → chia sẻ cho mọi module | Field/operator có whitelist; không dùng dict tùy ý làm contract |
| `requirements` | Text/form + revision trước → draft, QuerySpec hoặc câu hỏi | LLM extract → normalize → semantic validation → merge → readiness | LLM + rules; nguồn từ câu user; không gọi crawler; [README](../../src/requirements/README.md) |
| `data_access` | QuerySpec/URL đã duyệt → snapshot hợp lệ + vấn đề từng nguồn | Registry → crawler gateway/cache → validation → repository | Không viết lại crawler; tách verification/freshness; giữ snapshot cũ |
| `decision` | QuerySpec + snapshots → đánh giá từng condition, comparison, trade-off | Tính chi phí → lọc ba trạng thái → so sánh → evidence links | Logic xác định được; thiếu dữ liệu không thành pass; không có điểm AI bí mật |
| `api` | HTTP request → revision, job progress hoặc comparison response | Validate → điều phối modules → persist → response | Business logic nằm ngoài route; crawler chậm không giữ request vô hạn |

Tài liệu cạnh module: [domain](../../src/domain/README.md), [requirements](../../src/requirements/README.md), [data_access](../../src/data_access/README.md), [decision](../../src/decision/README.md), [api](../../src/api/README.md). Contract tổng quan ở [backend-contracts.md](../../src/domain/backend-contracts.md), tích hợp crawler ở [crawler-contract.md](../../src/data_access/crawler-contract.md), HTTP ở [api-contract.md](../../src/api/api-contract.md).

## Hướng kỹ thuật đề xuất

Một backend Python chia module, cùng một dịch vụ API. Đề xuất FastAPI + Pydantic vì phù hợp repo Python và chia sẻ schema/validation/OpenAPI cho frontend. Dependencies được khóa bằng uv.lock khi triển khai.

| Cách hiểu yêu cầu | Gain thực tế | Cost tăng thêm | Rủi ro | Khả năng tích hợp / dài hạn |
|---|---|---|---|---|
| Rules/regex hoàn toàn | Đơn vị tiền/ngày và mẫu đơn giản kiểm soát tốt | Thấp lúc đầu, tăng mạnh theo cách nói | Yếu với phủ định, OR, sửa nhiều lượt | Dùng cho normalize; không đủ làm parser chính |
| LLM trả JSON rồi dùng trực tiếp | Hiểu cách nói đa dạng | API và độ trễ | JSON đúng cấu trúc vẫn sai nghĩa hoặc tự thêm điều kiện | Không đủ độ kiểm soát cho bộ lọc quyết định |
| **LLM extraction + typed schema + rules + clarification** | Hiểu tiếng Việt, kiểm tra được và truy vết từng điều kiện | Thêm validator và bộ đánh giá | Còn lỗi ngữ nghĩa; phải đo và hỏi lại đúng chỗ | Đề xuất: gain/cost tốt trong nhóm mạnh; đổi provider qua một gateway |

JSON theo schema chỉ bảo đảm hình dạng, không chứng minh nghĩa đúng. Không dùng điểm confidence LLM tự khai làm xác suất chính xác.

**Provider đã xác nhận:** NVIDIA hosted NIM, model `nvidia/nemotron-3-super-120b-a12b`; cấu hình hiện nằm tại `.env` ở root với `NVIDIA_NIM_API` và `NVIDIA_NIM_MODEL`. Probe nhỏ đã gọi được API; chưa đủ kết luận chất lượng tiếng Việt hoặc bảo đảm schema enforcement. Cấu hình, kết quả và các giới hạn ở [nvidia-nim.md](../../src/requirements/nvidia-nim.md).

Storage cần giữ revision yêu cầu, job, snapshot và evidence để replay. Đề xuất SQLite cho dev local một backend/worker, qua repository + SQLAlchemy; dùng transaction ngắn và revision/lease conditional updates. Deployment nhiều process/host đề xuất PostgreSQL, chốt khi biết hosting. Bảng/trách nhiệm ở [API module](../../src/api/README.md); database được tạo khi app khởi động. Chưa cần vector database cho bộ lọc có cấu trúc; chỉ cân nhắc khi đã đo nhu cầu tìm ngữ nghĩa lịch trình.

Đề xuất extraction và comparison cùng dùng job lưu bền + polling, vì probe NIM đã có lượt timeout 35 giây. Bắt đầu một worker với giới hạn concurrency, timeout/deadline từng upstream; triển khai nhiều worker chỉ khi cần. Khởi động lại phải đánh dấu/recover job đang chạy; không để UI chờ mãi. Structured form update không cần gọi model và có thể trả ngay.

## Thứ tự làm và điều kiện hoàn thành

1. **Contract + bộ đánh giá tiếng Việt:** thống nhất budget basis, nhóm khách, condition tree, evidence và ví dụ JSON. Người crawl/frontend review ngay ranh giới của mình.
2. **Module requirements:** extraction, normalize, validation, câu hỏi có `field_path`, sửa nhiều lượt và revision. Chạy độc lập, chưa cần data thật.
3. **Decision engine với fixtures:** dữ liệu mẫu ghi rõ là mô phỏng; kiểm tra pass/fail/unknown, chi phí cùng basis, evidence và trade-off. Đảm bảo luồng từ yêu cầu đến kết quả có thể chạy trước khi crawler hoàn tất.
4. **API + state:** frontend tích hợp parse/clarification, job và comparison. Thay fixture gateway bằng crawler gateway khi contract ổn định.
5. **Data integration:** kiểm tra provenance, dedup, cache/freshness, nguồn lỗi và partial result; đối chiếu mẫu thật có gán nhãn thủ công.

Trong bước 2 cần bộ gold khởi đầu khoảng 50 câu + 15 chuỗi sửa nhiều lượt, bao gồm cả câu phải hỏi lại. Đo đúng field/đơn vị, hard-soft, phủ định/AND-OR, readiness và hành vi cập nhật; ghi latency/cost theo provider. Chốt ngưỡng release sau baseline, không tuyên bố độ chính xác khi chưa đo.

Checks quan trọng: không bịa field; không tự bỏ điều kiện bắt buộc; cùng input/snapshot/policy cho cùng kết quả decision; replay được lý do mỗi kết luận; lỗi một nguồn không xóa kết quả hợp lệ từ nguồn khác.

## API shape để frontend góp ý

| Endpoint đề xuất | Input → output |
|---|---|
| `POST /v1/requirements` | Text/form + mode/URL → resource; text trả 202 + parse job, form hợp lệ có thể trả 201 |
| `GET /v1/requirements/{id}` | Resource id → revision hiện tại, draft/readiness/clarifications hoặc parse status |
| `PATCH /v1/requirements/{id}` | Expected revision + answers/edits → revision mới hoặc 202 + parse job; revision cũ trả 409 |
| `POST /v1/comparisons` | Requirement id/revision + offer selections nếu có → 202, comparison id + job id |
| `GET /v1/jobs/{id}` | Job id → trạng thái/tiến độ/error/result reference |
| `POST /v1/jobs/{id}/cancel` | Job đang chạy → yêu cầu hủy; result terminal không bị overwrite |
| `GET /v1/comparisons/{id}` | Comparison id → trạng thái hoặc kết quả + evidence references |
| `GET /v1/evidence/{id}` | Evidence id → field, raw value/quote, URL, thời điểm, verification |

Các query/job khóa vào revision và snapshot cụ thể; sửa tiêu chí tạo lần đánh giá mới. Error có code/path/retryable; timeout model/crawler phân biệt với yêu cầu mơ hồ và không có tour phù hợp. ID không thay kiểm tra quyền truy cập; deployment public cần giới hạn truy cập session/job, rate limit và CORS phù hợp hosting.

## Điểm cần team chốt

- Provider/model đã được user chọn là NVIDIA NIM/Nemotron 3 Super. Cần chốt ngân sách/quota, cấu hình reasoning sau gold evaluation và xác minh mức bảo đảm structured output của hosted endpoint.
- Cả hai luồng đã được user chọn. Người crawl cần review contract đề xuất và xác nhận danh mục nguồn/field/search capability thực sự hỗ trợ.
- Chính sách ngôn ngữ và readiness đề xuất ở [backend-flows.md](../../src/api/backend-flows.md); luôn cho user xem/sửa cách hiểu. Bộ gold ở [requirements-evaluation.md](requirements-evaluation.md).
- Chính sách freshness theo field/nguồn và cách xử lý giá thiếu phụ thu; không chốt TTL tùy ý trước mẫu thật.
- Hosting/public database, thời gian lưu nhu cầu/log và mức auth cần cho demo. Dev storage mặc định đề xuất SQLite; không log toàn bộ nội dung cá nhân hoặc key mặc định.

Nguồn kỹ thuật tham khảo: [FastAPI request body](https://fastapi.tiangolo.com/tutorial/body/) mô tả Pydantic validation và OpenAPI; [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) mô tả kiểm soát coercion. Kiểm tra nghĩa nghiệp vụ vẫn do backend xây dựng.

Storage tham khảo: [SQLAlchemy version counters](https://docs.sqlalchemy.org/en/20/orm/versioning.html); conditional update/row count vẫn cần cho worker claim và revision CAS. [SQLite WAL](https://www.sqlite.org/wal.html) chỉ cho một writer tại một thời điểm; không coi SQLite local là phương án nhiều host mặc định.
