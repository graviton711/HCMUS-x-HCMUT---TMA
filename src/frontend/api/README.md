# API boundary

This module is the sole frontend HTTP boundary. Its DTOs must match `src/backend/models.py` and [`docs/backend-contract.md`](../../../docs/backend-contract.md), not the removed `src/api/v2` implementation. Validate responses before rendering; keep credentials out of URLs, logs and persistent history.

Requirements/comparisons remain the current synchronous core. Session, catalog, account, proposal, job, history, evidence and what-if methods are added only with matching backend routes and TestClient contract tests. Do not return synthetic success for an unsupported endpoint.

Mutations serialize once and reuse the same idempotency key on a retry. Do not retry validation/conflict responses. Abort/owner guards prevent stale responses from updating another session; cancellation of the browser request does not imply cancellation of a backend job.
