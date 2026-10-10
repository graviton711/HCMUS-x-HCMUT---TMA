# features/preferences

Control ngôn ngữ và theme cho user.

- Input/output: đọc/ghi qua cơ chế `shared/preferences` (`usePreferences`).
- Workflow: `ui/PreferencesControl` render language picker + theme toggle.
- Interface: barrel của slice export `PreferencesControl`.
- Quyết định kỹ thuật: state nằm ở `shared` (layer thấp nhất, mọi nơi đều import được); feature này chỉ sở hữu control. `PreferencesControl.module.css` viết hoa PascalCase như mọi component module khác.
