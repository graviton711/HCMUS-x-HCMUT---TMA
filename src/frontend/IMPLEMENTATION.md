# Frontend integration plan

React + TypeScript + Vite runs as the `src/frontend` sibling module. The existing backend in `src/backend` is authoritative; frontend integration must not introduce a second API/model tree.

## Boundaries

| Module | Responsibility | Interface |
|---|---|---|
| `api/` | Active `current.ts` transport/DTOs for guest search; dormant migration DTOs are not mounted | `docs/backend-contract.md` |
| `app/` | Routing, locale/theme, session and account shell | API client; browser storage only for drafts/credentials scoped to the tab |
| `features/workspace/` | Active guest interpretation/search/snapshot display; proposal/job/what-if components remain port targets | Backend resources; no client-side eligibility/ranking |
| `components/` | Reusable controls/dialogs/sidebar | Typed props and callbacks |
| `tests/` | Unit, contract and browser flows | Fixtures remain test-only |

## Migration rules

- Active routes must use current backend paths and DTOs; do not adapt current models into synthetic `/v2` resources. Dormant components remain disabled until ported.
- Keep current synchronous requirement/comparison API stable while adding session/catalog and richer features under `src/backend`.
- Owner identity, persistence, validation, price/freshness, eligibility, job state and history references are backend-owned.
- Unsupported routes must fail explicitly; never return fake successful resources or let localStorage become authorization/history source.
- Update this document and `src/frontend/README.md` before changing runtime contracts; add TestClient contract coverage alongside backend route changes.

## Local commands

From repository root, start backend with `uv run tour-backend serve`; in another terminal run `pnpm.cmd --dir src/frontend dev`. Verify with `typecheck`, `test`, and `build` scripts in the frontend package.
