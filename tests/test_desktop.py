"""Validate the Tauri desktop shell scaffold (no Rust build required)."""

import json
import struct
import tomllib
from pathlib import Path

DESK = Path(__file__).resolve().parents[1] / "surfaces" / "desktop"
TAURI = DESK / "src-tauri"


def _read(p):
    return p.read_text(encoding="utf-8")


def test_tauri_conf_is_valid_and_points_at_the_editor():
    conf = json.loads(_read(TAURI / "tauri.conf.json"))
    assert conf["productName"] == "Help Me Write Better"
    assert conf["identifier"].count(".") >= 2          # reverse-domain id
    assert conf["version"]
    assert conf["build"]["frontendDist"] == "../dist"
    assert "icons/icon.png" in conf["bundle"]["icon"]
    assert conf["app"]["windows"][0]["title"]


def test_shell_redirects_to_the_engine_app():
    html = _read(DESK / "dist" / "index.html")
    assert "ENGINE_URL" in html
    assert "/app" in html
    assert "location.replace" in html                  # actually navigates


def test_cargo_manifest_declares_tauri():
    cargo = tomllib.loads(_read(TAURI / "Cargo.toml"))
    assert cargo["package"]["name"]
    assert "tauri" in cargo["dependencies"]
    assert "tauri-build" in cargo["build-dependencies"]


def test_rust_entrypoints_present():
    main = _read(TAURI / "src" / "main.rs")
    assert "tauri::Builder::default()" in main
    assert "tauri::generate_context!()" in main
    assert "tauri_build::build()" in _read(TAURI / "build.rs")


def test_icon_is_a_valid_512_png():
    data = (TAURI / "icons" / "icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", data[16:24])
    assert w == 512 and h == 512
