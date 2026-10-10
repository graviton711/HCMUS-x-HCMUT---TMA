# entities/search-draft

Type, giá trị mặc định và helper tháng dùng chung cho search draft giữa workspace và session persistence. Không UI, không gọi backend.

- Input/output: type `SearchDraft`, `emptySearchDraft`, `validMonth`.
- Workflow: entity sở hữu shape; validation draft đã lưu nằm ở `features/session-history/model/validation`.
- Interface: barrel `src/entities/search-draft`.
- Quyết định kỹ thuật: tên mới (`SearchDraft`) đã thay toàn bộ alias legacy; field lưu trữ cũ vẫn load được nhờ validation tương thích.
