# Optional identity adapter

The current backend only implements anonymous `/v2/sessions`. Auth/account UI remains available without simulated credentials. Users can explicitly continue with an anonymous workspace. Do not send identity-adapter tokens to `/v2` until backend ownership mapping is confirmed.

`VITE_AUTH_BASE_URL` enables a separately deployed identity adapter. The following are **proposed integration assumptions, not existing backend endpoints**:

| Endpoint                  | Input / output                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `POST /auth/login`        | `{username,password}` → `{access_token,user}`                                              |
| `POST /auth/register`     | `{name,username,password,password_confirmation}` → `{access_token,user}`                   |
| `GET /auth/me`            | Bearer → `{user}` or user directly                                                         |
| `PATCH /auth/me`          | Bearer + `{name,username}` → `{user}` or user directly                                     |
| `POST /auth/logout`       | Bearer → success; clear local adapter session only after success                           |
| `POST /auth/google/start` | `{return_url}` → `{redirect_url}`; enabled separately with `VITE_AUTH_GOOGLE_ENABLED=true` |

User shape: `{id,name,username,google_email?,has_password?}`. The adapter bearer and profile are scoped to sessionStorage in the current tab and bound to the configured adapter URL. Passwords are never persisted. Local form assumptions: username 3–32 characters, password at least 8 characters, name at most 80 characters; the backend remains authoritative for credential policy and uniqueness. A 401 clears the adapter session; UI errors do not indicate login success. API URLs require an HTTP(S) origin; Google redirects require HTTPS or the app's own origin. OAuth callback, identity-to-anonymous-owner migration, linking/unlinking, account history export/delete and cross-device conversation storage still need backend contracts. Google callback must establish an adapter session server-side; frontend never reads bearer credentials from query parameters.

When browser storage is unavailable, the active identity session remains in memory for the current page. Clearing an expired or logged-out session also clears memory, so stale storage cannot restore it during the same page lifecycle. Refresh still requires the adapter cookie session or another sign-in.

UI preferences (VI/EN and light/dark) use independent versioned localStorage; source quotes/user content stay unchanged. Public contact creates an actual anonymous session, then submits `/v2/contacts` with its bearer and one stable idempotency key per submission; retries preserve the submission ID and key.
