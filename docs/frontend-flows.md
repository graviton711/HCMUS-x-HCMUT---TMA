# Luồng và trạng thái frontend

**Trạng thái:** Flow để review P1, đã đối chiếu backend `0b7e59f` ngày 03/10/2026. Bám wireframe đã chốt; hành vi FE còn mở giữ ở FLOW-1–6, field BE thiếu giữ G1–G8.
**Liên quan:** [planning](frontend-plan.md), [wireframe](wireframes.md), [checklist FE–BE](frontend-backend-checklist.md), [API v1 và payload](frontend-api-integration.md).

## Màn hình và hai luồng

| Bề mặt | Người dùng làm gì | Frontend cần gì |
|---|---|---|
| Input: tìm theo nhu cầu | Text hoặc form điểm đi/đến, ngày, nhóm khách, ngân sách, điều kiện và ưu tiên | Typed conditions/party/trees; scope đủ để tìm; catalog và rule UI còn C1/G4 |
| Input: so sánh URL | Dán/chỉnh 2–5 URL và nhu cầu tùy chọn | Syntax/duplicate validation; targets có stable IDs; canonical dedup còn C5 |
| Làm rõ / xác nhận | Sửa cách hiểu Bắt buộc/Ưu tiên/Cần làm rõ | Committed revision, clarifications/options/answers hoặc edits, readiness; giữ AND/OR |
| Đang xử lý | Nhìn thấy parse hoặc comparison đang chạy; sửa/hủy theo policy | Job status/phase/deadline, cancel; source progress chỉ có cuối job |
| Kết quả | Đối chiếu tour/offer, trạng thái ràng buộc và trade-off | Targets/candidates/evaluations/groups; giá/tên/nguồn/chính sách chưa đủ giữ G1–G3 |
| Panel evidence | Kiểm tra một nhận định hoặc field, mở nguồn | Reference chính xác, dữ kiện nguồn, thời điểm, trạng thái xác minh |

Đề xuất tổ chức Input và Results là hai màn; Processing là trạng thái chuyển tiếp, Evidence là panel trong Results. Route cụ thể và khôi phục khi refresh chốt ở P2; không tự thêm dashboard/profile/booking.

**Luồng nhu cầu:** Tạo session → nhập text hoặc form → POST requirement → nếu text: poll parse job rồi GET requirement → review/sửa/làm rõ → khi can_collect_data: POST comparison theo revision đã commit → poll job → GET comparison → evidence hoặc sửa/chạy lại. Còn blocker thì hiển thị dữ kiện và hạn chế kết luận; không bỏ điều kiện chưa hiểu.

**Luồng URL:** Tạo session → nhập 2–5 URLs và nhu cầu tùy chọn → POST requirement (chỉ URL/form nhận ngay revision, text thêm parse job) → POST comparison → poll/GET result → chọn offer qua reuse nếu cần → evidence hoặc sửa/thử lại URL lỗi. Không có hard condition thì filter_applied=false, eligibility=null; vẫn đối chiếu candidates, không gọi kết quả là “đạt nhu cầu”.

UI “xác nhận” dùng revision đã commit để tạo comparison, chưa có endpoint confirm riêng. Discovery cần scope truy vấn dương (điểm đến/nhà cung cấp); không mặc định ngày/party/budget bắt buộc. Không chờ mọi clarification mới thu thập nếu can_collect_data=true. Giá URL-only chưa public dù nội bộ có quotes: giữ hàng giá và yêu cầu G1, không ép user nhập budget để né thiếu contract.

Frontend không tự hiểu điều kiện như “không transit” thành kết luận đạt nếu backend chưa có cách đánh giá có căn cứ. Việc chuyển dữ liệu người dùng thành criteria và hỏi lại phải có trách nhiệm rõ ở C1–C3.

## Quy tắc thao tác đề xuất

