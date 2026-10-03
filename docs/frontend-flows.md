# Luồng và trạng thái frontend

**Trạng thái:** PLANNING, sửa ngày 03/10/2026 theo yêu cầu Minh Phú: hệ thống tự tìm/rank/so sánh ngay; bỏ bước user sàng lọc danh sách/chọn 2–3 tour. V1 còn tách mode/chưa ranking; G9/G10 giữ contract cần bổ sung. Budget 20 và cách đếm tour URL bên dưới là đề xuất để review, chưa được benchmark hoặc implement.
**Liên quan:** [planning](frontend-plan.md), [wireframe](wireframes.md), [checklist FE–BE](frontend-backend-checklist.md), [API hiện tại](frontend-api-integration.md).

## Flow mặc định

**Nhập nhu cầu + URL tùy chọn → review nhu cầu/phạm vi → hệ thống tìm, phân tích, đánh giá và rank → tự chọn tối đa 3 tour gợi ý và so sánh ngay → xem evidence/mở nhà cung cấp hoặc yêu cầu phương án khác.**

| Bề mặt | Người dùng làm gì | Dữ liệu / trách nhiệm |
|---|---|---|
| 1. Input chung | Nhập nhu cầu bằng text hoặc form, thêm URL tùy chọn | Một draft chung; URL và nhu cầu có nhãn riêng, validate từng field |
| 2. Review | Sửa Bắt buộc/Ưu tiên/Cần làm rõ và phạm vi tìm, xác nhận nhu cầu | Committed criteria/revision/readiness, giữ AND/OR và nguồn gốc phạm vi |
| 3. Kết quả + so sánh | Xem đề xuất/lý do và bảng đã được dựng; tour URL được phân tích/so chung | BE chọn nhóm và trả comparison/trade-off cùng criteria/snapshots; nhãn “Bạn cung cấp” / “Hệ thống đề xuất” |
| Processing | Theo dõi hiểu nhu cầu/đọc URL/tìm/đánh giá/so sánh, hủy hoặc thử lại | Phase thật từ BE; không phần trăm giả |
| Evidence panel | Kiểm tra một field/nhận định và mở nguồn | Reference đúng tour/offer/field, dữ kiện nguồn/thời điểm/giới hạn |

Ba bề mặt chính: Input, Review, Kết quả/so sánh. Không có màn danh sách/checkbox để user chọn tour trước bảng. Phiên ẩn danh; route/back/refresh còn P2. Field/catalog/tên biến có thể đổi sau; thiết kế dùng mẫu có nhãn minh họa.

## Số ứng viên tìm kiếm khác số tour hiển thị

| Phần | Số lượng / quy tắc |
|---|---|
| Đề xuất hiển thị | Tối đa **3 tour khác nhau** đã đánh giá/rank; ít hơn ba tour đủ điều kiện thì trả đúng số có được và lý do |
| Ứng viên retrieval nội bộ | Đề xuất khởi điểm tối đa **20 tour khác nhau mỗi lượt**, sau canonical dedup; BE đo chất lượng/thời gian để chốt budget theo policy. Đây là giả định thử nghiệm, không phải pagination UI |
| URL tham chiếu | Phân tích tất cả URL hợp lệ trong giới hạn input; nằm ngoài budget 20 của tour tìm thêm. V1 hiện URL 2–5, mục tiêu hỗ trợ một URL còn G9 |
| Có URL | Đề xuất giữ tour URL làm tham chiếu và so cùng tối đa 3 gợi ý mới: một URL + ba gợi ý = bốn tour đối chiếu. Ba là số gợi ý, không ngầm là giới hạn mọi cột. Cách đếm/bố cục/mobile này cần review tại FLOW-3/P3 |

BE tìm ứng viên từ nguồn đã duyệt, thu thập/chuẩn hóa/đánh giá rồi rank. Không dừng ở ba URL đầu tìm thấy và coi đó là ba đề xuất tốt nhất. Hệ thống tự dựng comparison/trade-off trên cùng criteria/snapshots; UI không render pool nội bộ hoặc bắt user tự sàng lọc.

Pool rộng hơn giúp có cơ sở chọn ba, chi phí là thêm truy xuất/đánh giá. Budget/deadline giới hạn compute; đo với BE/crawler tại G9/G10/D1. Khi coverage chưa đầy đủ, nêu phạm vi/nguồn/giới hạn, không khẳng định tốt nhất toàn thị trường. UI gọn nhưng pipeline vẫn tìm và đánh giá nhiều lựa chọn.

## Ranking / kết quả tự động

