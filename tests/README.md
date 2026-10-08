# Backend verification

Personalized core: form/text parity, missing/ambiguous/negative core fields, hard cap/OR coverage, targeted answer và preservation, remove/discard/CAS, URL/hybrid và legacy readiness bypass. Kiểm tra mixed semantic/core reply, generation targets, repair loại tour không được nói và grounding/polarity/slider tường minh. [Contract](../docs/personalized-requirement-policy.md).

08/10/2026: **358 passed** (311 baseline + 47 checks bổ sung), Ruff/diff đạt; 24 schemas v2, v1 không đổi. Live được chạy riêng: Nhật/Tết/follow-up15 assertions và semantic smoke5/5. [Báo cáo, failed attempts và giới hạn](../docs/backend-personalized-verification.md).

Structured retrieval/assessment: static filter trước pool, toàn bộ AND/OR trên cùng offer, coverage khi offer bị giới hạn, unknown giữ, citations/repair/timeout và replay; ranking order/bounds/ties/anchor độc lập pool, metric availability đúng comparability, party duplicate. API kiểm tra cancel/source pause và hết freshness sau khi chờ assessment; không publish kết quả muộn. SQL fake engine mô phỏng window count của offers. [Contract](../docs/retrieval-semantic-ranking.md).

Nghiệm thu phần này 08/10/2026: **311 passed** (35 checks mới + 276 baseline), Ruff/diff whitespace đạt; 24 schemas v2 và JSON schemas v1 không đổi. [Live smoke và giới hạn](../docs/backend-retrieval-assessment-results.md).

Supabase: test_supabase.py kiểm tra proof binding, imported unverified values, URL lookup, atomic isolation, stable snapshots, query limits/exclusions, errors/timeouts/schema và API confirm/comparison/evidence/ownership. Dùng rows và SQL engine giả, không network/.env. CLI probe/live smoke tách riêng, chỉ đọc catalog và dùng application DB tạm.

V2 kiểm tra proposal/version/atomicity/late results, durable events, matrix/rank/price/evidence bindings, URL-only/hybrid/exclusions, migration và role/audit/contact. Tests dùng temporary SQLite và mock upstream, không NIM/crawl live. Acceptance cụ thể ở docs/backend-v2-runtime.md.

Tests use synthetic inputs and temporary SQLite databases. No real credentials or network calls are needed.

- Requirements: grounded normalization, tour-price default, ambiguity, AND/OR, contradictions and patch preservation.
- Decision: three-valued logic, price bounds/children/charges, partial fields, stale data, offer separation and URL targets.
- API/state: both flows, owner isolation, idempotency, revisions, failed/cancelled/restarted jobs and evidence access.
- Gateway: NIM response/error contract and crawler source/evidence validation through mock transports.

`uv run pytest` runs deterministic checks. `uv run tour-backend probe-nim` is a separate paid/live synthetic probe; its success is not full gold accuracy.
## Semantic requirements tests

Gold v2 thêm ca Tết, paraphrases, partial OR/AND, scope transport, lịch âm/năm/tháng nhuận, targeted answers/CAS/provenance, query adapter và evidence-bound evaluation. Offline không gọi NIM; live evaluator v2 được chạy tường minh, không dùng smoke v1 thay kết quả v2. [Contract](../docs/requirements-semantics.md).

Date bounds không bị model hạ thành soft khi user chỉ nói linh hoạt ngày đi trong khoảng. Reserved lunar departure_window phải trả backend issue, không false-ready. Typed hard unsupported phải chặn confirm; bỏ condition phải rebuild issues. Pure clarification reply không được phát lại conditions cũ.

08/10/2026: toàn bộ suite 240 passed (85 semantic + 155 baseline), Ruff đạt. Live NIM smoke được ghi riêng tại [requirements-evaluation](../docs/requirements-evaluation.md), không gọi live trong pytest.

Supabase integration 08/10/2026: **276 passed** (155 baseline + 89 semantic + 32 Supabase), Ruff đạt. Reader tests dùng fake engine; API tests dùng SQLite tạm. Probe/ba modes/NIM live kiểm tra riêng bằng catalog read-only; [kết quả](../docs/supabase-tour-integration-plan.md). Không nâng smoke thành accuracy tổng quát.
## What-if acceptance

Tests bổ sung kiểm hard/soft group removal, AND/OR/joint blockers, cùng offer/snapshot, missing evidence và phần trăm có mẫu số, actionable budget/date edits, rank/ties/truncation, broad acquisition trước pool, API owner/CAS/idempotency/cancel/source/freshness và LLM selection fallback. [Policy](../docs/what-if-analysis.md). Dữ liệu synthetic/temporary SQLite; live catalog smoke tách riêng.

08/10/2026: **401 passed**, gồm43 what-if tests; Ruff đạt. Supabase/API live hai ca structured và NIM insight-selection probe riêng được ghi tại [báo cáo](../docs/backend-what-if-verification.md). Unknown/catalog evidence giới hạn giữ nguyên, không suy success job thành recommendation đủ hard.
# Catalog trust regression

`test_catalog_validation.py` kiểm policy opt-in của Supabase, trạng thái catalog_validated, receipt/URL/time/record binding, invalid proof không fallback, HTTP spoof/revocation, freshness độc lập và soft/what-if. Tests offline; kiểm chứng Supabase thật dùng application DB tạm và báo bounds theo [policy](../docs/catalog-validation-policy.md).
