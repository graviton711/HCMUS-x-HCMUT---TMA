# Luồng và trạng thái frontend

**Trạng thái:** PLANNING, sửa ngày 06/10/2026 theo review nhóm: chốt Giấy & Mực; Giới thiệu → form + xác nhận → Kết quả. Review không còn là màn riêng; bỏ stepper. V1 còn tách mode/chưa ranking/chat preview/phân tích/activity; G9–G13 cần chốt. Budget 20 và cách đếm tour URL vẫn là đề xuất, chưa benchmark hoặc implement.
**Liên quan:** [wireframe](wireframes.md), [giao thức v2](frontend-protocol-v2.md), [API v1](frontend-api-integration.md).

## Flow mặc định

**Giới thiệu → Tìm tour → form nhu cầu + URL tùy chọn, review và xác nhận tại chỗ → màn Kết quả hiển thị log xử lý → tối đa 3 gợi ý/bảng kiểm chứng/Phân tích AI → evidence hoặc trao đổi qua chat.**

| Bề mặt | Người dùng làm gì | Dữ liệu / trách nhiệm |
|---|---|---|
| 1. Giới thiệu | Xem dự án, tour minh họa, hướng dẫn/demo; nhấn Tìm tour | Widget vị trí/thời tiết minh họa có loading/từ chối quyền/fallback; provider/API/video thật chưa chốt, không chặn tìm |
| 2. Form + xác nhận | Điền field bắt buộc/tùy chọn, chat ghi chú; review criteria/phạm vi và xác nhận ngay form | Một draft chung, validation từng field, default có nhãn; committed revision/readiness giữ hard/soft/AND/OR |
| 3. Kết quả + so sánh | Sửa criteria trực tiếp hoặc chat tại cột yêu cầu rộng; xem bảng kiểm chứng và tab Phân tích AI | BE chọn nhóm tối đa ba gợi ý, giữ URL tham chiếu; phân tích/phép tính dùng cùng revision/offer/evidence |
| Processing trong màn 3 | Theo dõi nhật ký bước xử lý/skeleton, hủy hoặc thử lại lỗi | Prototype dùng log mock có nhãn; runtime chỉ phase/activity thật từ BE, không phần trăm giả (G13) |
| Evidence panel | Kiểm tra một field/nhận định và mở nguồn | Reference đúng tour/offer/field, dữ kiện nguồn/thời điểm/giới hạn |

Ba màn chính: Giới thiệu, form + xác nhận, Kết quả/so sánh; Evidence là panel. Cột yêu cầu màn 3 khoảng 340–380px/~30% desktop, mobile xếp dọc; bảng cuộn riêng. Bỏ Sửa yêu cầu/Lưu bản nháp/Tìm lại và thanh “1 nhu cầu / 2 xác nhận / 3 so sánh”. Phiên ẩn danh; route/back/refresh còn P2. Field/catalog/tên biến có thể đổi sau, không đồng nghĩa contract đã chốt.

## Form và criteria mặc định

- Bộ field mẫu cá nhân hóa: bắt buộc điểm đến/nơi khởi hành/ngày dự kiến/người lớn/ngân sách mỗi người lớn; mặc định hiển thị thời lượng ưu tiên 5 ngày, trẻ em 0, ngân sách là ưu tiên với coverage giá tour. Khách sạn/mua sắm/URL/ghi chú là tùy chọn. Mapping/validation/strength cần C1/G4, chưa sửa contract.
- Cột yêu cầu giữ đủ hàng tiêu chí/default/giá trị chưa biết và nhãn bắt buộc/ưu tiên; không giấu blocker hoặc tự bổ sung dữ kiện. Trẻ em >0 cần tuổi để đánh giá giá, unknown giữ blocker.
- Form/chat sửa cùng draft; chỉ gửi một biểu diễn theo contract, không text/form ghi đè nhau. Chat nhỏ ở form ghi thêm lưu ý, không tự biến ghi chú mơ hồ thành hard constraint.
- URL-only giữ trong kế hoạch: review phạm vi có nguồn, không ép bộ field cá nhân hóa hoặc suy ngân sách/sở thích từ tour. Prototype fixture Nhật Bản có nhãn và giới hạn, nhập khác không giả có retrieval thật.

## Chat và sửa trực tiếp tại kết quả

