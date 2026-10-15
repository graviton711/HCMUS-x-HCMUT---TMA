# entities/search-draft

Type và giá trị mặc định của search draft, khớp đúng các field backend hỗ trợ (`destinations`, `departure_city`, `date_from`/`date_to`, `budget_max`, `duration_days`, `transport`, `accommodation`, `travelers`). `date_from`/`date_to` là khoảng ngày khởi hành bao gồm cả hai đầu, không phải ngày về. Không UI, không gọi backend.

- Input/output: type `SearchDraft`, `emptySearchDraft`.
- Workflow: entity sở hữu shape; validation draft đã lưu nằm ở `features/session-history/model/validation`, bản lưu cũ có field thừa được strip khi load.
- Interface: barrel `src/entities/search-draft`.
- Quyết định kỹ thuật: shape chỉ chứa field backend chấm thật.
