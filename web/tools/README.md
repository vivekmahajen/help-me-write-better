# Pro Tools web panels (Trust-Layer UI)

A single static page (no build) with the four Trust-Layer panels — a thin client
of the gateway:

- **Plagiarism & AI detection** → `POST /v1/scan` — match-% dial + source list +
  the similarity disclaimer; a **three-band gauge** (human / uncertain / likely_ai)
  with the confidence note always visible (never a binary verdict).
- **Citations** → `POST /v1/cite` — paste DOIs/URLs/ISBNs/free-text, style picker,
  per-line warnings.
- **Templates** → `GET /v1/templates` + `POST /v1/improve` — a card gallery whose
  forms are rendered **from the template schema** (no per-template UI code), with
  variant output.
- **Style fingerprint** → `POST /v1/fingerprint` — the prose-metrics table.

`logic.js` holds the pure view-model shaping (unit-tested under `node --test`);
`app.js` is the DOM glue; `index.html` is the page.

## Use

Open `index.html` in a browser (or serve the folder), set the **API base URL** and
**API key** in the header — both persist in `localStorage`. The page calls your
deployed gateway; the key is sent as `Authorization: Bearer`.

> For local dev, point it at `http://localhost:8000` (the platform gateway) with a
> key from `write-better-admin create-key`.

## Test

```bash
cd web/tools && npm test    # node --test: view-model logic + the honesty rules
```

The pure logic is unit-tested (including "AI is always a 3-band gauge with the
confidence note, never a verdict" and "plagiarism keeps its disclaimer"). Visual
rendering needs a browser — verify by opening the page against a running gateway.
