# Supplier-site crawler

## Responsibility

Inspect one public tour-provider website and produce a compact, evidence-backed report containing the supplier profile, the provider's observed fields for a tour, and one real sample tour extracted from that provider. Cross-provider schema mapping is explicitly out of scope for this phase.

## Input and output

- Input: one HTTP(S) seed URL and bounded crawl options.
- Output: versioned UTF-8 JSON containing three sections only: supplier profile; tour fields observed on an actual detail page; one extracted example tour from that provider. Provider fields include a machine key and readable label (for example, `tour_code` and `Mã tour`). Every field carries a status; populated fields carry a source URL and evidence. Category/listing pages are not valid sample tours. Missing data is explicit, not guessed.
- JSON is the stable machine-readable boundary for later Google Sheets integration; the crawler does not generate a separate Markdown report. Experimental artifacts belong under `.local/crawl-reports/` (gitignored), not the repository root.

## Workflow

1. Validate the seed URL and reject local/private/reserved network targets.
2. Fetch and enforce robots.txt for the exact origin; honor redirects only within the allowed origin and revalidate every target.
3. Discover supplier information pages and prioritize a real tour-detail page from the same origin, under explicit page, response-size, and request-rate limits.
4. Parse HTML metadata and structured data defensively. Use JSON-LD `Organization`/`TravelAgency` for supplier facts and `Product`/`TouristTrip`/`Offer`/`AggregateOffer` for tour facts; malformed optional blocks must not abort the crawl.
5. Extract supplier fields and one sample tour with field-level provenance, including JSON paths, metadata keys, or explicit contact-link evidence. Do not fill supplier or tour fields by regex/label matching against flattened page text. If structured data or an explicit metadata/contact link does not expose a field, report it as unavailable instead of guessing from menus, widgets, footers, or unrelated page content.
6. Validate and serialize only the supplier profile, observed tour schema, and sample tour. Keep the report provider-specific; cross-provider schema mapping is out of scope.

## Interface with other modules

The JSON report is the stable boundary for later storage, review UI, or Google Sheets adapters. Future tour and departure crawlers can consume the source capability inventory and reuse the fetching/provenance conventions without changing this report's meaning.

## Decisions and constraints

- Python 3.12+; standard library only in v1 to keep local execution reproducible.
- Structured-data-first crawling: no browser automation, JavaScript execution, AI extraction, login, form submission, or write requests in v1. This implementation reads JSON-LD and explicit metadata/contact links already present in allowed HTML; it does not guess or call API endpoints. If a field is only visible in unstructured UI text, report it as unavailable rather than treating text matching as verified data.
- Same-origin, GET-only requests; conservative robots handling; bounded pages, bytes, timeout, and delay.
- Evidence distinguishes facts stated by the provider from independently verified facts. JSON-LD evidence includes the source URL, extraction method, and JSON path; metadata and contact links record their explicit source. V1 does not independently verify licenses or reputation; without a structured credential, license status is `not_observed`.
- For JSON-LD, retain source meanings such as `Offer.validFrom`; do not silently relabel an offer-validity date as a tour departure date.
- Offer price, departure availability, and seats are volatile. This source audit records whether/how they appear to be exposed, not their live status.

## Verification

Run `uv sync` to install the project and development tools from the committed lockfile. Then use `uv run supplier-crawler inspect <url>` to emit the three-section JSON report to stdout, or add `--output .local/crawl-reports/report.json` to save it. Run `uv run pytest` and `uv run ruff check .`. Offline fixture tests cover URL/network guards, robots policy, supplier and tour extraction, field-level evidence, limits, and stable report output; tests never depend on external sites.
