# Help Me Write Better — browser extension (#2)

A Manifest V3 WebExtension (Chrome/Edge/Firefox) that gives real-time writing
suggestions in **Gmail and standard web text fields**. It's a thin client of the
platform gateway's `POST /v1/check` — all checking logic lives server-side; the
extension only detects fields, debounces, and renders the shared suggestion model.

## How it works

- **`src/content.js`** — detects editable fields (`textarea`, `contenteditable`,
  Gmail compose), debounces input (~600ms), and renders suggestions as a floating
  card with **Fix** / **Dismiss**.
- **`src/background.js`** — the service worker holds the API key and makes the
  gateway calls. The page/content script never sees the key.
- **`src/core.js`** — pure logic (debounce, field detection, apply-suggestion,
  the `SuggestionEngine`), shared with the unit tests.

## Install (unpacked, for development)

1. Run the platform gateway somewhere reachable (e.g. `write_better.platform.wsgi:app`)
   and create an API key: `write-better-admin create-key --email you@example.com`.
2. Chrome/Edge → `chrome://extensions` → enable **Developer mode** → **Load
   unpacked** → select this `extension/` folder. (Firefox: `about:debugging` →
   **Load Temporary Add-on** → pick `manifest.json`.)
3. Click the extension → **Settings**, set the **API base URL** and paste the
   **API key**.
4. Type in Gmail or any web text field — suggestions appear.

## Test

```bash
cd extension && npm test   # node --test, no deps, no browser
```

Covers the pure logic: debounce, editable-field detection, get/set text,
apply-suggestion offsets, and the `SuggestionEngine` (debounce + previous-text
tracking + error handling).

## Scope & known limits

- **Google Docs is intentionally out of scope here.** Docs renders text to a
  `<canvas>`, so DOM injection doesn't work — that surface is the **Docs add-on**
  (Phase 3). This extension targets Gmail + standard web fields, where DOM access
  works.
- `contenteditable` fixes currently replace text by offset, which is crude for
  richly-formatted editors (caret/markup may shift). A range-preserving editor
  integration is a follow-up.

## Before publishing (flagged, not done)

- **Store review:** Chrome Web Store, Edge Add-ons, and Firefox AMO each review
  MV3 extensions; `host_permissions: ["<all_urls>"]` will draw scrutiny — narrow
  it to the gateway origin + the sites you support before submitting.
- **Privacy:** the extension sends field text to *your* configured API base URL
  only. Publish a clear data-handling disclosure; the platform already avoids
  storing document bodies (see `docs/PLATFORM.md`). Get the policy reviewed by
  counsel before shipping a tool that reads users' email/text.
