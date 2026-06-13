"""The Gap-4 stray services: merge, wordfinder, argument-check, localize-tone."""

import io
import json

from write_better import localize, web
from write_better.engine import Result
from write_better.modes import resolve_one, resolve_services
from write_better.prompt import build_user_message, fold_sources
from write_better.samples import SAMPLES


# --- modes resolve at the declared tiers -------------------------------------

def test_stray_services_and_tiers():
    assert resolve_one("merge").tier == "premium"
    assert resolve_one("wordfinder").tier == "routine"
    assert resolve_one("argument-check").tier == "premium"
    assert resolve_one("localize-tone").tier == "standard"
    assert resolve_one("combine").name == "merge"
    assert resolve_one("reverse-dictionary").name == "wordfinder"
    assert resolve_one("logic-check").name == "argument-check"
    assert resolve_one("localize").name == "localize-tone"


def test_instructions_carry_their_contracts():
    assert "DECISIONS" in resolve_one("merge").instruction
    assert "CONFLICT" in resolve_one("merge").instruction
    assert "register" in resolve_one("wordfinder").instruction
    assert "fact-check" in resolve_one("argument-check").instruction   # honesty note
    assert "NOT translation" in resolve_one("localize-tone").instruction
    for name in ("merge", "wordfinder", "argument-check", "localize-tone"):
        assert SAMPLES[name].strip()


# --- merge: texts[] folding --------------------------------------------------

def test_fold_sources_delimits_and_skips_blanks():
    out = fold_sources(["first draft", "  ", "second draft"])
    assert "=== SOURCE 1 ===\nfirst draft" in out
    assert "=== SOURCE 2 ===\nsecond draft" in out   # blank dropped, renumbered
    assert "SOURCE 3" not in out


def _post(body, monkeypatch):
    captured = {}

    def fake_improve(req):
        captured["req"] = req
        return Result(text="ok", model="m", services=resolve_services("merge"))

    monkeypatch.setattr(web, "has_api_key", lambda: True)
    monkeypatch.setattr(web, "improve", fake_improve)
    raw = json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    out = web.app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out)), captured


def test_web_merge_folds_texts_into_request(monkeypatch):
    status, _, cap = _post(
        {"services": "merge", "texts": ["draft A", "draft B"]}, monkeypatch)
    assert status.startswith("200")
    assert "=== SOURCE 1 ===" in cap["req"].text and "draft B" in cap["req"].text


# --- localize-tone: culture validation ---------------------------------------

def test_localize_cultures_registry():
    assert set(localize.ids()) == {"en-US-direct", "en-GB-understated", "en-formal-jp"}
    assert localize.is_supported("en-GB-understated")
    assert not localize.is_supported("klingon")
    assert "CULTURE = en-US-direct" in localize.augment(None, "en-US-direct")


def test_web_localize_unknown_culture_422(monkeypatch):
    status, body, _ = _post(
        {"text": "hi", "services": "localize-tone", "culture": "klingon"}, monkeypatch)
    assert status.startswith("422")
    assert body["code"] == "unknown_culture"
    assert "en-formal-jp" in body["supported"]


def test_web_localize_valid_culture_augments_request(monkeypatch):
    status, _, cap = _post(
        {"text": "Pay now.", "services": "localize-tone",
         "culture": "en-GB-understated", "request": "soften it"}, monkeypatch)
    assert status.startswith("200")
    assert "soften it" in cap["req"].free_form
    assert "CULTURE = en-GB-understated" in cap["req"].free_form


def test_prompt_injects_merge_instruction():
    modes = resolve_services("merge")
    msg = build_user_message(
        text=fold_sources(["a", "b"]),
        service_names=[m.name for m in modes], output_format="plain", show_changes=False,
        service_instructions=[(m.name, m.instruction) for m in modes if m.instruction])
    assert "=== SOURCE 1 ===" in msg and "DECISIONS" in msg
