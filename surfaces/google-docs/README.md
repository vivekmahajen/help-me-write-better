# Help Me Write Better — Google Docs add-on

An Apps Script editor add-on: a sidebar where you select text, pick a service,
and **Improve** replaces the selection in place. It calls the project's public
JSON API (`POST /`) via `UrlFetchApp`.

## Files
- `appsscript.json` — manifest (V8 runtime + the three OAuth scopes it needs).
- `Code.gs` — menu, sidebar, selection read/replace, and the API call.
- `Sidebar.html` — the sidebar UI (talks to `Code.gs` via `google.script.run`).

## Install (development)
1. Open a Google Doc → **Extensions → Apps Script**.
2. Create files matching this folder: paste `Code.gs`, add an HTML file named
   `Sidebar`, and (via Project Settings → "Show appsscript.json") paste
   `appsscript.json`. Or push with [`clasp`](https://github.com/google/clasp):
   `clasp push`.
3. Reload the doc → **Help Me Write Better → Open sidebar**, approve the scopes.
4. In the sidebar **Settings**, set the **Engine URL** (your deployed instance;
   note that Google's servers must be able to reach it, so a public HTTPS URL —
   not `localhost` — is required for real use).
5. Select text, choose a service, Improve.

## Publishing
Deploy as an **editor add-on** and submit to the Google Workspace Marketplace.
Once listed, set `WB_URL_DOCS=<listing url>` on the web deployment to flip the
"Google Docs" tile on the landing page (see `features.py`).
