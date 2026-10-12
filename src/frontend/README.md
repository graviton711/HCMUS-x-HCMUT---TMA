# Frontend

UI React + TypeScript + Vite cho `src/backend`. Backend contract là nguồn chuẩn duy nhất cho data, eligibility, persistence và identity.

## Kiến trúc

Dùng cấu trúc feature-sliced gọn. Dependency source chỉ chảy xuống: `app → pages → features → entities → shared`; một layer được bỏ qua nhưng không được import từ layer cao hơn hay slice ngang hàng. Chỉ giữ layer nào có trách nhiệm thật trong app này.

```text
src/frontend/
├── index.html, package.json, README.md, .env.example
├── config/               # eslint, vite, tsconfig, playwright, prettier
├── src/
│   ├── app/                 # App.tsx, main.tsx; providers/, routing/, runtime/, shell/
│   ├── pages/
│   │   ├── chat/              # ChatPage + useChat (route `/`); ui/, model/, lib/
│   │   ├── public/          # SupportPage, UnavailablePage (ui/ + barrel)
│   │   └── workspace/       # Legacy WorkspacePage (route `/tours` ẩn); ui/, model/, lib/
│   ├── features/
│   │   ├── preferences/     # Control ngôn ngữ/theme (ui/; state qua shared/preferences)
│   │   └── session-history/ # Session trình duyệt (model/, ui/, lib/ + barrel)
│   ├── entities/
│   │   └── search-draft/    # Type SearchDraft, giá trị mặc định, helper tháng
│   └── shared/
│       ├── api/             # types.ts, client.ts, errors.ts
│       ├── lib/             # Helper thuần (safeUrl)
│       ├── preferences/     # Cơ chế locale/theme (provider + hook)
│       ├── styles/          # tokens.css nạp trước, global.css sau
│       └── ui/              # Icon/, Dialog/ (mỗi primitive một folder)
├── public/              # Asset serve local và văn bản license
└── tests/               # E2E browser và contract test xuyên module
```

Source ứng dụng nằm dưới `src/`; package root chỉ giữ entry HTML, manifest và tool configuration. Mọi slice theo một chuẩn duy nhất: `index.ts` (public API duy nhất) cộng các segment `model/`, `ui/`, `lib/`; mỗi slice tự document trong `README.md` của nó. Consumer không được deep-import nội bộ của slice khác.
ESLint enforce chiều layer, cấm import chéo slice và bắt buộc public entry point.

