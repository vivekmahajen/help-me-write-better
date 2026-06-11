# Help Me Write Better — desktop app (#4)

A cross-platform desktop app (Electron) that **wraps the deployed web experience**.
It's a thin shell: it loads the gateway's web UI, so authentication and plan-cap
enforcement happen server-side — the desktop app runs the engine for the
signed-in user exactly like the browser does.

## Files

- `src/main.js` — Electron main process; opens a window onto `WB_APP_URL`.
- `src/config.js` — pure config helpers (URL resolution, secure window options),
  shared with the tests.

## Run

```bash
cd clients/desktop
npm install            # installs Electron
WB_APP_URL=https://your-deployment.example npm start
```

## Test

```bash
npm test   # node --test: URL validation + window security defaults
```

## Notes & scope

- Security defaults are on (`contextIsolation: true`, `nodeIntegration: false`).
- **System-wide checking** (checking text in *any* desktop app via the macOS
  Accessibility API / Windows UI Automation) is a **later milestone** — it's
  permission-gated and significant. This shell covers the in-app experience.
- Distribution (code signing + notarization for macOS, installers for Windows/
  Linux) and auto-update are packaging steps, not included here.
