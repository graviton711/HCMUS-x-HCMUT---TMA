# ingest — thu thập tour theo profile

Luồng chính 5 bước: danh sách link (sitemap trong `pipeline`) → agent vẽ map (`survey.py`) → crawl hàng loạt (`python -m ingest`, trang tĩnh qua `extract.py`, site động qua `browser` khi profile khai báo) → CSV sạch → database.

## Chạy nhanh

Mọi thông số vận hành nằm ở `configs/settings.yaml`; profile nằm ở `configs/profiles/<name>.yaml`. Output mặc định ghi xuống `.local/<source>/` (CSV, JSON detail, `quality.json`); state resume dùng chung `.local/_state.json`, key theo URL đầy đủ nên các source không xung đột.

```bash
# Chuỗi đầy đủ 5 bước cho 1 source (survey -> discover -> batch -> migrate -> publish)
uv run python -m ingest.run --source vietravel            # --limit 5: chỉ 5 tour; --skip-survey: tái dùng profile đã promote

# Crawl 1 tour duy nhất (trừu tượng debug một URL)
uv run python -m ingest https://travel.com.vn/chuong-trinh/...-pid-4363 -p vietravel

# Đổ danh sách URL từ sitemap/search trang nguồn -> .local/<source>/discovered.csv
uv run python -m ingest --discover -p vietravel           # --limit N: giới hạn; --since YYYY-MM-DD: chỉ URL lastmod mới hơn

# Crawl hàng loạt theo discovered.csv (resume: URL đã có trong tours.csv sẽ bị skip)
uv run python -m ingest --batch -p vietravel              # log "batch: 0 urls (490 skipped)" nghĩa là không còn URL mới — bình thường
uv run python -m ingest --batch meo.csv -p vietravel      # dùng CSV khác; --output tours-x.csv đổi nơi ghi kết quả

# Crawl mọi URL trong sitemap profile (bỏ qua bước discover)
uv run python -m ingest --sitemap -p vietravel

# Database: áp migrations, rồi publish detail JSON vào bảng tour
uv run python -m ingest --migrate
uv run python -m ingest --publish -p vietravel            # đọc .local/<source>/tours/ (hoặc --publish <DIR>)

# Site động: các flow browser/combo chạy tuần tự; --no-browser chặn tầng browser khi debug tĩnh
```

Chi tiết kỹ thuật từng bước nằm ở các mục dưới: workflow khảo sát (`survey.py`), chuẩn DSL profile (`extract.py`), hành vi resume/failure budget của batch, và hợp đồng publish.

Tài liệu này đặc tả hợp đồng kỹ thuật giữa Agent khảo sát (`survey.py`) và engine thu thập (`extract.py` + `pipeline.py`).

Mọi thông số vận hành (timeout, retry, workers, model survey, `min_evidence`...) nằm ở `configs/settings.yaml` theo `configs/settings.schema.json`. `opencode.model` cấu hình model OpenCode cho survey và chat legacy trên Render; local chat dùng riêng `codex.model` và `codex.reasoning_effort`. Survey tiếp tục gọi OpenCode CLI và chỉ cấu hình thêm `survey.variant`. Transport dùng connection reuse theo thread + `Accept-Encoding: gzip`, DNS cache `fetch.dns_ttl_s`, retry `fetch.retries` lần với backoff cho lỗi thoáng qua (timeout/reset/5xx/429, không retry lỗi SSL cert hay 4xx).

Mọi timestamp quan sát (`observed_at`, `fetched_at`) đều là giờ Việt Nam (`Asia/Ho_Chi_Minh`, `shared.now_vn_iso`), ISO-8601 kèm offset.

## 1. Nguyên tắc cốt lõi

* **Agent làm việc khó, Runner làm việc dễ:** Agent (LLM) phân tích DOM, tìm tọa độ chính xác và xuất ra `profile.yaml` thuần dữ liệu máy đọc được. Runner (`extract.py` trong engine, chạy qua `python -m ingest`) là code cơ học thuần túy — tuyệt đối không suy đoán hay chứa logic heuristic riêng của từng website (nguyên tắc bất biến là "không heuristic per-site"). Runner tự sort `offers` theo `(departure_date, price)` và normalize về snake_case nên agent chỉ trích list unsorted, không sort/không `lambda` trong `clean`.
* **Cấm văn xuôi trong profile:** Profile chỉ chứa selector, path, regex và primitive enum; không chứa câu điều kiện hoặc hướng dẫn bằng tiếng Anh/Việt tự nhiên.