1. Phân biệt câu hỏi về snapshot đang xem, đổi criteria và yêu cầu nhóm khác. Prototype nhận một số câu mẫu có nhãn; LLM/context/runtime còn G11.
2. Sửa trực tiếp hoặc chat tạo đề xuất **trước → sau**; bảng criteria giữ nguyên đến khi user xác nhận. Có Hủy; câu mơ hồ yêu cầu làm rõ. Không dùng PATCH text v1 để preview vì parse thành công sẽ commit.
3. Sửa field/slider/chat tạo diff và tự cuộn/focus đến khung xác nhận. Xác nhận commit atomic theo expected revision; nút Tìm kiếm hoặc lệnh chat mới chạy theo criteria đã xác nhận. Câu vừa sửa vừa yêu cầu tìm đợi confirm rồi chạy. Proposal hết hiệu lực khi context thay đổi; conflict giữ draft, không tự ghi đè. Revision giữ nội bộ, UI dùng thông báo kết quả theo yêu cầu trước.
4. Kết quả cũ gắn revision đã đánh giá, còn xem khi lượt mới chờ/lỗi/hủy. Response muộn không thay lượt mới; không tự nới ràng buộc để đủ ba tour.
5. Yêu cầu nhóm khác qua chat giữ criteria/URL, loại các tour đã xem và báo hết nhóm. Retry lỗi tác vụ/nguồn vẫn là hành động riêng.

## Tab Phân tích AI

- Bảng kiểm chứng giữ dữ kiện cùng hàng/evidence; tab bổ sung kết luận có căn cứ, đánh đổi, điều kiện áp dụng và điều chưa biết. Không trình bày suy nghĩ nội bộ hoặc thêm điểm/trọng số chưa chốt.
- Phép tính so giá phải giữ cùng basis/coverage/currency/offer; hiện operands và evidence. Ước tính cho số người lớn ghi giới hạn phụ thu/trẻ em, không gọi là tổng cuối.
- Đổi offer cập nhật giá/ngày/evidence/phép tính cùng snapshot. Criteria sửa không biến snapshot revision cũ thành đã phân tích lại. Backend G3/G10/G12 phải đủ trước runtime.

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

## Đổi yêu cầu hoặc nhóm gợi ý

- **Nhóm khác qua chat:** Giữ criteria/revision và URL; BE trả nhóm tiếp theo có căn cứ, loại các đề xuất đã xem theo canonical tour identity. Reuse pool/snapshot còn hợp lệ hoặc retrieval thêm trong budget; không có nhóm mới thì nói rõ, không trả lại nhóm cũ như thể mới.
- **Sửa criteria trực tiếp / qua chat:** Giữ draft, review diff và xác nhận trước khi chạy lại. Không tự nới hard constraints để đủ ba; đề xuất của nhu cầu cũ không mặc định bị loại trong nhu cầu mới.
- **Thử lại nguồn lỗi / cập nhật dữ liệu:** Khác tìm phương án khác; vẫn có thể ra tour cũ sau khi làm mới. Chỉ reuse snapshot hợp lệ; đổi URL/offer làm mới phần phụ thuộc.

Contract vòng kết quả/exclusion/budget/coverage/retry còn G9/G10; chưa đặt endpoint/enum/key mới. Mỗi lần chạy giữ snapshot riêng; kết quả trước còn xem được khi đang chờ.

## Các tổ hợp đầu vào

| Đầu vào | Cùng flow tự động |
|---|---|
| Chỉ nhu cầu | Hiểu/làm rõ → review → tìm/rank/so sánh tối đa ba đề xuất |
| Nhu cầu + URL | Đọc các tour URL, tìm/rank gợi ý mới → so chung cùng criteria |
| Chỉ URL, kể cả một URL | Đọc tour → gợi ý phạm vi có nguồn → review → tìm thêm và so chung |
| Không nhu cầu, không URL | Giữ màn nhập, hướng dẫn bổ sung ít nhất một loại đầu vào |

URL khác tuyến/dữ liệu không đủ thì hỏi phạm vi, không tự lấy giao mọi tuyến. Nhu cầu nêu rõ được ưu tiên; URL-only không ép ngày/party/budget. Bộ field bắt buộc của form cá nhân hóa còn C1, không biến thành quy tắc validate mới của API. Blocker đánh giá không làm mất dữ kiện tĩnh; không hard filter thì không gắn “đạt nhu cầu”.

