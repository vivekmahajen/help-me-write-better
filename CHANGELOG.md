# Changelog

## Unreleased — Trust Layer

### Added
- **Plagiarism detection** (Feature 1) and **AI-content detection** (Feature 2):
  external web-index scans via `POST /v1/scan` + `GET /v1/scans/{id}`, behind a
  vendor interface (Originality.ai default — see ADR-001). Idempotent content-hash
  caching (identical re-scans are free), per-plan scan-credit metering, and
  graceful `feature_unavailable` degradation when no vendor key is set. AI results
  are **banded (human / uncertain / likely_ai), never binary**, and always carry a
  confidence note; plagiarism results carry a similarity disclaimer.
- SDK: `client.scan()` / `client.getScan()`; OpenAPI documents `/v1/scan*`.
- `docs/features/plagiarism.md`, `docs/decisions/ADR-001-plagiarism-vendor.md`,
  `.env.example`.
- **Analytics events + public docs** (cross-cutting): named feature-adoption
  events in the usage log — `scan_completed`, `citation_generated`,
  `template_used` (with the template id) — so the analytics dashboard shows
  Trust/Template-layer usage. Pricing page gains a scan-credits section;
  `docs/comparison.md` records the 30-full / 1-partial matrix (rows flipped only
  after acceptance).
- **Creative / fiction tools** (Feature 5): 12 `category: creative` templates
  (premise, beat sheets, character voice, dialogue tightener, show-don't-tell,
  scene expander, synopsis, blurb, world-building, …). Long-form `context` on
  `/v1/improve` (never silently truncated — over-budget returns an explicit
  warning with the budget number). `POST /v1/fingerprint` — local prose-style
  metrics (sentence-length distribution, dialogue ratio, adverb density, filter
  words) tracked in analytics. `evals/character_voice_eval.py` (LLM-judge, ≥4/5).
  SDK: `client.fingerprint()`. `docs/features/creative.md`.
- **Marketing-copy templates** (Feature 4): a YAML template engine executed
  through `write` — `GET /v1/templates` (schema drives forms) + `template` /
  `template_fields` on `/v1/improve`, with N variants (clamped to the plan cap),
  422 on unknown template / missing field (schema echoed). Stdlib-only YAML
  subset loader (no pyyaml). 10 launch templates; adding a YAML needs no code.
  SDK: `client.listTemplates()` / `client.useTemplate()`. `docs/features/templates.md`.
- **Citation generator** (Feature 3): `POST /v1/cite` + `GET /v1/citations`.
  Zero marginal cost, no key — DOI→Crossref, ISBN→OpenLibrary, URL→meta tags,
  free-text→LLM/heuristic (flagged for verification). APA 7 / MLA 9 / Chicago
  formatters over a CSL-JSON intermediate; per-line warnings (one bad input
  doesn't fail the batch); optional save to a per-user bibliography. SDK:
  `client.cite()` / `client.listCitations()`. `docs/features/citations.md`.
