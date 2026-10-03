# Contracts generated from backend models

Run `uv run tour-backend export-schemas` after model changes. Do not edit generated JSON by hand.

- Frontend: `CreateRequirement`, `PatchRequirement`, `CreateComparison`, `Requirement`.
- Crawler: `CrawlRequest`, `CrawlResult`, `SourceCapability`.
- Internal LLM adapter: `Extraction` (not the public frontend request).

Schema version is `1.0`. Business rules and evidence/source bindings are also validated in Python; passing JSON Schema alone is insufficient.
