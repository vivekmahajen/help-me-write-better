"""The strict_limit hard-length guarantee: deterministic counters + engine loop."""

import io
import json

from write_better import length, web
from write_better.engine import Request, Result, improve
from write_better.modes import resolve_services


# --- deterministic counters/trim ---------------------------------------------

def test_counters():
    assert length.count_chars("hello world") == 11
    assert length.count_words("hello   world\n again") == 3
    assert length.count_words("") == 0


def test_within_limit():
    assert length.within_limit("abcd", max_chars=4)
    assert not length.within_limit("abcde", max_chars=4)
    assert length.within_limit("one two", max_words=2)
    assert not length.within_limit("one two three", max_words=2)


def test_trim_prefers_word_boundary():
    out = length.trim_to_limit("the quick brown fox jumps", max_chars=15)
    assert len(out) <= 15 and not out.endswith(" ")
    assert out == "the quick brown"
    assert length.trim_to_limit("one two three four", max_words=2) == "one two"


# --- engine enforcement loop (fake client, no network) -----------------------

class _FakeClient:
    """Returns a scripted sequence of texts, one per messages.create() call."""
    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0

        class _Messages:
            def create(inner, **kwargs):
                self.calls += 1
                body = self._texts[min(self.calls - 1, len(self._texts) - 1)]
                return _FakeMessage(body)
        self.messages = _Messages()


class _FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"type": "text", "text": text})()]
        self.usage = type("U", (), {"input_tokens": 5, "output_tokens": 7})()


def _req(text="hi", **kw):
    return Request(text=text, services=["resize"], **kw)


def test_first_attempt_within_limit_sets_met_true():
    client = _FakeClient(["short enough"])
    r = improve(_req(max_chars=20), client=client)
    assert client.calls == 1
    assert r.limit_met is True
    assert r.char_count == len("short enough")


def test_regenerates_then_succeeds():
    client = _FakeClient(["way too long to fit here", "tiny"])
    r = improve(_req(max_chars=5), client=client)
    assert client.calls == 2           # one retry
    assert r.limit_met is True and r.text == "tiny"


def test_gives_up_after_two_retries_and_trims_but_flags_false():
    over = "this output simply will not get shorter no matter what"
    client = _FakeClient([over, over, over])     # never complies
    r = improve(_req(max_chars=10), client=client)
    assert client.calls == 3           # first + two retries
    assert r.limit_met is False        # honest: model never met it
    assert r.char_count <= 10          # but the returned text truly fits (trimmed)


def test_no_limit_leaves_met_none():
    client = _FakeClient(["anything goes"])
    r = improve(_req(), client=client)
    assert client.calls == 1 and r.limit_met is None


# --- public API surfaces the fields ------------------------------------------

def test_web_response_includes_length_and_limit(monkeypatch):
    def fake_improve(req):
        assert req.max_chars == 30      # parsed from the body
        return Result(text="trimmed", model="m", services=resolve_services("resize"),
                      limit_met=False, char_count=7, word_count=1)

    monkeypatch.setattr(web, "has_api_key", lambda: True)
    monkeypatch.setattr(web, "improve", fake_improve)
    raw = json.dumps({"text": "x", "services": "resize", "max_chars": 30}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    body = web.app(environ, lambda s, h: cap.update(status=s))
    data = json.loads(b"".join(body))
    assert data["limit_met"] is False
    assert data["length"] == {"chars": 7, "words": 1}