| Module                     | Trách nhiệm và interface                                                                                                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app`                      | Bootstrap trình duyệt, providers, navigation và lắp ghép shell. Sở hữu session bar (điểm điều khiển sidebar duy nhất) và instance layout sidebar; không sở hữu business rule session hay tìm kiếm.                                  |
| `pages/chat`               | Màn hình search-first (`/`) và orchestration hội thoại: entry, composer, hỏi từng slot thiếu, so sánh 2 nhóm, nới điều kiện, hoàn tác, title từ destination, recovery hết hạn phiên. Dùng feature chat/session-history, entity search-draft và current API. |
| `pages/public`             | Màn hình hỗ trợ và fallback. Dùng shared UI và preferences; render nội dung public và link điều hướng.                                                                                                                           |
| `pages/workspace`          | Legacy: màn hình form/so sánh cũ (route `/tours` ẩn khỏi nav, giữ cho tới agent phase). Dùng feature session-history, entity search-draft, preferences và current API.                                                             |
| `features/session-history` | Tạo, đọc, sửa, xóa session lưu trên trình duyệt; export type/action session, `useSidebarLayout` và `SessionHistoryPanel` cho `app` (`SessionHistory`/`SessionSidebar` là nội bộ của panel). Giữ nguyên storage keys và behavior phân scope identity; bản lưu cũ có key thừa được strip khi load. |
| `features/chat`            | Primitive hội thoại (types message, Thread/Composer/ToolStatus/QuickReplies/ResultCards, helper format). Không gọi API, không đọc session; orchestration nằm ở `pages/chat`.                                                         |
| `features/preferences`     | Control ngôn ngữ và theme (`compact` cho rail/drawer); đọc/ghi qua interface shared preferences. Render duy nhất từ `app`.                                                                                                       |
| `entities/search-draft`    | Type và giá trị mặc định của search draft, khớp đúng field backend hỗ trợ. Không UI, không gọi backend.                                                                                                                          |
| `shared`                   | HTTP client backend, context/persistence preference toàn app, UI generic, token typography/màu/khoảng cách, helper thuần (`safeUrl`, `displaySessionTitle`). Không được import product pages/features.                           |

## Thiết kế giao diện

TourLens dùng hướng decision workspace ưu tiên bằng chứng: nền trung tính ấm, indigo cho hành động, màu trạng thái chỉ để biểu thị pass/fail/unknown; không dùng ảnh điểm đến trang trí. Manrope tự host là font UI với bộ glyph tiếng Việt và Latin; Space Grotesk chỉ dùng cho wordmark và số liệu. `shared/styles` giữ token và primitive chung; các module giữ CSS Module cạnh component. Bố cục phải nhất quán ở desktop/mobile, VI/EN, sáng/tối, bàn phím và reduced-motion.

Quy tắc tránh lỗi layout tái diễn: component cha chỉ điều khiển vị trí và khoảng cách, không ép width/height các nút con của component khác; control tự giữ kích thước nội tại và khai báo giới hạn co rõ ràng. Ảnh/biểu tượng phải giữ tỉ lệ; chỉ crop khi có vùng crop chủ ý, không scale ngang/dọc độc lập.

## Ranh giới runtime

- `shared/api` là HTTP client duy nhất ở runtime. Chỉ dùng route backend hiện tại; không fallback `/v2`, không fake resource, không fixture fallback ở runtime. Error message backend là tiếng Anh, `code` trong `{error: {code, message}}` ổn định để UI map sang VI/EN khi cần.
- Flow đã kết nối: guest session → OpenCode agent session → MCP tools → hard filter/soft verdict → snapshot/history đã persist.
- Browser storage là persistence, không phải authorization. Profile reader chỉ chọn scope history đã có trên trình duyệt; không authenticate hay authorize request. Giữ nguyên các key history, access-token, display-preference, sidebar-layout và behavior tương thích của chúng.
- Auth/account, gửi contact, proposals/revisions, jobs/events, what-if, evidence/messages và validation pricing/freshness nâng cao chưa kết nối. Chỉ implement khi có backend contract và test tương ứng; không bao giờ tin owner ID do client gửi.
- Giữ nguyên điều hướng URL/hash, VI/EN, sáng/tối, reduced-motion, bàn phím và responsive. Style page/component đặt trong CSS Module cạnh bên; global styles chỉ giới hạn ở primitive dùng chung.

## Kiểm chứng

Chạy từ repo root:

Vitest kiểm tra logic từng slice cùng các hồi quy xuyên app đặt trong `tests/` (gồm điều hướng route và backend contract); Playwright E2E kiểm tra luồng trình duyệt đầy đủ.

```powershell
corepack pnpm@11.25.0 --dir src/frontend test
corepack pnpm@11.25.0 --dir src/frontend typecheck
corepack pnpm@11.25.0 --dir src/frontend lint
corepack pnpm@11.25.0 --dir src/frontend build
```

Tích hợp browser dùng database SQLite chỉ cho test. Chạy OpenCode server ở terminal thứ nhất:

```powershell
opencode serve --hostname 127.0.0.1 --port 4098
```

Ở terminal backend:

```powershell
$env:DATA_PROVIDER='fixture'
$env:DATABASE_URL='sqlite:///./artifacts/frontend-e2e.db'
$env:OPENCODE_SERVER_URL='http://127.0.0.1:4098'
uv run tour-backend serve
```

Ở terminal khác chạy `corepack pnpm@11.25.0 --dir src/frontend dev`, rồi chạy `corepack pnpm@11.25.0 --dir src/frontend test:e2e`. Playwright cần Chrome; không dùng production data.

## Ghi nguồn asset

| Asset                          | Nguồn / license                                                                          |
| ------------------------------ | ---------------------------------------------------------------------------------------- |
| Font Manrope và Space Grotesk  | [Google Fonts](https://github.com/google/fonts); văn bản SIL OFL 1.1 nằm cạnh file font  |
| `mark.svg`                     | Biểu tượng định vị/ống kính vector trong suốt, vẽ lại theo avatar TourLens do người dùng cung cấp |
