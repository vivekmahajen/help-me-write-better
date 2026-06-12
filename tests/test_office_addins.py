"""Validate the Word (Office.js) and Google Docs (Apps Script) add-in surfaces."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from write_better.modes import MODES

ROOT = Path(__file__).resolve().parents[1] / "surfaces"
WORD = ROOT / "word"
DOCS = ROOT / "google-docs"
VALID = {m.name for m in MODES}

_OFFICE_NS = "{http://schemas.microsoft.com/office/appforoffice/1.1}"


def _read(p):
    return p.read_text(encoding="utf-8")


def _services_in(text):
    """Extract a JS string array literal of service names from a file."""
    block = re.search(r"(?:WB_SERVICES|SERVICES)\s*=\s*\[(.*?)\]", text, re.DOTALL).group(1)
    return re.findall(r'"([a-z\-]+)"', block) or re.findall(r"'([a-z\-]+)'", block)


# --- Word --------------------------------------------------------------------

def test_word_manifest_is_valid_taskpane_for_document():
    root = ET.fromstring(_read(WORD / "manifest.xml"))
    assert root.tag == _OFFICE_NS + "OfficeApp"
    assert root.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "TaskPaneApp"
    assert root.findtext(_OFFICE_NS + "Id")
    assert root.findtext(_OFFICE_NS + "Permissions") == "ReadWriteDocument"
    hosts = [h.attrib["Name"] for h in root.iter(_OFFICE_NS + "Host")]
    assert hosts == ["Document"]                      # targets Word
    src = root.find(f".//{_OFFICE_NS}SourceLocation").attrib["DefaultValue"]
    assert src.endswith("taskpane.html")


def test_word_taskpane_uses_office_and_word_api():
    html = _read(WORD / "taskpane.html")
    assert "appsforoffice.microsoft.com/lib/1/hosted/office.js" in html
    assert 'src="config.js"' in html and 'src="taskpane.js"' in html
    js = _read(WORD / "taskpane.js")
    assert "Office.onReady" in js
    assert "Word.run" in js
    assert "insertText" in js and "InsertLocation.replace" in js   # replaces selection
    assert "wbImprove" in js


def test_word_config_contract_and_services():
    cfg = _read(WORD / "config.js")
    assert "services: [service]" in cfg and 'method: "POST"' in cfg
    assert set(_services_in(cfg)) <= VALID


# --- Google Docs -------------------------------------------------------------

def test_docs_manifest_has_required_scopes():
    m = json.loads(_read(DOCS / "appsscript.json"))
    assert m["runtimeVersion"] == "V8"
    scopes = set(m["oauthScopes"])
    assert "https://www.googleapis.com/auth/script.external_request" in scopes  # UrlFetchApp
    assert "https://www.googleapis.com/auth/documents.currentonly" in scopes
    assert "https://www.googleapis.com/auth/script.container.ui" in scopes      # sidebar


def test_docs_code_wires_menu_selection_and_api():
    gs = _read(DOCS / "Code.gs")
    assert "function onOpen" in gs and "showSidebar" in gs
    assert "getSelection" in gs and "replaceSelectionWith" in gs
    assert "UrlFetchApp.fetch" in gs
    assert "services: [service]" in gs and "format: 'plain'" in gs   # POST / contract
    assert "createHtmlOutputFromFile('Sidebar')" in gs


def test_docs_sidebar_calls_backend_and_lists_real_services():
    html = _read(DOCS / "Sidebar.html")
    assert "google.script.run" in html
    assert "improveSelection" in html and "getApiBase" in html
    assert set(_services_in(html)) <= VALID
