# Local backend examples

Real Supabase catalog: use API **v2** and [this walkthrough](backend-supabase-v2.md). The v1 fixture examples below require `DATA_PROVIDER=fixture`; `.invalid` URLs do not refer to Supabase records.

Backend v2: [request walkthrough](backend-v2.md), [runtime/limitations](../docs/backend-v2-runtime.md), [generated schemas](../contracts/v2/). The v1 walkthrough below remains valid. `protocol-v2/` contains design fixtures, not server-generated responses.

Structured hard filter → per-offer pool → semantic assessment → deterministic ranking: [new flow and test guide](backend-retrieval-semantic-v2.md), [verification results](../docs/backend-retrieval-assessment-results.md).

Five core inputs across form/text/edits: [personalized walkthrough](backend-personalized-v2.md). `uv run python examples/check-personalized-v2.py` explicitly calls real NIM and the configured Supabase reader, uses isolated in-memory application SQLite, and saves public responses under ignored `data/live-tests/`. It tests the original Japan/Tet inputs, then supplies **synthetic** adult/budget/year/window/route answers for Tet. It does not use a running server, change catalog rows, or save session tokens. Prerequisites: existing root `.env`, `DATA_PROVIDER=supabase`, valid NIM/catalog credentials. Technical failures return a nonzero exit code; recommendations still depend on catalog proof/freshness.

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
## What-if

[Hướng dẫn test sau comparison](backend-what-if-v2.md); `check-what-if-v2.py` kiểm API với application SQLite in-memory và Supabase read-only, lưu public artifacts riêng; không ghi catalog hoặc `.env`. Gửi structured equivalents cho ca Nhật và ca Tết đã bổ sung **synthetic** số người/trần giá/năm/nghĩa khoảng; không gọi lại extraction. Script có một NIM insight-selection probe riêng trên metrics synthetic, dùng `--skip-nim` để bỏ probe đó. Không gộp probe synthetic vào kết quả tour thật.
# Catalog validation

`backend-catalog-validation.md` giải thích cấu hình trust/TTL và kiểm chứng Supabase read-only theo [policy](../docs/catalog-validation-policy.md); không cần bulk proof backfill.
