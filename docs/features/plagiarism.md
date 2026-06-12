# Plagiarism + AI-content detection (Features 1 & 2)

External, web-index scans behind the gateway — **not** LLM-only. Results carry
explicit uncertainty language by design; nothing is presented as a verdict.

> Vendor: **Originality.ai** (bundles both scans under one key) — see
> [ADR-001](../decisions/ADR-001-plagiarism-vendor.md). Set `ORIGINALITY_API_KEY`.
> Without it, the API returns a structured `feature_unavailable` error — never a
> fake heuristic.

## Request

```bash
curl -s http://localhost:8000/v1/scan \
  -H "Authorization: Bearer $KEY" -H "content-type: application/json" \
  -d '{"text":"<your text>","check":{"modes":["plagiarism","ai_detection"],"min_match_pct":1.0}}'
```

`modes`: `plagiarism`, `ai_detection`, or both (one request, credits summed).

## Response (plagiarism)

```json
{ "scan_id": "…", "status": "complete",
  "plagiarism": { "overall_match_pct": 12.4,
    "sources": [{ "url": "…", "title": "…", "match_pct": 7.1, "spans": [] }],
    "scanned_words": 842, "credits_charged": 2, "cached": false,
    "disclaimer": "Match percentages indicate textual similarity to indexed sources, not a legal determination of plagiarism." } }
```

## Response (AI detection) — banded, never binary

```json
{ "ai_detection": { "band": "likely_ai", "score": 0.83,
    "confidence_note": "AI detectors are probabilistic and produce false positives, especially for non-native English writers and formulaic genres. Treat this as a signal, not a verdict.",
    "per_section": [{ "start": 0, "end": 400, "band": "uncertain", "score": 0.55 }],
    "credits_charged": 1 } }
```

Bands (config in `scans.py`): `human < 0.35 ≤ uncertain < 0.70 ≤ likely_ai`. The
`confidence_note` is always present — surface it un-truncated in every UI.

## Async + caching

`GET /v1/scans/{id}` fetches a result (supports a future webhook/async vendor).
Scans are **idempotent**: keyed by `sha256(normalized_text)` per mode-set, so an
identical re-scan returns the cached result with `credits_charged: 0, cached: true`
and never re-bills.

## Billing

Metered as **scan credits** (`ceil(words/500)` for plagiarism, 1 per AI scan),
capped per plan per month (`scans.SCAN_CAPS`: Free 0 / Starter 20 / Pro 100 /
Business 300). Over cap → **402 `scan_cap_reached`** before the vendor is called.

## Graceful degradation

- Missing key / vendor down → **503 `feature_unavailable`** with `retry_after`
  (and a `Retry-After` header). No credits charged; the failed scan isn't cached.

## Deferred (within these features)

UI panels (web results dial + source list, Word/Docs comment highlights, the
"Cite this source" hand-off to Feature 3), and live-vendor wiring — the backend
contract, caching, metering, and SDK are in place.
