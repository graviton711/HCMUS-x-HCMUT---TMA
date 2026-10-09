"use strict";
// UI copy only. User text, identities and original evidence never enter this catalog.
window.PrototypeEnglish = (() => {
  const catalog = Object.create(null);
  const add = pairs => pairs.trim().split("\n").forEach(line => {
    const at = line.indexOf("|");if (at > 0) catalog[line.slice(0,at).trim()] = line.slice(at+1).trim();
  });
  add(`
Đến nội dung chính|Skip to content
Dữ liệu & phản hồi mô phỏng|Simulated data & responses
Không gian review ↗|Design review ↗
Một chuyến đi. Nhiều góc nhìn.|One trip. Many perspectives.
MỘT CHUYẾN ĐI. NHIỀU GÓC NHÌN.|ONE TRIP. MANY PERSPECTIVES.
Giới thiệu|About
Tìm tour|Find tours
Liên hệ chúng tôi|Contact us
Liên hệ|Contact
Hỗ trợ người dùng|Help & support
Hỗ trợ|Help
Chuyến đi mới|New trip
Lưu trên trình duyệt này|Saved in this browser
Đã lưu trên trình duyệt này|Saved in this browser
Chưa lưu được · giữ tab này mở|Unable to save · keep this tab open
Lượt tìm|Searches
Về giới thiệu|Back to overview
HỖ TRỢ LỰA CHỌN TOUR|HELPING YOU CHOOSE A TOUR
Chọn kỹ,|Choose thoughtfully,
đi thảnh thơi.|travel at ease.
Đối chiếu tour theo nhu cầu, hiểu từng đánh đổi và kiểm chứng dữ kiện trước khi quyết định.|Compare tours against your needs, understand the trade-offs and check the evidence before deciding.
Cách sử dụng|How it works
Nhật Bản, một ý tưởng cho chuyến tới.|Japan, an idea for your next trip.
Ảnh minh họa điểm đến|Illustrative destination photo
Trước khi lên đường|Before you set off
Widget mô phỏng|Demo widget
Bạn đang ở đâu?|Where are you starting from?
Chưa xác định vị trí|Location not selected
Thử vị trí hiện tại|Try current location
Thử khi từ chối quyền|Try denied permission
Thời tiết tại nơi khởi hành|Weather at your departure city
Chọn vị trí để xem thời tiết minh họa.|Choose a location to see sample weather.
Dữ liệu mẫu, không phải dự báo thực tế.|Sample data, not a real forecast.
Một nơi để bắt đầu.|A place to begin.
Vài tour Nhật Bản minh họa. Nhu cầu của bạn sẽ là điểm xuất phát khi tìm và so sánh.|A few sample tours of Japan. Your needs set the direction for searching and comparing.
Nhật Bản|Japan
NHẬT BẢN|JAPAN
TP.HCM|Ho Chi Minh City
Thành phố, núi và một nhịp đi thư thả.|Cities, mountains and an unhurried pace.
/ người lớn|/ adult
Tour minh họa|Sample tour
Văn hóa, phố cổ và những ngôi đền.|Culture, old streets and temples.
Góc nhìn khác giữa đô thị và cảnh núi.|Another view of city life and mountain scenery.
Giá mẫu chưa gồm mọi phụ thu; chưa phải gợi ý cá nhân hóa.|Sample prices exclude some surcharges; these are not personalized recommendations.
Thử nhu cầu mẫu|Try sample trip details
Hiểu lựa chọn trước khi chọn.|Understand your options before choosing.
Đi cùng giúp bạn đối chiếu tour trọn gói theo cùng tiêu chí và nhìn rõ thông tin còn thiếu.|Đi cùng compares package tours using the same criteria and makes missing information visible.
Kể điều bạn cần|Tell us what you need
Điền thông tin chuyến đi, thêm URL tour hoặc ghi chú riêng nếu có.|Enter your trip details, with a tour URL or personal notes if you have them.
Xác nhận và theo dõi|Confirm and follow along
Kiểm tra nhu cầu, rồi xem hệ thống đang thu thập và đối chiếu điều gì.|Review your needs, then see what the system is gathering and comparing.
So sánh, hỏi thêm|Compare and ask questions
Mở nguồn từng dữ kiện, đọc phân tích AI và trao đổi để điều chỉnh nhu cầu.|Check each fact’s source, read the AI analysis and chat to refine your needs.
Xem một lượt tìm tour|See a tour search
Demo tương tác|Interactive demo
Bắt đầu bằng nhu cầu của bạn|Start with your needs
“Đi Nhật Bản từ TP.HCM, khoảng 5 ngày, ngân sách 35 triệu/người lớn.”|“Japan from Ho Chi Minh City, about 5 days, a budget of VND 35 million per adult.”
Minh họa cách sử dụng; chưa kết nối backend.|An example of the flow; the backend is not connected.
Đi từng bước theo nhịp của bạn.|Take each step at your own pace.
Chạy demo|Play demo
CHUYẾN ĐI BẮT ĐẦU TỪ BẠN|THE TRIP STARTS WITH YOU
Bạn muốn đi đâu,|Where would you like to go,
và đi như thế nào?|and how would you like to travel?
Điền thông tin cần thiết. Thêm những điều bạn quan tâm để việc so sánh có ý nghĩa hơn.|Enter the essentials. Add what matters to you to make the comparison more useful.
Bản mẫu dùng tour Nhật Bản, khởi hành TP.HCM tháng 11/2026. Dữ liệu tour và chat đều minh họa.|This demo uses Japan tours departing from Ho Chi Minh City in November 2026. Tour data and chat responses are illustrative.
Thông tin chuyến đi|Trip details
Cần điền|Required
Điểm đến|Destination
Chọn điểm đến|Choose a destination
Khởi hành từ|Departing from
Khởi hành|Departure
Chọn nơi khởi hành|Choose a departure city
Ngày dự kiến|Preferred date
Tour mẫu: 10–17/11/2026.|Sample tours: 10–17 November 2026.
Số người lớn|Number of adults
Người lớn|Adults
Ngân sách / người lớn|Budget / adult
Ngân sách|Budget
Ưu tiên giá tour, chưa bao gồm mọi phụ thu. Đây chưa phải tổng chi phí chuyến đi.|A preferred tour price, excluding some surcharges. This is not the total trip cost.
Thêm một chút về bạn|A little more about you
Tùy chọn|Optional
Thời lượng ưu tiên|Preferred duration
Thời lượng|Duration
Khoảng 5 ngày|About 5 days
Khoảng 6 ngày|About 6 days
Chưa chỉ định|Not specified
Số trẻ em|Number of children
Trẻ em|Children
Tuổi từng trẻ|Each child’s age
Tuổi trẻ em|Children’s ages
Mỗi tuổi 0–17, cách nhau bằng dấu phẩy. Không tự suy ra giá trẻ em.|Ages 0–17, separated by commas. Children’s prices are not inferred.
Khách sạn|Hotel
Từ 3 sao|3 stars or above
Từ 4 sao|4 stars or above
Từ 5 sao|5 stars or above
Điểm mua sắm|Shopping stops
Mua sắm|Shopping
Ưu tiên ít điểm|Prefer fewer stops
Bắt buộc không có|No stops required
URL tour đang cân nhắc|Tour URL you are considering
URL tham chiếu|Reference URL
Giữ tour bạn gửi làm tham chiếu để đối chiếu cùng các gợi ý.|Keep the tour you share as a reference alongside the suggestions.
Điều gì quan trọng với bạn?|What matters to you?
Mức sở thích mẫu|Sample preference levels
Kéo thanh để thể hiện ưu tiên. Mức mẫu có thể đổi; đây là sở thích, không phải điều kiện bắt buộc.|Move the sliders to express your priorities. These are preferences, not requirements.
Thông tin này sẽ hiện ở cột yêu cầu. Bạn có thể sửa trực tiếp hoặc trao đổi qua chat ở màn kết quả.|These details appear in your requirements panel. Edit them directly or use chat on the results screen.
Xác nhận & tìm tour|Confirm & find tours
KHÔNG CHỈ LÀ GIÁ|MORE THAN THE PRICE
Một chuyến đi hợp ý|A trip that suits you
nằm trong từng chi tiết.|is in the details.
Lịch trình, điểm mua sắm hay một chính sách hủy rõ ràng — mỗi điều đều đáng được đặt cạnh nhau.|An itinerary, shopping stops or a clear cancellation policy — each deserves a closer comparison.
Còn điều gì bạn muốn nhắn?|Anything else to add?
Ghi chú tùy chọn · Chat mô phỏng|Optional notes · Demo chat
Bạn có thể thêm lưu ý về bữa ăn, nhịp đi hay thành viên trong đoàn.|Add notes about meals, pace or members of your group.
Ghi chú thêm|Additional notes
Lưu ý thêm|Additional notes
Về thông tin chuyến đi|Back to trip details
CÙNG NHU CẦU · NHIỀU GÓC NHÌN|YOUR NEEDS · DIFFERENT PERSPECTIVES
Chuyến đi hợp với bạn,|A trip that suits you,
nhìn rõ từng lựa chọn.|with every option in view.
Đối chiếu dữ kiện, hiểu đánh đổi và trao đổi để tìm lựa chọn hợp ý hơn.|Compare the facts, understand the trade-offs and chat to refine your options.
Tìm kiếm|Search
Chưa có kết quả|No results yet
Yêu cầu của bạn|Your requirements
Đã xác nhận|Confirmed
Sửa nhiều mục rồi xác nhận cùng lúc. Hủy sẽ về bản đã xác nhận gần nhất.|Edit several fields and confirm them together. Cancelling restores the last confirmed version.
Sửa nhiều mục|Edit multiple fields
Trao đổi về chuyến đi|Talk about your trip
Mô phỏng|Demo
Tôi có thể giải thích tour, sửa yêu cầu hoặc tìm nhóm khác. Mọi thay đổi đều chờ bạn xác nhận.|I can explain tours, suggest changes or find another group. Every change waits for your confirmation.
Sửa ngân sách + thời lượng|Change budget + duration
So sánh giá|Compare prices
Nhóm khác|Another group
Tin nhắn về yêu cầu hoặc kết quả|Message about requirements or results
Nhận một số câu mẫu · Chưa kết nối AI|Supports sample prompts · AI not connected
TIẾN ĐỘ MÔ PHỎNG|SIMULATED PROGRESS
Đang chuẩn bị những lựa chọn cho bạn.|Preparing options for you.
Dừng chờ|Stop waiting
Phản hồi chậm hơn dự kiến. Thông tin của bạn vẫn được giữ.|The response is taking longer than expected. Your details are saved.
3 tour gợi ý cho bạn|3 suggested tours
Nhóm 01 · Dữ liệu minh họa|Group 01 · Sample data
Căn cứ đề xuất|Basis for suggestions
Bộ tour minh họa cố định, chưa truy xuất hoặc xếp hạng theo yêu cầu.|A fixed sample set, not retrieved or ranked against your requirements.
Dữ kiện so sánh|Compare facts
Phân tích AI|AI analysis
Đặt cạnh nhau để thấy rõ.|See them side by side.
Cùng tiêu chí. Mở nguồn ở mỗi dữ kiện.|The same criteria. Open the source for each fact.
Vuốt ngang để đối chiếu · giữ tiêu chí và tên tour|Swipe to compare · criteria and tour names stay visible
Giá công bố/người lớn, chưa đủ phụ thu. Dữ liệu và nguồn minh họa; chưa xác minh độc lập.|Published price per adult, with some surcharges missing. Data and sources are illustrative, not independently verified.
Phạm vi nguồn còn giới hạn.|Source coverage is limited.
Cách đọc kết quả|How to read the results
Thử tình huống trong bản mẫu|Try demo scenarios
1 URL tham chiếu mẫu|1 sample reference URL
Kết quả|Results
3 gợi ý|3 suggestions
2 gợi ý|2 suggestions
Chỉ URL|URL only
Một nguồn lỗi|One source failed
Không có gợi ý|No suggestions
Phản hồi|Response
Bình thường (~4 giây)|Normal (~4 seconds)
Chậm (~9 giây)|Slow (~9 seconds)
Mất kết nối|Connection lost
Chạy tình huống|Run scenario
Review UI bằng fixture. Không API, LLM, định vị hoặc thời tiết thật. Chọn tình huống rồi chạy để xem loading.|Review the UI with fixed sample data. No real API, LLM, location or weather. Choose a scenario to see the loading state.
LIÊN HỆ CHÚNG TÔI|CONTACT US
Một góp ý của bạn,|Your feedback,
một trải nghiệm tốt hơn.|a better experience.
Góp ý về cách tìm tour, bảng so sánh hoặc những thông tin bạn muốn nhìn rõ hơn.|Share feedback about tour searches, comparisons or information you want to see more clearly.
Loại liên hệ|Contact category
Góp ý trải nghiệm|Experience feedback
Thông tin tour / nguồn|Tour / source information
Cần hỗ trợ|Need support
Email liên hệ (tùy chọn)|Contact email (optional)
Bạn muốn nhắn điều gì?|What would you like to share?
Tạo liên hệ mẫu|Create demo message
Góp ý được giữ trong tab, chưa gửi ra ngoài. Bạn có thể xử lý ở trang quản trị mẫu.|Feedback stays in this tab and is not sent externally. Review it in the demo admin page.
Đang xây dựng cùng bạn.|Building this with you.
Đi cùng tập trung vào tour có nguồn, so sánh rõ ràng và những đánh đổi có thể kiểm chứng.|Đi cùng focuses on sourced tours, clear comparisons and trade-offs you can verify.
Bạn có thể mở trang quản trị để theo dõi nguồn, phiên trao đổi và xử lý liên hệ trong mẫu.|Open the admin page to track sources, sessions and demo feedback.
Mở trang quản trị mẫu ↗|Open demo admin ↗
Xem hướng dẫn sử dụng|View the guide
HỖ TRỢ NGƯỜI DÙNG|HELP & SUPPORT
Đọc rõ hơn.|Read with clarity.
Chọn tự tin hơn.|Choose with confidence.
Từ việc sửa nhu cầu đến kiểm tra nguồn: những thao tác bạn cần khi cân nhắc một chuyến đi.|From editing your needs to checking a source: the tools for considering a trip.
Sửa nhu cầu rồi xác nhận|Edit your needs, then confirm
Chọn Sửa nhiều mục, sửa từng giá trị hoặc kéo thanh sở thích. Mọi thay đổi được gom chung để xác nhận một lần. Hủy tất cả khôi phục bản đã xác nhận gần nhất.|Choose Edit multiple fields, edit a value or move a preference slider. Confirm all changes together, or cancel all to restore the last confirmed version.
Tìm kiếm khi bạn sẵn sàng|Search when you are ready
Sau khi xác nhận, bấm Tìm kiếm hoặc nhắn “tìm kiếm đi”. Kết quả cũ còn xem được trong lúc xử lý và được ghi rõ nếu chưa theo nhu cầu mới.|After confirming, click Search or type “search tours”. Previous results remain visible while processing and are labelled if they use earlier requirements.
Đối chiếu dữ kiện và phân tích|Compare facts and analysis
Tab Dữ kiện so sánh đặt các tour cạnh nhau. Tab Phân tích AI giải thích chênh lệch giá, đánh đổi và điều còn thiếu; các ví dụ hiện đều mô phỏng.|Compare facts puts tours side by side. AI analysis explains price differences, trade-offs and missing information. All examples are simulated.
Kiểm tra nguồn trước khi quyết định|Check sources before deciding
Mở từng ô giá, lịch hoặc chính sách để xem dữ kiện và giới hạn. Giá công bố chưa phải tổng cuối; lịch khởi hành chưa chứng minh còn chỗ.|Open a price, date or policy cell to see its evidence and limits. Published prices are not final totals; a departure date does not prove availability.
Tiếp tục chuyến đi của bạn.|Continue your trip.
Lượt tìm tour và phần trao đổi đều nằm trong mục Tìm tour.|Tour searches and conversations are both in Find tours.
Về Tìm tour|Back to Find tours
Góp ý với nhóm|Share feedback
Đi cùng · Prototype Giấy & Mực ·|Đi cùng · Giấy & Mực prototype ·
Quản trị mẫu ↗|Demo admin ↗
Tour, giá và phản hồi minh họa ·|Sample tours, prices and responses ·
Nguồn ảnh & font ↗|Photo & font credits ↗
DỮ KIỆN & NGUỒN|FACTS & SOURCES
Dữ liệu minh họa cho review UI · Chưa phải tour thật|Sample data for UI review · Not real tours
Bật JavaScript để xem ba màn và tương tác prototype.|Enable JavaScript to view the screens and use this prototype.
Tiết kiệm chi phí|Lower cost
Khách sạn tiện nghi|Hotel comfort
Nhịp đi thư thả|Unhurried pace
Trải nghiệm văn hóa|Cultural experiences
Không ưu tiên|No priority
Ưu tiên nhẹ|Low priority
Vừa phải|Moderate
Quan trọng|Important
Rất quan trọng|Very important
Ưu tiên cao nhất|Highest priority
Rất quan tâm|Very interested
người|people
người lớn|adults
Phạm vi từ tour tham chiếu|Scope from the reference tour
Thông tin cần thiết|Essential details
Thông tin bổ sung|Additional details
Phạm vi giá|Price scope
Giá tour / người lớn · ưu tiên|Preferred tour price / adult
Mức độ sở thích|Preference levels
Kéo để sửa ưu tiên · Mức mẫu|Move to adjust priorities · Sample levels
Chưa xác nhận|Not confirmed
Đang tìm theo yêu cầu mới. Kết quả trước vẫn được giữ để bạn tham khảo.|Searching with new requirements. Previous results stay available for reference.
Yêu cầu đã thay đổi. Bấm Tìm kiếm để cập nhật kết quả.|Requirements have changed. Click Search to update the results.
Đang tìm kiếm…|Searching…
Kết quả theo yêu cầu trước|Results for previous requirements
Kết quả theo yêu cầu đã xác nhận|Results for confirmed requirements
Sẵn sàng tìm kiếm|Ready to search
Đang tìm…|Searching…
Đang tìm theo yêu cầu mới|Searching with new requirements
Kết quả chưa theo yêu cầu mới|Results use previous requirements
Có thay đổi chưa xác nhận|Unconfirmed changes
Đang tìm kiếm|Searching
Kết quả dùng đúng bản yêu cầu|Results match this version
Bảng và phân tích bên dưới vẫn dùng bản yêu cầu trước.|The table and analysis below still use previous requirements.
Bạn còn thay đổi chưa xác nhận.|You have unconfirmed changes.
Kết quả mới sẽ thay thế khi xử lý xong.|New results will replace these when processing finishes.
Bấm Tìm kiếm để cập nhật.|Click Search to update.
Các ô đang sửa chưa áp dụng. Bạn có thể sửa thêm, xác nhận cả nhóm hoặc hủy về bản đã xác nhận.|These edits are not applied yet. Keep editing, confirm the group or cancel to restore the confirmed version.
Bảng cũ được giữ trong lúc xử lý. Hủy tìm kiếm vẫn giữ yêu cầu đã xác nhận.|The previous table stays visible during processing. Cancelling the search keeps confirmed requirements.
Bảng và phân tích dùng cùng bản yêu cầu đã xác nhận. Tour minh họa chưa được kiểm tra đủ để kết luận đáp ứng mọi điều kiện.|The table and analysis use the same confirmed requirements. Sample tours have not been fully checked against every condition.
Xác nhận yêu cầu rồi bắt đầu tìm tour.|Confirm your requirements, then start searching.
Xem yêu cầu của bảng này|View this table’s requirements
Chưa có đủ dữ kiện để phân tích.|Not enough facts to analyze.
Điều chỉnh yêu cầu qua chat hoặc kiểm tra nguồn; không tạo nhận định khi chưa có tour.|Adjust requirements in chat or check sources. No conclusions are generated without tours.
Chưa có ngân sách cá nhân để đánh giá.|No personal budget to assess.
Giá công bố của gợi ý đầu nằm trong ngân sách ưu tiên.|The first suggestion’s published price is within your preferred budget.
PHÂN TÍCH MINH HỌA · THEO LƯỢT KẾT QUẢ ĐANG XEM|SAMPLE ANALYSIS · FOR THE SEARCH YOU ARE VIEWING
Giá thấp hơn có một đánh đổi.|A lower price has a trade-off.
Một tour, chưa đủ để so đánh đổi.|One tour is not enough to compare trade-offs.
Chênh lệch giá công bố / người lớn|Published price difference / adult
Chưa đủ tour|Not enough tours
Cần ít nhất hai tour|At least two tours needed
Giá gợi ý 01|Suggestion 01 price
Giá gợi ý 02|Suggestion 02 price
Chưa thể tính|Cannot calculate yet
Chưa có số người|Group size not specified
nhóm chưa rõ|group size unknown
Chưa gồm phụ thu|Surcharges excluded
và giá trẻ em|and children’s prices
. Chưa phải tổng cuối của chuyến đi.|. This is not the final trip total.
Kiểm tra giá mẫu|Check sample price
Đối chiếu với yêu cầu đã dùng|Compare with the requirements used
Phạm vi Nhật Bản lấy từ tour tham chiếu, chưa suy ra sở thích riêng.|The Japan scope comes from the reference tour. Personal preferences are not inferred.
Thời lượng ưu tiên:|Preferred duration:
Xem lịch & thời lượng|View dates & duration
Tiết kiệm giá, đổi lại thêm thời gian|A lower price, with more time needed
Xem lịch trình mua sắm|View shopping stops
Điều chưa biết ảnh hưởng quyết định|Missing facts affect your decision
Phụ thu, chính sách hủy hoặc dịch vụ còn thiếu ở một số tour. Các giá gắn với lịch riêng; chưa xác minh còn chỗ hoặc nguồn độc lập.|Some tours lack surcharges, cancellation policies or service details. Prices refer to specific departures; availability and independent sources are unverified.
Mở dữ kiện còn thiếu|View missing facts
Mức sở thích của lượt này|Preferences for this search
Thể hiện mức bạn chọn trong mẫu; chưa dùng để tính điểm hoặc xếp hạng thật.|Shows the levels you selected in the demo; these do not calculate real scores or rankings.
Xem phép tính và điều kiện áp dụng|View calculations and conditions
Chưa có hai tour để tính chênh lệch|Two tours are needed to calculate a difference
Cùng đơn vị VND / người lớn và phạm vi giá tour. Giá thuộc ngày công bố ở từng cột; khác lịch khởi hành và chưa đủ phụ thu nên chưa chứng minh tour nào rẻ hơn về tổng cuối.|Both prices use VND per adult and the same tour-price scope. They refer to different departures and exclude some surcharges, so they do not establish which final total is lower.
Phép tính từ fixture, không điểm AI hay tổng nhóm do backend xác nhận. Đổi offer cập nhật giá, ngày, bằng chứng và các phép tính cùng lúc.|Calculations use fixed sample data, not AI scores or backend-confirmed group totals. Changing the offer updates the price, date, evidence and calculations together.
Mẫu giải thích từ dữ liệu cố định, chưa có AI hoặc xếp hạng theo yêu cầu mới. Nhận định có điều kiện, không kết luận tour tốt nhất hay thay bạn quyết định.|Explanations use fixed data, without AI or ranking against new requirements. They describe conditions, not a best tour or a decision on your behalf.
Dữ kiện và phân tích từ cùng lượt kết quả. Trao đổi ở cột yêu cầu để điều chỉnh.|Facts and analysis come from the same search. Use the requirements panel to make changes.
Bộ tour Nhật Bản / TP.HCM tháng 11 cố định. Chưa truy xuất, kiểm tra đủ ràng buộc hoặc xếp hạng theo nhu cầu.|A fixed set of Japan tours from Ho Chi Minh City in November. No retrieval, full constraint checking or personalized ranking.
Tham chiếu minh họa · Chưa đọc URL đã nhập|Sample reference · Entered URL not fetched
So với bản đã xác nhận gần nhất. Bạn có thể tiếp tục sửa nhiều mục.|Compared with the last confirmed version. You can keep editing several fields.
Bỏ|Remove
Bạn đã yêu cầu tìm kiếm; xác nhận cả nhóm xong sẽ bắt đầu tìm.|You requested a search. It starts once you confirm the whole group.
Xác nhận cả nhóm để cập nhật. Tìm kiếm khi bạn sẵn sàng.|Confirm the whole group to apply changes. Search when you are ready.
Tiếp tục sửa|Keep editing
Hủy tất cả|Cancel all
Đã hủy mọi thay đổi chưa xác nhận và khôi phục bản đã xác nhận gần nhất.|All unconfirmed changes were cancelled and the last confirmed version restored.
Sửa nhiều thông tin|Edit trip details
Chỉnh các mục cần đổi rồi thêm vào cùng nhóm xác nhận.|Edit the fields you need, then add them to the same confirmation group.
Thêm vào nhóm xác nhận|Add to confirmation group
Đóng trình sửa|Close editor
Đợi phản hồi hiện tại hoặc dừng chờ trước khi sửa.|Wait for the response or stop waiting before editing.
Thêm số trẻ em và tuổi cùng lúc ở ô Trẻ em.|Enter the number of children and their ages together in Children.
Sửa|Edit
Hủy|Cancel
Tuổi từng trẻ, cách nhau bằng dấu phẩy|Each child’s age, separated by commas
Tuổi: 6, 10|Ages: 6, 10
Tiếp tục phản hồi|Resume response
Xác nhận sửa hoặc chọn Giữ nguyên trước khi tìm kiếm nhé.|Confirm your edits or keep the current version before searching.
Đợi phản hồi hiện tại hoặc dừng chờ để tiếp tục.|Wait for the response or stop waiting to continue.
Đang chuẩn bị phản hồi mẫu…|Preparing a sample response…
Bạn muốn ngân sách cuối là bao nhiêu triệu VND / người lớn? Prototype cần số tuyệt đối, ví dụ “đổi ngân sách thành 37 triệu”.|What should the final budget be in million VND per adult? Enter an absolute amount, for example “set budget to 37 million”.
Bạn muốn ngân sách bao nhiêu triệu VND / người lớn? Ví dụ: “đổi ngân sách thành 32 triệu”.|What budget would you like in million VND per adult? For example, “set budget to 32 million”.
Trong mẫu, bạn có thể đổi thành 5 hoặc 6 ngày; chọn trực tiếp ngày khởi hành ở bảng yêu cầu.|This demo supports 5 or 6 days. Set the departure date directly in the requirements panel.
Chưa áp dụng thay đổi nào.|No changes applied.
Tôi đã gom các thay đổi vào cùng bản nháp. Sửa thêm hoặc xác nhận cả nhóm bên dưới; yêu cầu đã xác nhận vẫn được giữ.|I grouped the changes into one draft. Keep editing or confirm the whole group below. Your confirmed requirements are kept.
Xác nhận sửa hoặc Giữ nguyên trước khi lấy nhóm khác nhé.|Confirm your edits or keep the current version before requesting another group.
Bộ mẫu chưa còn nhóm mới. Nhóm hiện tại được giữ lại; bạn có thể điều chỉnh yêu cầu.|No more groups in this sample set. The current group is kept; you can adjust your requirements.
Tôi đang lấy nhóm minh họa thứ hai, giữ nguyên yêu cầu và loại các tour đã xem.|Loading the second sample group, keeping your requirements and excluding tours already viewed.
Tôi bắt đầu tìm theo yêu cầu bạn đã xác nhận.|Starting a search with your confirmed requirements.
Chưa có ít nhất hai tour để so chênh lệch. Có thể kiểm tra nguồn của tour đang có.|At least two tours are needed to compare prices. You can check the available tour’s sources.
Xem giá & nguồn|View price & source
Phản hồi theo lượt kết quả đang xem; chưa phải tổng nhóm đủ phụ thu.|Based on the search you are viewing; not a group total including all surcharges.
Chưa có tour để kiểm tra chính sách.|No tour available to check its policy.
Một số tour thiếu chính sách hủy hoặc phụ thu. Chưa đủ căn cứ để kết luận chi phí cuối.|Some tours lack cancellation policies or surcharges. There is not enough evidence to determine final costs.
Kiểm tra chính sách|Check policy
Bạn có thể nhắn “đổi ngân sách thành 32 triệu và thời lượng thành 6 ngày”, sửa khách sạn/mua sắm, hỏi về giá hoặc yêu cầu nhóm khác. Lưu ý riêng có thể sửa trực tiếp. Chat hiện nhận câu mẫu.|Try “set budget to 32 million and duration to 6 days”, change the hotel or shopping stops, ask about prices or request another group. Edit personal notes directly. This chat supports sample prompts.
Lượt tìm đang tạm dừng.|This search is paused.
Đã dừng chờ mô phỏng.|Stopped waiting in the demo.
Kết quả trước được giữ lại.|Previous results are kept.
Chưa có kết quả mới.|No new results yet.
Tiếp tục lượt tìm|Resume search
Xác nhận sửa hoặc Giữ nguyên trước khi tìm kiếm.|Confirm your edits or keep the current version before searching.
Hiểu yêu cầu và kiểm tra dữ kiện đầu vào|Read requirements and check input details
Đọc URL tham chiếu và tìm tour từ nguồn mẫu|Read the reference URL and search sample sources
Chuẩn hóa giá / offer rồi đối chiếu điều kiện|Normalize prices / offers and check conditions
Sắp nhóm, dựng bảng và phân tích có dẫn chứng|Group tours, build the table and analyze with evidence
Chưa nhận được kết quả mới.|No new results received.
Thử lại|Try again
Đã chuẩn bị kết quả minh họa. Bạn có thể xem nguồn, phân tích hoặc trao đổi thêm.|Sample results are ready. Check sources, read the analysis or continue chatting.
Đã thêm vào lưu ý. Bản mẫu chưa tự chuyển ghi chú thành điều kiện.|Added to your notes. The demo does not turn notes into constraints automatically.
Chưa có thay đổi mới. Nhóm đang sửa được giữ lại.|No new changes. Your current draft is kept.
Yêu cầu đã đổi ở nơi khác. Bản nháp được giữ để review; chưa xác nhận.|Requirements changed elsewhere. The draft is kept for review and has not been confirmed.
Đã xác nhận toàn bộ thay đổi. Tôi bắt đầu tìm kiếm theo lời nhắn của bạn.|All changes confirmed. Starting the search you requested.
Đã xác nhận toàn bộ thay đổi. Bấm Tìm kiếm hoặc nhắn “tìm kiếm đi” để cập nhật kết quả.|All changes confirmed. Click Search or type “search tours” to update results.
Đang mô phỏng xác định vị trí…|Simulating location detection…
Đang tải thời tiết mẫu…|Loading sample weather…
TP.HCM · Vị trí minh họa|Ho Chi Minh City · Sample location
29°C · Có mây · Thời tiết minh họa|29°C · Cloudy · Sample weather
Widget mô phỏng; nơi khởi hành chưa tự thay đổi.|Demo widget; your departure city has not changed.
Không cấp quyền vị trí (mô phỏng). Bạn vẫn có thể chọn nơi đi trong form.|Location permission denied (demo). You can still select your departure city in the form.
Điền điểm đến, ngày và ngân sách của bạn.|Enter your destination, date and budget.
Hệ thống đối chiếu tour, giá và dữ kiện còn thiếu.|The system compares tours, prices and missing facts.
Xem bảng, mở nguồn và trao đổi qua chat để điều chỉnh.|View the table, open sources and chat to make changes.
Tiếp tục bằng Google|Continue with Google
Đăng nhập|Log in
Tạo tài khoản|Create account
Chuyến đi của bạn|Your trips
Tìm tour mới|New tour search
Tìm phiên đã lưu|Search saved chats
Lịch sử riêng của @|Private history for @
Dữ liệu mẫu · lưu trên trình duyệt này|Sample data · saved in this browser
Đang điền nhu cầu|Drafting requirements
Đang tìm|Searching
Đang tạm dừng|Paused
Có kết quả|Results available
Một phần nguồn|Partial sources
Chưa thành công|Unsuccessful
Đã dừng|Stopped
Đã ghim|Pinned
Hôm nay|Today
Hôm qua|Yesterday
Trước đó|Earlier
Không tìm thấy phiên|No chats found
Chưa có phiên đã lưu|No saved chats yet
Thử tên chuyến đi hoặc điểm đến khác.|Try another trip name or destination.
Bắt đầu tìm tour để giữ nhu cầu và cuộc trò chuyện ở đây.|Start a search to keep your requirements and conversation here.
Các lượt tìm trong phiên|Searches in this chat
Xem lại kết quả cũ giữ nguyên yêu cầu và cuộc trò chuyện hiện tại.|Revisit previous results while keeping your current requirements and conversation.
Phạm vi từ URL|Scope from URL
Đang xem|Viewing
Xem kết quả|View results
Tiếp tục|Continue
Chưa có lượt tìm. Nhu cầu và tin nhắn vẫn được lưu trong phiên này.|No searches yet. Your requirements and messages are still saved in this chat.
Nhu cầu mẫu đã sẵn sàng. Kiểm tra trước khi xác nhận.|Sample requirements are ready. Review them before confirming.
Đổi tên phiên|Rename chat
Bỏ ghim|Unpin
Ghim phiên|Pin chat
Xóa phiên|Delete chat
Tên phiên|Chat name
Lưu tên|Save name
Xóa phiên này?|Delete this chat?
Phiên|Chat
, nhu cầu, tin nhắn và các lượt tìm của phiên sẽ được xóa khỏi bản mẫu trên trình duyệt này.|, its requirements, messages and searches will be deleted from this browser’s demo.
Các phiên khác được giữ.|Other chats are kept.
Giữ phiên|Keep chat
Đã xóa phiên mẫu.|Demo chat deleted.
Đã xóa lịch sử mẫu của tài khoản này.|Demo history deleted for this account.
Đang xem lượt tìm cũ. Yêu cầu hiện tại được giữ.|Viewing a previous search. Current requirements are kept.
Tài khoản của tôi|My account
Các phiên tìm tour|Your tour chats
Tùy chọn phiên mới|New chat options
Đăng xuất|Log out
Mỗi chuyến đi,|Every trip,
đều có thể tiếp nối.|can pick up where you left off.
Lưu những điều bạn đã hỏi, những tour đã tìm. Khi trở lại, bạn bắt đầu từ nơi mình dừng.|Keep your questions and tour searches. When you return, pick up where you left off.
Kyoto, Nhật Bản|Kyoto, Japan
Ảnh minh họa|Illustrative photo
Chuyến đi của riêng bạn.|A trip of your own.
Chào bạn trở lại.|Welcome back.
Chỉ cần một vài thông tin để giữ lại những cuộc trò chuyện và lượt tìm tour.|Just a few details to keep your conversations and tour searches.
Đăng nhập để tiếp tục những điều bạn đang cân nhắc cho chuyến đi.|Log in to continue exploring the options for your trip.
hoặc tạo tài khoản|or create an account
hoặc đăng nhập bằng tài khoản|or log in with your username
Họ và tên|Full name
Tên tài khoản|Username
Mật khẩu|Password
Xác nhận mật khẩu|Confirm password
Bản mẫu tương tác · Chưa xác thực thật.|Interactive demo · Authentication is simulated.
Mật khẩu chỉ dùng để thử form, không được lưu. Email có thể liên kết sau trong Tài khoản.|Passwords are only for testing this form and are not stored. Link an email later in My account.
Tài khoản mẫu:|Demo account:
. Dùng mật khẩu thử bất kỳ từ 8 ký tự; không lưu hoặc kiểm tra mật khẩu thật.|. Use any test password of 8+ characters. Real passwords are not stored or verified.
Vào bằng tài khoản mẫu|Use demo account
Nhập họ tên từ 2 ký tự.|Enter a full name of at least 2 characters.
Nhập tên tài khoản.|Enter your username.
Dùng 3–32 chữ thường, số, dấu chấm, gạch ngang hoặc gạch dưới.|Use 3–32 lowercase letters, numbers, dots, hyphens or underscores.
Tên tài khoản đã có trong bản mẫu. Chọn tên khác.|This username already exists in the demo. Choose another.
Chưa có tài khoản này trong bản mẫu. Bạn có thể tạo tài khoản.|This account does not exist in the demo. You can create one.
Tài khoản này dùng Google. Chọn Tiếp tục bằng Google.|This account uses Google. Choose Continue with Google.
Dùng mật khẩu thử từ 8 ký tự.|Use a test password of at least 8 characters.
Mật khẩu xác nhận chưa khớp.|The passwords do not match.
Đang tạo tài khoản mẫu…|Creating demo account…
Đang đăng nhập mẫu…|Logging in to the demo…
Đã đăng nhập mẫu. Lịch sử riêng của bạn đã sẵn sàng.|Logged in to the demo. Your private history is ready.
Liên kết Google mẫu|Link demo Google account
Chọn tài khoản Google mẫu|Choose a demo Google account
Chọn email minh họa để thử luồng liên kết với tài khoản đang đăng nhập.|Choose a sample email to link it to your current account.
Chọn tài khoản để thử luồng tiếp tục bằng Google.|Choose an account to try Continue with Google.
Tài khoản Google/Gmail minh họa, không kết nối Google và không đọc thư. Không nhập thông tin thật.|Sample Google/Gmail identity. No connection to Google or access to email. Use demo information.
KHÔNG GIAN CỦA BẠN|YOUR SPACE
Tài khoản của tôi.|My account.
Hồ sơ, cách đăng nhập và những chuyến đi đã lưu.|Your profile, sign-in methods and saved trips.
Hồ sơ|Profile
Đăng nhập & liên kết|Login & connections
Dữ liệu của bạn|Your data
Về phiên tìm tour|Back to your tour chat
Thông tin cá nhân|Personal details
Tên hiển thị giúp cuộc trò chuyện gần gũi hơn. Tên tài khoản dùng để đăng nhập.|Your display name personalizes conversations. Use your username to log in.
Lưu thay đổi|Save changes
Liên kết Google để đăng nhập thuận tiện hơn. Tài khoản tạo bằng tên đăng nhập có thể bổ sung Gmail tại đây.|Link Google for easier login. Accounts created with a username can add Gmail here.
Chưa liên kết · Tùy chọn|Not linked · Optional
Đã liên kết trong bản mẫu|Linked in the demo
Ngắt liên kết|Unlink
Liên kết Google|Link Google
Chỉ dùng danh tính và email để đăng nhập, không yêu cầu quyền đọc Gmail. Mọi thao tác liên kết ở bản mẫu đều mô phỏng.|Uses your identity and email for login, without requesting Gmail read access. All connections in this demo are simulated.
Thêm cách đăng nhập bằng mật khẩu|Add password login
Cần một cách đăng nhập khác trước khi ngắt liên kết Google. Mật khẩu thử không được lưu.|Add another login method before unlinking Google. Test passwords are not stored.
Mật khẩu mới|New password
Thêm mật khẩu mẫu|Add demo password
Xuất lịch sử|Export history
Tải nhu cầu, cuộc trò chuyện và các lượt tìm dưới dạng JSON.|Download requirements, conversations and searches as JSON.
Xuất dữ liệu|Export data
Xóa lịch sử tìm tour|Delete tour search history
Xóa tất cả phiên mẫu thuộc tài khoản này.|Delete all demo chats belonging to this account.
Xóa lịch sử|Delete history
Có thể bổ sung tiếp|Ideas for later
Quản lý thiết bị đăng nhập và đăng xuất từ xa.|Manage signed-in devices and log out remotely.
Nơi khởi hành, thành viên và ưu tiên mặc định cho chuyến mới.|Default departure city, group members and preferences for new trips.
Thông báo khi lượt tìm hoàn thành hoặc có dữ kiện mới.|Notifications when a search finishes or new facts become available.
Đã đăng xuất mẫu. Lịch sử được giữ cho lần đăng nhập sau.|Logged out of the demo. History is kept for your next login.
Đã chuẩn bị tệp lịch sử mẫu để tải xuống.|Your demo history file is ready to download.
Đã đổi tên phiên.|Chat renamed.
Đã lưu hồ sơ mẫu.|Demo profile saved.
Chưa lưu được. Giữ tab mở và thử lại.|Unable to save. Keep this tab open and try again.
Đã thêm cách đăng nhập mẫu; không lưu mật khẩu.|Demo login method added. The password is not stored.
Đã liên kết Google/Gmail mẫu.|Demo Google/Gmail account linked.
Ngắt liên kết Google?|Unlink Google?
Bạn vẫn đăng nhập bằng tên tài khoản và mật khẩu mẫu. Lịch sử tìm tour được giữ.|You can still log in with your username and demo password. Tour history is kept.
Giữ liên kết|Keep connection
Đã ngắt liên kết Google mẫu.|Demo Google account unlinked.
Xóa toàn bộ lịch sử?|Delete all history?
Giữ lịch sử|Keep history
Xóa tất cả phiên|Delete all chats
Đã ghim phiên.|Chat pinned.
Đã bỏ ghim phiên.|Chat unpinned.
Xác nhận hoặc hủy thay đổi trước khi tiếp tục tìm.|Confirm or cancel changes before continuing your search.
Ẩn|Hide
Hiện|Show
Giữ nguyên|Keep current version
Xác nhận|Confirm
Nhập từ 1 đến 100 người lớn.|Enter 1–100 adults.
Nhập ngân sách hợp lệ bằng VND, lớn hơn 0.|Enter a valid budget in VND, greater than 0.
Chọn ngày từ 07/10/2026.|Choose a date on or after 7 October 2026.
Nhập từ 0 đến 20 trẻ em.|Enter 0–20 children.
Điền đủ tuổi từng trẻ (0–17), cách nhau bằng dấu phẩy.|Enter each child’s age (0–17), separated by commas.
Nhập URL HTTP(S) hợp lệ, không có tài khoản hoặc mật khẩu.|Enter a valid HTTP(S) URL without a username or password.
Chọn mức sở thích từ 0 đến 5.|Choose a preference level from 0 to 5.
Đổi ngân sách thành 32 triệu và thời lượng thành 6 ngày|Set budget to 32 million and duration to 6 days
So sánh giá các tour|Compare tour prices
Tìm nhóm khác|Find another group
  `);

  add(`
Review Giấy & Mực · Đi cùng|Giấy & Mực review · Đi cùng
Quản trị dự án · Đi cùng|Project admin · Đi cùng
Đoạn nguồn minh họa · Đi cùng|Sample source excerpt · Đi cùng
Khung review desktop / mobile · Đi cùng|Desktop / mobile preview · Đi cùng
Không gian review thiết kế|Design review space
PROTOTYPE HIỆN HÀNH · 08/10/2026|CURRENT PROTOTYPE · 08/10/2026
Đăng nhập, giữ lại cuộc trò chuyện và tiếp tục lượt tìm tour.|Log in, keep your conversations and continue previous tour searches.
Giấy & Mực, cùng trải nghiệm so sánh đã được chọn.|Giấy & Mực, with the selected comparison experience.
TRONG BẢN MẪU NÀY|IN THIS PROTOTYPE
Tài khoản · Lịch sử phiên|Accounts · Chat history
Google hoặc đăng ký đơn giản.|Google or a simple signup.
Phiên mới, nháp và những lượt tìm cũ.|New chats, drafts and previous searches.
Hồ sơ, liên kết Gmail và dữ liệu của bạn.|Profile, Gmail connection and your data.
Thử đăng nhập →|Try logging in →
Thử tạo tài khoản →|Try creating an account →
Prototype hiện hành và trang quản trị|Current prototype and admin page
Mở prototype Giấy và Mực hiện hành|Open the current Giấy & Mực prototype
Núi Phú Sĩ, ảnh điểm đến minh họa; mở prototype để xem giao diện hiện tại|Mount Fuji, illustrative destination photo; open the prototype to see the current interface
TRẢI NGHIỆM NGƯỜI DÙNG|USER EXPERIENCE
Màu giấy, mực và xanh nhạt|Paper, ink and pale green colors
Một nơi để tìm tour, hỏi thêm và quay lại những lựa chọn đang cân nhắc.|A place to find tours, ask questions and revisit options you are considering.
Đăng nhập, đăng ký và tài khoản của tôi|Login, signup and my account
Lịch sử phiên, nháp và từng lượt tìm|Chat history, drafts and individual searches
Bảng so sánh, phân tích và nguồn dữ kiện|Comparison table, analysis and evidence sources
Mở prototype ↗|Open prototype ↗
Xem mobile 390px →|View mobile at 390px →
Mở trang quản trị mẫu|Open demo admin
Quản trị dự án|Project admin
Nguồn|Sources
Phiên mẫu|Demo sessions
Liên hệ|Contacts
Đang hoạt động|Active
QUẢN TRỊ MẪU|DEMO ADMIN
Không gian riêng để nhóm theo dõi nguồn, hoạt động và những góp ý cần xử lý.|A space for the team to monitor sources, activity and feedback that needs attention.
Tổng quan phiên và lượt tìm|Session and search overview
Quản lý, kiểm tra và tạm dừng nguồn|Manage, check and pause sources
Liên hệ, trạng thái và ghi chú nội bộ|Contacts, statuses and internal notes
Mở trang admin ↗|Open admin ↗
Xem liên hệ →|View contacts →
BẠN REVIEW NHỮNG GÌ?|WHAT TO REVIEW
Cảm giác dễ đọc|An easy read
quan trọng hơn hiệu ứng.|matters more than effects.
Nhìn ra khác biệt giữa các tour?|Can you see the differences between tours?
Giá công bố, thời lượng, mua sắm và chính sách có dễ đối chiếu không?|Are published prices, duration, shopping stops and policies easy to compare?
Hiểu lý do và phần còn thiếu?|Are the reasons and gaps clear?
Mở “Vì sao có gợi ý này?” và bấm một ô trong bảng để xem nguồn.|Open “Why this suggestion?” and click a table cell to see its source.
Dùng trên điện thoại có thuận tay?|Does it work comfortably on a phone?
Chọn Mobile trong khung review; thử cuộn bảng và mở/đóng panel nguồn.|Choose Mobile in the preview; try scrolling the table and opening or closing a source panel.
Ý tưởng được chọn theo công việc cần làm.|References chosen for the task at hand.
Tham khảo cách tổ chức thông tin; giao diện, icon và bố cục của prototype được tự dựng.|References for organizing information; the interface, icons and layouts were built for this prototype.
01 / DU LỊCH|01 / TRAVEL
Klook · Tour & trải nghiệm ↗|Klook · Tours & experiences ↗
Ngôn ngữ tour, điểm đến và thứ tự ảnh → tên → thông tin.|Tour terminology, destinations and the photo → name → details hierarchy.
02 / SO SÁNH|02 / COMPARISON
Đặt đối tượng và dữ kiện theo cùng hàng để đối chiếu trực tiếp.|Align options and facts in the same rows for direct comparison.
03 / GIẢI THÍCH|03 / EXPLANATIONS
Giữ dữ kiện chính luôn hiện; thông tin bổ sung mở khi cần.|Keep core facts visible; expand details when needed.
Nhãn rõ, hint cạnh field và lỗi cụ thể. Tham khảo cho bước nhập/review.|Clear labels, nearby hints and specific errors for input and review.
Ảnh & chữ có nguồn.|Photos & type with credits.
Ảnh điểm đến chỉ minh họa, không xác nhận nội dung tour hoặc dịch vụ.|Destination photos are illustrative and do not verify tour content or services.
Núi Phú Sĩ và chùa Chureito|Mount Fuji and Chureito Pagoda
Phố gần đền Sensō-ji tại Tokyo|A street near Sensō-ji Temple in Tokyo
Cổng torii đỏ ở Kyoto|Red torii gates in Kyoto
Ảnh:|Photos:
. Font:|. Fonts:
và|and
, SIL Open Font License. Icon và ký hiệu “đi cùng” tự vẽ; tên thương hiệu đang là tên tạm.|, SIL Open Font License. Icons and the “đi cùng” mark were drawn for the prototype; the brand name is provisional.
Chỉ giữ prototype hiện hành và trang quản trị. Ảnh điểm đến, tour, tài khoản và phản hồi đều minh họa.|Only the current prototype and admin page are kept. Photos, tours, accounts and responses are illustrative.
HTML/CSS/JS thử nghiệm trong PLANNING · Auth/Google và lưu phiên trên trình duyệt là mô phỏng; chưa tích hợp backend thật.|Experimental HTML/CSS/JS in PLANNING · Authentication, Google and browser history are simulated; no real backend integration.
Hệ thống hỗ trợ lựa chọn tour cá nhân hóa|A system for personalized tour selection
← Bảng review thiết kế|← Design review
Giấy & Mực · Bản hiện hành|Giấy & Mực · Current version
Khung|Viewport
Mở riêng ↗|Open separately ↗
Khung đổi viewport thật của prototype · Dữ liệu minh họa · Chọn khung để review tài khoản, phiên và so sánh|Changes the prototype’s actual viewport · Sample data · Choose a size to review accounts, chats and comparisons
Prototype lựa chọn tour|Tour selection prototype
TRANG NGUỒN MẪU · KHÔNG PHẢI WEBSITE NHÀ CUNG CẤP|SAMPLE SOURCE PAGE · NOT THE SUPPLIER’S WEBSITE
Về bảng so sánh ↗|Back to comparison ↗
MINH HỌA LIÊN KẾT TỚI ĐÚNG VỊ TRÍ|DEMONSTRATING A LINK TO THE EXACT EXCERPT
Dữ liệu fixture giống bảng so sánh. Đoạn được dẫn tới có nền vàng nhạt; anchor chỉ hoạt động trong trang mẫu này. Nguồn thật cần locator đã kiểm tra và fallback.|The same sample data as the comparison table. The linked excerpt is highlighted; anchors only work on this demo page. Real sources need checked locators and fallbacks.
Nhà cung cấp|Supplier
Nhận diện theo nguồn|Identified by source
Giá công bố|Published price
VND / người lớn|VND / adult
Lịch & thời lượng|Dates & duration
Chưa xác nhận còn chỗ|Availability not confirmed
Lịch trình|Itinerary
Các điểm đến công bố|Published destinations
Bao gồm|Included
Theo lịch đang xem|For this departure
Ưu tiên của bạn|Your preference
Phụ thu|Surcharges
Ngoài giá công bố|Beyond the published price
Hủy / đổi|Cancellation / changes
Cần đọc điều kiện|Check the conditions
Dữ liệu & nguồn|Data & sources
Theo từng dữ kiện|For each fact
Một phần|Partial
Nhà cung cấp công bố|Supplier published
5 ngày, không có điểm mua sắm trong lịch trình mẫu.|5 days, with no shopping stops in the sample itinerary.
Cân bằng các ưu tiên|Balanced preferences
Phụ thu phòng đơn chưa được công bố.|Single-room surcharge not published.
Ưu tiên giá công bố|Lower published price
Giá công bố thấp hơn trong nhóm, nhiều điểm tham quan.|A lower published price in this group, with many sights.
6 ngày và 2 điểm mua sắm theo lịch trình.|6 days and 2 scheduled shopping stops.
Ưu tiên thời lượng|Preferred duration
5 ngày, giá công bố nằm trong khoảng ưu tiên.|5 days, with a published price within the preferred range.
Chính sách hủy và phụ thu còn thiếu dữ kiện.|Cancellation policy and surcharges are missing.
Cần xác nhận mức phụ thu phòng đơn.|Single-room surcharge needs confirmation.
Giá công bố thấp hơn trong nhóm minh họa mới.|A lower published price in the new sample group.
6 ngày và 1 điểm mua sắm theo lịch trình.|6 days and 1 scheduled shopping stop.
Chính sách hủy chưa được công bố.|Cancellation policy not published.
Bạn cung cấp|Shared by you
Tour bạn gửi được giữ để đối chiếu.|Your shared tour is kept for comparison.
Giá công bố cao hơn khoảng ưu tiên.|Published price exceeds the preferred range.
Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình|Return flights, 4 hotel nights, scheduled meals
Vé bay khứ hồi, 5 đêm khách sạn, bữa ăn theo lịch trình|Return flights, 5 hotel nights, scheduled meals
Vé bay, khách sạn; bữa ăn chưa rõ|Flights and hotel; meal details unknown
Vé bay, 4 đêm khách sạn; bữa ăn chưa rõ|Flights and 4 hotel nights; meal details unknown
Không có trong lịch trình công bố|None in the published itinerary
2 điểm theo lịch trình|2 scheduled stops
1 điểm theo lịch trình|1 scheduled stop
Phòng đơn chưa công bố|Single room: not published
Phòng đơn: 4.200.000 ₫|Single room: 4,200,000 VND
Phòng đơn: 4.000.000 ₫|Single room: 4,000,000 VND
Phòng đơn: 3.800.000 ₫|Single room: 3,800,000 VND
Trước 30 ngày: phí 20% giá tour|30+ days before departure: fee of 20% of tour price
Trước 30 ngày: phí 30% giá tour|30+ days before departure: fee of 30% of tour price
Trước 30 ngày: phí 25% giá tour|30+ days before departure: fee of 25% of tour price
Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến|Mount Fuji and Chureito Pagoda, illustrative destination photo
Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến|Red torii gates in Kyoto, illustrative destination photo
Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến|A street near Sensō-ji Temple in Tokyo, illustrative destination photo
Những cổng torii nối tiếp nhau ở Kyoto, ảnh điểm đến minh họa|A series of torii gates in Kyoto, illustrative destination photo
Giá trị ghi nhận · minh họa|Recorded value · Sample
Dữ kiện|Fact
Độ đầy đủ tour|Tour completeness
Trạng thái nguồn|Source status
Xác minh độc lập|Independent verification
Chưa có|Not available
Ghi nhận lúc|Recorded at
Lịch đang xem|Departure being viewed
Trích đoạn minh họa, không phải nội dung crawl thật|Sample excerpt in Vietnamese, not real collected content
Chưa có locator cho dữ kiện này|No locator for this fact
Mở đúng đoạn nguồn mẫu|Open the exact sample excerpt
Chưa có đoạn nguồn cho dữ kiện này|No source excerpt for this fact
Giới hạn cần biết|Limits to know
Thời điểm ghi nhận không tự chứng minh dữ liệu còn mới. Cả hai hướng dùng cùng fixture để review cách trình bày.|A recording time does not prove freshness. The prototype uses the same sample data to review its presentation.
Thử đổi lịch minh họa|Try another sample departure
Lịch / giá đi kèm|Departure / linked price
Control này kiểm tra giá, ngày và nguồn cùng đổi. Đây chưa phải kết quả đánh giá/ranking lại của backend.|This control checks that price, date and evidence change together. It is not a backend reassessment or ranking.
Có trong nguồn mẫu|Present in sample source
Chưa đọc được nguồn|Source could not be read
Chưa có dữ kiện|No data yet
Chưa có chứng cứ cho dữ kiện này|No evidence for this fact
Chưa có thời điểm|No timestamp
Nguồn tham chiếu đang được mô phỏng là không đọc được. Bạn vẫn có thể xem các gợi ý tìm thêm.|The reference source is simulated as unreadable. Additional suggestions remain available.
Không có dữ kiện để kết luận. Thông tin còn thiếu không được coi là đã đáp ứng yêu cầu.|No facts to support a conclusion. Missing information does not count as meeting a requirement.
Đây là giá công bố cho một người lớn ở lịch đang xem. Chưa có đủ mọi phụ thu để tính tổng cuối cho nhóm.|This is the published price for one adult on this departure. Some surcharges are missing, so a final group total cannot be calculated.
Có lịch khởi hành công bố chưa có nghĩa tour còn chỗ. Cần xác nhận với nhà cung cấp.|A published departure date does not guarantee availability. Confirm with the supplier.
Dữ kiện do nhà cung cấp công bố. Bản mẫu không có nguồn độc lập để xác nhận lại.|Facts published by the supplier. This demo has no independent source to verify them.
Vì sao có gợi ý này?|Why this suggestion?
Vì sao gợi ý tương tự?|Why a similar suggestion?
Cơ sở trong bộ dữ liệu minh họa|Basis in the sample data
Cùng phạm vi Nhật Bản|The same Japan scope
Dựa trên tour bạn gửi|Based on your shared tour
Những điểm hợp với ưu tiên|How it matches your preferences
Tour nằm trong phạm vi Nhật Bản được lấy từ URL tham chiếu. Chưa có nhu cầu cá nhân để kết luận tối ưu cho bạn.|The Japan scope comes from the reference URL. Without personal requirements, it cannot be called optimal for you.
Điều cần cân nhắc|Things to consider
Kiểm tra dữ kiện|Check the facts
Thứ tự và lý do này là ví dụ thiết kế. Bản mẫu không tính điểm, không tự rank và không xác nhận tour phù hợp khi ràng buộc bắt buộc chưa biết.|The order and reasons are design examples. The demo does not score, rank or confirm suitability when mandatory constraints are unknown.
LÝ DO & ĐÁNH ĐỔI|REASONS & TRADE-OFFS
Gợi ý tương tự|Similar suggestion
Cùng phạm vi Nhật Bản từ tour bạn gửi.|The same Japan scope as your shared tour.
Cơ sở gợi ý tương tự|Basis for similar suggestions
/ người lớn · chưa đủ mọi phụ thu|/ adult · Some surcharges missing
So sánh tour theo nhu cầu đã xác nhận, mọi thông tin là minh họa|Compare tours against confirmed requirements; all information is illustrative
Tiêu chí|Criteria
Gợi ý minh họa|Sample suggestion
Nguồn đọc lỗi|Source read error
Những tour tương tự,|Similar tours,
đặt cạnh tour bạn gửi.|beside your shared tour.
Tìm thêm theo phạm vi tour bạn gửi. Chưa suy ra nhu cầu hoặc sở thích cá nhân.|Find more tours within your reference tour’s scope. Personal needs or preferences are not inferred.
Gợi ý theo nhu cầu đã xác nhận. Đối chiếu điểm hợp, điều cần cân nhắc và nguồn phía sau mỗi dữ kiện.|Suggestions for confirmed requirements. Compare preferences, trade-offs and the source behind each fact.
Theo phạm vi tour tham chiếu|Within the reference tour’s scope
Cùng nhu cầu|The same requirements
Chưa có nhu cầu cá nhân. Giá, lịch và đặc điểm tour gửi chưa được coi là ngân sách hoặc sở thích của bạn.|No personal requirements yet. Your shared tour’s price, dates and features are not treated as your budget or preferences.
Chưa có gợi ý để đối chiếu.|No suggestions to compare yet.
Trong tình huống minh họa này, chưa tìm được tour đáp ứng phạm vi đã xác nhận.|In this demo scenario, no tours were found within the confirmed scope.
Tour bạn gửi vẫn được giữ bên dưới.|Your shared tour is kept below.
Trao đổi ở khung chat để điều chỉnh phạm vi tìm.|Use chat to adjust the search scope.
Sửa yêu cầu|Edit requirements
Bạn cung cấp · URL minh họa|Shared by you · Sample URL
Tour tham chiếu chưa đọc được|Reference tour could not be read
Giữ URL và các gợi ý tìm thêm. Chưa đủ dữ kiện để kết luận tour tham chiếu.|The URL and additional suggestions are kept. There is not enough data to assess the reference tour.
Thử lại nguồn|Retry source
Bạn cung cấp · Tham chiếu để đối chiếu|Shared by you · Comparison reference
/ người lớn · minh họa|/ adult · Sample
Chưa còn nhóm gợi ý mới trong bộ mẫu.|No more suggestion groups in the sample set.
Nhóm hiện tại được giữ lại. Bạn có thể sửa yêu cầu; bản thật sẽ báo giới hạn nguồn và phạm vi tìm.|The current group is kept. Edit your requirements; the real app will report source limits and search scope.
Hiện có 2 gợi ý để đối chiếu.|2 suggestions are available to compare.
Không thêm tour chưa đủ điều kiện chỉ để lấp đủ ba lựa chọn.|Tours that do not qualify are not added just to fill three slots.
Đây là gợi ý tương tự, chưa phải tối ưu cá nhân.|These are similar suggestions, not personally optimized options.
Cơ sở là phạm vi Nhật Bản từ tour bạn gửi; bổ sung nhu cầu nếu muốn so theo ưu tiên riêng.|Based on the Japan scope from your shared tour. Add your needs to compare personal preferences.
Một nguồn tham chiếu chưa đọc được.|A reference source could not be read.
Các gợi ý tìm thêm vẫn được giữ. Bạn có thể thử lại nguồn tham chiếu.|Additional suggestions are kept. You can retry the reference source.
Bạn đang xem lịch khác của gợi ý 01.|You are viewing another departure for suggestion 01.
Giá, ngày và nguồn trong fixture đã đổi cùng nhau. Thứ tự gợi ý chưa được backend đánh giá lại.|Sample price, date and evidence changed together. The backend has not reassessed the suggestion order.
Giá thấp hơn, thời lượng dài hơn|Lower price, longer duration
Xem căn cứ|View basis
Xem dữ kiện|View facts
Cơ sở đang xem|Current basis
Ưu tiên và giới hạn|Preferences and limits
Nhóm và thứ tự trên prototype là dữ liệu minh họa cố định. Backend sẽ cung cấp ranking, lý do, phạm vi nguồn và policy; bản mẫu không tính điểm hoặc chọn ba phần tử đầu từ API.|Groups and order are fixed sample data. The backend will provide ranking, reasons, source scope and policy; the demo does not score or select the first three API items.
Tour bạn gửi|Your shared tour
Giữ làm tham chiếu khi có URL. Cách đếm ba gợi ý mới cộng tour tham chiếu đang cần review, chưa phải contract đã duyệt.|Kept as a reference when a URL is supplied. Three new suggestions plus a reference tour is still under review, not an approved contract.
01 · Gợi ý, không quyết định thay bạn|01 · Suggestions, not decisions on your behalf
Nhìn lý do và đánh đổi của từng tour trước khi quyết định. Có thể yêu cầu nhóm khác hoặc sửa nhu cầu.|Review each tour’s reasons and trade-offs before deciding. Request another group or change your needs.
02 · Giá gắn với một lịch cụ thể|02 · Price belongs to a specific departure
Giá công bố/người lớn, phụ thu, phòng và số người là các dữ kiện khác nhau. Chưa đủ dữ kiện thì chưa kết luận tổng cuối.|Published adult price, surcharges, room setup and group size are separate facts. Without enough data, a final total cannot be determined.
03 · Mở nguồn ở từng ô|03 · Open each cell’s source
Bấm vào giá, lịch, chính sách hoặc phần còn thiếu để xem trạng thái dữ kiện, nguồn, trích đoạn và giới hạn.|Click a price, date, policy or missing fact to see its status, source, excerpt and limits.
04 · Phân biệt các trạng thái|04 · Distinguish data statuses
Dữ kiện có hay thiếu khác độ đầy đủ của tour. Nhà cung cấp công bố khác xác minh độc lập. Thời điểm ghi nhận không tự chứng minh dữ liệu còn mới.|A present or missing fact differs from tour completeness. Supplier publication differs from independent verification. A recording time does not prove freshness.
Căn cứ của lượt đang xem|Basis for this search
YÊU CẦU ĐÃ DÙNG|REQUIREMENTS USED
Tour và thứ tự cố định để review bố cục. Bộ mẫu chưa lọc hoặc xếp hạng theo thay đổi nhu cầu; không kết luận đã đáp ứng mọi ràng buộc.|Fixed tours and order for layout review. The demo does not filter or rank against changed needs or conclude that every constraint is met.
Bạn muốn cân nhắc điều gì cho chuyến đi tiếp theo?|What would you like to consider for your next trip?
Đã chuẩn bị nhóm tour minh họa. Bạn có thể hỏi thêm hoặc sửa yêu cầu trước khi tìm tiếp.|A sample tour group is ready. Ask a question or edit requirements before searching again.
có nháp|draft pending
Fixture minh họa|Sample data
Yêu cầu đã dùng cho nhóm hiện tại|Requirements used for the current group
Phạm vi dùng cho nhóm hiện tại|Scope used for the current group
Chọn đăng nhập hoặc đăng ký|Choose login or signup
Cài đặt tài khoản|Account settings
Đóng lịch sử|Close history
Thu gọn lịch sử|Collapse history
Mở lịch sử phiên|Open chat history
Đóng tài khoản|Close account
Đóng hộp thoại|Close dialog
Đóng panel nguồn|Close source panel
Gửi tin nhắn|Send message
Gửi ghi chú|Add note
Ví dụ: Minh Phú|Example: Minh Phú
Ví dụ: minhphu|Example: minhphu
Ví dụ: đổi ngân sách, giải thích giá hoặc tìm nhóm khác…|Try changing your budget, asking about prices or finding another group…
Ví dụ: có người lớn tuổi, ưu tiên đi thong thả…|For example: travelling with older adults, prefer a slower pace…
  `);

  add(`
QUẢN TRỊ MẪU · DỮ LIỆU MÔ PHỎNG|DEMO ADMIN · SIMULATED DATA
Về trải nghiệm người dùng ↗|Back to user experience ↗
Không gian quản trị dự án|Project administration
Admin mẫu · Quyền mô phỏng|Demo admin · Simulated permissions
MỘT GÓC NHÌN TOÀN DỰ ÁN|A VIEW OF THE WHOLE PROJECT
Theo dõi rõ.|Monitor clearly.
Xử lý đúng chỗ.|Act where it matters.
Nguồn dữ liệu, những cuộc trao đổi và góp ý đang cần nhóm quan tâm.|Data sources, conversations and feedback that need the team’s attention.
Khoảng thời gian mẫu|Sample date range
7 ngày đến 07/10/2026|7 days ending 07/10/2026
Ngày 07/10/2026|07/10/2026 only
Toàn bộ mẫu|All demo records
Mọi số liệu và thao tác đều mô phỏng trong tab này. Chưa kết nối hệ thống, chưa crawl hoặc gửi phản hồi ra ngoài.|All figures and actions are simulated in this tab. No system connection, crawling or external responses.
Tổng quan|Overview
Nguồn dữ liệu|Data sources
Phiên trao đổi|Sessions
Tổng quan dự án|Project overview
Các lượt tìm trong kỳ|Searches in this period
Đếm theo lượt, gồm cả lỗi|Counted per search, including failures
Tin nhắn chỉ đếm tin người dùng. Retry cùng lượt không tạo phiên hoặc lượt tìm mới.|Only user messages are counted. Retrying the same search does not create a new session or search.
Cần nhóm quan tâm|Needs team attention
Trạng thái hiện tại|Current status
Hoạt động gần đây|Recent activity
Xem các phiên →|View sessions →
Quản lý khả năng lấy dữ liệu và trạng thái truy cập của từng nguồn.|Manage each source’s collection capability and access status.
Thêm nguồn mẫu|Add demo source
Thêm nguồn vào danh sách kiểm tra|Add a source to the checklist
Tên hiển thị|Display name
Domain mẫu|Sample domain
Profile tham chiếu|Reference profile
Nguồn mới là nháp, chưa duyệt. Kiểm tra mẫu rồi bật nguồn; không gọi domain thật.|New sources start as unapproved drafts. Run the demo check before enabling; no real domain is contacted.
Lưu nguồn nháp|Save source draft
Đóng|Close
Tất cả|All
Đang bật|Enabled
Tạm dừng|Paused
Bản nháp|Draft
Tìm nguồn|Search sources
Nguồn dữ liệu mẫu|Sample data sources
Nguồn / domain|Source / domain
Thu thập|Collection
Quyền truy cập|Access
Snapshot mẫu|Sample snapshot
Lần đọc gần nhất|Last read
Chi tiết|Details
Tạm dừng không xóa snapshot cũ. Nguồn bị chặn hoặc chưa kiểm tra không thể bật.|Pausing keeps old snapshots. Blocked or unchecked sources cannot be enabled.
Liên hệ từ người dùng|User contacts
Phân loại, cập nhật trạng thái và ghi nhận cách nhóm xử lý.|Categorize, update statuses and record how the team responds.
Thử gửi góp ý mẫu ↗|Try demo feedback ↗
Trạng thái|Status
Chưa xử lý|New
Đang xử lý|In progress
Đã xử lý|Resolved
Liên hệ mẫu trong khoảng thời gian đã chọn|Demo contacts in the selected period
Nội dung|Message
Gửi lúc|Sent at
Xử lý|Actions
Ghi chú chỉ dành cho nhóm. Cập nhật trạng thái không gửi email hay tin nhắn cho người dùng.|Notes are for the team. Status updates do not send emails or messages to users.
Theo dõi số phiên, tin người dùng và lượt tìm trong phạm vi đã chọn.|Monitor sessions, user messages and searches in the selected range.
Mỗi dòng là một phiên|One session per row
Trạng thái phiên|Session status
Đang mở|Open
Không hoạt động|Idle
Hết hạn|Expired
Phiên trao đổi mẫu có hoạt động trong kỳ|Demo sessions active in this period
Phiên / bắt đầu|Session / started
Tin người dùng|User messages
Lượt tìm gần nhất|Latest search
Theo dõi|Actions
Chi tiết chỉ có số đếm và tiến độ tác vụ. Bản mẫu không lưu nội dung trao đổi hay nhu cầu tour vào trang quản trị.|Details only show counts and job progress. Conversation content and personal tour requirements are not stored in admin.
Dữ liệu demo giữ trong tab đến khi đóng tab.|Demo data stays in this tab until it is closed.
Khôi phục dữ liệu mẫu|Reset demo data
CHI TIẾT · MÔ PHỎNG|DETAILS · DEMO
Bật JavaScript để dùng trang quản trị mẫu.|Enable JavaScript to use demo admin.
Đã duyệt mẫu|Demo approved
Bị chặn|Blocked
Chưa kiểm tra|Unchecked
Ổn định|Healthy
Hoàn tất|Completed
Lỗi|Failed
Đã hủy|Cancelled
Đang chạy|Running
Tất cả bản ghi mô phỏng|All simulated records
Phiên có hoạt động|Active sessions
Đếm phiên riêng biệt trong kỳ|Distinct sessions in this period
Không gồm phản hồi AI và log|Excludes AI responses and logs
Gồm hoàn tất, đang chạy, lỗi, hủy|Includes completed, running, failed and cancelled
Liên hệ cần xử lý|Contacts needing attention
Liên hệ trong kỳ, chưa đóng|Open contacts in this period
Góp ý và yêu cầu hỗ trợ của người dùng|User feedback and support requests
Xử lý →|Handle →
Tạm dừng, chưa duyệt hoặc bị chặn|Paused, unapproved or blocked
Xem nguồn →|View sources →
Snapshot hiện tại · chưa là dữ liệu crawl thật|Current snapshot · Not real crawled data
Chưa có hoạt động trong khoảng thời gian này.|No activity in this period.
Quản lý →|Manage →
Không có nguồn theo bộ lọc này.|No sources match these filters.
Mở liên hệ →|Open contact →
Không có liên hệ theo bộ lọc và khoảng thời gian này.|No contacts match these filters and dates.
Xem tiến độ →|View progress →
Không có phiên có hoạt động theo bộ lọc này.|No active sessions match this filter.
Tạm dừng nguồn|Pause source
Bật nguồn mẫu|Enable demo source
Kiểm tra & duyệt mẫu|Check & approve demo
Làm mới dữ liệu mẫu|Refresh sample data
Check và refresh chỉ đổi trạng thái mô phỏng. Nguồn bị chặn giữ bị chặn; chưa có request tới website.|Check and refresh only change simulated status. Blocked sources stay blocked; no website requests are made.
Tên nguồn|Source name
Ghi chú nguồn|Source notes
Lưu thông tin nguồn mẫu|Save demo source details
Lịch sử quản lý|Management history
Chưa có thay đổi trong tab này.|No changes in this tab yet.
Mã liên hệ|Contact ID
Cách liên hệ|Contact details
Người dùng chưa để lại|Not provided by the user
Ghi chú nội bộ|Internal note
Lưu xử lý mẫu|Save demo update
Chưa gửi email hoặc phản hồi ra ngoài.|No email or response sent externally.
Tiến độ phiên|Session progress
Hoạt động cuối|Last activity
Tiến độ mô phỏng. Không hiển thị nội dung chat hoặc thông tin nhu cầu cá nhân.|Simulated progress. Chat content and personal requirements are not shown.
Kiểm tra lúc|Checked at
Field có dữ liệu|Fields with data
Chưa xác định|Unknown
Chất lượng|Health
Đã cập nhật trạng thái nguồn mẫu.|Demo source status updated.
Đã mô phỏng kiểm tra nguồn. Nguồn bị chặn không được bật.|Source check simulated. Blocked sources cannot be enabled.
Đã cập nhật thời điểm làm mới mẫu; chưa crawl thật.|Demo refresh time updated; no real crawl performed.
Tên nguồn cần có nội dung.|Enter a source name.
Đã cập nhật tên và ghi chú nguồn mẫu.|Demo source name and notes updated.
Đã lưu trạng thái và ghi chú nội bộ trong mẫu.|Demo status and internal note saved.
Điền đủ tên, domain mẫu và profile.|Enter a name, sample domain and profile.
Đã thêm nguồn nháp. Kiểm tra mẫu trước khi bật.|Draft source added. Run the demo check before enabling it.
Đã khôi phục nguồn, liên hệ và số đếm demo.|Demo sources, contacts and counts reset.
Giá theo lịch|Departure-specific price
Ngày khởi hành|Departure date
Chính sách hủy|Cancellation policy
Tin người dùng · số đếm mẫu|User messages · Sample count
Lượt tìm mẫu|Sample search
Tin người dùng đã nhận · không lưu nội dung|User message received · Content not stored
Bắt đầu lượt tìm minh họa|Sample search started
Tạo liên hệ mẫu|Demo contact created
Thêm nguồn nháp|Draft source added
Sửa tên và ghi chú nguồn|Source name and notes edited
Tạm dừng nguồn mẫu|Demo source paused
Kiểm tra/duyệt nguồn mô phỏng|Source check / approval simulated
Làm mới dữ liệu mô phỏng|Sample data refreshed
Nhóm đã kiểm tra điều gì, cần theo dõi gì thêm…|What the team checked and what needs follow-up…
Tên hoặc domain mẫu|Sample name or domain
  `);
  add(`
Liên hệ|Contact
Tạo liên hệ mẫu|Create demo contact
Phần chưa biết cũng cần cân nhắc|Consider what is still unknown
Giá chưa phải tổng cuối cho nhóm|Price is not the final group total
Các giá thuộc lịch công bố; phụ thu và điều kiện phòng có thể làm thay đổi tổng chi phí.|Prices belong to published departures; surcharges and room conditions can change the total cost.
Đề xuất trong phạm vi nguồn được hỗ trợ.|Suggestions within supported sources.
Không khẳng định tốt nhất toàn thị trường.|Not a claim of the best tour on the market.
Chưa đủ nhiều tour để so sánh đánh đổi.|Not enough tours to compare trade-offs.
Chưa gồm phụ thu. Chưa phải tổng cuối của chuyến đi.|Surcharges excluded. This is not the final trip total.
Chưa phải tổng cuối của chuyến đi.|This is not the final trip total.
Chưa gồm phụ thu và giá trẻ em. Chưa phải tổng cuối của chuyến đi.|Surcharges and children’s prices excluded. This is not the final trip total.
Giá tour mẫu cho nhóm chưa rõ|Sample tour price for an unspecified group
Bạn muốn thay đổi hay hỏi thêm điều gì?|What would you like to change or ask?
Có người lớn tuổi, muốn đi thong thả…|Travelling with older adults, prefer a slower pace…
Điều bạn thấy hữu ích, hoặc muốn nhóm cải thiện…|What you found useful, or would like the team to improve…
Điều hướng chính|Main navigation
Cách xem kết quả|Result views
Đồng bộ giữa yêu cầu và kết quả|Requirements and results alignment
Bảng so sánh tour, có thể cuộn ngang|Tour comparison table, scrolls horizontally
Cuộn bảng về bên trái|Scroll table left
Cuộn bảng sang bên phải|Scroll table right
Các phiên tìm tour|Your tour chats
Ghi chú tùy chọn|Optional notes
Chat mô phỏng|Demo chat
Dữ liệu minh họa|Sample data
Nhật Bản · từ URL|Japan · From URL
Nhật Bản từ URL|Japan from URL
Giá trị ghi nhận|Recorded value
minh họa|sample
Đã sửa|Edited
thay đổi|changes
Đang sửa|Editing
Xác nhận tất cả|Confirm all
Chờ xác nhận|Awaiting confirmation
Bạn có thể hỏi về tour, sửa yêu cầu hoặc tiếp tục một lượt tìm trước đây.|Ask about tours, edit requirements or continue a previous search.
Lịch sử phiên|Chat history
Đóng lịch sử phiên|Close chat history
Đóng chi tiết|Close details
Khu vực quản trị|Admin sections
Đã điền nhu cầu mẫu Nhật Bản vào form để review. Chưa đổi yêu cầu đã xác nhận.|Sample Japan details filled in for review. Confirmed requirements are unchanged.
Mất kết nối trong tình huống mô phỏng. Yêu cầu đã xác nhận vẫn được giữ; bảng bên dưới là lượt kết quả trước.|Connection lost in the demo scenario. Confirmed requirements are kept; the table below shows the previous search.
Mất kết nối trong tình huống mô phỏng. Yêu cầu đã xác nhận vẫn được giữ; chưa có kết quả để so sánh.|Connection lost in the demo scenario. Confirmed requirements are kept; no results are available to compare yet.
Phạm vi tìm|Search scope
Điểm đến tham chiếu|Reference destination
Thông tin tour bạn gửi.|Your shared tour’s details.
Phạm vi Nhật Bản được lấy từ tour này; chưa suy ra ưu tiên cá nhân.|The Japan scope comes from this tour. Personal preferences are not inferred.
Giá công bố cao hơn khoảng ưu tiên. Tour vẫn được giữ để bạn xem.|Published price exceeds the preferred range. The tour is still available for reference.
Ảnh minh họa điểm đến của tour tham chiếu|Illustrative destination photo for the reference tour
Theo yêu cầu đã dùng cho lượt kết quả này|Based on the requirements used for this search
Danh sách nguồn, cuộn ngang nếu cần|Source list, scroll horizontally if needed
Danh sách liên hệ|Contact list
Danh sách phiên|Session list
Tên hoặc domain|Name or domain
Dùng domain .example cho dữ liệu minh họa|Use an .example domain for sample data
Trang quản trị mẫu: nguồn dữ liệu, liên hệ và phiên trao đổi. Toàn bộ dữ liệu mô phỏng.|Demo administration: sources, contacts and sessions. All data is simulated.
Giấy & Mực: prototype ba màn giới thiệu, điền nhu cầu và so sánh tour có chat. Dữ liệu minh họa.|Giấy & Mực: an overview, trip details and tour comparison prototype with chat. Sample data.
Prototype Giấy & Mực đã chọn: ba màn, chat, phân tích và trạng thái mô phỏng.|The selected Giấy & Mực prototype: three screens, chat, analysis and simulated states.
  `);
  const folded = Object.fromEntries(Object.entries(catalog).map(([key,value])=>[key.toLocaleLowerCase("vi-VN"),value.toLowerCase()]));
  function translate(value) {
    if (Object.hasOwn(catalog,value)) return catalog[value];
    if (Object.hasOwn(folded,value)) return folded[value];
    for (const [pattern,render] of templates) {
      const match = value.match(pattern);
      if (match) return render(...match.slice(1));
    }
    // Only combine known UI clauses. Unrecognized free text remains untouched.
    if (value.includes(" · ")) {
      const parts = value.split(" · ");
      const result = parts.map(part => translate(part));
      if (result.some((part,index)=>part!==parts[index])) return result.join(" · ");
    }
    if (value.includes(". ")) {
      const parts = value.split(/(?<=\.) /), result = parts.map(part=>translate(part));
      if (result.some((part,index)=>part!==parts[index])) return result.join(" ");
    }
    const colon = value.match(/^([^:]+): (.+)$/);
    if (colon && (Object.hasOwn(catalog,colon[1]) || Object.hasOwn(folded,colon[1]))) return translate(colon[1])+": "+translate(colon[2]);
    return value;
  }
  const number = value => value.replace(/\./g,"").replace(",",".");
  const currency = value => Number(value.replace(/\./g,"")).toLocaleString("en-GB")+" VND";
  const countLabel = (count,noun,plural=noun+"s") => count+" "+(count==="1"?noun:plural);
  const templates = [
    [/^(\d+) ngày (\d+) đêm$/, (days,nights)=>days+" days "+nights+" nights"],
    [/^(\d+(?:,\d+)?) triệu$/, amount=>number(amount)+" million VND"],
    [/^([\d.]+) ₫$/, amount=>currency(amount)],
    [/^([\d.]+) ₫ \/ người lớn$/, amount=>currency(amount)+" / adult"],
    [/^([\d.]+) ₫ × (\d+) người lớn$/,(amount,count)=>currency(amount)+" × "+count+" adults"],
    [/^(\d+) người$/, count=>countLabel(count,"person","people")],
    [/^(\d+) người lớn$/, count=>countLabel(count,"adult")],
    [/^(\d+) thay đổi chờ xác nhận$/, count=>countLabel(count,"change")+" awaiting confirmation"],
    [/^(\d+) chờ xác nhận$/, count=>count+" awaiting confirmation"],
    [/^Đã sửa (.+)$/, label=>"Edited "+translate(label)],
    [/^Đang sửa (.+)$/, label=>"Editing "+translate(label)],
    [/^Xác nhận tất cả (\d+) thay đổi$/, count=>(count==="1"?"Confirm ":"Confirm all ")+countLabel(count,"change")],
    [/^Xác nhận (\d+) thay đổi$/, count=>"Confirm "+countLabel(count,"change")],
    [/^Sửa (.+)$/, label=>"Edit "+translate(label)],
    [/^Bỏ thay đổi (.+)$/, label=>"Remove change: "+translate(label)],
    [/^Hiện (.+)$/, label=>"Show "+translate(label)],
    [/^Ẩn (.+)$/, label=>"Hide "+translate(label)],
    [/^Menu tài khoản (.+)$/, name=>"Account menu for "+name],
    [/^Tùy chọn phiên (.+)$/, title=>"Chat options for "+title],
    [/^Lượt tìm (\d+)(.*)$/, (count,tail)=>"Search "+count+tail],
    [/^(\d+) phiên và (\d+) lượt tìm trên trình duyệt này\. Mỗi tài khoản có lịch sử riêng; bản mẫu chưa đồng bộ sang thiết bị khác\.$/,(chats,searches)=>chats+" chats and "+searches+" searches in this browser. Each account has its own history; this demo does not sync across devices."],
    [/^Tất cả phiên, nhu cầu, tin nhắn và lượt tìm của @(.+) sẽ bị xóa khỏi bản mẫu này\. Hồ sơ và liên kết Google được giữ\.$/, username=>"All chats, requirements, messages and searches for @"+username+" will be deleted from this demo. The profile and Google connection are kept."],
    [/^Còn (\d+) thông tin cần kiểm tra\. Các giá trị đã nhập được giữ lại\.$/,count=>count+" fields need attention. Your entries are kept."],
    [/^Điền (.+) trước khi tìm\.$/,label=>"Enter "+translate(label)+" before searching."],
    [/^(\d+) tiêu chí khác với lượt kết quả đang xem$/,count=>count+" criteria differ from the search you are viewing"],
    [/^Giá tour mẫu cho (\d+) người lớn$/,count=>"Sample tour price for "+count+" adults"],
    [/^(\d+) gợi ý mô phỏng$/,count=>countLabel(count,"sample suggestion")],
    [/^(\d+) tour gợi ý cho bạn$/,count=>countLabel(count,"suggested tour")],
    [/^(\d+) gợi ý tương tự tour bạn gửi$/,count=>count+" suggestions similar to your reference tour"],
    [/^Nhóm (\d+)$/,count=>"Group "+count],
    [/^(\d+) \/ 3 · (.+)$/,(count,copy)=>count+" / 3 · "+translate(copy)],
    [/^Câu hỏi đang dở: (.+)$/,question=>"Unfinished question: "+question],
    [/^Xem nguồn (.+) của (.+)$/,(field,tour)=>"View source for "+translate(field)+" on "+tour],
    [/^Phòng 2 người · lịch (.+)$/,date=>"Twin room · departure "+date],
    [/^(.+) · phòng 2 người$/,date=>date+" · twin room"],
    [/^(.+) · Ghi nhận 03\/10\/2026 10:42 \(minh họa\)$/,prefix=>prefix+" · Recorded 03/10/2026 10:42 (sample)"],
    [/^(.+) \(minh họa\)$/,prefix=>prefix+" (sample)"],
    [/^Trích đoạn mô phỏng · (.+) · Chưa xác minh độc lập\.$/,hint=>"Sample excerpt · "+translate(hint)+" · Not independently verified."],
    [/^Đã tạo liên hệ mẫu (.*?)\. Mở trang quản trị cùng tab để xem và xử lý; chưa gửi ra ngoài\.$/,id=>"Created demo message "+id+". Open admin in this tab to review it; nothing has been sent externally."],
    [/^(\d+) liên hệ đang chờ$/,count=>count+" contacts waiting"],
    [/^(\d+) nguồn cần kiểm tra$/,count=>count+" sources to check"],
    [/^(\d+) tour \/ (\d+) offer mẫu$/,(tours,offers)=>tours+" tours / "+offers+" sample offers"],
    [/^(\d+) tour đối chiếu$/,count=>countLabel(count,"tour")+" compared"],
    [/^(\d+) tour$/,count=>countLabel(count,"tour")],
    [/^(\d+) offer$/,count=>count+" offers"],
    [/^(\d+) · toàn phiên$/,count=>count+" · entire session"],
    [/^00:00–24:00 · giờ Việt Nam$/,()=>"00:00–24:00 · Vietnam time"],
    [/^01–07\/10\/2026 · giờ Việt Nam$/,()=>"01–07/10/2026 · Vietnam time"],
    [/^(.+) có giá công bố thấp hơn ([\d.]+) ₫ \/ người lớn so với (.+)\. Đổi lại là 6 ngày và điểm mua sắm\.$/,(tour,price,other)=>tour+" has a published price "+currency(price)+" lower per adult than "+other+". The trade-off is 6 days and shopping stops."],
    [/^(.+) có giá công bố thấp hơn (.+), nhưng kéo dài 6 ngày và có điểm mua sắm\. Lựa chọn phụ thuộc ưu tiên của bạn\.$/,(tour,other)=>tour+" has a lower published price than "+other+", but lasts 6 days and includes shopping stops. The choice depends on your priorities."],
    [/^(.+) có thể kiểm tra dữ kiện, nhưng chưa có tour thứ hai để đối chiếu\.$/,tour=>"You can check the facts for "+tour+", but there is no second tour to compare."],
    [/^(.+) có (\d+ ngày \d+ đêm)\. So với gợi ý đầu, giá công bố thấp hơn ([\d.]+) ₫ \/ người lớn; chưa đủ dữ kiện để so tổng chi phí mỗi ngày\.$/,(tour,days,price)=>tour+" lasts "+translate(days)+". Its published price is "+currency(price)+" lower per adult than the first suggestion. There is not enough data to compare daily total costs."],
    [/^Thời lượng ưu tiên: (.+)\. Gợi ý đầu có (.+)\.$/,(preferred,days)=>"Preferred duration: "+translate(preferred)+". The first suggestion lasts "+translate(days)+"."],
    [/^Giá công bố của gợi ý đầu vượt ngân sách ưu tiên (.+)\.$/,price=>"The first suggestion’s published price exceeds your preferred budget by "+translate(price)+"."],
    [/^Thời lượng ưu tiên: (.+)\.$/,duration=>"Preferred duration: "+translate(duration)+"."],
    [/^Gợi ý đầu có (.+)\.$/,duration=>"The first suggestion lasts "+translate(duration)+"."],
    [/^(.+) có giá công bố thấp hơn gợi ý đầu, đổi lại lịch 6 ngày và có điểm mua sắm\.$/,tour=>tour+" has a lower published price than the first suggestion, with a 6-day trip and shopping stops."],
    [/^(.+) còn thiếu chính sách hủy\. Hãy xác nhận trước khi quyết định\.$/,tour=>"The cancellation policy for "+tour+" is missing. Confirm it before deciding."],
    [/^(.+) có (.+)\. So với gợi ý đầu, giá công bố thấp hơn ([\d.]+) ₫ \/ người lớn; chưa đủ dữ kiện để so tổng chi phí mỗi ngày\.$/,(tour,stops,price)=>tour+" has "+translate(stops)+". Its published price is "+currency(price)+" lower per adult than the first suggestion. There is not enough data to compare daily total costs."],
    [/^Ví dụ: (.+)$/,value=>"Example: "+value],
    [/^Lượt tìm: (.+)$/,status=>"Search: "+status],
    [/^Cập nhật liên hệ: (.+)$/,status=>"Contact updated: "+status],
    [/^(.+) → (.+)$/,(before,after)=>translate(before)+" → "+translate(after)]
  ];
  function chatInput(value) {
    let text = value.toLocaleLowerCase("vi-VN");
    const replacements = [
      [/\b(?:find|show|get|search for) (?:an? )?(?:another|next|different) (?:group|tours?)\b/g,"nhóm khác"],
      [/\b(?:another|next|different) group\b/g,"nhóm khác"],
      [/\b(?:cancel|discard) (?:all )?(?:changes|edits|draft)\b/g,"hủy thay đổi"],
      [/\bkeep (?:the )?(?:current|original)(?: version)?\b/g,"giữ nguyên"],
      [/\b(?:no|without|remove) shopping(?: stops?)?\b/g,"không mua sắm"],
      [/\b(?:fewer|less) shopping(?: stops?)?\b/g,"ít mua sắm"],
      [/\b(?:search|find)(?: for)?(?: tours?)?(?: again)?\b/g,"tìm kiếm"],
      [/\b(?:change|update|set|adjust)\b/g,"đổi"],
      [/\bincrease\b/g,"tăng"],[/\bdecrease\b/g,"giảm"],[/\b(?:to|at)\b/g,"thành"],
      [/\bbudget\b/g,"ngân sách"],[/\b(?:duration|length)\b/g,"thời lượng"],
      [/\b(?:million|mn)\b/g,"triệu"],[/\bdays?\b/g,"ngày"],[/\badults?\b/g,"người lớn"],
      [/\bhotels?\b/g,"khách sạn"],[/\bstars?\b/g,"sao"],[/\bshopping(?: stops?)?\b/g,"mua sắm"],
      [/\b(?:departure date|departing on|departure)\b/g,"khởi hành"],
      [/\bcompare\b/g,"so sánh"],[/\b(?:prices?|costs?|cheaper)\b/g,"giá"],
      [/\b(?:cancellation|policy|policies)\b/g,"chính sách"],[/\bsurcharges?\b/g,"phụ thu"],[/\bsources?\b/g,"nguồn"]
    ];
    replacements.forEach(([pattern,replacement])=>{text=text.replace(pattern,replacement);});
    return text;
  }
  return Object.freeze({translate,chatInput});
})();