## Quy tắc thao tác / backend hiện tại

- Một draft nhu cầu + URL; text/form là hai cách sửa nhu cầu, không gửi cả hai ghi đè nhau. Validation theo field/URL, giữ input khi lỗi.
- Draft khác committed revision/result snapshot; sửa nhu cầu không đổi ý nghĩa kết quả cũ. Response/job cũ không ghi đè lượt mới; giữ IDs, hủy chờ FE không đồng nghĩa BE dừng.
- Text patch lỗi/hủy giữ revision trước; 409 thì GET mới và giữ draft để review, không tự retry ghi đè. Khôi phục đúng context cũ còn G6.
- URL lỗi không làm mất gợi ý tìm thêm; retrieval lỗi không làm mất URL đã đọc. Giữ tham chiếu lỗi/lý do và cách thử lại.
- Giá/ngày/evidence đổi cùng offer snapshot; thiếu giá/phụ thu không tự tính thay BE. Evidence đóng về phần tử mở; URL mở nguồn phải được kiểm tra.
- V1 discover không nhận URL; compare_urls nhận 2–5 nhưng không retrieval thêm. Engine có evaluations/groups/trade-off, chưa ranking/Top 3. G9/G10 mở rộng thu thập chung, nhóm tự động/vòng phương án khác/budget; không nối hai response tại FE.
- V1 xác nhận dùng committed revision/readiness để tạo comparison, chưa endpoint confirm riêng hoặc chat preview không commit. G11–G13 ghi phần còn thiếu, không tự đặt DTO mới; G1–G10/D1–D5 vẫn còn.

## Ma trận trạng thái

Các tên UI dưới đây là mô tả trạng thái local, **không phải enum mới của API**.

| Tình huống | UI / hành động tiếp theo |
|---|---|
| Input thiếu/sai | Lỗi theo field/URL, focus tới lỗi; giữ các giá trị hợp lệ |
| Criteria mơ hồ | Hiển thị câu hỏi và lý do; dùng can_collect_data cho thu thập, can_evaluate_hard_constraints/blockers cho kết luận; không gom thành một boolean “ready” |
| Parse revision 0 | Poll parse job, chưa render như Requirement đầy đủ hoặc chạy comparison; lỗi giữ input để sửa |
| Đang xử lý / chậm | Skeleton + nhật ký bước mock có nhãn trong prototype; runtime phase/activity thật, source progress v1 chưa streaming (G13), không phần trăm giả |
| Chat/sửa trực tiếp | Diff → xác nhận/hủy; mơ hồ làm rõ, stale proposal/conflict giữ criteria, chat hỏi dùng đúng snapshot (G11) |
| Widget giới thiệu | Mock loading/ready/từ chối quyền/error; fallback vẫn cho Tìm tour, không đọc vị trí thật trong prototype |
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
- [x] FLOW-2 — Theo review 06/10: Giới thiệu → form + xác nhận → BE tự tìm/rank/so sánh; sửa criteria/chat/diff, bảng + Phân tích AI, bỏ stepper/chọn tour thủ công. Contract G9–G13 còn mở.
- [ ] FLOW-3 — Review budget 20, cách đếm URL tham chiếu + ba gợi ý, ranking/vòng phương án khác/offer/binding G9/G10 và metadata/trade-off G2/G3.
- [ ] FLOW-4 — Revision/parse/answers/edits, chat preview/commit atomic/cancel/stale proposal, response cũ/conflict, polling/activity và exclusion vòng cũ (G11/G13).
- [ ] FLOW-5 — Route/back/refresh/token/IDs/hết hạn, đúng revision và result round; giữ G6.
- [ ] FLOW-6 — Mobile kết quả/so sánh tự động, tham chiếu URL và evidence; không thiết kế màn chọn tour.

## Walkthrough

Giới thiệu → Tìm tour → form bắt buộc/tùy chọn + chat ghi chú → review và xác nhận tại chỗ → nhật ký xử lý → bảng kiểm chứng/Phân tích AI/evidence. Sửa trực tiếp/chat tạo diff trước xác nhận; nhóm khác qua chat. Giữ tour tham chiếu và snapshot revision cũ khi chờ/lỗi/hủy; dữ kiện thiếu/cũ/nguồn lỗi/coverage có giới hạn rõ.
