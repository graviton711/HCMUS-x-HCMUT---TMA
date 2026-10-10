# Khôi phục gợi ý tour từ catalog thật

Trạng thái: **đã triển khai ngày 10/10/2026**. Frontend và backend đã gộp, commit/push trên `backend` tại checkout chính theo yêu cầu user. Từ nay cả hai phần tiếp tục làm trên `backend`; worktree frontend riêng không còn dùng. Catalog Supabase tiếp tục read-only. Kết quả và giới hạn ở [verification](recommendation-recovery-verification.md).

## Kết quả kiểm tra

- Comparison `comparison_3a02307bed914588b1be3b387ce2b406`, lúc 10:52 GMT+7 ngày 10/10, đã hoàn thành; 0 gợi ý, 20 tour cần kiểm tra, empty reason `ONLY_UNVERIFIED`. AI bỏ qua vì không có tour đạt hard constraints.
- Requirement của lượt này: điểm đến **TP.HCM**, xuất phát **TP.HCM**, khởi hành **tháng 2/2026**, 2 người lớn, giá tour/người lớn từ 0 đến 59.000.090 VND. Ngày tìm là tháng 10/2026; kho hiện có 0 lịch tháng 2/2026. Không tự đổi sang 2027 hoặc đổi điểm đến thành Việt Nam.
- Supabase có 1.210 tours, 3.319 offers, 3 providers. Quan sát offer mới nhất là 08/10/2026 18:47 GMT+7, đã hơn 40 giờ trước lượt tìm. TTL ngày/giá hiện là 24 giờ; đây không phải lịch tự động crawl.
- 0/3.319 offers có `field_meta.pricing`. Metadata hiện có source URL, observed_at và verification_status. Trong tours: 1.148 giá `from`, 62 `contact`, không có `exact`.
- Chuẩn hóa destinations: 438 tour nhận diện đủ, 198 nhận diện một phần, 574 chưa nhận diện được điểm nào. Đây là thống kê theo catalog địa danh backend, không phải kết luận rằng crawler thiếu toàn bộ điểm đến.
- Retrieval quét tối đa 1.000 tour theo ID trước khi xếp mức liên quan, lấy tối đa 1.000 offers, giữ 20 tour. Lượt trong ảnh bị giới hạn cả scan/pool/offers. Tour ngoài phạm vi nhưng chưa đủ dữ kiện để loại có thể nằm trong bảng cần kiểm tra.
- Kiểm tra bổ sung: Nhật Bản tháng 11/2026 có 11 tour/14 lịch được catalog nhận diện, tính mọi nơi xuất phát. Riêng xuất phát TP.HCM và giá người lớn đang lưu <=30 triệu có 0 lịch. Có lịch TP.HCM ngày 05/11 giá từ 33.999.000 hoặc 34.999.000 VND; đây chỉ là giá trị lưu, chưa chứng minh giá/lịch còn mới.

Các kiểm tra trên không sửa database hoặc gọi LLM, không chứng minh catalog đã đầy đủ toàn bộ thị trường.

## Quyết định đã chốt với user

**Ngân sách mặc định là trần giá tour niêm yết; phụ thu và phần chưa rõ báo riêng.** Hard/soft không thay đổi: nơi đi, nơi đến, thời gian, trần giá vẫn hard; sở thích được xét sau pool.

`estimate_cost` cho tiền thực trả yêu cầu pricing_complete=true trước khi kiểm tra trần. Giá `from` có lower bound nhưng không có upper bound. Listed evaluator đã được tách riêng:

1. **Giá tour niêm yết:** dùng giá người lớn của đúng offer phù hợp tháng/ngày, currency/basis/kind/source/freshness hợp lệ. Giá `from` dưới trần đạt tiêu chí *mức giá niêm yết*; luôn giữ nhãn “giá từ”, không hứa chắc số tiền thực trả dưới trần. Giá trên trần bị loại; contact/missing/conflicting vẫn unknown.
2. **Chi phí bổ sung/thực trả:** phân tích inclusions, exclusions, surcharges và applicability theo nhóm khách. Thiếu thông tin giữ unknown, không coi phụ thu bằng 0. Trần tổng tiền thực trả, nếu user yêu cầu riêng, vẫn cần upper bound đáng tin cậy và đầy đủ các khoản bắt buộc.

