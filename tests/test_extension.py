"""Validate the browser-extension surface: manifest, assets, and engine wiring."""

import json
import re
import struct
from pathlib import Path

from write_better.modes import MODES

EXT = Path(__file__).resolve().parents[1] / "surfaces" / "extension"


def _read(name):
    return (EXT / name).read_text(encoding="utf-8")


def test_manifest_is_valid_mv3():
    m = json.loads(_read("manifest.json"))
    assert m["manifest_version"] == 3
    assert m["name"] and m["version"] and m["description"]
    assert m["background"]["service_worker"] == "background.js"
    assert m["action"]["default_popup"] == "popup.html"
    assert m["options_page"] == "options.html"
    # least-privilege: no broad host_permissions baked in (uses optional + activeTab)
    assert m["host_permissions"] == ["http://localhost/*"]
    assert "storage" in m["permissions"] and "contextMenus" in m["permissions"]


def test_all_referenced_files_exist():
    m = json.loads(_read("manifest.json"))
    refs = {m["background"]["service_worker"], m["action"]["default_popup"], m["options_page"]}
    refs |= set(m["icons"].values())
    for cs in m["content_scripts"]:
        refs |= set(cs["js"])
    # html pages pull in their scripts
    refs |= {"config.js", "popup.js", "options.js", "content.js"}
    for r in refs:
        assert (EXT / r).exists(), f"missing referenced file: {r}"


def test_icons_are_valid_pngs_of_declared_size():
    for size in (16, 48, 128):
        data = (EXT / "icons" / f"icon{size}.png").read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", data[16:24])     # IHDR width/height
        assert w == size and h == size


def test_config_services_are_all_real_engine_services():
    cfg = _read("config.js")
    listed = re.search(r"WB_SERVICES\s*=\s*\[(.*?)\]", cfg, re.DOTALL).group(1)
    names = re.findall(r'"([a-z\-]+)"', listed)
    assert names, "WB_SERVICES should not be empty"
    valid = {m.name for m in MODES}
    assert set(names) <= valid, f"unknown services in the extension: {set(names) - valid}"


def test_api_helper_posts_to_engine_contract():
    cfg = _read("config.js")
    assert "services: [service]" in cfg          # matches POST / body shape
    assert 'method: "POST"' in cfg
    assert "data.error" in cfg                    # surfaces engine errors


def test_background_wires_context_menu_and_popup_bridge():
    bg = _read("background.js")
    assert 'id: "wb-improve"' in bg
    assert "contextMenus.create" in bg and "contextMenus.onClicked" in bg
    assert "wb-replace" in bg                      # tells the page to swap the selection
    assert "return true" in bg                     # async sendResponse channel kept open


def test_content_script_replaces_or_falls_back_to_clipboard():
    cs = _read("content.js")
    assert "wbReplaceSelection" in cs
    assert "clipboard.writeText" in cs             # fallback when the field can't be edited
    assert "wb-replace" in cs and "wb-error" in cs
