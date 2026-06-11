# Platform layer — turning the engine into a product

This documents the **platform foundation** that wraps the stateless engine with
identity, storage, metering, and billing — the "one backend hub" every surface
calls. It's a multi-phase program; this is **Phase 1, slice 1 (the spine)**.

## Architecture

```
            thin clients (later phases)
   web UI · browser extension · Word/Docs add-ins · desktop · mobile · CLI · SDKs
                                  │
                                  ▼  (all call the same gateway)
                    ┌───────────────────────────────┐
                    │  Platform gateway  /v1/*       │
                    │  auth → cap-check → meter      │
                    └───────────────┬───────────────┘
                                    │ calls (untouched)
                                    ▼
                         write_better engine  (improve)
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
          accounts /           metering /            billing
          api keys             cap enforce           (interface)
              └──────────── SQLite store ────────────┘
```

The engine is **not modified**. The platform is a package (`write_better.platform`)
layered around it.

## What's built (this slice)

| Piece | Module | Notes |
|---|---|---|
| Storage | `platform/store.py` | SQLite (stdlib). Tables: `users`, `api_keys`, `usage_events`. Never stores document bodies. |
| Accounts + API keys | `platform/accounts.py` | PBKDF2 password hashing; API keys stored as SHA-256 hash, shown once. |
| Web sessions + login | `platform/webauth.py` | Cookie sessions; `POST /auth/signup\|login\|logout`, `GET /auth/me`. End-user surfaces auth here; programmatic uses API keys. |
| OAuth (Google/Microsoft) | `platform/oauth.py` + webauth | Real OIDC authorization-code flow (injectable transport); `GET /auth/oauth/{provider}/start\|callback`. State-cookie CSRF check; links to existing email or creates a passwordless user. |
| Metering + caps | `platform/metering.py` | Premium-model generations metered per `plans.py` monthly cap; routine/standard uncapped. Enforced **before** spending on the engine. |
| Billing | `platform/billing.py` + `billing_web.py` | `BillingProvider` interface. `LocalBillingProvider` works with no keys. **`StripeBillingProvider` is fully wired** — Checkout + customer portal sessions over the Stripe REST API, plus webhook signature verification and handlers (`checkout.session.completed`/`subscription.*` set the plan; `subscription.deleted`/`payment_failed` downgrade to Free). `GET /billing/plans`, `POST /billing/checkout\|portal\|webhook`. |
| Saved docs + versions | `platform/store.py` + gateway | `POST/GET /v1/documents`, `GET/PATCH/DELETE /v1/documents/{id}`, `GET/POST /v1/documents/{id}/versions`. Bodies stored **only** on explicit save; strict per-user ownership. |
| Preferences sync | `platform/store.py` + gateway | `GET/PUT /v1/preferences` (JSON blob: default tone/audience/dialect). |
| History | `platform/store.py` + gateway | `GET /v1/history` over the usage log — **metadata only, no document bodies**. |
| Real-time check (#1) | `write_better/realtime.py` + `POST /v1/check` | Low-latency "as you type" path: local rules pass (spelling/grammar/punctuation/style/caps), changed-sentence diff, per-span cache. Normalized `{range, type, severity, message, replacements}` suggestions. **Uncapped, ~0 cost** (no model call); a `deep_check` hook can add a cheap-model pass later. |
| Analytics (#9) | `platform/analytics.py` + `GET /v1/analytics` | Aggregates the usage log into **words written, services used, issues by type, activity by day, time-saved estimate**, and **week-over-week insights**. `rollup()` gives the team view (adoption + top issues) — wires into Teams (#8). Aggregate metrics only; **no document bodies**. |
| Versioned gateway | `platform/gateway.py` | WSGI app: `GET /v1`, `/v1/account`, `/v1/usage`, `/v1/history`, `/v1/preferences`, `/v1/documents…`, `POST /v1/improve`, `POST /v1/check` (API-key auth). |
| OpenAPI contract | `platform/openapi.py` | OpenAPI 3.1 spec served at `GET /v1/openapi.json`; dependency-free docs viewer at `GET /v1/docs`. Single source of truth, cross-checked against live routes in tests. |
| JS/TS SDK | `sdk/js/` | `@help-me-write-better/sdk` — ESM JS + TypeScript declarations, zero deps, Node 18+. Typed methods for every endpoint. |
| Composed app | `platform/wsgi.py` | `/v1/*` → gateway, else the existing demo app. |
| Admin CLI | `platform/admin.py` | `write-better-admin create-user|create-key|set-plan|usage`. |

### Try it

```bash
export WB_DB_PATH=./wb.db
write-better-admin create-user --email you@example.com --password "a-strong-pass" --plan pro
write-better-admin create-key  --email you@example.com --name ci      # prints the key once
# call the metered gateway (serve write_better.platform.wsgi:app, then):
curl -X POST http://localhost:8000/v1/improve \
  -H "Authorization: Bearer wbk_..." -H "Content-Type: application/json" \
  -d '{"text":"their going to the store","services":"correct"}'
curl http://localhost:8000/v1/usage -H "Authorization: Bearer wbk_..."
```

`POST /v1/improve` returns `{ text, model, services, usage, quota }`; a request
that would exceed the plan's premium cap is rejected with **402** (`cap_reached`)
*before* the engine is called.

## Deferred (sequenced)

Per the build order, **not** in this slice:

- **Phase 1 is complete.** Accounts, API keys, metering + caps, saved docs +
  history, preferences, the OpenAPI spec + JS/TS SDK, web login + OAuth, and real
  Stripe billing are all done (see the table above). The web UI is still the
  unauthenticated demo — routing it through the gateway with login is a small
  follow-up.
- **Phases 2–3 surfaces shipped:** real-time check path (#1); **browser
  extension (#2)** (`extension/`, MV3, Gmail + web fields); **Word add-in**
  (`addins/word/`, Office.js task pane) and **Google Docs add-on**
  (`addins/google-docs/`, Apps Script Workspace Add-on — the right surface for
  Docs' canvas) (#3). All are thin clients of the gateway.
- **Phase 4 in progress:** **analytics (#9)** is done — the data layer
  (`GET /v1/analytics`, weekly insights, team `rollup`); a visual dashboard is a
  thin client of that endpoint (follow-up). Next: **teams + shared style guide
  (#8)**, then **desktop + mobile/keyboard (#4)**.
- **Phase 2:** the low-latency real-time check path (#1), then the browser
  extension (#2).
- **Phase 3:** Word + Docs add-ins (#3).
- **Phase 4:** analytics dashboards (#9), teams + shared style guide (#8), desktop
  + mobile/keyboard (#4).

## Deploy note

The gateway needs a **persistent database**. SQLite-on-local works for dev/tests;
serverless filesystems (Vercel) are ephemeral, so production needs a managed
Postgres (the `Store` DAO surface is small enough to swap). The Vercel entrypoint
(`app.py`) still serves the existing demo; point a DB-backed deployment at
`write_better.platform.wsgi:app` when the database is provisioned.

## Privacy & compliance obligations (flagged, not solved)

The spec's hard rule #4 makes privacy the product's trust. This slice already
**does not persist document bodies** (only metadata + metering). Still required
before shipping surfaces that read people's email/documents — these need real
implementation and **legal/security review**, not code alone:

- Encryption at rest for the database; TLS in transit (platform/infra config).
- A published data-retention & "we don't train on your text" policy + Terms.
- GDPR/CCPA: data export + deletion endpoints; data-processing records.
- SOC 2 path for the Business/enterprise tier.
- Per-surface secure token storage; App Store / Play Store keyboard "full access"
  justification; store-review cycles (Chrome/Edge/Firefox, AppSource, Workspace
  Marketplace, App Store, Play Store).

> This is engineering scaffolding, not legal advice. Get the data policy and terms
> reviewed by counsel before shipping any surface that reads user documents.
