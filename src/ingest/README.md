# ingest — thu thập tour theo profile

Luồng chính 5 bước: danh sách link (sitemap trong `pipeline`) → agent vẽ map (`survey.py`) → crawl hàng loạt (`python -m ingest`, trang tĩnh qua `dsl.py`, site động qua `browser` khi profile khai báo) → CSV sạch → database.

Tài liệu này đặc tả hợp đồng kỹ thuật giữa Agent khảo sát (`survey.py`) và engine thu thập (`dsl.py` + `pipeline.py`).

## 1. Nguyên tắc cốt lõi

* **Agent làm việc khó, Runner làm việc dễ:** Agent (LLM) phân tích DOM, tìm tọa độ chính xác và xuất ra `profile.yaml` thuần dữ liệu máy đọc được. Runner (`dsl.py` trong engine, chạy qua `python -m ingest`) là code cơ học thuần túy — tuyệt đối không suy đoán hay chứa logic heuristic riêng của từng website (nguyên tắc bất biến là "không heuristic per-site").
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

Để đảm bảo dữ liệu đầu ra đạt đúng chuẩn Target Canonical của [docs/data-contract.md](file:///d:/GSpace/MLAI/docs/data-contract.md) mà không nhồi heuristic vào Runner, **Agent trực tiếp cung cấp code làm sạch qua thuộc tính `clean`**:

* **`clean` (Khuyến nghị cốt lõi):** Biểu thức Python một dòng hoặc lambda string biến đổi giá trị thô `val`.
  Môi trường thực thi cung cấp sẵn: biến `val`, các module `re`, `json`, `html`.
  * Trích xuất số: `clean: "int(re.sub(r'\D', '', str(val)))"`
  * Chuẩn hóa danh sách Title Case: `clean: "[s.strip().title() for s in re.split(r'[,;]', val) if s.strip()]"`
  * Dọn sạch HTML/Unicode entity: `clean: "re.sub(r'<[^>]+>', '\n', html.unescape(val)).strip()"`
  * Chuẩn hóa Enum: `clean: "'flight' if 'bay' in str(val).lower() else ('bus' if 'xe' in str(val).lower() else 'mixed')"`

* **`transform` (Legacy fallback):** Hỗ trợ `int`, `regex`, `split`, `single_list`, `trim`.

Runner thực thi cơ học biểu thức `clean` trên `val`. Nếu biểu thức ném lỗi hoặc trả sai format, vòng lặp `SELF-TEST` của Agent sẽ báo lỗi ngay lập tức.


### 2.3. Cờ điều khiển Render (`render`) và Quy trình Quyết định

Agent khảo sát tự chủ quyết định cấu hình render dựa trên bản chất kỹ thuật của website:
* `render: false` (mặc định): Tải trang tĩnh qua HTTP GET (`urllib`). Sử dụng khi static HTML hoặc embedded JSON (JSON-LD, hydration blob) đã chứa đủ các trường canonical (như PYS Travel). Tối ưu tốc độ (~200ms/trang) và compute.
* `render: true`: Tải và render JavaScript qua Playwright headless Chromium (`wait_until="networkidle"`). Bắt buộc sử dụng khi static HTML chỉ chứa placeholder rỗng hoặc thiếu các trường quyết định (`itinerary`, `inclusions`, `exclusions`, `departure_pattern`) do website là Next.js/React SPA render client-side (như Vietravel).

**Quy trình Agent tự quyết định:**
1. Khảo sát static HTML trước: Tải HTML tĩnh và kiểm tra các trường canonical.
2. Nếu các trường cốt lõi bị rỗng do client-side rendering:
   - Chuyển sang flow browser: Dùng `python -m ingest.render` để lấy DOM hoàn chỉnh sau render vào `raw/tour-*.html`.
   - Xác định tọa độ (CSS selector / section / label_sibling) trên DOM đã render.
   - Khai báo `render: true` và `flows: [browser]` trong `profile.yaml`.
3. Tự kiểm thử (`python -m ingest.extract`): Chạy kiểm thử trên các file đã render trong `raw/` và xác nhận kết quả trên file `.jsonl`.

Trường không tồn tại trên web được đánh dấu: `status: not_observed`.

**Field `offers` (tầng ngày khởi hành cố định):** `list[dict]` — mỗi phần tử `{departure_date: "YYYY-MM-DD", price: int|null, availability: available|sold_out|unknown}`, dựng bằng biểu thức `clean` từ bảng lịch/tab của nguồn. Giá trên lịch khởi hành (nếu có) ưu tiên hơn giá bìa. Site không công bố ngày cố định → `offers: []` + khai báo `departure_pattern`. Site ẩn lịch sau tab động (kiểu Vietravel) → `offers: []` + `status: not_observed` trong `unknowns.md`, không suy đoán.

---

## 3. Trách nhiệm các Script

| Script | Trách nhiệm | Input | Output |
|---|---|---|---|
| `survey.py` (`python -m ingest.survey`) | Điều phối Agent khảo sát domain, tự kiểm thử bằng `ingest.extract` trên tập `raw/` | Domain / origin URL | `profile.yaml`, `evidence.md`, `unknowns.md`, `raw/` |
| `render.py` | Helper render URL động qua Playwright Chromium, xuất HTML ra file; `--capture-net <dir>` ghi thêm mọi JSON response (XHR) vào `<dir>/` + index `network.json` để dò endpoint API | URL + File đích (+ `--capture-net`) | File HTML hoàn chỉnh sau render (+ network capture) |
| `pipeline.py` (`python -m ingest`) | Crawl hàng loạt theo profile: trang tĩnh qua `dsl.py`, site động qua `browser` khi profile khai báo flow | Danh sách URL + profile | CSV + JSON + provenance |



## 4. Vận hành & tốc độ (`survey.py`)

* **Workdir dài hạn:** `artifacts/agent_surveys/<source>/_work` thay cho thư mục tạm — tồn tại qua các lần chạy nên `raw/` tích lũy tự nhiên (agent được dặn không tải lại file có sẵn); timeout/crash không mất phần đã tải. `raw/` vẫn được sao chép ra `artifacts/agent_surveys/<source>/raw` ở cuối mỗi lần chạy để làm bằng chứng.
* **Prefetch cơ học:** trước khi khởi động agent, wrapper tải song song `robots.txt`, các sitemap khai báo trong robots và `/sitemap.xml` vào `raw/`. Đây là việc không cần LLM; agent đỡ các request đầu và ít tốn lượt LLM turn. Prefetch chỉ là best-effort — lỗi sẽ bị bỏ qua, agent tự xử lý nguồn.
* **Timing log:** mỗi lần chạy in elapsed của từng giai đoạn (prefetch, agent, tổng) kèm mã trả về của opencode để biết nghẽn ở đâu.
* **Môi trường dependency:** wrapper đưa `.venv/Scripts` (hoặc `.venv/bin`) lên đầu `PATH` của tiến trình opencode — agent gõ `python` là venv của dự án, có sẵn `bs4`/`pyyaml`/`playwright`, không `pip install` vào Python hệ thống. Agent chỉ được gọi `python`, không gọi `python3` (trên Windows alias này trỏ về Python hệ thống, thiếu dependency). Không tìm thấy `.venv` thì giữ nguyên PATH (agent tự lo như cũ).
* **Quy tắc UTF-8:** `profile.yaml` phải chứa tiếng Việt verbatim (UTF-8 thuần, cấm `\uXXXX`). Sau khi ghi, agent bắt buộc kiểm tra bằng `yaml.safe_load` và in một field tiếng Việt; nếu ra escape thì ghi lại file.