- Đổi tab giữ draft riêng cho từng kiểu nhập; không âm thầm chuyển dữ liệu giữa hai kiểu.
- Validation hiện ngay tại field; lỗi một URL chỉ ra URL đó. Giữ input để sửa, không reset toàn bộ form khi request lỗi.
- Criteria đã submit và draft đang sửa là hai snapshot khác nhau; kết quả luôn ghi rõ criteria dùng để tạo nó.
- Text patch giữ committed revision đến parse thành công; lỗi/hủy giữ bản trước. Khi 409 revision/clarification conflict, GET mới và giữ draft để review, không tự retry ghi đè. Đổi mode tạo requirement mới.
- Submit mới vô hiệu kết quả request cũ. Chốt hủy phía BE riêng; hủy chờ ở trình duyệt không mặc định là BE đã dừng xử lý.
- Giữ `requirement_id/revision/job_id/comparison_id` cho từng lần chạy; response/job cũ có thể cập nhật snapshot cũ nhưng không ghi đè màn đang chạy snapshot mới. Cần G6 để refresh vẫn lấy party/trees đúng revision cũ.
- Sửa tiêu chí làm rõ kết quả cũ chưa ứng với draft mới; chạy lại các bước cần BE tính/lọc. Sắp xếp chỉ ở FE nếu đã nhận đủ tập kết quả và quy tắc cho phép.
- Giữ cùng tiêu chí giữa các tour; khi một tour có nhiều offer, chỉ rõ offer đang đối chiếu và đổi đúng giá/ngày/evidence cùng nhau.
- URL nhiều offer chưa chọn: giữ dữ kiện tour, ô phụ thuộc offer nêu MULTIPLE_OFFERS_UNSELECTED; chọn từ offer_options, POST comparison mới kèm reuse_comparison_id. Discovery có candidate từng offer; không gửi offer_selections theo target. Không chọn offer rẻ nhất ngầm.
- Giữ cột URL bị blocked/unsupported/error và lý do; trong discovery có thể xem tour bị loại/cần xác minh. Đổi targets hoặc revision discovery cần thu thập mới; stale selection cho tải lại nguồn, không âm thầm đổi offer.
- Evidence đóng về đúng phần tử mở nó; panel trên mobile không che lối quay lại và giữ được nhãn tour/field.
- Mở trang nhà cung cấp/nguồn bằng URL từ dữ liệu đã kiểm tra; không biến thao tác này thành đặt tour.

## Ma trận trạng thái

Các tên UI dưới đây là mô tả trạng thái local, **không phải enum mới của API**.

| Tình huống | UI / hành động tiếp theo |
|---|---|
| Input thiếu/sai | Lỗi theo field/URL, focus tới lỗi; giữ các giá trị hợp lệ |
| Criteria mơ hồ | Hiển thị câu hỏi và lý do; dùng can_collect_data cho thu thập, can_evaluate_hard_constraints/blockers cho kết luận; không gom thành một boolean “ready” |
| Parse revision 0 | Poll parse job, chưa render như Requirement đầy đủ hoặc chạy comparison; lỗi giữ input để sửa |
| Đang xử lý | Skeleton/phase thật; source progress chưa streaming, không hiển thị phần trăm giả |
| Thành công | So sánh dữ kiện cùng tiêu chí; mọi trade-off mở được evidence |
| Không hard filter | Hiển thị candidates dù groups rỗng; không gắn “đạt nhu cầu”, không suy empty từ số eligible |
| Nhiều offers chưa chọn | Tour tĩnh vẫn hiện; ô ngày/giá phụ thuộc offer chưa kết luận; cho chọn snapshot |
| Một phần nguồn thất bại | Giữ tour thành công, nêu URL/nguồn lỗi và cách thử lại; không giấu lỗi |
| Không có tour phù hợp | Nêu lý do đã biết và cho sửa criteria; phân biệt với nguồn không lấy được dữ liệu |
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

- [ ] FLOW-1 — Chốt control text/form, catalog/range/± ngày, budget basis/coverage, party và hard/soft/AND/OR; giữ G4/G7.
- [ ] FLOW-2 — URL đã 2–5, criteria tùy chọn; chốt số cột discovery, canonical dedup, UI không filter và hàng giá cần G1.
- [ ] FLOW-3 — Review URL offer reuse và discovery candidate từng offer; cách xem pass/fail/unknown, tour bị loại/lý do, metadata/trade-off còn G2/G3.
- [ ] FLOW-4 — Review revision/text parse/answers/edits, cancel/retry/idempotency, response cũ và conflict giữ draft; chốt polling policy.
- [ ] FLOW-5 — Chốt route/back/refresh, token/IDs persistence, đúng revision và hết hạn; thiếu public revision context giữ G6.
- [ ] FLOW-6 — V1 chỉ session ẩn danh, chốt placeholder đăng nhập; phương án mobile comparison/evidence vẫn cần thiết kế/review.

## Tiêu chí walkthrough

Người dùng có thể nhập một nhu cầu hoặc nhóm URL, biết kết quả dựa trên criteria nào, đối chiếu đúng giá/ngày, tìm một trade-off và kiểm tra nguồn tương ứng. Khi dữ liệu thiếu/cũ/nguồn lỗi, họ hiểu hạn chế và biết thao tác tiếp theo.
