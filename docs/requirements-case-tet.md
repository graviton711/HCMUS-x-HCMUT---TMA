# Ca test extraction: tour ghép đoàn dịp Tết

Trạng thái: giữ baseline review ngày 07/10/2026 bên dưới; semantic v2 đã implement và kiểm chứng ngày 08/10/2026. Baseline thử một lượt qua `/v2/requirements` → worker NIM → proposal, DB tạm, không confirm/comparison/crawl. Parser cũ `vi-conditions-v5`, model `nvidia/nemotron-3-super-120b-a12b`; có một repair. [Test runtime mới](../examples/backend-semantic-v2.md), [kết quả kiểm chứng](requirements-evaluation.md).

## Input nguyên văn

> Tết Nguyên đán năm nay e dự định đi du lịch ghép đoàn bằng xe ô tô từ Hải Phòng đi dọc miền trung vào Đà Nẵng hoặc Tây Nguyên.
> Cty nào uy tín và dv tốt, giá hợp lý, tour có các điểm đẹp gần gũi thiên nhiên e tham khảo ạ.
> Từ 27/12 âm đến mùng 4 Tết ạ.

## Kết quả mong đợi — ý nghĩa, chưa phải DTO mới

| Ý user | Điều cần giữ / không được tự suy |
|---|---|
| Từ Hải Phòng | Origin Hải Phòng, không đảo thành điểm đến. Đây là địa danh rõ, thiếu catalog là lỗi backend, không phải user thiếu thông tin |
| Đà Nẵng hoặc Tây Nguyên | OR/contains_any; không AND, không chỉ giữ Đà Nẵng hoặc tự chọn một thành phố Tây Nguyên |
| Đi dọc miền Trung | Giữ ý hành trình/corridor; chưa ép mọi tour phải ghé một danh sách điểm cụ thể. Cần xác định đây là yêu cầu route bắt buộc hay mô tả |
| Bằng xe ô tô | Phương tiện đường bộ/ô tô; chưa suy số chỗ hoặc loại xe khách cụ thể. Catalog/crawler cần thống nhất taxonomy phương tiện |
| Du lịch ghép đoàn | Lưu yêu cầu loại tour, báo rõ khả năng hỗ trợ/filter; không âm thầm bỏ hoặc gán vào included_services |
| Tết năm nay, 27/12 âm → mùng 4 | User đã xác nhận đây là khoảng có thể đi. Giữ calendar=lunar/holiday + raw text; năm cần rõ trước khi đổi ngày. Tháng 12 âm thuộc năm âm trước Tết. Không hiểu 27/12 là ngày dương, không tự đặt duration |
| Giá hợp lý | Ưu tiên định tính, chưa có số tiền/currency/basis; không tạo cap, không tự gán slider cost=4/5 hoặc đồng nhất hoàn toàn với rẻ nhất |
| Công ty uy tín, dịch vụ tốt, thiên nhiên | Giữ các preferences có quote; metric/evidence chưa có thì unsupported/unresolved. Không tự gán trust score, hotel_stars hoặc tên công ty |
| Số người/tuổi/phòng | Chưa được nói; không suy một người lớn từ đại từ “e” |

User đã xác nhận: khoảng 27/12–mùng 4 là **thời gian có thể đi**. Sau khi resolve calendar/year, điều kiện đúng là departure_date >= ngày bắt đầu và return_date <= ngày kết thúc; không ép eq hai ngày hoặc tự yêu cầu tour kéo dài toàn bộ khoảng. Câu hỏi còn mở: Tết năm nào (câu trích có thể từ bài cũ)?

## Kết quả runtime trong lượt thử

`job.status=succeeded`, `proposal.status=needs_clarification`, `can_collect_data=false`, `can_evaluate_hard_constraints=false`.

| Condition đã trích | Giá trị sau normalize | Reason |
|---|---|---|
| departure_origin/in, Hải Phòng | unresolved | UNKNOWN_ENTITY |
| destinations/contains_any, Đà Nẵng + Tây Nguyên | unresolved cả nhóm | UNKNOWN_ENTITY |
| transport/in, xe ô tô | unresolved | UNKNOWN_ENTITY |
| departure_date/eq, 27/12 âm | unresolved | DATE_NEEDS_CLARIFICATION; clarification hiện DATE_YEAR_REQUIRED |
| return_date/eq, mùng 4 Tết | unresolved | DATE_NEEDS_CLARIFICATION |

Raw extraction giữ OR và không tự invent số tiền/người/ngày dương. Catalog hiện thiếu Hải Phòng, Tây Nguyên, xe ô tô; nhóm destination normalize thất bại cả nhóm dù Đà Nẵng có alias. Câu hỏi về ngày chỉ hỏi năm là chưa đủ để giải quyết lịch âm và window.

Sau xác nhận của user, hai date predicates eq trong lượt thử sai ý availability; cần gte/lte và lịch âm/năm đã resolve. Đây là semantic failure, dù value hiện chưa được đổi thành ngày dương.

Trong output lượt này không có điều kiện/preference riêng cho ghép đoàn, uy tín, dịch vụ tốt, giá hợp lý, thiên nhiên. Quote destination có “miền trung” nhưng không có route constraint riêng. Parse thành công về kỹ thuật chưa đạt coverage/semantic expectations.

## Cách người dùng test lại

### Đối chiếu response người dùng tải

File được review: `C:/Users/Admin/Downloads/response_1791384047993.json`, received_at `2026-10-07T14:38:51.208782+00:00`. DTO Proposal validate thành công; mọi source quote/span khớp message. Có 5 conditions, cả 5 unresolved; 0 soft conditions, preference tree rỗng, preference_levels=null, notes rỗng; 6 clarifications. `base_revision=0`, preview revision 1 là bản nháp, proposal version 2; chưa có bản nhu cầu đã confirm từ response này.

