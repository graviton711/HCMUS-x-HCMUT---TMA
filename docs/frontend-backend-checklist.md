# Checklist thống nhất frontend–backend

**Trạng thái:** Danh sách quyết định cho P1, chưa phải API mới đã chốt. [Data contract](data-contract.md) vẫn là nguồn schema hiện tại; khi thống nhất phải cập nhật nguồn đó, không duy trì một schema cạnh tranh trong frontend.
**Owner:** FE + BE cùng review; BE xác nhận dữ liệu/khả năng xử lý, FE xác nhận đủ để thực hiện [flow](frontend-flows.md).

## Contract hiện có

`POST /api/compare` nhận:

```json
{ "tour_urls": ["https://example.test/tour/a", "https://example.test/tour/b"] }
```

Response có `status: completed | partial | error`, `tours`, `trade_offs`, `issues`. Tour/Offer/Provider dùng field wrapper `value`, `raw_value`, `status`, `evidence`; mức đầy đủ và mức xác minh là hai trục riêng.

Chưa có contract cho tìm theo nhu cầu/làm rõ; `offers[].price` chưa xác định offer cụ thể; đơn vị/tổng giá nhóm, freshness và quote nguồn chưa đủ để thực hiện toàn bộ wireframe.

## Các quyết định cần chốt

| ID | Cần thống nhất | Đầu ra bắt buộc / ảnh hưởng UI |
|---|---|---|
| C1 | Schema criteria | Field/kiểu/bắt buộc/range/default: điểm đi/đến, ngày và độ linh hoạt, nhóm khách/tuổi, ngân sách+currency+đơn vị, ràng buộc cứng, ưu tiên. Lỗi trả đúng field; đơn vị số ngày/ngân sách rõ ràng. |
| C2 | API hai kiểu đầu vào | Method/path/body cho nhu cầu và URL; dùng chung hay endpoint riêng; URL mode có criteria hay không. Làm rõ yêu cầu có được BE hỗ trợ không, trả field/câu hỏi nào và FE gửi tiếp ra sao. |
| C3 | Kết quả lọc/cá nhân hóa | Criteria chuẩn hóa được trả về; mỗi điều kiện đạt/không đạt/chưa biết, lý do tour bị loại/thiếu dữ liệu, tiêu chí sắp xếp/trọng số nếu có. Không coi thiếu bằng chứng là đạt. |
| C4 | Lifecycle | Đồng bộ hay job; trạng thái/stage, thời gian chờ, timeout, hủy, thử lại, chống submit lặp, khôi phục sau mất mạng/refresh. `request_id`/`job_id` nếu dùng phải định nghĩa rõ. |
| C5 | ID và reference | Cách định danh tour/offer/evidence ổn định; canonical URL, dedup, thứ tự offer. Trade-off trỏ tới đúng offer+field+evidence, không chỉ `offers[]`; đổi ngày không mở nhầm bằng chứng. |
| C6 | Giá và nhóm khách | Giá tham chiếu hay theo offer; fixed/from/contact; currency của offer có kế thừa tour không; đơn vị người/nhóm; giá trẻ em/độ tuổi và phụ thu. Tổng giá có những khoản nào/chưa biết gì; backend tính tổng nếu đủ dữ liệu, FE chỉ định dạng. |
| C7 | Evidence | Có raw_value/quote/excerpt nào thực sự được lưu; nguồn, timestamp, extraction và verification. Evidence nhiều nguồn/mâu thuẫn xử lý thế nào; thiếu quote không cho FE tự dựng trích dẫn. |
| C8 | Freshness | Policy theo field, mốc thời gian/timezone, ngưỡng cũ, cache và thao tác kiểm tra lại. BE trả trạng thái hay FE tính theo policy có version; timestamp không thay thế xác minh. |
| C9 | Lỗi và kết quả không đủ | HTTP status + business status, mã lỗi ổn định, lỗi theo URL/field, retryable hay không. Phân biệt zero matches, một tour, partial và tất cả nguồn lỗi; danh mục issues và cách hiển thị. |
| C10 | Tính nhất quán schema | Required/null/partial, provider display_name bắt buộc hay optional, offer thiếu ngày/giá, offers rỗng, schema version và thay đổi tương thích. Required policy hiện có chỗ chưa thống nhất; giải quyết trước khi sinh type. |
| C11 | Bộ JSON mẫu | Các scenario ở bảng dưới, schema validation và expected UI; mẫu phải đi qua cùng schema với API thật. |

## Checklist review contract