## 2. Chuẩn Profile DSL (Machine-Readable Contract)

Mỗi trường trong `fields.<field_name>` phải tuân thủ đúng một trong các cơ chế sau:

### 2.1. Nguồn trích xuất (`source`)

1. **`json_ld`:**
   ```yaml
   source: json_ld
   entity: TouristTrip          # lọc entity @type (tùy chọn)
   path: offers.price           # truy cập theo dot-notation
   ```
2. **`css`:**
   ```yaml
   source: css
   selector: "h1.tour-title"    # CSS selector hợp lệ của BeautifulSoup
   attr: text                   # "text" (mặc định) hoặc tên attribute (vd: "content")
   ```
3. **`label_sibling`:**
   ```yaml
   source: label_sibling
   label: "Thời gian:"          # nhãn neo trong văn bản
   ```
4. **`section` (dành cho soft-fields: lịch trình, bao gồm, loại trừ, chính sách hoàn hủy, phụ thu, giá trẻ em):**
   ```yaml
   source: section
   start_label: "Lịch trình"    # heading bắt đầu
   stop_labels:                 # danh sách heading dừng
     - "Giá tour bao gồm"
     - "Chính sách hoàn hủy"
   ```
5. **`api` (endpoint JSON nội bộ):**
   ```yaml
   source: api
   url: "https://site/api/tour?code={tour_code}"   # placeholder nạp từ field đã trích trước đó ({tour_code}, {url}...)
   path: data.departures            # dot-notation vào JSON response
   ```
   Runner GET endpoint công khai same-origin SAU khi trích xong các field khác, đi bộ theo `path` rồi chạy `clean`. Cách dò endpoint trong survey: bật `render: true`, chạy `ingest.survey_fetch`, rồi kiểm tra `raw/browser-api/network.json`; agent đọc file đó rồi khai báo rule `api`.

### 2.2. Cơ chế làm sạch dữ liệu (`clean` & `transform`)

Để dữ liệu crawl khớp catalog và giữ preprocessing theo từng nguồn mà không nhồi heuristic vào Runner, **Agent trực tiếp cung cấp code làm sạch qua thuộc tính `clean`** theo [data contract](../../docs/data-contract.md). Publish ghi bảng Supabase theo `migrations/001_tour_schema.sql` (+ evidence, `field_meta`); backend chỉ đọc:

* **`clean` (Khuyến nghị cốt lõi):** Biểu thức Python một dòng hoặc lambda string biến đổi giá trị thô `val`.
  Môi trường thực thi cung cấp sẵn: biến `val`, các module `re`, `json`, `html`,
  và các helper an toàn `research(pattern, text, group=1, flags=0)` (trả `""`
  khi không khớp thay vì ném lỗi), `refindall(pattern, text, flags=0)` (trả `[]`
  khi không khớp).
  * Trích xuất số: `clean: "int(re.sub(r'\D', '', str(val)))"`
  * Chuẩn hóa danh sách Title Case: `clean: "[s.strip().title() for s in re.split(r'[,;]', val) if s.strip()]"`
  * Dọn sạch HTML/Unicode entity: `clean: "re.sub(r'<[^>]+>', '\n', html.unescape(val)).strip()"`
  * Chuẩn hóa Enum: `clean: "'flight' if 'bay' in str(val).lower() else ('bus' if 'xe' in str(val).lower() else 'mixed')"`
  * Trích regex an toàn: `clean: "research(r'Giá từ\\s*([\\d.]+)', str(val))"`

  **Luật bất biến:** mọi `clean` phải là hàm toàn phần — không được ném lỗi với
  bất kỳ input nào.   Cấm gọi `.group()` trên kết quả `re.search` chưa kiểm tra;
  dùng `research` hoặc guard tường minh. Engine cách ly lỗi theo field: expression nào
  ném lỗi thì field đó thành rỗng và evidence đánh dấu, tour vẫn sống.

* **`transform` (Legacy fallback):** Hỗ trợ `int`, `regex`, `split`, `single_list`, `trim`.

Runner thực thi cơ học biểu thức `clean` trên `val`. Nếu biểu thức ném lỗi hoặc trả sai format, vòng lặp `SELF-TEST` của Agent sẽ báo lỗi ngay lập tức.


### 2.3. Cờ điều khiển Render (`render`) và Quy trình Quyết định

