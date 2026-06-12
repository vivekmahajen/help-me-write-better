# Help Me Write Better — browser extension

"Fix text in any tab." A Manifest V3 extension that talks to the project's
public JSON API (`POST /`). No bundler, no dependencies — just static files.

## What it does
- **Right-click → "Improve with Help Me Write Better"** on selected text in any
  page or editable field. The improved text replaces your selection in place
  (or lands on the clipboard if the field can't be edited).
- **Toolbar popup**: paste text, pick a service, and improve it on the spot.
- **Settings**: point it at the hosted API, a self-hosted instance, or a local
  `http://localhost:8000`. It requests host permission only for the URL you set.

## Load it unpacked (development)
1. Run an engine locally: `python -m write_better.web` (or use your deployed URL).
2. `chrome://extensions` → enable **Developer mode** → **Load unpacked** →
   select this `surfaces/extension/` folder.
3. Open the extension's **Settings** and set the **Engine URL** (default
   `http://localhost:8000`), then pick a default service.

Works in Chrome, Edge, Brave, and other Chromium browsers.

## Icons
`icons/*.png` are generated deterministically by `icons/generate_icons.py`
(stdlib only). Re-run it if you change the brand color.

## Publishing
Zip this folder and submit it to the Chrome Web Store / Edge Add-ons. Once it's
listed, set `WB_URL_EXTENSION=<store url>` on the web deployment — that flips the
"Browser extension" tile on the landing page from *coming soon* to a live link
(see `features.py`). The tile stays honest until a real store URL exists.
