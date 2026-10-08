# ingest — thu thập tour theo profile

Luồng chính 5 bước: danh sách link (sitemap trong `pipeline`) → agent vẽ map (`survey.py`) → crawl hàng loạt (`python -m ingest`, trang tĩnh qua `extract.py`, site động qua `browser` khi profile khai báo) → CSV sạch → database.

Tài liệu này đặc tả hợp đồng kỹ thuật giữa Agent khảo sát (`survey.py`) và engine thu thập (`extract.py` + `pipeline.py`).

Mọi thông số vận hành (timeout, retry, workers, model survey, `min_evidence`...) nằm ở `configs/settings.yaml` theo `configs/settings.schema.json`; code chỉ giữ fallback, không phải nguồn sự thật. Transport dùng connection reuse theo thread + `Accept-Encoding: gzip`, DNS cache `fetch.dns_ttl_s`, retry `fetch.retries` lần với backoff cho lỗi thoáng qua (timeout/reset/5xx/429, không retry lỗi SSL cert hay 4xx).

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
   Runner GET endpoint công khai same-origin SAU khi trích xong các field khác, đi bộ theo `path` rồi chạy `clean`. Cách dò endpoint: `render_url.py --capture-net <dir>` ghi lại mọi JSON XHR vào `<dir>/network.json`; agent đọc file đó rồi khai báo rule `api`. Vẫn chịu mọi quy tắc GET công khai same-origin.

### 2.2. Cơ chế làm sạch dữ liệu (`clean` & `transform`)

Để đảm bảo dữ liệu đầu ra đạt đúng chuẩn Target Canonical của [docs/data-contract.md](../../docs/data-contract.md) mà không nhồi heuristic vào Runner, **Agent trực tiếp cung cấp code làm sạch qua thuộc tính `clean`**:

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
* `render: false` (mặc định): Tải trang tĩnh qua HTTP GET (`urllib`). Sử dụng khi static HTML hoặc embedded JSON (JSON-LD, hydration blob) đã chứa đủ các trường canonical (như PYS Travel). Tối ưu tốc độ (~200ms/trang) và compute.
* `render: true`: Tải và render JavaScript qua Playwright headless Chromium (`wait_until="networkidle"`). Bắt buộc sử dụng khi static HTML chỉ chứa placeholder rỗng hoặc thiếu các trường quyết định (`itinerary`, `inclusions`, `exclusions`, `departure_pattern`) do website là Next.js/React SPA render client-side (như Vietravel).

**Quy trình Agent tự quyết định:**
1. Khảo sát static HTML trước: Tải HTML tĩnh và kiểm tra các trường canonical.
2. Nếu các trường cốt lõi bị rỗng do client-side rendering:
   - Chuyển sang flow browser: Dùng `python -m ingest.render` (file thật `render.py`, được copy thành `render_url.py` trong workdir survey) để lấy DOM hoàn chỉnh sau render vào `raw/tour-*.html`.
   - Xác định tọa độ (CSS selector / section / label_sibling) trên DOM đã render.
   - Khai báo `render: true` và `flows: [browser]` trong `profile.yaml`.
3. Tự kiểm thử (`python -m ingest.extract`): Chạy kiểm thử trên các file đã render trong `raw/` và xác nhận kết quả trên file `.jsonl`.

Trường không tồn tại trên web được đánh dấu: `status: not_observed`.

## 2.4. Hợp đồng Discovery (khai báo cách tìm link tour)

Mỗi site phân trang/search khác nhau nên agent phải khảo sát và khai báo khối `discovery` trong `profile.yaml`. Engine chỉ chạy cơ học theo khai báo, cấm rẽ nhánh theo tên site.

