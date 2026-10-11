# entities/search-draft

Type và giá trị mặc định của search draft, khớp đúng các field backend hỗ trợ (`destinations`, `departure_city`, `date_from`/`date_to`, `budget_max`, `duration_days`, `transport`, `accommodation`, `travelers`). Không UI, không gọi backend.

- Input/output: type `SearchDraft`, `emptySearchDraft`, `currentForm`/`validAdults`.
- Workflow: entity sở hữu shape và mapping sang field backend; validation draft đã lưu nằm ở `features/session-history/model/validation`, bản lưu cũ có field thừa được strip khi load.
- Workflow: entity sở hữu shape; validation draft đã lưu nằm ở `features/session-history/model/validation`, bản lưu cũ có field thừa được strip khi load.
- Interface: barrel `src/entities/search-draft`.
- Quyết định kỹ thuật: shape chỉ chứa field backend chấm thật; tiêu chí chưa hỗ trợ không có trong type thay vì bị chặn ở `form.ts` lúc gửi.
