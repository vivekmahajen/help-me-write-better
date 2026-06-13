# Changelog

## Unreleased — Trust Layer

### Added
- **Citations: 3 → 5 styles, type-aware, + BibTeX** (Gap-4 depth, PR-3): a pure-
  Python CSL-subset renderer over the existing CSL-JSON pipeline — APA, MLA,
  Chicago, Harvard, IEEE, each correct across four item types (article, book,
  chapter, webpage), golden-tested byte-for-byte (5×4). Adds `to_bibtex` export,
  IEEE numbered in-text (`[1]`, `[2]` by position), and **explicit** unbundled-
  style degradation (falls back to APA *with a warning* — never silent). See
  `docs/decisions/ADR-002-csl.md` for why we render in pure Python rather than
  adopt citeproc-py (lxml weight + vendoring). The `cite` contract is unchanged.
- **Marketing templates → 26** (Gap-4 depth, PR-2): added `cold-email-followup`,
  `case-study`, `press-release`, `google-rsa`, `facebook-ad`, `x-thread`,
  `youtube-metadata`, `launch-announcement`, `webinar-invite`,
  `app-store-listing`, `job-posting`, `objection-faq`, `newsletter-intro`,
  `pricing-copy`, `testimonial-polish`, and `value-prop`. The char-limited assets
  (RSA, app-store) declare their platform limits in-prompt.
- **`strict_limit` hard-length guarantee** (Gap-4 depth, PR-2): request flags
  `max_chars` / `max_words` enforce a real cap — the engine checks the output,
  regenerates up to twice with a tighter instruction, then deterministically
  trims as a last resort and reports `limit_met: false` (never lies). New pure
  `length.py` counters back both the engine and UI character counters. The
  response gains `length: {chars, words}` and `limit_met` (open API + gateway).
- **Everyday templates → 16** (Gap-4 depth, PR-1): added `reference-request`,
  `performance-review`, `self-review`, `wedding-toast`, `congratulations`,
  `dispute-charge`, `rental-application`, `teacher-note`, and `dating-profile`.
  Pure YAML (zero engine code); each prompt carries guardrails for its
  emotionally-loaded context (no burned bridges, no clichés, no invented facts —
  `[bracketed placeholders]` instead). A golden-fixture snapshot sweep asserts
  every required field renders and conditionals resolve.
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