```yaml
discovery:
  method: sitemap            # sitemap | search_pages (mặc định sitemap khi thiếu khối này)
  # --- search_pages: danh sách SSR phân trang, mỗi card link 1 lần/ngày khởi hành ---
  entry: "https://site/tim-kiem?q=&type=tour"  # trang 1 (đã chứa link trang 2..N)
  page_param: page            # tên query param số trang
  per_page_param: perPage     # tên query param cỡ trang (optional)
  per_page: 50
  max_pages: 200              # trần an toàn; engine dừng ở số trang thực tế nhỏ hơn
  strip_query: true            # lột ?startday=... để dedupe về slug duy nhất
  keep_query: [startday]      # dự trữ: param lịch để seed offers ở bước sau
```

Quy tắc agent khi khảo sát discovery: xác định SSR hay API/JS (SSR mới dùng `search_pages`; JS thì khai `render: true` + endpoint `api` nếu có); đọc tổng số tour trên trang 1 và link trang cuối để đặt `max_pages`; mô tả hình dạng link (có `?startday=` không) để đặt `strip_query`; self-test trên 2 trang rồi đối chiếu với tập sitemap (nếu có) để chứng minh không sót.

Vận hành `search_pages`: fetch song song theo `batch.workers` (mỗi worker một fetcher/limiter riêng, tốc độ tăng tuyến tính; `fetch.delay_s` là núm lịch sự duy nhất), đi theo đợt để giữ thứ tự trang ổn định; `--limit N` dừng ngay khi đủ N slug (smoke test chỉ tốn trang 1); mỗi đợt ghi nối `discovered.csv` và flush ngay nên ngắt giữa chừng vẫn giữ phần đã liệt kê. Batch crawl cũng lưu `_state.json` định kỳ, không chỉ lúc cuối. Batch crawl cách request cùng origin bằng start-spacing (`max(batch.delay_s, fetch.delay_s)` giữa các lần bắt đầu fetch) thay vì mutex ôm cả tour, nên parse song song mà vẫn lịch sự.

**Field `offers` (tầng ngày khởi hành cố định):** `list[dict]` snake_case duy nhất — mỗi phần tử `{departure_date: "YYYY-MM-DD", price: int|null, availability: available|sold_out|unknown}`, dựng bằng biểu thức `clean` từ bảng lịch/tab của nguồn (chỉ trích list unsorted, Runner tự sort theo `(departure_date, price)` và normalize camelCase→snake_case sau capture browser). Giá trên lịch khởi hành (nếu có) ưu tiên hơn giá bìa. Site không công bố ngày cố định → `offers: []` + khai báo `departure_pattern`. Site ẩn lịch sau tab động (kiểu Vietravel) → `offers: []` + `status: not_observed` trong `unknowns.md`, không suy đoán.

---

## 3. Trách nhiệm các Script

| Script | Trách nhiệm | Input | Output |
|---|---|---|---|
| `survey.py` (`python -m ingest.survey`) | Điều phối Agent khảo sát domain, tự kiểm thử bằng `ingest.extract` trên tập `raw/` | Domain / origin URL | `profile.yaml`, `evidence.md`, `unknowns.md`, `raw/` |
| `render.py` | Helper render URL động qua Playwright Chromium, xuất HTML ra file; `--capture-net <dir>` ghi thêm mọi JSON response (XHR) vào `<dir>/` + index `network.json` để dò endpoint API. File thật là `render.py`, khi survey được copy thành `render_url.py` trong workdir (`survey.py` copy) nên docs agent ghi `render_url.py` | URL + File đích (+ `--capture-net`) | File HTML hoàn chỉnh sau render (+ network capture) |
| `pipeline.py` (`python -m ingest`) | Crawl hàng loạt theo profile: trang tĩnh qua `extract.py`, site động qua `browser` khi profile khai báo flow | Danh sách URL + profile | CSV + JSON + provenance |
| `run.py` (`python -m ingest.run --source <source>`) | Chạy full chuỗi một lệnh: survey (`--promote`) → discover → batch → migrate → publish; dừng ngay ở bước fail đầu tiên. Không audit trong chain (batch đã chấm evidence từng tour; audit chạy tay khi đổi profile/nguồn mới) | source trong `configs/sources-mvp.csv` | DB tour |
| | `--discover` liệt kê link theo khối `discovery` và lưu `.local/<source>/discovered.csv` cho `--batch`; `--publish` và `audit --urls` mặc định trỏ vào output của batch (`<output.dir>/<source>/tours`, `tours.csv`) | | |
| Dạng thủ công (ghi đè default): `python -m ingest <tour_url>`, `--batch <csv>`, `--output`, `--out-dir`, `--publish <dir>`, `audit --urls <file>` | | | |

