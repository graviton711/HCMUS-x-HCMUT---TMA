# Kiến trúc hệ thống

**Trạng thái:** Đã chốt kiến trúc mục tiêu theo xác nhận ngày 03/10/2026. Repo hiện chưa có module nào được implement; stack và chi tiết API còn mở được xử lý trong planning frontend/backend.

## Sơ đồ tổng quan

```mermaid
flowchart LR
    U[Người dùng]

    subgraph APP[Ứng dụng decision support]
        UI[Web UI<br/>nhu cầu hoặc URL tour]
        API[API / điều phối truy vấn]
        PARSE[Chuẩn hóa nhu cầu<br/>và hỏi lại khi thiếu]
        COMP[Lọc ràng buộc<br/>và so sánh minh bạch]
        RESULT[Kết quả + bằng chứng<br/>người dùng tự chọn]
        UI --> API --> PARSE --> COMP --> RESULT --> UI
    end

    subgraph DATA[Lớp nguồn và dữ liệu]
        REG[Danh mục versioned<br/>configs/profiles/*.yaml]
        ADAPTER[Source adapters<br/>JSON-LD → JSON/API được phép]
        VALID[Chuẩn hóa + kiểm tra<br/>provenance và observed_at]
        STORE[Tour, offer, nhà cung cấp<br/>và snapshot nguồn]
        REG --> ADAPTER --> VALID --> STORE
    end

    subgraph EXT[Nguồn ngoài]
        PROVIDER[Website nhà cung cấp]
        VERIFY[Nguồn độc lập<br/>đăng ký, giấy phép, đánh giá]
    end

    API --> REG
    API -->|URL người dùng cung cấp| ADAPTER
    ADAPTER -->|chỉ URL được phép| PROVIDER
    VERIFY --> VALID
    STORE --> COMP
```

## Luồng truy vấn

```mermaid
flowchart TD
    A[Nhập nhu cầu hoặc tour cần so sánh] --> B{Đầu vào hợp lệ và đủ rõ?}
    B -->|Chưa| C[Hỏi làm rõ ràng buộc]
    C --> B
    B -->|Đủ| D[Chọn nguồn trong danh mục đã duyệt]
    D --> E[Đọc JSON-LD / JSON / API được phép]
    E --> F{Field có nguồn và qua kiểm tra?}
    F -->|Không| G[Đánh dấu thiếu hoặc chưa xác minh]
    F -->|Có| H[Chuẩn hóa cùng schema, giữ provenance]
    G --> I[Lọc điều kiện cứng]
    H --> I
    I --> J[So sánh tiêu chí và trade-off]
    J --> K[Hiển thị kết quả, evidence, thời điểm lấy]
    K --> L[Người dùng chọn; không đặt tour thay]
```

## Trách nhiệm các phần

| Phần | Trách nhiệm |
|---|---|
| Web UI | Nhận nhu cầu/URL; hiển thị bảng so sánh, dữ liệu thiếu và evidence. |
| API / điều phối | Chọn luồng truy vấn, nguồn đủ điều kiện và điều phối các bước xử lý. |
| Danh mục nhà cung cấp | `configs/profiles/<nguồn>.yaml` là nguồn chuẩn trong Git: origin, sitemaps, pattern URL tour, alias field và pattern lọc. Kết quả khảo sát nguồn (quyền crawl, field có/thiếu, giới hạn, ngày kiểm tra) ghi theo [provider registry](provider-registry.md). Danh mục được cập nhật có chủ đích, không dò toàn bộ Internet. |
| Source adapters | Ưu tiên JSON-LD/JSON/API được phép; chỉ bổ sung adapter theo nguồn khi định dạng khác nhau. Không lấy matching toàn trang làm dữ kiện quyết định. |
| Chuẩn hóa và kiểm tra | Ánh xạ field vào schema chung, giữ giá trị gốc, nguồn, phương pháp, trạng thái xác minh và thời điểm quan sát; từ chối field không đạt kiểm tra. |
| Kho dữ liệu | Lưu hồ sơ nhà cung cấp, hồ sơ tour ổn định và snapshot offer biến động riêng biệt. |
| Bộ so sánh | Áp dụng ràng buộc cứng trước; so sánh tiêu chí công khai, giải thích trade-off; không tạo xếp hạng bí mật. |
| Nguồn độc lập | Bổ sung bằng chứng kiểm tra nhà cung cấp; không coi tự khai báo trên trang bán tour là xác minh độc lập. |

## Quy tắc dữ liệu và thời gian

- Hồ sơ/capability nhà cung cấp có thể được khảo sát và làm mới trước.
- Tour và offer chỉ lấy theo nhu cầu hoặc URL đang so sánh; không crawl trước toàn bộ tour.
- Giá, ngày khởi hành, tình trạng chỗ và phụ thu luôn gắn `observed_at`. Có thể dùng cache khi triển khai, nhưng phải hiển thị thời điểm và cảnh báo dữ liệu cũ; chưa chốt TTL.
- Nếu nguồn bị robots/điều khoản chặn hoặc không trả field sạch, không gọi endpoint đó; trả trạng thái không hỗ trợ/thiếu dữ liệu thay vì suy đoán.
- Mọi kết luận hiển thị phải truy ngược được về field và nguồn chứng minh.

## Giả định và quyết định còn mở

- Phạm vi là web demo; contract API dùng JSON, nhưng framework UI/backend, database và hosting chưa chốt.
- Danh mục nguồn hiện được team quản lý trong Git (`configs/profiles/*.yaml` và kết quả khảo sát ở `docs/provider-registry.md`); không có bản Google Sheets song song. Nếu sau này cần giao diện cho người không quen Git, phải chuyển nguồn chuẩn thay vì duy trì hai bản.
- Cách đo độ phù hợp, trọng số tiêu chí, độ tin cậy nguồn và chính sách freshness cần chốt sau khi có bộ dữ liệu mẫu và wireframe được review.
- Phải kiểm tra quyền truy cập và khả năng trích xuất theo từng nguồn trước khi đưa nguồn vào luồng so sánh.
