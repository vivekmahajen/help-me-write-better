# Help Me Write Better — Word add-in (#3)

An Office Add-in (Office.js) task pane for Microsoft Word. A thin client of the
platform gateway — it reads the document or selection, calls `POST /v1/check`
(real-time issues) or `POST /v1/improve` (rewrites), and applies accepted fixes
back into the document. Sidebar UX is the realistic pattern inside Word (true
inline isn't available).

## Files

- `manifest.xml` — Office Add-in manifest (host: Word; `ReadWriteDocument`).
- `src/taskpane.html` / `src/taskpane.js` — the task pane UI + Office.js glue.
- `src/api.js` — pure gateway client + helpers (no Office.js), shared with tests.

## How it works

- **Check document** → reads `body.text`, calls `/v1/check`, lists suggestions
  (`{range, severity, message, replacements}`). **Fix** locates the original text
  via `Body.search()` and replaces it (Word ranges aren't plain-text offsets).
- **Improve selection** → sends the selection to `/v1/improve` with a chosen
  service and replaces it with the result.
- **Settings** — API base URL + key (API-key auth), stored in `localStorage`.

## Develop / sideload

1. Serve the `src/` files over HTTPS (Office requires HTTPS) and update
   `manifest.xml` `SourceLocation`/`IconUrl` to that origin.
2. Sideload `manifest.xml` in Word (Insert → Add-ins → Upload My Add-in, or the
   Office dev tooling), then open the task pane and set your API base URL + key.

## Test

```bash
cd addins/word && npm test   # node --test: client request shaping, errors, helpers
```

## Before publishing (flagged)

- **AppSource (Office Store) review** is required to distribute; the manifest,
  HTTPS hosting, and icons must be production URLs.
- **Privacy:** document text is sent only to your configured API base URL; the
  platform doesn't store document bodies (see `docs/PLATFORM.md`). Provide a data
  disclosure and get terms reviewed by counsel before shipping.
