"""Long-form context (PR-4): typed input, front-trim budget, continuity, evals."""

import io
import json

from evals import continuity_eval, voice_consistency_eval
from write_better import context as ctx
from write_better import voice, web
from write_better.engine import PREMIUM_MODEL, Request, Result, improve
from write_better.modes import resolve_one, resolve_services
from write_better.prompt import build_user_message
from write_better.samples import SAMPLES


# --- pure context module -----------------------------------------------------

def test_normalize_accepts_string_and_typed_dict():
    assert ctx.normalize("hello") == ("hello", "preceding_manuscript")
    assert ctx.normalize({"text": "x", "role": "outline"}) == ("x", "outline")
    assert ctx.normalize({"text": "x", "role": "bogus"})[1] == "preceding_manuscript"
    assert ctx.normalize(None) == ("", "preceding_manuscript")


def test_estimate_and_is_long():
    assert ctx.estimate_tokens("abcd" * 100) == 100
    assert ctx.is_long("x" * (ctx.LONG_CONTEXT_TOKENS * 4))
    assert not ctx.is_long("short")


def test_budget_front_trims_and_reports():
    text = "OLD START. " + ("y" * 50) + " RECENT END"
    kept, trunc = ctx.budget(text, max_chars=20)
    assert len(kept) <= 20
    assert kept.endswith("RECENT END")           # the tail is kept
    assert trunc["dropped_chars"] == len(text) - len(kept)
    assert ctx.budget("short", max_chars=100) == ("short", None)


# --- prompt role headers -----------------------------------------------------

def test_context_role_headers():
    for role, marker in [("preceding_manuscript", "preceding manuscript"),
                         ("outline", "outline"), ("style_reference", "style reference")]:
        msg = build_user_message(text="go", service_names=["write"], output_format="plain",
                                 show_changes=False, context="CTX", context_role=role)
        assert marker in msg and "CTX" in msg


# --- engine budgeting + premium routing --------------------------------------

class _Fake:
    def __init__(self):
        self.model = None

        class _M:
            def create(inner, **kw):
                self.model = kw["model"]
                return type("Msg", (), {
                    "content": [type("B", (), {"type": "text", "text": "out"})()],
                    "usage": type("U", (), {"input_tokens": 1, "output_tokens": 1})()})()
        self.messages = _M()


def test_engine_truncates_over_budget_context():
    big = "z" * (ctx.BUDGET_CHARS + 100)
    r = improve(Request(text="continue", services=["write"], context=big), client=_Fake())
    assert r.context_truncated and r.context_truncated["dropped_chars"] >= 100


def test_engine_promotes_long_context_to_premium():
    long_ctx = "word " * (ctx.LONG_CONTEXT_TOKENS + 50)   # comfortably long
    client = _Fake()
    r = improve(Request(text="continue", services=["clarify"], context=long_ctx), client=client)
    assert client.model == PREMIUM_MODEL and r.model == PREMIUM_MODEL


def test_engine_no_context_no_truncation():
    r = improve(Request(text="hi", services=["clarify"]), client=_Fake())
    assert r.context_truncated is None


# --- continuity service + deterministic voice drift --------------------------

def test_continuity_service_and_sample():
    m = resolve_one("continuity")
    assert m.tier == "standard"
    assert "CONTINUITY" in m.instruction and "do not\nrewrite" not in m.instruction
    assert resolve_one("canon-check").name == "continuity"
    assert SAMPLES["continuity"].strip()


def test_voice_drift_signal():
    ref = "She walked. He ran. The dog barked. Night fell."          # short, punchy
    sample = ("In a remarkably and almost impossibly elaborate fashion, the "
              "extraordinarily verbose narrator continued endlessly elaborating.")
    d = voice.voice_drift(ref, sample)
    assert set(d["deltas"]) == {"mean_sentence_len", "adverb_density", "dialogue_ratio"}
    assert d["drift"] in ("low", "medium", "high")
    assert voice.voice_drift(ref, ref)["drift"] == "low"             # identical -> low


# --- web surfaces context_truncated ------------------------------------------

def test_web_surfaces_context_truncated(monkeypatch):
    def fake_improve(req):
        assert req.context == "canon" and req.context_role == "outline"
        return Result(text="ok", model="m", services=resolve_services("write"),
                      context_truncated={"kept_chars": 3, "dropped_chars": 9})
    monkeypatch.setattr(web, "has_api_key", lambda: True)
    monkeypatch.setattr(web, "improve", fake_improve)
    raw = json.dumps({"text": "go", "services": "write",
                      "context": {"text": "canon", "role": "outline"}}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    body = web.app(environ, lambda s, h: cap.update(status=s))
    data = json.loads(b"".join(body))
    assert data["context_truncated"] == {"kept_chars": 3, "dropped_chars": 9}


# --- evals run offline with fakes --------------------------------------------

def test_continuity_eval_harness():
    good = continuity_eval.run_eval(lambda c, p: "report", judge=lambda r, f: 3)
    assert good["passed"] and good["rate"] == 1.0
    weak = continuity_eval.run_eval(lambda c, p: "report", judge=lambda r, f: 1)
    assert not weak["passed"]


def test_voice_consistency_eval_harness():
    res = voice_consistency_eval.run_eval(
        lambda c, b: "She climbed. Dust everywhere.", judge=lambda c, o: 5)
    assert res["passed"] and res["score"] == 5
    assert "drift" in res["drift"]                       # deterministic signal attached
