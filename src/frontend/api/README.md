# API boundary

This module is the sole frontend HTTP boundary. The active workspace uses `current.ts` and DTOs matching `src/backend/models.py` and [`docs/backend-contract.md`](../../../docs/backend-contract.md), not the removed `src/api/v2` implementation. Validate responses before rendering; keep credentials out of URLs, logs and persistent history.

The supported vertical slice is guest session, basic destination catalog, requirement interpretation, synchronous comparison, and owner-scoped history/detail. Structured form support is limited to destination, departure city/date, budget cap and duration. Unsupported criteria must be rejected or left visibly unassessed, never converted into synthetic success. Account/Auth, proposal, job, evidence and what-if methods require matching backend routes and TestClient contract tests.

Mutations serialize once and reuse the same idempotency key on a retry. Do not retry validation/conflict responses. Abort/owner guards prevent stale responses from updating another session; cancellation of the browser request does not imply cancellation of a backend job.
