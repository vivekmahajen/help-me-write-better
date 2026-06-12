"""Personal dictionary / never-flag rules (#5): store, engine prompt, gateway."""

import io
import json

from write_better.engine import Result
from write_better.modes import resolve_services
from write_better.prompt import build_user_message
from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store


# --- store -------------------------------------------------------------------

def test_store_dictionary_crud_and_dedupe():
    s = Store(":memory:")
    u = accounts.create_user(s, "a@b.com", "supersecret")
    uid = u["id"]
    assert s.list_dictionary(uid) == []
    assert s.add_dictionary_term(uid, "Kubernetes") is True
    assert s.add_dictionary_term(uid, "Kubernetes") is True   # idempotent, still present
    assert s.add_dictionary_term(uid, "  ") is False          # blank rejected
    s.add_dictionary_term(uid, "kanban")
    assert s.list_dictionary(uid) == ["Kubernetes", "kanban"]  # sorted
    assert s.remove_dictionary_term(uid, "Kubernetes") is True
    assert s.remove_dictionary_term(uid, "Kubernetes") is False  # already gone
    assert s.list_dictionary(uid) == ["kanban"]
    s.close()


# --- engine prompt -----------------------------------------------------------

def test_prompt_renders_protected_terms_block():
    msg = build_user_message(
        text="We use Kubernetes and kanban.",
        service_names=["correct"], output_format="plain", show_changes=False,
        protected_terms=["Kubernetes", "kanban"],
    )
    assert "PROTECTED TERMS" in msg
    assert "- Kubernetes" in msg and "- kanban" in msg
    assert "never flag" in msg


def test_prompt_omits_block_when_no_terms():
    msg = build_user_message(
        text="hello", service_names=["correct"], output_format="plain",
        show_changes=False, protected_terms=[])
    assert "PROTECTED TERMS" not in msg


# --- gateway -----------------------------------------------------------------

def _gateway_with_capture():
    """A gateway whose engine records the Request it was given."""
    store = Store(":memory:")
    captured = {}

    def fake_engine(req):
        captured["req"] = req
        return Result(text="ok", model="claude-haiku-4-5",
                      services=resolve_services("correct"), input_tokens=1, output_tokens=1)

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


def test_gateway_dictionary_endpoints():
    store, gw, user, token, _ = _gateway_with_capture()
    status, body = _call(gw, token, "GET", "/v1/dictionary")
    assert status.startswith("200") and body == {"terms": []}

    status, body = _call(gw, token, "POST", "/v1/dictionary", {"term": "Kubernetes"})
    assert status.startswith("201") and body["terms"] == ["Kubernetes"]

    status, body = _call(gw, token, "POST", "/v1/dictionary", {"term": ""})
    assert status.startswith("400")

    status, body = _call(gw, token, "DELETE", "/v1/dictionary", {"term": "Kubernetes"})
    assert status.startswith("200") and body["terms"] == []

    status, _ = _call(gw, token, "DELETE", "/v1/dictionary", {"term": "ghost"})
    assert status.startswith("404")


def test_gateway_injects_dictionary_into_improve():
    store, gw, user, token, captured = _gateway_with_capture()
    _call(gw, token, "POST", "/v1/dictionary", {"term": "Kubernetes"})
    _call(gw, token, "POST", "/v1/dictionary", {"term": "kanban"})

    status, _ = _call(gw, token, "POST", "/v1/improve",
                      {"text": "we use kubernetes", "services": "correct"})
    assert status.startswith("200")
    assert captured["req"].protected_terms == ["Kubernetes", "kanban"]
