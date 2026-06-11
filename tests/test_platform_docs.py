import io
import json

import pytest

from write_better.platform import accounts, metering
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


# --- store: documents + versions ---------------------------------------------

def test_create_document_and_versions(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    doc = store.create_document(user["id"], "My note", "first draft")
    assert doc["title"] == "My note"
    assert doc["content"] == "first draft"
    assert doc["versions"] == 1

    updated = store.add_document_version(user["id"], doc["id"], "second draft")
    assert updated["content"] == "second draft"
    assert updated["versions"] == 2

    versions = store.list_document_versions(user["id"], doc["id"])
    assert [v["content"] for v in versions] == ["second draft", "first draft"]  # newest first


def test_list_rename_delete(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    d1 = store.create_document(user["id"], "One", "x")
    store.create_document(user["id"], "Two", "y")
    assert {d["title"] for d in store.list_documents(user["id"])} == {"One", "Two"}

    store.rename_document(user["id"], d1["id"], "One-renamed")
    assert store.get_document(user["id"], d1["id"])["title"] == "One-renamed"

    assert store.delete_document(user["id"], d1["id"]) is True
    assert store.get_document(user["id"], d1["id"]) is None
    assert len(store.list_documents(user["id"])) == 1


def test_document_ownership_isolation(store):
    a = accounts.create_user(store, "a@b.com", "supersecret")
    b = accounts.create_user(store, "b@b.com", "supersecret")
    doc = store.create_document(a["id"], "private", "secret body")

    # B cannot read, version, rename, or delete A's document
    assert store.get_document(b["id"], doc["id"]) is None
    assert store.list_document_versions(b["id"], doc["id"]) is None
    assert store.add_document_version(b["id"], doc["id"], "evil") is None
    assert store.rename_document(b["id"], doc["id"], "hacked") is None
    assert store.delete_document(b["id"], doc["id"]) is False
    # A's document is intact
    assert store.get_document(a["id"], doc["id"])["content"] == "secret body"


# --- store: preferences -------------------------------------------------------

def test_preferences_roundtrip(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    assert store.get_preferences(user["id"]) == {}
    store.set_preferences(user["id"], {"default_tone": "friendly", "dialect": "en-GB"})
    assert store.get_preferences(user["id"])["default_tone"] == "friendly"
    # upsert overwrites
    store.set_preferences(user["id"], {"default_tone": "formal"})
    assert store.get_preferences(user["id"]) == {"default_tone": "formal"}


# --- store: history is metadata-only -----------------------------------------

def test_history_records_metadata_not_bodies(store):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    metering.record(store, user, resolve_services("tighten"), "claude-haiku-4-5", 9, 3)
    hist = store.history(user["id"])
    assert len(hist) == 1
    row = hist[0]
    assert row["services"] == "tighten" and row["model"] == "claude-haiku-4-5"
    assert "content" not in row and "text" not in row  # no document bodies in history


# --- gateway end-to-end (fake engine, no network) -----------------------------

def _fake_engine(req):
    return Result(text="POLISHED", model="claude-haiku-4-5",
                  services=resolve_services(req.services), input_tokens=5, output_tokens=2)


def _call(app, method, path, token=None, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    chunks = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], b"".join(chunks)


@pytest.fixture
def app_token(store):
    user = accounts.create_user(store, "dev@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    return make_gateway(store, engine=_fake_engine), token


def test_cross_surface_save_and_list(app_token):
    """Acceptance: save a doc with one client (key), see it from another."""
    app, token = app_token
    status, data = _call(app, "POST", "/v1/documents", token=token,
                         body={"title": "Draft", "content": "hello world"})
    assert status.startswith("201")
    doc_id = json.loads(data)["document"]["id"]

    # a "different surface" = any client with the same key
    status, data = _call(app, "GET", "/v1/documents", token=token)
    assert status.startswith("200")
    docs = json.loads(data)["documents"]
    assert any(d["id"] == doc_id and d["title"] == "Draft" for d in docs)

    status, data = _call(app, "GET", f"/v1/documents/{doc_id}", token=token)
    assert json.loads(data)["document"]["content"] == "hello world"


def test_gateway_versions_and_delete(app_token):
    app, token = app_token
    doc_id = json.loads(_call(app, "POST", "/v1/documents", token=token,
                              body={"title": "v", "content": "one"})[1])["document"]["id"]
    _call(app, "POST", f"/v1/documents/{doc_id}/versions", token=token, body={"content": "two"})
    status, data = _call(app, "GET", f"/v1/documents/{doc_id}/versions", token=token)
    assert [v["content"] for v in json.loads(data)["versions"]] == ["two", "one"]

    status, _ = _call(app, "DELETE", f"/v1/documents/{doc_id}", token=token)
    assert status.startswith("200")
    status, _ = _call(app, "GET", f"/v1/documents/{doc_id}", token=token)
    assert status.startswith("404")


def test_gateway_preferences_sync(app_token):
    app, token = app_token
    _call(app, "PUT", "/v1/preferences", token=token, body={"default_tone": "friendly"})
    status, data = _call(app, "GET", "/v1/preferences", token=token)
    assert json.loads(data)["preferences"]["default_tone"] == "friendly"


def test_gateway_history_after_improve(app_token):
    app, token = app_token
    _call(app, "POST", "/v1/improve", token=token, body={"text": "tidy this", "services": "tighten"})
    status, data = _call(app, "GET", "/v1/history", token=token)
    hist = json.loads(data)["history"]
    assert len(hist) == 1 and hist[0]["services"] == "tighten"


def test_documents_require_auth(store):
    app = make_gateway(store, engine=_fake_engine)
    status, _ = _call(app, "GET", "/v1/documents")
    assert status.startswith("401")