- [ ] C1–C3 được thống nhất: mỗi field UI có nơi gửi/nhận và cách xử lý khi chưa biết.
- [ ] C4 được chọn dựa trên đo thời gian BE và giới hạn gateway/mạng; có lifecycle cho các nhánh không thành công.
- [ ] C5–C8 đủ để xác định đúng offer, giá, evidence và độ mới ở từng ô.
- [ ] C9–C10 có bảng HTTP/business status và schema không mâu thuẫn.
- [ ] C11 có JSON thật hoặc mô phỏng ghi rõ, expected state và kết quả validate.
- [ ] Có một OpenAPI/JSON Schema chuẩn cùng ví dụ; FE sinh type từ nguồn đó và chọn validation runtime tương thích, không gõ lại DTO theo cảm tính.
- [ ] Chốt API base URL/local/demo, CORS, auth nếu thuộc phạm vi, giới hạn input và timeout.
- [ ] Chốt retry/cache cho request có chi phí crawler; refetch không được tự chạy lại crawl chỉ vì đổi focus cửa sổ.
- [ ] FE + BE review từng trường hợp dưới đây và ghi quyết định vào data contract. Điểm chưa chốt phải có owner và phần UI bị chặn.

## Chọn cơ chế xử lý ở C4

| Phương án | Gain | Chi phí / rủi ro | Khi phù hợp |
|---|---|---|---|
| Request đồng bộ | Kết quả cuối trong một request; lifecycle dễ theo dõi | Timeout/ngắt kết nối mất kết quả; retry có thể lặp crawl | Thời gian xử lý đo được đủ ngắn và ổn định trong giới hạn request |
| Job + polling có kiểm soát | Theo dõi lâu, khôi phục trạng thái, lấy kết quả sau mất kết nối | BE lưu job/kết quả; cần TTL, dedup, cancel và polling policy | Crawler/AI kéo dài hoặc biến động, cần khôi phục đáng tin cậy |

Đề xuất job khi đo thực tế cho thấy request đồng bộ dễ timeout; đây là tăng khả năng kiểm soát có giá trị, không chỉ thêm kiến trúc. Streaming chỉ cân nhắc nếu stage/result từng phần tạo lợi ích rõ cho UI; không bắt buộc cho demo.

## Bộ mẫu JSON cần nhận

| Scenario | Nội dung để kiểm tra |
|---|---|
| URL success | Ít nhất 2 tour, nhiều offer cho một tour, giá/ngày khác nhau và trade-off mở đúng evidence |
| Nhu cầu success | Request criteria và response ghi lại criteria chuẩn hóa, kết quả lọc/cá nhân hóa có căn cứ |
| Clarification | Input cần bổ sung và response xác định field/câu hỏi; chỉ áp dụng nếu C2 chọn luồng này |
| Partial | Một nguồn lỗi, tour khác dùng được; lỗi chỉ rõ URL và khả năng thử lại |
| Empty / một tour | Zero matches có lý do, và một tour còn lại; không tạo trade-off giả |
| Field thiếu / partial | `value: null`, enum/field optional, `offers: []`, phụ thu chưa biết; không crash hoặc tính giá thiếu |
| Freshness / verification | Timestamp khác nhau theo field, nguồn tự công bố/độc lập, policy cũ và evidence mâu thuẫn nếu được hỗ trợ |
| Validation / lỗi toàn bộ | Input sai theo field/URL, nguồn không hỗ trợ, toàn bộ nguồn thất bại, lỗi hệ thống theo C9 |
| Timeout / request cũ | Không trả kịp, hai request trả đảo thứ tự; job đang chạy/hoàn tất/thất bại/hết hạn nếu chọn job |

Đề xuất lưu schema và mẫu trong thư mục contract chung có version; vị trí cụ thể chốt cùng BE. Mỗi fixture ghi scenario, schema version và expected UI. Không tạo JSON “đã chốt” trước khi C1–C10 được review.

## Ranh giới trách nhiệm

- **BE:** Chuẩn hóa/tìm tour, kiểm tra nguồn, lọc điều kiện, tính giá có căn cứ, đánh giá/trade-off và reference. Chỉ trả tiến độ có thể đo được.
- **FE:** Input/validation trải nghiệm, render dữ liệu và các mức trạng thái, mở evidence, điều khiển thao tác và định dạng tiền/ngày.
- **Cùng chịu trách nhiệm:** Schema/type/validation, ý nghĩa status, policy retry/freshness và regression fixture khi contract thay đổi.