- BE rank theo nhu cầu/ưu tiên đã xác nhận; trả nhóm gợi ý, lý do/tiêu chí/evidence, phần chưa biết, coverage/budget và policy version. Thuật toán/trọng số/tie-break còn G10; FE không tự tính rank hoặc lấy ba phần tử đầu v1 làm Top 3.
- Hard fail không được bù bằng ưu tiên; hard unknown không coi pass hay dùng để lấp đủ ba. Tour URL không đạt/chưa biết vẫn là tham chiếu với lý do rõ.
- Ba đề xuất là ba tour khác nhau; phải nêu offer/context cho giá/ngày, giữ evidence/snapshot và không ngầm chọn offer rẻ nhất. User vẫn có thể đổi ngày/offer; việc này khác bước chọn tour thủ công.
- Chỉ URL/chưa có ưu tiên cá nhân: dữ kiện tour giúp gợi ý phạm vi để user review; không suy giá thành ngân sách hoặc đặc điểm tour thành sở thích. Đề xuất tương tự phải nói rõ cơ sở, không gọi là tối ưu cá nhân.
- Tour URL được giữ/so chung, không tự được kết luận phù hợp. Canonical dedup giữ cả nguồn gốc và offer; tour đã có từ URL không lặp thành gợi ý mới để lấp đủ ba.

## Muốn tìm lại

- **Tìm phương án khác:** Giữ criteria/revision và URL; BE trả nhóm tiếp theo có căn cứ, loại các đề xuất đã xem theo canonical tour identity. Reuse pool/snapshot còn hợp lệ hoặc retrieval thêm trong budget; không có nhóm mới thì nói rõ, không trả lại nhóm cũ như thể mới.
- **Sửa nhu cầu / URL:** Giữ draft, review thay đổi rồi tìm/đánh giá/rank/so sánh lại. Không tự nới hard constraints để đủ ba; đề xuất của nhu cầu cũ không mặc định bị loại trong nhu cầu mới.
- **Thử lại nguồn lỗi / cập nhật dữ liệu:** Khác tìm phương án khác; vẫn có thể ra tour cũ sau khi làm mới. Chỉ reuse snapshot hợp lệ; đổi URL/offer làm mới phần phụ thuộc.

Contract vòng kết quả/exclusion/budget/coverage/retry còn G9/G10; chưa đặt endpoint/enum/key mới. Mỗi lần chạy giữ snapshot riêng; kết quả trước còn xem được khi đang chờ.

## Các tổ hợp đầu vào

| Đầu vào | Cùng flow tự động |
|---|---|
| Chỉ nhu cầu | Hiểu/làm rõ → review → tìm/rank/so sánh tối đa ba đề xuất |
| Nhu cầu + URL | Đọc các tour URL, tìm/rank gợi ý mới → so chung cùng criteria |
| Chỉ URL, kể cả một URL | Đọc tour → gợi ý phạm vi có nguồn → review → tìm thêm và so chung |
| Không nhu cầu, không URL | Giữ màn nhập, hướng dẫn bổ sung ít nhất một loại đầu vào |

URL khác tuyến/dữ liệu không đủ thì hỏi phạm vi, không tự lấy giao mọi tuyến. Nhu cầu nêu rõ được ưu tiên; không ép ngày/party/budget nếu không cần. Chỉ làm rõ phần cần truy vấn; blocker đánh giá không làm mất dữ kiện tĩnh. Không hard filter thì không gắn “đạt nhu cầu”.

## Quy tắc thao tác / backend hiện tại

- Một draft nhu cầu + URL; text/form là hai cách sửa nhu cầu, không gửi cả hai ghi đè nhau. Validation theo field/URL, giữ input khi lỗi.
- Draft khác committed revision/result snapshot; sửa nhu cầu không đổi ý nghĩa kết quả cũ. Response/job cũ không ghi đè lượt mới; giữ IDs, hủy chờ FE không đồng nghĩa BE dừng.
- Text patch lỗi/hủy giữ revision trước; 409 thì GET mới và giữ draft để review, không tự retry ghi đè. Khôi phục đúng context cũ còn G6.
- URL lỗi không làm mất gợi ý tìm thêm; retrieval lỗi không làm mất URL đã đọc. Giữ tham chiếu lỗi/lý do và cách thử lại.
- Giá/ngày/evidence đổi cùng offer snapshot; thiếu giá/phụ thu không tự tính thay BE. Evidence đóng về phần tử mở; URL mở nguồn phải được kiểm tra.
- V1 discover không nhận URL; compare_urls nhận 2–5 nhưng không retrieval thêm. Engine có evaluations/groups/trade-off, chưa ranking/Top 3. G9/G10 mở rộng thu thập chung, nhóm tự động/vòng phương án khác/budget; không nối hai response tại FE.
- V1 xác nhận dùng committed revision/readiness để tạo comparison, chưa endpoint confirm riêng. Giữ lifecycle v1 làm nền, không tự đặt DTO mới; G1–G8/D1–D5 vẫn còn.

## Ma trận trạng thái

Các tên UI dưới đây là mô tả trạng thái local, **không phải enum mới của API**.

