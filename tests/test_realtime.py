import io
import json

import pytest

from write_better import realtime
from write_better.realtime import Suggestion, check_span, check_text, sentences
from write_better.platform import accounts, metering
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store


def _types(suggestions):
    return {s.type for s in suggestions}


# --- rules detect issues at correct offsets -----------------------------------

def test_misspelling_with_offset_and_replacement():
    text = "I will recieve it."
    sugs = check_text(text)
    sp = next(s for s in sugs if s.type == "spelling")
    assert text[sp.start:sp.end] == "recieve"
    assert sp.replacements == ("receive",)
    assert sp.severity == "high"


def test_repeated_word():
    text = "This is the the end."
    sugs = check_text(text)
    rep = next(s for s in sugs if s.type == "grammar" and s.message == "Repeated word.")
    assert text[rep.start:rep.end] == "the the"
    assert rep.replacements == ("the",)


def test_contraction_missing_apostrophe():
    sugs = check_text("I dont know.")
    c = next(s for s in sugs if s.replacements == ("don't",))
    assert c.type == "grammar"


def test_lowercase_i_and_sentence_capital():
    sugs = check_text("i think so. but not always.")
    assert any(s.type == "capitalization" and s.replacements == ("I",) for s in sugs)
    assert any(s.type == "capitalization" and s.replacements == ("B",) for s in sugs)


def test_double_space_and_space_before_punct():
    sugs = check_text("Hello  world . Bye")
    assert any(s.type == "style" and s.message == "Remove the extra space." for s in sugs)
    assert any(s.type == "punctuation" for s in sugs)


def test_case_preserved_in_replacement():
    sugs = check_text("Teh start.")
    sp = next(s for s in sugs if s.type == "spelling")
    assert sp.replacements == ("The",)  # capital preserved


def test_clean_text_has_no_suggestions():
    assert check_text("This is a perfectly fine sentence.") == []


# --- offsets are absolute across multiple sentences ---------------------------

def test_offsets_absolute_in_second_sentence():
    text = "All good here. I will recieve it."
    sugs = check_text(text)
    sp = next(s for s in sugs if s.type == "spelling")
    assert text[sp.start:sp.end] == "recieve"


def test_sentences_segmentation_preserves_offsets():
    text = "One. Two! Three?"
    for start, end, span in sentences(text):
        assert text[start:end] == span


# --- changed-sentence diff ----------------------------------------------------

def test_diff_only_checks_changed_sentences():
    previous = "I will recieve it. The cat sat."
    # second sentence changed to introduce a new misspelling; first is unchanged
    current = "I will recieve it. The cat seperate."
    sugs = check_text(current, previous=previous)
    # the unchanged first sentence's 'recieve' is skipped; only the changed one fires
    assert all("recieve" != current[s.start:s.end] for s in sugs)
    assert any(current[s.start:s.end] == "seperate" for s in sugs)


def test_no_previous_checks_everything():
    sugs = check_text("recieve teh thing.")
    assert len([s for s in sugs if s.type == "spelling"]) == 2


# --- caching ------------------------------------------------------------------

def test_check_span_is_cached():
    check_span.cache_clear()
    check_span("teh quick fox.")
    check_span("teh quick fox.")
    info = check_span.cache_info()
    assert info.hits >= 1


# --- gateway endpoint ---------------------------------------------------------

def _call(app, token, body):
    raw = json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/check",
               "HTTP_AUTHORIZATION": f"Bearer {token}",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out))


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def test_gateway_check_returns_suggestions(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store)
    status, data = _call(app, token, {"text": "i dont recieve it"})
    assert status.startswith("200")
    assert data["count"] >= 3
    assert all({"range", "type", "severity", "message", "replacements"} <= set(s)
               for s in data["suggestions"])


def test_gateway_check_is_uncapped_and_metered(store):
    # Free plan (premium cap 0) can still call /v1/check unlimited.
    user = accounts.create_user(store, "f@b.com", "supersecret")  # free
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store)
    for _ in range(5):
        status, _ = _call(app, token, {"text": "teh"})
        assert status.startswith("200")
    # metered (5 events) but none premium -> never consumes the cap
    summary = store.usage_since(user["id"], metering.period_start())
    assert summary["calls"] == 5
    assert summary["premium_calls"] == 0


def test_gateway_check_requires_text(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store)
    status, _ = _call(app, token, {"notext": True})
    assert status.startswith("400")
