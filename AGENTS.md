# Documentation-First Workflow

## 1. Planning Protocol

Khi đang ở `PLANNING`:

* Không implement production code.
* Chỉ brainstorm, phân tích và tinh chỉnh kế hoạch cùng user.
* Mục tiêu là tạo **kế hoạch tối thiểu nhưng đủ để implement toàn bộ pipeline**.
* Có thể chạy script nhỏ, prototype hoặc experiment để kiểm chứng giả định.
* Được tạo cấu trúc module như `src/<module>/`, nhưng mỗi module chỉ chứa tài liệu `.md`, chưa chứa code.
* Mỗi module phải có tài liệu mô tả tối thiểu:

  * Trách nhiệm.
  * Input/output.
  * Workflow.
  * Interface với module khác.
  * Quyết định kỹ thuật quan trọng.

AI phải tiếp tục trao đổi và chỉnh sửa tài liệu cho đến khi user chủ động yêu cầu chuyển sang `IMPLEMENTATION`.

Tuyệt đối không hỏi, gợi ý hoặc nhắc user có muốn chuyển sang IMPLEMENTATION hay không.

## 2. Strength-First Decision Rule

Khi đề xuất hoặc lựa chọn phương án kỹ thuật, AI phải ưu tiên hướng giải quyết theo tiêu chí **mạnh nhất trong phạm vi hợp lý**, không tự động chọn hướng đơn giản hơn chỉ vì dễ implement hơn.

Quy tắc đánh giá:

* Ưu tiên phương án tạo ra hệ thống mạnh hơn rõ rệt về chất lượng, độ chính xác, khả năng mở rộng, khả năng kiểm soát, khả năng debug hoặc khả năng phát triển lâu dài.
* Chấp nhận tăng chi phí về thời gian, độ phức tạp, compute hoặc công sức nếu phần gain thu được là xứng đáng.
* Không được "co về hướng đơn giản" nếu hướng đó làm hệ thống yếu đi đáng kể.
* Chỉ được cắt giảm những phần **đẹp về kiến trúc nhưng không làm hệ thống mạnh hơn thực tế**.
* Khi cần đơn giản hóa, phải đơn giản hóa theo hướng giữ hoặc tăng sức mạnh cốt lõi của hệ thống, không làm mất năng lực quan trọng.
* Nếu có nhiều phương án, AI phải so sánh theo trục:

  * Gain thực tế.
  * Chi phí tăng thêm.
  * Rủi ro kỹ thuật.
  * Khả năng implement trong pipeline hiện tại.
  * Tác động dài hạn đến chất lượng hệ thống.

Mặc định chọn phương án có **tỷ lệ gain / cost tốt nhất trong nhóm các phương án mạnh**, thay vì chọn phương án dễ nhất.

AI không được né phương án khó nếu phương án đó là hướng đúng để làm hệ thống mạnh hơn.

## 3. Implementation Protocol

Chỉ bắt đầu implement khi user yêu cầu rõ ràng chuyển sang `IMPLEMENTATION`.

Trước mỗi thay đổi:

1. Xác định tài liệu bị ảnh hưởng trong:

   * `docs/`
   * `src/<module>/README.md` hoặc tài liệu cạnh module.

2. Cập nhật hoặc tạo tài liệu trước.

3. Yêu cầu user review nếu thay đổi làm lệch kế hoạch đã chốt.

4. Implement sát theo tài liệu.

5. Sau khi implement, kiểm tra và cập nhật để code và tài liệu luôn nhất quán.

Nếu module chưa có tài liệu, bắt buộc tạo tài liệu cạnh module trước khi viết code.

## 4. Documentation Rules

Tài liệu phải:

* Ngắn gọn, chính xác, dễ review.
* Chỉ chứa thông tin cần để hiểu và implement.
* Được rút gọn hoặc tách nhỏ khi trở nên quá dài.
* Phản ánh trạng thái hiện tại của code, không mô tả thiết kế đã lỗi thời.

Ví dụ: 
Đây chỉ là ví dụ về cấu trúc, không bắt buộc phải chứa các tài liệu này. Cần tùy biến theo từng project.

```text
docs/
  system-architecture.md
  project-workflow.md
  adr/

src/
  retrieval/
    README.md
  generation/
    README.md
  evaluation/
    README.md
```

## 5. Communication 

Luôn giữ reply càng ngắn gọn càng tốt, người đọc vào là nắm được vấn đề ngay, không nói những thứ hiển nhiên hoặc không liên quan.

## 6. Frontend / UI/UX Skills

Trước công việc frontend/UI/UX, đọc `docs/frontend-design-preparation.md` để chọn skill trong `.agents/skills/` đúng phạm vi. Skill không thay thế Planning Protocol, proposal, wireframe hoặc data contract. Không áp quy tắc landing/marketing vào bảng so sánh và form của sản phẩm; chỉ chọn phong cách cụ thể khi hướng thiết kế đó đã được thống nhất.

## 7. Branch Scope — Minh Phú

Theo phân công đã được Minh Phú xác nhận lại ngày 08/10/2026: công việc backend thực hiện trên `backend`; frontend thực hiện trên `feature/minh-phu`. Kiểm tra branch trước mọi mutation, không tự chuyển nhánh để sửa sai phạm vi. Không commit hoặc push vào `main` hay các nhánh crawler. Việc commit/push/PR theo yêu cầu cụ thể của user.