| Tình huống | UI / hành động tiếp theo |
|---|---|
| Input thiếu/sai | Lỗi theo field/URL, focus tới lỗi; giữ các giá trị hợp lệ |
| Criteria mơ hồ | Hiển thị câu hỏi và lý do; dùng can_collect_data cho thu thập, can_evaluate_hard_constraints/blockers cho kết luận; không gom thành một boolean “ready” |
| Parse revision 0 | Poll parse job, chưa render như Requirement đầy đủ hoặc chạy comparison; lỗi giữ input để sửa |
| Đang xử lý | Skeleton/phase thật; source progress chưa streaming, không hiển thị phần trăm giả |
| Thành công | BE tự chọn tối đa 3 đề xuất và so sánh ngay, giữ tour URL tham chiếu/lý do/evidence |
| Không có phương án mới | Giữ kết quả trước và báo rõ đã hết lựa chọn đủ điều kiện trong phạm vi/budget; cho sửa nhu cầu |
| Chưa đủ 3 đề xuất | Đề xuất đúng số tour đủ điều kiện; phần không đạt/cần xác minh vẫn xem được và có lý do, không tạo lựa chọn giả |
| Không hard filter | Xem đề xuất có cơ sở/phạm vi dù groups rỗng; không gắn “đạt nhu cầu”, không suy empty từ số eligible |
| Nhiều offers chưa chọn | Tour tĩnh vẫn hiện; ô ngày/giá phụ thuộc offer chưa kết luận; cho chọn snapshot |
| Một phần nguồn thất bại | Giữ tour thành công, nêu URL/nguồn lỗi và cách thử lại; không giấu lỗi |
| Không tìm thêm được tour | Giữ tour URL đã đọc; phân biệt không phù hợp với lỗi retrieval; cho sửa phạm vi |
| Không có tour phù hợp | Nêu lý do đã biết và cho sửa criteria; giữ URL cung cấp để xem lý do, phân biệt với lỗi truy xuất |
| Chỉ có 1 tour | Hiển thị dữ kiện và giới hạn so sánh; không tạo trade-off giữa nhiều lựa chọn |
| Toàn bộ source attempts thất bại | Job failed SOURCES_UNAVAILABLE, result có thể null; lỗi truy xuất, không nói “không có tour phù hợp” |
| Không nguồn được hỗ trợ | Job có thể succeeded + NO_SUPPORTED_TARGETS; giữ URL/reason, cho đổi URL; không gọi là không có tour trên thị trường |
| Mất mạng/timeout | Giữ input; thông báo có thể thử lại. Nếu có job, kiểm tra trạng thái trước khi tạo job trùng |
| Dữ liệu thiếu/một phần | Nhãn chữ và chi tiết field; không suy ra giá trị hoặc bỏ hàng tiêu chí |
| Dữ liệu cũ/chưa có policy freshness | Hiển thị timestamp; chỉ gắn “cũ” khi có policy đã chốt |
| Nguồn tự công bố/chưa xác minh độc lập | Nêu đúng trạng thái bằng chứng; không đổi thành dấu “đã xác minh” chung cho tour |
| Cancel / response đến muộn | Đọc response cancel; dừng poll terminal, không ghi kết quả cũ đè màn mới; đóng tab không phải cancel |
| Revision/answer/offer cũ | Giữ draft/kết quả trước; GET revision hoặc tải nguồn lại; cho review trước khi submit mới |
| Phiên hết hạn / resource mất | Xử lý 401/404, giữ draft theo policy; phiên mới không lấy lại result phiên cũ |

Fact data_state, completeness, verification là các trục riêng; freshness chưa public đủ mọi ô (G5). Trạng thái API queued/running/succeeded/partial/failed/cancelled khác trạng thái đánh giá pass/fail/unknown và eligibility. Empty_reason có thể ALL_INELIGIBLE/ONLY_UNVERIFIED trong khi vẫn có candidates; giữ dữ kiện/lý do để người dùng xem.

## Điểm review ở P1

- [ ] FLOW-1 — Control text/form, catalog/range/± ngày/budget/party/hard/soft/AND/OR; giữ G4/G7.
- [x] FLOW-2 — Theo sửa đổi của user: nhập chung → review → BE tự tìm/rank/so sánh ngay; bỏ chọn 2–3 tour, có tìm phương án khác/sửa nhu cầu. Contract G9/G10 còn mở.
- [ ] FLOW-3 — Review budget 20, cách đếm URL tham chiếu + ba gợi ý, ranking/vòng phương án khác/offer/binding G9/G10 và metadata/trade-off G2/G3.
- [ ] FLOW-4 — Revision/parse/answers/edits, cancel/retry/idempotency, response cũ/conflict, polling và exclusion vòng cũ.
- [ ] FLOW-5 — Route/back/refresh/token/IDs/hết hạn, đúng revision và result round; giữ G6.
- [ ] FLOW-6 — Mobile kết quả/so sánh tự động, tham chiếu URL và evidence; không thiết kế màn chọn tour.

## Walkthrough

Nhập nhu cầu/URL → đề xuất và bảng đối chiếu ngay, có lý do/evidence. Không cần sàng lọc danh sách hay chọn ba tour. Không đồng ý thì tìm phương án khác hoặc sửa yêu cầu. Giữ tour tham chiếu để so chung; thiếu/cũ/nguồn lỗi/coverage có giới hạn và hành động rõ.