Mọi output crawl đều namespac theo source (`.local/<source>/`) nên nhiều nguồn không ghi đè nhau; `_state.json` dùng chung vì key là URL đầy đủ. Thư mục `data/` chỉ chứa registry versioned do người quản lý (vd `data/providers.toml`), không chứa output crawl.

## Chất lượng run-over-run

Mỗi batch ghi `.local/<source>/quality.json`: số tour, giá trung bình, tỷ lệ fill từng field bắt buộc (`quality.fill_fields`), và số field rơi vào fallback (rỗng). Lần chạy sau so với lần trước theo ngưỡng `quality.*` (`min_tours_ratio`, `max_price_shift`, `min_fill_rate`); lệch băng chỉ cảnh báo (log + file), không fail batch — tỷ lệ fallback tăng dần chính là tín hiệu site đổi layout, rẻ hơn re-survey mù.



## 4. Vận hành & tốc độ (`survey.py`)

* **Workdir dài hạn:** `artifacts/agent_surveys/<source>/_work` thay cho thư mục tạm — tồn tại qua các lần chạy nên `raw/` tích lũy tự nhiên (agent được dặn không tải lại file có sẵn); timeout/crash không mất phần đã tải. `raw/` vẫn được sao chép ra `artifacts/agent_surveys/<source>/raw` ở cuối mỗi lần chạy để làm bằng chứng.
* **Prefetch cơ học:** trước khi khởi động agent, wrapper tải song song `robots.txt`, các sitemap khai báo trong robots và `/sitemap.xml` vào `raw/`. Đây là việc không cần LLM; agent đỡ các request đầu và ít tốn lượt LLM turn. Prefetch chỉ là best-effort — lỗi sẽ bị bỏ qua, agent tự xử lý nguồn.
* **Timing log:** mỗi lần chạy in elapsed của từng giai đoạn (prefetch, agent, tổng) kèm mã trả về của opencode để biết nghẽn ở đâu.
* **Môi trường dependency:** wrapper đưa `.venv/Scripts` (hoặc `.venv/bin`) lên đầu `PATH` của tiến trình opencode — agent gõ `python` là venv của dự án, có sẵn `bs4`/`pyyaml`/`playwright`, không `pip install` vào Python hệ thống. Agent chỉ được gọi `python`, không gọi `python3` (trên Windows alias này trỏ về Python hệ thống, thiếu dependency). Không tìm thấy `.venv` thì giữ nguyên PATH (agent tự lo như cũ).
* **Quy tắc UTF-8:** `profile.yaml` phải chứa tiếng Việt verbatim (UTF-8 thuần, cấm `\uXXXX`). Sau khi ghi, agent bắt buộc kiểm tra bằng `yaml.safe_load` và in một field tiếng Việt; nếu ra escape thì ghi lại file.
* **Ngắt an toàn:** batch/discover chạy daemon pool (`_map_ordered`), drain theo thứ tự với timeout 0.2s; Ctrl+C (FastExit qua `run_cli`, exit 130) lưu CSV/`_state.json` đã flush rồi thoát ngay mà không chờ request đang bay. Detail JSON ghi qua file `.tmp` + `os.replace` nên không corrupt khi ngắt giữa chừng.