Agent khảo sát tự chủ quyết định cấu hình render dựa trên bản chất kỹ thuật của website:
* `render: false` (mặc định): Tải trang tĩnh qua `SafeFetcher` HTTP GET. Dùng khi static HTML hoặc embedded JSON đã có đủ trường canonical.
* `render: true`: Tải và render JavaScript qua Playwright headless Chromium. Mọi browser request được route qua `SafeFetcher`; chỉ GET same-origin, robots-allowed, mỗi response tối đa 2 MB và request cách nhau ít nhất 1 giây. Dùng khi static HTML chỉ có placeholder rỗng hoặc thiếu trường quyết định do website là SPA.

**Quy trình Agent tự quyết định:**
1. Khảo sát static HTML trước: Tải HTML tĩnh và kiểm tra các trường canonical.
2. Nếu các trường cốt lõi bị rỗng do client-side rendering, khai `render: true`/`flows: [browser]` trước khi chạy `ingest.survey_fetch`; inspect DOM và `raw/browser-api/network.json` để định nghĩa tọa độ.
3. Tự kiểm thử (`python -m ingest.extract --all`): Chạy trên toàn bộ tour trong manifest; API GET dùng chung giới hạn origin/robots/kích thước/tốc độ và cache `raw/api-cache/`.

Trường không tồn tại trên web được khai báo rõ bằng `status: not_observed` và phải ghi cách kiểm tra trong `evidence.md`/`unknowns.md`. Giá trị rỗng khi profile vẫn khai báo extractor là lỗi chưa phân loại, không được xem như vắng mặt hợp lệ. Field bắt buộc không quan sát được làm self-test tour fail; không suy đoán hay tự điền.

Self-test kiểm tra toàn bộ tour detail đã phát hiện, không lấy mẫu mặc định 20. Tất cả URL phải được liệt kê/dedupe trước khi kiểm tra; fetch tuần tự theo từng origin, cách nhau ít nhất 1 giây, chỉ cùng origin, tôn trọng `robots.txt`, tối đa 2 MB mỗi response. Dùng cache để sửa profile và chạy lại extraction không tải lại các trang đã lấy. Lỗi sau retry phải có trong manifest và báo cáo coverage; không được tính thành PASS.

`ingest.survey_fetch` thực hiện discovery và lưu snapshot/cache: `python -m ingest.survey_fetch --profile profile.yaml --raw-dir raw`. Lệnh union/dedupe URL từ sitemap và listing đã khai báo, ghi `tour_urls.txt` cùng `tour_pages.csv` (URL, file, status, error), rồi fetch tuần tự. Sitemap/listing và trang tour thành công được cache trong `raw/`; dùng `--refresh` để tải snapshot mới. Listing vượt `max_pages`, robots không tải được, hoặc trang lỗi sau retry đều được ghi là gap; không được tuyên bố coverage đầy đủ.

`ingest.extract` hỗ trợ self-test toàn bộ HTML đã lưu: `python -m ingest.extract --all raw --profile profile.yaml -o selftest.jsonl`. Lệnh đọc mọi HTML theo manifest, xuất record cùng `record_field_checks`, và tóm tắt PASS/tổng cho từng field và từng tour. Nếu manifest có URL chưa tải thành công, có file hỏng hoặc field chưa xác minh thì báo GAP/FAIL và exit khác 0.

Kiểm chứng có hai lớp: shape/format theo canonical field và evidence từ raw value tại rule nguồn. Destination phải là các địa điểm đơn được nguồn xác nhận bằng taxonomy/structured data; nhãn ghép chưa tách được thì báo unresolved, không tự split. Route là danh sách chặng có thứ tự. `record_field_checks` trong detail JSON cho biết `verified`, `not_observed`, `failed` hoặc `unverified` cùng lý do; `record_evidence` và `record_missing` vẫn là kết quả tổng hợp tương thích.

## 2.4. Hợp đồng Discovery (khai báo cách tìm link tour)

Mỗi site phân trang/search khác nhau nên agent phải khảo sát và khai báo khối `discovery` trong `profile.yaml`. Engine chỉ chạy cơ học theo khai báo, cấm rẽ nhánh theo tên site.

