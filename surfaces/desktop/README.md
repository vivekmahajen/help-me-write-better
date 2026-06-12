# Help Me Write Better — desktop app (Tauri)

A thin, native desktop window over the hosted editor (`/app`). Tauri ships a
small Rust binary that hosts the OS webview — far lighter than Electron — and
the editor already talks to the public JSON API directly, so there's no custom
backend code here.

## Layout
```
desktop/
  dist/index.html         # shell: redirects the webview to the engine's /app
  src-tauri/
    tauri.conf.json       # Tauri v2 config (window, bundle, icon)
    Cargo.toml            # Rust crate (tauri + tauri-build)
    build.rs              # tauri_build::build()
    src/main.rs           # tauri::Builder::default().run(...)
    icons/icon.png        # 512px base icon (generate_icon.py); `tauri icon` derives the rest
```

## Point it at your engine
Edit `ENGINE_URL` in `dist/index.html` (defaults to the hosted instance; use a
self-hosted URL or `http://localhost:8000` for local dev), then rebuild.

## Build / run (development)
Prerequisites: a [Rust toolchain](https://rustup.rs) and the Tauri CLI
(`cargo install tauri-cli --version "^2"`), plus your platform's webview deps
(see the Tauri docs).

```bash
cd surfaces/desktop/src-tauri
cargo tauri icon icons/icon.png   # generate platform icons (.ico/.icns/png) once
cargo tauri dev                   # run the app
cargo tauri build                 # produce installers for the current OS
```

## Publishing
Build per-OS installers (`cargo tauri build`) and distribute them (direct
download, or the Microsoft Store / a Mac notarized DMG). Once there's a download
page, set `WB_URL_DESKTOP=<url>` on the web deployment to flip the "Desktop app"
tile on the landing page from *coming soon* to a live link (see `features.py`).
