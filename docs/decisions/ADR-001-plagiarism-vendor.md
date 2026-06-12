# ADR-001 — Plagiarism + AI-detection vendor

Status: accepted · Date: 2026-06-12

## Context

Features 1 (plagiarism) and 2 (AI-content detection) require an external service
that scans text against a web index — an LLM cannot do this honestly. We want a
single vendor that bundles **both** scans under one key (one account, one bill,
one integration), with predictable per-word pricing and a polling or webhook
model that fits our stateless WSGI gateway.

## Options

| | Copyleaks | Originality.ai |
|---|---|---|
| Plagiarism | ✅ | ✅ |
| AI detection | ✅ (same key) | ✅ (same key) |
| Pricing model | credits; ~$0.0072 / 100 words (plagiarism) on volume tiers | 1 credit / 100 words; Pro ≈ $0.01 / credit → **$0.10 / 1k words** |
| Completion | webhook (async) | mostly synchronous JSON response |
| Auth | OAuth login → bearer token (token refresh) | static `X-OAI-API-KEY` header |
| SDKs | official multi-language | REST-first |

### Cost-per-1k-words math (planning figures)

- Originality.ai: 1k words = 10 credits ≈ **$0.10** plagiarism, AI detection
  similar — call it **~$0.10–$0.20 / 1k words** for a combined scan.
- Copyleaks: ~**$0.072 / 1k words** plagiarism on mid volume; cheaper at scale
  but the webhook + token-refresh integration is heavier.

Our billing meters a **scan credit per 500 words** (`ceil(words/500)`), which at
the above vendor costs keeps a comfortable margin against the per-tier scan
allowances in `plans.py`-style config (Free 0 / Starter 20 / Pro 100 / Business
300 credits per month).

## Decision

**Default vendor: Originality.ai.** Rationale:

1. **Bundled** plagiarism + AI detection under one static API key — simplest auth
   for a stateless gateway (no OAuth token refresh to manage server-side).
2. **Synchronous-leaning** responses simplify the first integration; our `scans`
   table + polling endpoint still supports a genuinely async vendor later.
3. Per-word pricing is transparent and easy to map onto our credit metering.

The integration is written behind a `PlagiarismVendor` **interface**, so swapping
to Copyleaks (webhook-driven) is a new adapter, not a rewrite. The HTTP call is
injected, so tests never touch the network.

## Consequences

- Env: `ORIGINALITY_API_KEY` (see `.env.example`). Missing key →
  `feature_unavailable` (never a fake heuristic result).
- A Copyleaks adapter can be added if its volume pricing or index coverage wins;
  the `scans` schema, caching, metering, and API contract are vendor-agnostic.
