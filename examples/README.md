# Local backend examples

All tours below are synthetic; `.invalid` URLs are fixture identifiers and are never fetched.

1. Start `uv run tour-backend serve` in the repo root.
2. Create a session at `POST /v1/sessions`; use its token in `Authorization: Bearer <token>`.
3. POST `discover-form.json` or `compare-urls.json` to `/v1/requirements`.
4. POST `{ "requirement_id": "<id from step 3>", "revision": 1 }` to `/v1/comparisons`.
5. Poll `/v1/jobs/<job_id>` until terminal; read `/v1/comparisons/<comparison_id>`.

For natural language replace `form` with `text`; creation returns 202 and a parse job. Read the resulting requirement/revision after that job completes. Swagger UI is at `http://127.0.0.1:8000/docs`.

Optional environment settings are illustrated by `backend.env.example`; keep credentials in the existing root `.env`. The example is not loaded automatically.