```yaml
discovery:
  method: sitemap            # sitemap | search_pages (mặc định sitemap khi thiếu khối này)
  # Nếu sitemap là nguồn chính nhưng có listing riêng, khai báo thêm listing:
  listing:
    entry: "https://site/tim-kiem?q=&type=tour"
    page_param: page
    per_page_param: perPage
    per_page: 50
    max_pages: 200
    strip_query: true
  # Có thể khai nhiều listing phụ bằng `listings: [...]`.
  # --- search_pages: danh sách SSR phân trang, mỗi card link 1 lần/ngày khởi hành ---
  entry: "https://site/tim-kiem?q=&type=tour"  # trang 1 (đã chứa link trang 2..N)
  page_param: page            # tên query param số trang
  per_page_param: perPage     # tên query param cỡ trang (optional)
  per_page: 50
  max_pages: 200              # trần an toàn; engine dừng ở số trang thực tế nhỏ hơn
  strip_query: true            # lột ?startday=... để dedupe về slug duy nhất
  keep_query: [startday]      # dự trữ: param lịch để seed offers ở bước sau
```

Quy tắc agent khi khảo sát discovery: xác định SSR hay API/JS (SSR mới dùng `search_pages`; JS thì khai `render: true` + endpoint `api` nếu có); đọc trang cuối thật để đặt `max_pages`; mô tả hình dạng link (có `?startday=` không) để đặt `strip_query`; enumerate toàn bộ tour, dedupe URL và đối chiếu listing với sitemap khi có. Self-test cuối chạy trên toàn bộ tour đã enumerate, không chỉ 2 trang hoặc mẫu cố định.

Vận hành `search_pages`: fetch song song theo `batch.workers` (mỗi worker một fetcher/limiter riêng, tốc độ tăng tuyến tính; `fetch.delay_s` là núm lịch sự duy nhất), đi theo đợt để giữ thứ tự trang ổn định; `--limit N` dừng ngay khi đủ N slug (smoke test chỉ tốn trang 1); mỗi đợt ghi nối `discovered.csv` và flush ngay nên ngắt giữa chừng vẫn giữ phần đã liệt kê. Batch crawl cũng lưu `_state.json` định kỳ, không chỉ lúc cuối. Batch crawl cách request cùng origin bằng start-spacing (`max(batch.delay_s, fetch.delay_s)` giữa các lần bắt đầu fetch) thay vì mutex ôm cả tour, nên parse song song mà vẫn lịch sự.

**Field `offers` (tầng ngày khởi hành cố định):** `list[dict]` snake_case duy nhất — mỗi phần tử giữ `{departure_date, price, price_type, availability, price_by_age, supplements, single_supplement, conditions}` khi nguồn có các dữ kiện đó. `price_type` thuộc offer (`fixed|from|contact|unknown`), không kế thừa từ tour; giữ giá theo nhóm tuổi và phụ thu có cấu trúc để backend tính cost khi đủ căn cứ. Dựng bằng biểu thức `clean` từ bảng lịch/tab của nguồn (chỉ trích list unsorted, Runner tự sort theo `(departure_date, price)` và normalize camelCase→snake_case sau capture browser). Giá trên lịch khởi hành (nếu có) ưu tiên hơn giá bìa. Site không công bố ngày cố định → `offers: []` + khai báo `departure_pattern`. Site ẩn lịch sau tab động (kiểu Vietravel) → `offers: []` + `status: not_observed` trong `unknowns.md`, không suy đoán.

---

## 3. Trách nhiệm các Script

| Script | Trách nhiệm | Input | Output |
|---|---|---|---|
| `survey.py` (`python -m ingest.survey`) | Điều phối Agent khảo sát domain; bootstrap robots/sitemap | Domain / origin URL | `profile.yaml`, `evidence.md`, `unknowns.md`, `raw/` |
| `survey_fetch.py` (`python -m ingest.survey_fetch`) | Union/dedupe discovery URL, tải có robots/origin/rate/size guard, cache discovery/tour HTML và ghi gap manifest | `profile.yaml` | `tour_urls.txt`, `tour_pages.csv`, snapshot raw |
| `render.py` | Helper thủ công render một URL động và capture JSON response; survey full inventory dùng `survey_fetch.py` để áp dụng origin/robots/size/rate guard cho mọi request | URL + File đích (+ `--capture-net`) | File HTML hoàn chỉnh sau render (+ network capture) |
| `pipeline.py` (`python -m ingest`) | Crawl hàng loạt theo profile: trang tĩnh qua `extract.py`, site động qua `browser` khi profile khai báo flow | Danh sách URL + profile | CSV + JSON + provenance |
| `run.py` (`python -m ingest.run --source <source>`) | Chạy full chuỗi một lệnh: survey (`--promote`) → discover → batch → migrate → publish; dừng ngay ở bước fail đầu tiên. Không audit trong chain (batch đã chấm evidence từng tour; audit chạy tay khi đổi profile/nguồn mới) | source trong `configs/sources-mvp.csv` | DB tour |
| | `--discover` liệt kê link theo khối `discovery` và lưu `.local/<source>/discovered.csv` cho `--batch`; `--publish` và `audit --urls` mặc định trỏ vào output của batch (`<output.dir>/<source>/tours`, `tours.csv`) | | |
| Dạng thủ công (ghi đè default): `python -m ingest <tour_url>`, `--batch <csv>`, `--output`, `--out-dir`, `--publish <dir>`, `audit --urls <file>` | | | |