Kết quả trùng các khoảng thiếu trong probe trước: đúng field cơ bản/contains_any/provenance/không invent số người; chưa normalize origin/transport/destination, eq hai ngày sai ý availability đã được user xác nhận, các yêu cầu định tính và tour type/route chưa được biểu diễn đầy đủ. `UNKNOWN_ENTITY` không phân biệt catalog thiếu với input mơ hồ; `SEARCH_SCOPE_REQUIRED` hỏi lại nơi đến dù user đã nêu, do mất cả OR group khi một entity chưa biết.

Unresolved.value.raw là quote cả cụm, không expose raw_values từng entity; không thể kết luận từ response này model đã tách entity đúng hay alias lookup thiếu ở từng nhánh. Cần giữ raw entity slots và resolver status để debug phần này, không sửa bằng cách yêu cầu user nói lại Hải Phòng. Không tự quy đổi “xe ô tô” thành loại xe coach cụ thể.

Đánh giá: schema/provenance đạt, đủ để kiểm thử luồng proposal; semantic coverage/normalization/temporal chưa đạt cho ca lọc tour. Không chấm accuracy phần trăm từ một file. Fix cần đi cùng gold assertions về coverage, OR, availability gte/lte, calendar/year và clarification responsibility.

1. POST `/v2/sessions`, Authorize SessionBearer bằng `data.token`.
2. POST `/v2/requirements`: `input.kind=text`, `input.text` nguyên văn trên, timezone `Asia/Ho_Chi_Minh`.
3. Chờ GET `/v2/jobs/{job_id}` terminal; nếu failed, tách lỗi NIM/schema khỏi đánh giá semantic.
4. GET `/v2/proposals/{proposal_id}`: kiểm tra preview.conditions/hard_tree/preference_tree/party, sources.quote, clarifications/readiness. Không cần confirm/comparison để test extraction.
5. Đối chiếu bảng ý nghĩa mong đợi, ghi phần đúng/thiếu/sai. Không dùng `succeeded` hoặc JSON hợp lệ làm tiêu chí duy nhất.

## Hướng cải thiện để thảo luận

- Catalog địa danh/phương tiện đồng bộ crawler; giữ nhánh OR đã biết và nhánh chưa resolve thay vì mất cả nhóm. Không map ô tô thành coach khi chưa đủ nghĩa.
- Intent representation giữ qualitative preferences, tour type và route; coverage audit phát hiện ý user bị bỏ, với quote nguyên văn. Chưa có metric vẫn giữ để giải thích giới hạn.
- Temporal representation tách calendar/year/holiday/window semantics khỏi solar DateValue; clarification đúng thiếu gì, converter lịch âm xác định sau khi year/window được resolve. Chặn lunar quote đi qua solar parser nhầm.
- Gold tests chia bước raw extraction → normalization → clarify/readiness; thêm biến thể có năm, available window vs exact dates, OR vs AND. Chạy NIM nhiều lượt và report từng assertion/repair/latency, không chỉ schema pass.

Tại thời điểm review baseline, chưa chốt schema/converter hoặc criteria cho uy tín/giá hợp lý. Các thay đổi sau đó được mô tả ở contract semantic; phần baseline này giữ nguyên làm đối chiếu.

## Lượt bổ sung câu làm rõ khoảng thời gian

File review: `C:/Users/Admin/Downloads/response_1791384696942.json`, received_at `2026-10-07T14:50:45.188823+00:00`. Input thêm ý được đi bất kỳ ngày nào từ 27/12 âm, phải kết thúc không muộn hơn mùng 4, không ép đúng hai ngày biên.

- departure_date đổi eq → gte; return_date đổi eq → lte, đúng availability đã xác nhận. Chưa có ngày chuẩn: cả hai unresolved.raw giữ chung cả câu khoảng thời gian.
- Vẫn 5 conditions/5 unresolved/0 soft/6 clarifications; can_collect_data và can_evaluate_hard_constraints đều false. Source quote/span đều khớp text.
- Có hai DATE_YEAR_REQUIRED giống nhau; số reason codes readiness giảm không chứng minh đã resolve ngày. Vẫn hỏi lại điểm đến dù input đã nói.
- Một lượt input được làm rõ cho thấy improvement về operator, chưa chứng minh xử lý được câu gốc hoặc stability.

User chốt ngày 07/10/2026: uy tín, dịch vụ tốt, giá hợp lý, gần thiên nhiên mặc định soft; explicit bắt buộc mới hard. Giữ intent ngay cả khi chưa có metric/evidence để đánh giá. Pipeline và các gate tại [kế hoạch cải thiện](requirements-improvement-plan.md) đã được triển khai.

## Kết quả runtime semantic v2

Câu gốc giữ 11 conditions, bốn soft; origin/transport/destination/tour type/route có entity typed. Đà Nẵng hoặc Tây Nguyên vẫn OR. Hai ngày giữ lịch âm/group/semantics và một câu hỏi năm; chưa gửi xác nhận của người dùng vào API thì khoảng vẫn ambiguous. Route strength còn được hỏi vì “đi dọc” chưa nói bắt buộc. Không hỏi lại nơi đến hoặc tạo budget/party.

Khi trả lời availability và năm Tết giả định 2027, hai bounds thành departure >= 2027-02-03, return <= 2027-02-09. Route có thể trả lời soft/hard bằng question ID thực; giữ nhu cầu khác và provenance. Không có năm hoặc hard metric chưa hỗ trợ thì confirm bị chặn. Three qualitative metrics soft hiện unsupported không blocking; nature chờ evidence itinerary. Snapshot test Việt Nam là synthetic, không tour thật.
