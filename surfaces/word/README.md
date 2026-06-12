# Help Me Write Better — Microsoft Word add-in

An Office.js task-pane add-in: select text in your document, pick a service, and
**Improve** replaces the selection in place. It calls the project's public JSON
API (`POST /`).

## Files
- `manifest.xml` — Office Add-in manifest (task pane, `ReadWriteDocument`).
- `taskpane.html` / `taskpane.js` — the pane UI and Word API calls (`Word.run`).
- `config.js` — the API helper + service list (engine URL stored in `localStorage`).

## Sideload (development)
Office Add-ins must be served over **HTTPS**; the task pane can't run from
`file://`.

1. Serve this folder over HTTPS, e.g. `npx http-server -S -p 3000` (or any HTTPS
   static server). The manifest's URLs already point at `https://localhost:3000`.
2. Run an engine (`python -m write_better.web`) or use your deployed URL.
3. Sideload `manifest.xml`:
   - **Windows/Mac**: Word → Insert → Add-ins → My Add-ins → Upload My Add-in.
   - or use `office-addin-debugging start manifest.xml`.
4. Open the pane, set the **Engine URL** in Settings, select text, Improve.

## Publishing
Host the files on a real HTTPS origin, update every `https://localhost:3000` URL
in `manifest.xml` (including `<AppDomains>` and `SourceLocation`) to that origin,
then submit to **AppSource** (or distribute the manifest internally). Once live,
set `WB_URL_WORD=<listing url>` on the web deployment to flip the "Microsoft
Word" tile on the landing page (see `features.py`).
