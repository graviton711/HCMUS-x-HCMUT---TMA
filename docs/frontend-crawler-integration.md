# Đối chiếu frontend, backend và crawler

**Trạng thái:** PLANNING; cập nhật trên `feature/minh-phu` ngày 03/10/2026. Giữ yêu cầu frontend G1–G8 tại [checklist](frontend-backend-checklist.md); merge code có sẵn không đồng nghĩa pipeline nguồn thật đã tích hợp.

## Nguồn tham khảo và phạm vi merge

| Nhánh lấy từ origin | Commit đối chiếu | Nội dung |
|---|---|---|
| backend | `0b7e59f` | API v1, models, worker, decision engine, fixture và HTTP crawler gateway |
| feat/supplier_crawler_docs | `4b720a9` | Data contract cũ, team/provider docs, configs và package tourcrawl; không chỉ có tài liệu |
| feat/supplier_crawler_agent | `6f84417` | Kế thừa nhánh docs, thêm 3 script khảo sát/crawl/verify profile, ignore artifacts |

Mọi merge, xử lý conflict và chỉnh tài liệu chỉ ở `feature/minh-phu`. Nhánh `backend` giữ commit ban đầu, không nhận commit frontend; các nhánh nguồn chỉ fetch/tham khảo. Planning frontend trước đó đã được chuyển về nhánh của Minh Phú.

Conflict package phải hợp nhất, không chọn nguyên một phía: giữ dependencies/CLI backend; thêm BeautifulSoup/PyYAML, CLI tour-crawl và browser extra của crawler. Package discovery chứa cả modules backend, tourcrawl và shared; pytest giữ async config và src path. Giữ quy tắc lint backend, bổ sung src path của crawler; sinh lại uv.lock từ pyproject đã hợp nhất. Các quyết định này chỉ phục vụ merge code đã có.

## Pipeline hiện có và phần chưa nối

| Phần | Input → output hiện tại | Giới hạn với frontend |
|---|---|---|
| [tourcrawl pipeline](../src/tourcrawl/pipeline/README.md) | URL/profile/settings → CSV tổng quan + JSON raw/detail: title, json_ld, tour_info, sections, itinerary_days, departure_schedule | Chưa trả CrawlResult version 1.0 hoặc public ComparisonResult |
| [profiles](../src/tourcrawl/profiles/README.md) | configs/profiles YAML origin/flows/aliases/anchors → config engine | Hai profiles cấu hình không phải hai nguồn đã duyệt; chưa có SourceCapability/checked_at/TTL/bộ đo field thật |
| scripts/run_site_survey.py | Website → raw samples + prompt khảo sát trong artifacts/agent_surveys | Artifacts/profile khảo sát chưa có trong Git, không phải fixture FE đã review |
| scripts/crawl_with_profile.py | Profile aliases trong artifacts + sitemap → CSV field dạng text và availability_status | Chuỗi giá/ngày, nhiều giá ghép, không typed offer/quote/evidence IDs; không dùng thẳng làm bảng so sánh |
| scripts/verify_fields_profile.py | Profile dạng fields + HTML đã lưu → báo cáo thử quy tắc JSON-LD | Text rules báo SKIP; khác định dạng aliases mà script CSV đọc; chưa là field engine chung |
| [gateway backend](../src/data_access/README.md) | CrawlRequest → fixture hoặc HTTP POST đến CRAWLER_URL (contract đề xuất /crawl) → CrawlResult đã validate | tourcrawl/scripts chưa cung cấp HTTP exchange hay adapter chuyển output sang contract BE |

FE tiếp tục gọi **API v1 duy nhất**. CLI/CSV/raw JSON không phải endpoint frontend; không expose raw HTML, artifacts hoặc logic parsing vào FE. Có thể khảo sát dữ liệu để chốt UI, nhưng không gọi đó là response production.

## Ánh xạ cần BE + crawler thống nhất

