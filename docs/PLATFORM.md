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
| Metering + caps | `platform/metering.py` | Premium-model generations metered per `plans.py` monthly cap; routine/standard uncapped. Enforced **before** spending on the engine. |
| Billing | `platform/billing.py` | `BillingProvider` interface. `LocalBillingProvider` works with no keys; `StripeBillingProvider` is a clear stub (documents the calls, raises until wired). |
| Saved docs + versions | `platform/store.py` + gateway | `POST/GET /v1/documents`, `GET/PATCH/DELETE /v1/documents/{id}`, `GET/POST /v1/documents/{id}/versions`. Bodies stored **only** on explicit save; strict per-user ownership. |
| Preferences sync | `platform/store.py` + gateway | `GET/PUT /v1/preferences` (JSON blob: default tone/audience/dialect). |
| History | `platform/store.py` + gateway | `GET /v1/history` over the usage log — **metadata only, no document bodies**. |
| Versioned gateway | `platform/gateway.py` | WSGI app: `GET /v1`, `/v1/account`, `/v1/usage`, `/v1/history`, `/v1/preferences`, `/v1/documents…`, `POST /v1/improve` (API-key auth). |
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

- **Phase 1 remainder:** OAuth (Google/Microsoft) + web session login; real Stripe
  wiring (Checkout, portal, `invoice.paid`/`payment_failed` webhooks); OpenAPI
  spec + JS/TS SDK. *(Saved documents, versions, preferences, and history are
  done — see the table above.)*
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
