# features/preferences

Control ngôn ngữ và theme cho user.

- Input/output: đọc/ghi qua cơ chế `shared/preferences` (`usePreferences`).
- Workflow: `ui/PreferencesControl` render language picker + theme toggle.
- Interface: barrel của slice export `PreferencesControl`. Prop `compact` render dạng icon-only cho rail sidebar và drawer mobile.
- Quyết định kỹ thuật: state nằm ở `shared` (layer thấp nhất, mọi nơi đều import được); feature này chỉ sở hữu control. Control được render duy nhất từ `app` (qua prop `controls` của `SessionHistoryPanel`) để tránh trùng điều khiển. `PreferencesControl.module.css` viết hoa PascalCase như mọi component module khác. Component cha chỉ định vị wrapper, không override kích thước button bên trong; root và picker giữ kích thước nội tại để trigger không bị flex-shrink cắt nội dung.
- Trình bày: picker và theme toggle dùng vùng tương tác tối thiểu 40px, trạng thái hover/focus rõ ràng. Trong footer sidebar, control thu gọn vừa một hàng với thông tin tài khoản. Popover căn vào trong cạnh phải của control để không tràn sidebar, có viền và entrance ngắn ở cả hai theme.
