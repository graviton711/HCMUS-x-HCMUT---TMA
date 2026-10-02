# scripts — khảo sát nguồn và thu thập dữ liệu theo profile

Tài liệu đặc tả hợp đồng kỹ thuật giữa Agent khảo sát (`run_site_survey.py`) và Runner thu thập (`crawl_with_profile.py`).

## 1. Nguyên tắc cốt lõi

* **Agent làm việc khó, Runner làm việc dễ:** Agent (LLM) phân tích DOM, tìm tọa độ chính xác và xuất ra `profile.yaml` thuần dữ liệu máy đọc được. Runner (`crawl_with_profile.py`) là script cơ học tối giản (< 100 dòng), tuyệt đối không suy đoán hay chứa logic heuristic riêng của từng website.
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
4. **`section` (dành cho soft-fields: lịch trình, bao gồm, loại trừ):**
   ```yaml
   source: section
   start_label: "Lịch trình"    # heading bắt đầu
   stop_labels:                 # danh sách heading dừng
     - "Giá tour bao gồm"
     - "Chính sách hoàn hủy"
   ```

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
   - Chuyển sang flow browser: Dùng `render_url.py` để lấy DOM hoàn chỉnh sau render vào `raw/tour-*.html`.
   - Xác định tọa độ (CSS selector / section / label_sibling) trên DOM đã render.
   - Khai báo `render: true` và `flows: [browser]` trong `profile.yaml`.
3. Tự kiểm thử (`crawl_with_profile.py`): Chạy kiểm thử trên các file đã render trong `raw/` và xác nhận kết quả trên file `.jsonl`.

Trường không tồn tại trên web được đánh dấu: `status: not_observed`.

---

## 3. Trách nhiệm các Script

| Script | Trách nhiệm | Input | Output |
|---|---|---|---|
| `run_site_survey.py` | Điều phối Agent khảo sát domain, tự kiểm thử với `crawl_with_profile.py` trên tập `raw/` | Domain / origin URL | `profile.yaml`, `evidence.md`, `unknowns.md`, `raw/` |
| `render_url.py` | Helper độc lập render URL động qua Playwright Chromium và xuất HTML ra file | URL + File đích | File HTML hoàn chỉnh sau render |
| `crawl_with_profile.py` | Thu thập dữ liệu tour cơ học theo tọa độ profile (nghiêm ngặt < 100 dòng) | URL tour hoặc file HTML + `profile.yaml` | File JSON Lines (`.jsonl`) chuẩn hoá |


