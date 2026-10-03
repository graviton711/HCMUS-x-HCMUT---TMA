# Backend verification

Tests use synthetic inputs and temporary SQLite databases. No real credentials or network calls are needed.

- Requirements: grounded normalization, tour-price default, ambiguity, AND/OR, contradictions and patch preservation.
- Decision: three-valued logic, price bounds/children/charges, partial fields, stale data, offer separation and URL targets.
- API/state: both flows, owner isolation, idempotency, revisions, failed/cancelled/restarted jobs and evidence access.
- Gateway: NIM response/error contract and crawler source/evidence validation through mock transports.

`uv run pytest` runs deterministic checks. `uv run tour-backend probe-nim` is a separate paid/live synthetic probe; its success is not full gold accuracy.