| Dữ liệu crawler có đường lấy | Contract cần cho BE/FE | Việc chưa hoàn thành |
|---|---|---|
| title/name, profile, URL | Tour identity/supplier display_name/canonical URL | Xác định đúng tour/chủ nguồn; bổ sung public DTO (G2), không coi HTML title luôn là tên tour |
| departureName/departure_city, destination, duration | departure_origin/destinations canonical IDs, duration_days/nights | Normalize có nguồn; không suy điểm đến từ title hay suy route/transit thành điểm đến |
| departure_schedule.departures, departureDate, prices/tiered_prices | TourSnapshot + OfferSnapshot đúng ngày; PriceQuote/ExtraCharge/pricing_complete có Fact | Stable offer binding, currency/basis/age brackets, xung đột giá và phụ thu; đáp ứng G1 |
| itinerary_days/sections/page_prose/notes | Nội dung itinerary/inclusions/exclusions/cancellation có raw quote/locator/evidence | Kiểm tra đoạn đúng field, thêm domain/public fields trước khi dùng G3; không dùng fuzzy/full-page text làm điều kiện giá/ngày |
| fetched_at_utc / observed_at | Fact và Evidence observed_at + SourceCapability TTL | Freshness của dữ kiện biến động và quality từng ô; G5 vẫn mở |
| verified/partial/unverified của departure_evidence | Evidence grounding và verification supplier_published/independently_verified/unverified | `verified` crawler chỉ là kiểm tra giá trị xuất hiện trong context; không phải xác minh độc lập |
| availability_status string hoặc thông tin lịch | Offer availability theo domain đã thống nhất | Script đoán available từ ngày/weekly schedule, BE hiện field availability dạng số không âm; cần chốt nghĩa, không suy còn chỗ |

Trong pipeline, context dùng kiểm tra departure có cả JSON của chính departure đã trích; phép match này không chứng minh bằng nguồn độc lập. `price_mismatch` phải giữ như dữ liệu xung đột/chưa xác minh, không chọn giá thuận lợi. Data contract cũ hard/soft + LLM text comparison là yêu cầu tham khảo; decision engine v1 hiện chưa thực hiện so sánh nội dung mềm bằng LLM.

## Việc cần chốt thêm cho dữ liệu thật

| ID | Công việc / điều kiện hoàn thành | Owner | Phụ thuộc frontend |
|---|---|---|---|
| D1 | Chốt adapter + transport CrawlRequest/CrawlResult: IDs, source status, mode discover/compare_urls, deadline, offer/evidence binding; có response fixture validate và HTTP /crawl hoặc phương án gateway đã thống nhất | Backend + crawler | P5.2; G1/G2/G8 |
| D2 | Chốt registry Git/profile → SourceCapability: approved domains, access_status/checked_at, searchable/returned fields và freshness_seconds; kiểm tra nguồn thật trước khi bật | Crawler + backend | C1/C8, P5.2–P5.3 |
| D3 | Chốt raw pricing/date/availability → typed data; phân biệt lịch định kỳ và ngày cụ thể, công bố giá và giá đủ nhóm, unavailable/unknown và số chỗ | Crawler + backend pricing | G1/G5, P4.4/P5.3 |
| D4 | Giữ locator/raw_quote/snapshot/time và kiểm chứng riêng từng field; `verified` nội bộ không chuyển thành independently_verified. Nghiệm thu stop/reason khi nguồn không được phép/không kiểm tra được | Crawler + backend | C7/C9, P3.5/P5.3 |
| D5 | Thống nhất profiles aliases và fields; xác định engine thực sự chạy rules, bổ sung mẫu offline + gold field expectations; không coi text SKIP hoặc CSV ô không rỗng là field PASS | Crawler | C11, P5.2 |

Quan sát cần xử lý ở D4: fetch_robots có thể trả None khi lỗi; run_tour hiện chỉ chặn khi có parser và disallow, chưa dừng khi không kiểm tra được robots. Source access gating của BE vẫn cần chốt trước khi nguồn thật đi vào kết quả người dùng. Đây là vấn đề code hiện hữu cần owner sửa/nghiệm thu, không tự thay production crawler trong giai đoạn planning.

Ưu tiên trao đổi D1 cùng G1/G2/G8. Các đường lấy title/price/itinerary đã có giúp chuẩn bị adapter, nhưng **không đóng gap chỉ vì có code trích xuất**; chỉ đóng khi API public trả đúng schema/evidence và scenario được nghiệm thu.

## Kiểm tra sau merge

- Kiểm tra merge ancestry, không còn conflict markers, pyproject/uv.lock hợp lệ và không mất CLI/module của một phía.
- Chạy tests offline backend + tourcrawl và lint theo cấu hình đã hợp nhất; không gọi NIM/crawl thật để xác nhận merge.
- Giữ 38 task frontend/C1–C11/FLOW-1–6; bổ sung D1–D5, không cắt yêu cầu khi data chưa đáp ứng.
- Đã sync lockfile vào môi trường riêng `.uv/merge-env` (giữ `.venv` cũ); **107 tests passed**, lint `src tests scripts` đạt. API tests dùng SQLite tạm/fixture/NIM stub; chưa chạy NIM/site survey/browser/crawl nguồn thật hoặc frontend E2E.
