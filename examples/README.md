# Local backend examples

Backend v2: [request walkthrough](backend-v2.md), [runtime/limitations](../docs/backend-v2-runtime.md), [generated schemas](../contracts/v2/). The v1 walkthrough below remains valid. `protocol-v2/` contains design fixtures, not server-generated responses.

All tours below are synthetic; `.invalid` URLs are fixture identifiers and are never fetched.

1. Start `uv run tour-backend serve` in the repo root.
2. Open `/docs`, execute `POST /v1/sessions`, then click **Authorize** and paste only the returned `token` (without `Bearer`). Swagger adds `Authorization: Bearer <token>` automatically. Keep this same session for subsequent requests.
3. POST `discover-form.json` or `compare-urls.json` to `/v1/requirements`. In Swagger, the **So sánh URL mô phỏng** example works with the default fixture provider and returns 201 with `id` and `revision: 1`, without calling NIM.
4. POST `{ "requirement_id": "<id from step 3>", "revision": 1 }` to `/v1/comparisons`. Replace the example ID with the actual returned `id`. Omit `offer_selections` and `reuse_comparison_id` on the first comparison; these refer to a completed previous comparison.
5. Poll `/v1/jobs/<job_id>` until terminal; read `/v1/comparisons/<comparison_id>`.

For natural language replace `form` with `text`; creation returns 202 and a parse job. Read the resulting requirement/revision after that job completes. Swagger UI is at `http://127.0.0.1:8000/docs`.

## Checking database writes

The default database is `data/backend.db`. A successful session request writes `sessions`; a URL-only/form requirement writes `resources` and `requirement_revisions`; an accepted comparison writes `resources` and `jobs` immediately. The worker then saves its result. Tour snapshots are inside the comparison payload, not separate catalog tables.

Refresh or reopen the SQLite viewer after requests. Check **Server response** in Swagger: 401 means missing/invalid/expired token, 404 means the ID does not exist in this session, 409 means the resource state/revision must be checked, and 422 means invalid input. Rejected requests do not create a comparison/job. Opening `/docs` alone does not create data.

After a backend code update, stop the old server with Ctrl+C, restart it, and reload `/docs` to see the new Authorize button and examples.

Optional environment settings are illustrated by `backend.env.example`; keep credentials in the existing root `.env`. The example is not loaded automatically.
