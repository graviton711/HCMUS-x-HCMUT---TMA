# Account/Auth integration target

Current `src/backend` does not yet provide an identity adapter or owner-scoped account routes. The UI-auth implementation from `main` is therefore not runtime-connected. This document records the port target; no account credential flow should be enabled until backend routes and tests exist.

## Target boundary

- Frontend calls backend `/auth/*`; backend alone calls Supabase Auth and validates identity with the configured project.
- Frontend never trusts a client-supplied owner ID. Anonymous guest session remains separate from account identity.
- Password is memory-only; provider tokens live in `sessionStorage` scoped to the service origin, never localStorage, URL, logs or SQLite.
- Supabase configuration is optional. Without it, UI must show account unavailable while guest workflow remains usable.
- Account history uses current backend `/history` routes after owner-scoped persistence is implemented; do not call `/v2/history`.

## Required tests before enabling UI

Stub Supabase Auth HTTP calls. Cover confirmation-required signup, invalid/expired/cross-project tokens, refresh/logout revocation, owner isolation, refresh single-flight, identity switch and late-response guards. Do not create real users or require live Google/SMTP setup for tests.
