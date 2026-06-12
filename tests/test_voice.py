"""Personal voice profile (#4): derive from samples, inject into the engine."""

import io
import json

from write_better import voice
from write_better.engine import Result
from write_better.modes import resolve_services
from write_better.prompt import build_user_message
from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store

_SAMPLE = (
    "I keep my notes short. No fluff. When something matters, I say it plainly and move on. "
    "Honestly? Most writing is twice as long as it needs to be."
)


# --- pure voice module -------------------------------------------------------

def test_render_voice_profile_includes_descriptor_and_excerpt():
    block = voice.render_voice_profile(_SAMPLE)
    assert block is not None
    assert "VOICE PROFILE" in block
    assert "average sentence length" in block         # measured descriptor
    assert "I keep my notes short" in block           # the author's own sample
    assert "do not flatten" in block


def test_render_voice_profile_none_when_empty():
    assert voice.render_voice_profile("") is None
    assert voice.render_voice_profile(None) is None
    assert voice.render_voice_profile("   ") is None


def test_build_profile_exposes_fingerprint_and_descriptor():
    p = voice.build_profile(_SAMPLE)
    assert p["samples"] == _SAMPLE
    assert p["fingerprint"]["sentences"] >= 3
    assert p["descriptor"]
    assert voice.build_profile("")["descriptor"] == ""


# --- engine prompt -----------------------------------------------------------

def test_prompt_includes_voice_profile_block():
    msg = build_user_message(
        text="rewrite this", service_names=["paraphrase"], output_format="plain",
        show_changes=False, voice_profile=voice.render_voice_profile(_SAMPLE))
    assert "VOICE PROFILE" in msg
    assert "I keep my notes short" in msg


# --- gateway -----------------------------------------------------------------

def _gateway_with_capture():
    store = Store(":memory:")
    captured = {}

    def fake_engine(req):
        captured["req"] = req
        return Result(text="ok", model="claude-haiku-4-5",
                      services=resolve_services("paraphrase"), input_tokens=1, output_tokens=1)

    gw = make_gateway(store, engine=fake_engine)
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    return store, gw, user, token, captured


def _call(gw, token, method, path, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path,
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = gw(environ, lambda s, h: cap.update(status=s, headers=h))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def test_gateway_voice_crud():
    store, gw, user, token, _ = _gateway_with_capture()
    status, body = _call(gw, token, "GET", "/v1/voice")
    assert status.startswith("200") and body == {"voice": None}

    status, body = _call(gw, token, "PUT", "/v1/voice", {"samples": _SAMPLE})
    assert status.startswith("201")
    assert body["voice"]["descriptor"]
    assert body["voice"]["samples"] == _SAMPLE

    status, body = _call(gw, token, "PUT", "/v1/voice", {"samples": "  "})
    assert status.startswith("400")

    status, body = _call(gw, token, "DELETE", "/v1/voice")
    assert status.startswith("200") and body == {"voice": None}


def test_gateway_injects_voice_profile_into_improve():
    store, gw, user, token, captured = _gateway_with_capture()
    _call(gw, token, "PUT", "/v1/voice", {"samples": _SAMPLE})
    status, _ = _call(gw, token, "POST", "/v1/improve",
                      {"text": "make this sound like me", "services": "paraphrase"})
    assert status.startswith("200")
    vp = captured["req"].voice_profile
    assert vp and "VOICE PROFILE" in vp and "I keep my notes short" in vp


def test_no_voice_profile_when_unset():
    store, gw, user, token, captured = _gateway_with_capture()
    _call(gw, token, "POST", "/v1/improve", {"text": "hi", "services": "correct"})
    assert captured["req"].voice_profile is None