Mọi output crawl đều namespac theo source (`.local/<source>/`) nên nhiều nguồn không ghi đè nhau; `_state.json` dùng chung vì key là URL đầy đủ. Thư mục `data/` chỉ chứa registry versioned do người quản lý (vd `data/providers.toml`), không chứa output crawl.

## Chất lượng run-over-run

Mỗi batch ghi `.local/<source>/quality.json`: số tour, giá trung bình, tỷ lệ fill từng field bắt buộc (`quality.fill_fields`), và số field rơi vào fallback (rỗng). Lần chạy sau so với lần trước theo ngưỡng `quality.*` (`min_tours_ratio`, `max_price_shift`, `min_fill_rate`); lệch băng chỉ cảnh báo (log + file), không fail batch — tỷ lệ fallback tăng dần chính là tín hiệu site đổi layout, rẻ hơn re-survey mù. Batch không crawl được tour nào (resume hết, hoặc mọi URL fail) **không ghi snapshot và không đè baseline cũ** — so sánh rỗng-vs-không-rỗng chỉ sinh warning giả; quality mới chỉ được ghi khi run có ít nhất một tour (detail JSON) cho từng source.



## 4. Vận hành & tốc độ (`survey.py`)

* **Workdir dài hạn:** `artifacts/agent_surveys/<source>/_work` thay cho thư mục tạm — tồn tại qua các lần chạy nên `raw/` tích lũy tự nhiên (agent được dặn không tải lại file có sẵn); timeout/crash không mất phần đã tải. `raw/` vẫn được sao chép ra `artifacts/agent_surveys/<source>/raw` ở cuối mỗi lần chạy để làm bằng chứng.
* **Prefetch cơ học:** trước khi khởi động agent, wrapper tải song song `robots.txt`, các sitemap khai báo trong robots và `/sitemap.xml` vào `raw/`. Đây là việc không cần LLM; agent đỡ các request đầu và ít tốn lượt LLM turn. Prefetch chỉ là best-effort — lỗi sẽ bị bỏ qua, agent tự xử lý nguồn.
* **Timing log:** mỗi lần chạy in elapsed của từng giai đoạn (prefetch, agent, tổng) kèm mã trả về của opencode để biết nghẽn ở đâu.
* **Môi trường dependency:** wrapper đưa `.venv/Scripts` (hoặc `.venv/bin`) lên đầu `PATH` của tiến trình opencode — agent gõ `python` là venv của dự án, có sẵn `bs4`/`pyyaml`/`playwright`, không `pip install` vào Python hệ thống. Agent chỉ được gọi `python`, không gọi `python3` (trên Windows alias này trỏ về Python hệ thống, thiếu dependency). Không tìm thấy `.venv` thì giữ nguyên PATH (agent tự lo như cũ).
* **Quy tắc UTF-8:** `profile.yaml` phải chứa tiếng Việt verbatim (UTF-8 thuần, cấm `\uXXXX`). Sau khi ghi, agent bắt buộc kiểm tra bằng `yaml.safe_load` và in một field tiếng Việt; nếu ra escape thì ghi lại file.
* **Ngắt an toàn:** batch/discover chạy daemon pool (`_map_ordered`), drain theo thứ tự với timeout 0.2s; Ctrl+C (FastExit qua `run_cli`, exit 130) lưu CSV/`_state.json` đã flush rồi thoát ngay mà không chờ request đang bay. Detail JSON ghi qua file `.tmp` + `os.replace` nên không corrupt khi ngắt giữa chừng.