Không đổi âm thầm ý nghĩa `estimated_cost` trong API hoặc lịch sử. Contract phải biểu diễn rõ thước đo ngân sách; policy mới có version, snapshot ghi semantics. Giá theo nhóm/trẻ em cần basis và age/applicability phù hợp, không nhân giá adult tùy tiện.

### Contract triển khai

- `BudgetV2.measure`: listed hoặc payable. Payload/snapshot cũ thiếu measure đọc là payable. Input mới từ form/text dùng listed cho tour_price, payable cho trip_total hoặc lời yêu cầu tổng/thực trả. Sửa riêng số tiền giữ measure trước đó.
- `OfferSnapshotV2.listed_price_quotes`: facts riêng, không thay price_quotes/pricing_complete dùng để tính thực trả. Adapter xác nhận label adult, currency VND, kind from/exact, source và record metadata hợp lệ; amount dương của đúng offer. From giữ nguyên kind. Metadata pricing mâu thuẫn không được bypass qua đường listed.
- Listed per_adult (hoặc per_person khi không có trẻ) xét scalar niêm yết; group_total/nhóm trẻ chưa có breakdown thích hợp vẫn unknown. Kết quả công khai measure/kind/warning; không suy upper bound thực trả từ listed.
- Retrieval ưu tiên SQL parameterized địa danh/ngày/giá trên toàn bảng trước bounded paginated scan; thứ tự acquisition không nâng raw values thành hard pass. Row_number theo provider phân bổ nguồn. Offers ưu tiên toàn bộ date tree và listed budget trên cùng row trước fair window/cap. Analysis what-if không ưu tiên theo hard constraints.
- Tìm mới chặn nếu toàn bộ các nhánh thời gian hard có thể chứng minh đã qua trong timezone requirement. Unresolved không tự loại; OR còn nhánh tương lai vẫn cho tìm. Đọc history/what-if snapshot cũ giữ policy gốc.
- Policy v2.3-listed không gợi ý offer đã khởi hành trước ngày đánh giá, kể cả nằm trong tháng đang chọn, khi ngày đó có dữ kiện usable. URL-only vẫn xem lịch cũ; history dùng kết quả/time gốc. Mã DEPARTURE_ALREADY_PASSED không nâng lịch stale thành fail.
- Audit báo riêng listed quotes usable/stale/unverified và payable quotes; không coi các qualifier thiếu của payable là thiếu giá niêm yết. Prompt giữ nguyên văn các từ niêm yết/thực trả/phụ thu để backend chọn measure.
- Không triển khai crawler scheduler khi code crawler/endpoint refresh của nhóm chưa có trong contract hiện hành. Bổ sung hướng dẫn audit/recrawl; không ghi timestamp hoặc giá giả vào Supabase.

## Workflow mục tiêu và interface

`FE/LLM input -> requirement được xác nhận -> retrieval có giới hạn nhưng có phân trang -> hard constraints trên từng offer -> pool đạt -> đánh giá soft bằng LLM -> recommendation + chi phí bổ sung + what-if`.

