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
