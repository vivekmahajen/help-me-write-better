# ADR-002 — Citation rendering: pure-Python CSL-subset, not citeproc-py

**Status:** accepted · **Date:** 2026-06 · **Supersedes:** the original 3-style
hand-built formatters in `citation.py`.

## Context

`citation.py` already resolves inputs (DOI→Crossref, ISBN→OpenLibrary, URL→meta,
free-text→LLM/heuristic) into **CSL-JSON** behind an `HttpGet` interface, then
renders 3 styles (APA, MLA, Chicago) with hand-written formatters. Gap-4 asks for
"the full CSL ecosystem (thousands of styles)."

The canonical way to render arbitrary CSL is **citeproc-py**, which interprets the
official `.csl` style files. We evaluated it.

## Decision

Render with a **pure-Python, data-driven CSL-subset renderer** over our existing
CSL-JSON — type-aware across the four common item types (article, book, chapter,
webpage) — for a **curated set of bundled styles**. Unsupported styles **degrade
explicitly** (fall back to APA *with a warning*, never a silent substitution).

We do **not** adopt citeproc-py at this time.

## Why not citeproc-py

1. **Dependency weight.** citeproc-py pulls **lxml** (a C-extension). The repo's
   deploy posture is deliberately light — `templating.py` hand-parses a YAML
   subset to avoid PyYAML, and `app.py` already treats the one heavy native dep
   (psycopg) as a risk to guard. Adding lxml to every serverless cold start cuts
   against that.
2. **Vendoring.** citeproc-py renders nothing without the `.csl` **style files**
   and **locale XML** on disk. Shipping "thousands of styles" means vendoring the
   CSL styles repo (~tens of MB) or fetching at runtime; neither is available in
   the build/test environment here, and runtime fetch breaks the offline,
   network-free test guarantee.
3. **Correctness surface.** A small, golden-tested set of styles we render
   exactly is more trustworthy than thousands we render through an
   un-pinned-data path. A wrong citation is worse than no citation.

## Consequences

- **Bundled styles** (type-aware, golden-tested): APA 7, MLA 9, Chicago
  author-date, Harvard, IEEE. Adding a style is a per-style renderer + fixtures.
- **Long tail:** any other style id resolves to APA and the response carries a
  `warning` naming the substitution — honest, never silent.
- **BibTeX** export is derived deterministically from CSL-JSON (no style file).
- **Reversible:** the CSL-JSON core is unchanged, so adopting citeproc-py later
  (bundling styles + accepting lxml) is purely additive — the resolver layer and
  the `cite` contract stay put.
