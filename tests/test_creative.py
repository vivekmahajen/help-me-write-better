import io
import json

import pytest

from evals import character_voice_eval as cve
from write_better import templating as t
from write_better.platform import accounts, metering
from write_better.platform.gateway import CONTEXT_BUDGET_CHARS, make_gateway
from write_better.realtime import style_fingerprint
from write_better.prompt import build_user_message
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services


# --- creative templates -------------------------------------------------------

def test_creative_templates_load():
    creative = t.list_templates("creative")
    assert len(creative) >= 10
    ids = {c["id"] for c in creative}
    assert {"story-premise", "character-voice", "save-the-cat"} <= ids


def test_character_voice_template_renders():
    tpl = t.get_template("character-voice")
    out = t.validate_and_render(tpl, {"profile": "gruff sailor", "passage": "She smiled."})
    assert "gruff sailor" in out and "She smiled." in out
    assert tpl.defaults["service"] == "paraphrase"


# --- style fingerprint --------------------------------------------------------

def test_style_fingerprint_metrics():
    text = ('"Get down!" she shouted. He ran very quickly, breathing hard. '
            'The long, winding road stretched on and on into the grey distance ahead.')
    fp = style_fingerprint(text)
    assert fp["sentences"] == 3
    assert fp["sentence_length"]["mean"] > 0
    assert 0 < fp["dialogue_ratio"] < 1          # has dialogue
    assert fp["adverb_density"] > 0              # "quickly"
    assert fp["filter_words"]["count"] >= 1      # "very"
    assert "very" in fp["filter_words"]["top"]


# --- long-form context injection ----------------------------------------------

def test_build_user_message_includes_context():
    msg = build_user_message(text="continue the scene", service_names=["write"],
                             output_format="plain", show_changes=False,
                             context="Chapter 1 established that Mara fears the sea.")
    assert "CONTEXT" in msg and "Mara fears the sea" in msg


def _call(app, path, token, body):
    raw = json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_AUTHORIZATION": f"Bearer {token}",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def test_improve_passes_context_to_engine():
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    captured = {}

    def engine(req):
        captured["context"] = req.context
        return Result(text="ok", model="m", services=resolve_services(req.services),
                      input_tokens=1, output_tokens=1)

    app = make_gateway(store, engine=engine)
    status, _ = _call(app, "/v1/improve", token,
                      {"text": "continue", "services": "write",
                       "context": "Mara fears the sea."})
    assert status.startswith("200")
    assert "Mara fears the sea." in captured["context"]


def test_over_budget_context_is_passed_through_and_truncation_surfaced():
    # PR-4 behavior change: the gateway no longer omits over-budget context; it
    # passes it to the engine (which front-trims) and surfaces context_truncated.
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    captured = {}

    def engine(req):
        captured["context"] = req.context
        return Result(text="ok", model="m", services=resolve_services(req.services),
                      input_tokens=1, output_tokens=1,
                      context_truncated={"kept_chars": 10, "dropped_chars": 5})

    app = make_gateway(store, engine=engine)
    big = "x" * (CONTEXT_BUDGET_CHARS + 1)
    status, data = _call(app, "/v1/improve", token,
                         {"text": "continue", "services": "write", "context": big})
    assert status.startswith("200")
    assert captured["context"] == big                       # passed through, not dropped
    assert data["context_truncated"] == {"kept_chars": 10, "dropped_chars": 5}


# --- fingerprint endpoint -----------------------------------------------------

def test_fingerprint_endpoint():
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store)
    status, data = _call(app, "/v1/fingerprint", token,
                         {"text": "She ran. He waited very patiently in the long hall."})
    assert status.startswith("200")
    assert "fingerprint" in data and data["fingerprint"]["sentences"] == 2
    # recorded for analytics (uncapped)
    assert store.usage_since(user["id"], metering.period_start())["calls"] == 1


# --- eval harness (offline, mocked) ------------------------------------------

def test_eval_harness_pass_and_fail():
    gen = lambda profile, passage: "Aye. The harbor. Home waters at last."
    passed = cve.run_eval(gen, judge=lambda out, fix: 5)
    assert passed["passed"] is True and passed["score"] == 5
    failed = cve.run_eval(gen, judge=lambda out, fix: 2)
    assert failed["passed"] is False
