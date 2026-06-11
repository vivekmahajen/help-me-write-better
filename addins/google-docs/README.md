# Help Me Write Better — Google Docs add-on (#3)

A Google Workspace Add-on (Apps Script, card-based sidebar) for Google Docs. A
thin client of the platform gateway — it reads the document, calls `POST /v1/check`,
shows issues in a card, and applies accepted fixes via `Body.replaceText`. This
is the right surface for Docs because Docs renders text to a `<canvas>`, so the
browser extension can't inject there.

## Files

- `appsscript.json` — Workspace Add-on manifest (Docs homepage trigger, OAuth
  scopes: current document + external request).
- `src/Code.gs` — the Apps Script: cards, config, gateway calls, apply-fix.
- `src/helpers.js` — pure helpers (shared as Apps Script globals **and**
  unit-tested under Node).

## Deploy

1. Create an Apps Script project (or `clasp create`), and add the files from
   `src/` plus `appsscript.json`.
2. Store config from the sidebar (API base URL + key) — saved per-user in
   `PropertiesService`.
3. **Publishing:** the manifest needs a real `logoUrl`, and to call your gateway
   from a published add-on you must add your API domain to the project's URL-fetch
   allowlist / verification. Deploy as a Workspace Add-on and submit to the
   Google Workspace Marketplace.

## Test

```bash
cd addins/google-docs && npm test   # node --test: the pure helpers
```

Only the pure helpers are unit-tested here; `Code.gs` uses `CardService` /
`DocumentApp` / `UrlFetchApp`, which run inside Google's Apps Script runtime.

## Before publishing (flagged)

- **Workspace Marketplace review** + OAuth verification are required to publish.
- **Privacy:** document text is sent only to your configured API base URL; the
  platform doesn't store document bodies. Provide a data disclosure and get terms
  reviewed by counsel before shipping.
