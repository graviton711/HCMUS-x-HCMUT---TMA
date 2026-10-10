# Profile Hub migration verification

`corepack pnpm --dir tests/profile-hub-sql install --frozen-lockfile`, then `corepack pnpm --dir tests/profile-hub-sql test`. Uses in-memory PostgreSQL (PGlite), runs the actual migration twice and checks RLS, RPC permissions, typed payloads, per-owner capacity, idempotency, version conflicts, deletion privacy and account cascade. Auth roles/`auth.uid()` are a local harness. This does not connect to Supabase or verify hosted REST configuration/multi-connection concurrency; cloud checks are in `examples/profile-hub-supabase.md`.
# Avatar migration

`node tests/profile-hub-sql/verify-avatars.mjs` checks the private bucket migration twice, owner-only exact paths, cross-owner reads/inserts/updates/deletes and anonymous isolation using local PostgreSQL/WASM. Supabase Storage HTTP and hosted permissions still require the setup check in `examples/profile-hub-supabase.md`.
