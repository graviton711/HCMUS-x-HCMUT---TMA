# Personal travel data

Malformed personal-store rows, versions, timestamps and mutation receipts are rejected with `PROFILE_HUB_DATA_INVALID`; provider content is never returned in errors.

Contract: [Profile Hub](../../../docs/profile-hub.md). Models validate preferences, reusable template values and historical saved-tour snapshots. Routes authenticate hosted users only, bind snapshots to owned `comparison_v2` resources, and expose v2 envelopes. Repository reads/writes the Auth project's Supabase REST/RPC using the verified user bearer, with per-item CAS and 24-hour idempotency receipts. SQLite history and crawler/catalog remain separate. Migration/setup: `examples/profile-hub-supabase.md`.