- FE gửi điểm đến riêng với nơi khởi hành, thời gian có năm, basis/coverage ngân sách và party; trả lại request lỗi sớm nếu chọn tháng/ngày đã qua cho lượt discovery mới. Giữ đọc lại lịch sử cũ.
- Crawler ghi các giá trị đã quan sát cùng source URL/observed_at; giữ loại giá from/contact/exact đúng nguồn. Cập nhật offer thực sự đọc lại, không chỉ timestamp của provider.
- Data access chuẩn hóa hai phía bằng cùng catalog địa danh/alias/quan hệ city-country và vai trò điểm đi/đến. Chuỗi nhiều địa danh chỉ tách theo quy tắc có kiểm tra; tên thành phố cụ thể không được thay bằng quốc gia để nới hard constraint.
- Retrieval trả matching offers và coverage/truncation. Nhiều tháng dùng OR của từng khoảng tháng, không lấy cả tháng ở giữa. Giữ ngày và giá cùng một offer; unknown không chiếm toàn bộ pool hiển thị.
- Decision trả riêng kết quả hard của giá niêm yết, trạng thái phụ thu/chi phí thực trả và dữ kiện chứng minh. LLM chỉ đánh giá soft trên pool đạt hard theo policy đã công bố; không dùng LLM đổi unknown thành pass.
- FE phân biệt gợi ý đạt nhu cầu với tour thiếu thông tin để kiểm tra; gợi ý có giá từ vẫn hiển thị giới hạn của mức giá đó. Không báo “không có tour trong kho” khi retrieval chưa đầy đủ.
- What-if dùng cùng thước đo giá, cùng quan hệ AND/OR và phạm vi truy vấn; nếu mở rộng truy vấn phải ghi phạm vi mới. Không trình bày tỷ lệ đóng góp trên pool bị cắt như kết quả của toàn bộ catalog.

## Thứ tự thực hiện đề xuất

1. Chốt contract ngân sách và cập nhật docs/README/schema affected trước code. Tách evaluator giá niêm yết khỏi estimator chi phí thực trả; thêm policy version và nhãn kết quả.
2. Hoàn thiện normalization với các địa danh thực tế bị thiếu trong kho. Push down các bộ lọc có giá trị chuẩn vào PostgreSQL, phân trang và phân bổ offers giữa nguồn/tour; không chỉ tăng LIMIT. Cảnh báo coverage khi còn giới hạn.
3. Crawler chạy lại một tập tour mẫu có nhu cầu và lịch tương lai, rồi thiết lập chạy hằng ngày nếu dùng TTL 24 giờ. Tận dụng các cột hiện có; bổ sung metadata giá theo nguồn khi cần, không đặt complete=true để ép pass. Backend giữ read-only tour store.
4. FE chặn tháng/ngày quá khứ cho tìm mới, làm rõ tháng/năm, nơi đi/nơi đến, giá tour niêm yết và phụ thu. Không tự chọn lại giá trị của user.
5. Test một lát cắt thật có positive/negative rõ ràng rồi mở rộng nguồn và địa danh.

## Tiêu chí kiểm chứng

- Positive: một offer đã đọc lại nguồn, đúng nơi đi/đến, tháng/ngày và giá niêm yết dưới trần -> vào pool và được đánh giá soft. Nếu from, recommendation có nhãn giá từ và giới hạn chi phí thực trả.
- Negative: sai nơi đến hoặc giá niêm yết vượt trần -> fail tương ứng; stale/missing/contact/conflicting -> unknown đúng lý do.
- Chọn 11/2026 OR 01/2027 không nhận 12/2026; giá rẻ lịch ngoài tháng không giúp offer trong tháng đạt trần.
- Trần tổng thực trả riêng không pass khi from/upper unknown hoặc thiếu phụ thu bắt buộc. Metadata không biến giá from thành exact.
- Nhu cầu tháng 2/2026 khi tìm mới vào 10/2026 -> lỗi rõ trước chạy comparison; đọc snapshot cũ vẫn được.
- Tour có ID ngoài 1.000 dòng đầu và nguồn có nhiều lịch vẫn được xét qua retrieval phù hợp; nếu còn cap thì response nói rõ phạm vi chưa đầy đủ.
- What-if thay đổi đúng một nhóm điều kiện, không tự đổi hard thành soft hay dùng sai thước đo giá; lịch sử giữ policy gốc.

## Code/tài liệu liên quan

- `src/decision/engine.py`: freshness, estimate_cost và price bounds.
- `src/data_access/supabase/{reader,adapter,pricing}.py`: scan/offer caps, normalization, binding metadata.
- `src/requirements/catalog.py`: alias và place relations.
- `src/frontend/components/MonthPicker.tsx`, `src/frontend/api/form.ts`: lựa chọn tháng và validation.
- `docs/search-correctness-repair.md`, `docs/catalog-validation-policy.md`, `examples/catalog-price-metadata.md`: policy payable giữ nguyên; listed measure bổ sung theo contract này.
