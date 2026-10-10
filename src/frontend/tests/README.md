# Frontend verification

- `api/current.test.ts` checks the active HTTP client: no `/v2` prefix/envelope, Bearer ownership, history cursors, and no mutation retries.
- `api/backend-runtime.test.ts` invokes the real FastAPI app with SQLite + fixture catalog and validates session, catalog, requirement, comparison snapshots and history responses.
- `tests/CurrentWorkspace.test.tsx` covers guest session creation, requirement interpretation, comparison rendering, and blocking unsupported criteria.
- The existing form/results/workspace unit suites preserve migration-source behavior; they are not evidence that the disabled proposal/job/account/what-if flows run on the current backend.
- Fixtures and mocked API responses stay in tests. Runtime never falls back to fixture data when a live provider is configured.

From the repository root:

```powershell
corepack pnpm@11.25.0 --dir src/frontend test
corepack pnpm@11.25.0 --dir src/frontend typecheck
corepack pnpm@11.25.0 --dir src/frontend lint
corepack pnpm@11.25.0 --dir src/frontend build
```

## Browser integration

Start the current backend in fixture mode with a test-only SQLite database, then start Vite and run Playwright:

```powershell
$env:DATA_PROVIDER='fixture'
$env:DATABASE_URL='sqlite:///./artifacts/frontend-e2e.db'
$env:NVIDIA_NIM_API=''
uv run tour-backend serve
```

In a second terminal:

```powershell
$env:BACKEND_URL='http://127.0.0.1:8000'
corepack pnpm@11.25.0 --dir src/frontend dev
```

In a third terminal:

```powershell
corepack pnpm@11.25.0 --dir src/frontend test:e2e
```

Playwright covers the guest flow from interpretation through persisted comparison reload, verifies account/contact routes clearly report that their backend features are not ported, and checks a narrow viewport. E2E requires Chrome; `PLAYWRIGHT_CHROME_PATH` may select its executable. Do not point it at a database or provider with production data.
