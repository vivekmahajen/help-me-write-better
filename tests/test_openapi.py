import io
import json

import pytest

from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.openapi import spec
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services


# --- spec structure -----------------------------------------------------------

def test_spec_is_openapi_31_with_security():
    s = spec()
    assert s["openapi"] == "3.1.0"
    assert s["info"]["title"] and s["info"]["version"]
    schemes = s["components"]["securitySchemes"]
    assert schemes["bearerAuth"]["scheme"] == "bearer"
    assert schemes["apiKeyHeader"]["name"] == "X-API-Key"


def test_spec_is_json_serializable():
    json.dumps(spec())  # would raise on a non-serializable value


def test_every_operation_has_operationid_and_responses():
    for path, item in spec()["paths"].items():
        for method, op in item.items():
            if method == "parameters":
                continue
            assert op.get("operationId"), f"{method} {path} missing operationId"
            assert op.get("responses"), f"{method} {path} missing responses"


def test_all_ref_targets_exist():
    s = spec()
    schemas = s["components"]["schemas"]

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref:
                assert ref.startswith("#/components/schemas/")
                assert ref.split("/")[-1] in schemas, f"dangling ref {ref}"
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)


# --- spec <-> implementation consistency --------------------------------------

def _fake_engine(req):
    return Result(text="ok", model="claude-haiku-4-5",
                  services=resolve_services(req.services), input_tokens=1, output_tokens=1)


def _call(app, method, path, token, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path,
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


_MIN_BODY = {
    "ImproveRequest": {"text": "hi", "services": "tighten"},
    "CheckRequest": {"text": "teh cat"},
    "DocumentInput": {"title": "t", "content": "c"},
    "VersionInput": {"content": "c"},
    "RenameInput": {"title": "renamed"},
    "Preferences": {"k": "v"},
    "CreateOrgInput": {"name": "Acme"},
    "AddMemberInput": {"email": "nobody@example.com"},
    "StyleGuide": {"tone": "warm"},
    "ScanRequest": {"text": "hello world", "check": {"modes": ["plagiarism"]}},
}


def _body_for(op):
    rb = op.get("requestBody")
    if not rb:
        return None
    ref = rb["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    return _MIN_BODY.get(ref, {})


def test_every_spec_route_is_wired_in_the_gateway():
    """Hitting each documented route must not return 'no such endpoint' — proves
    the spec can't document a path the gateway doesn't actually serve."""
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, engine=_fake_engine)

    # a real document so {id} routes resolve
    _, created = _call(app, "POST", "/v1/documents", token, {"title": "t", "content": "c"})
    doc_id = created["document"]["id"]

    for path, item in spec()["paths"].items():
        concrete = path.replace("{id}", str(doc_id))
        for method, op in item.items():
            if method == "parameters":
                continue
            status, data = _call(app, method.upper(), concrete, token, _body_for(op))
            assert data.get("error") != "no such endpoint", \
                f"spec documents {method.upper()} {path} but gateway has no such endpoint"
            assert not status.startswith("401"), f"{method} {path} unexpectedly unauthorized"

    store.close()


def test_documented_paths_cover_the_core_api():
    paths = spec()["paths"]
    for required in ("/v1/improve", "/v1/check", "/v1/scan", "/v1/scans/{id}",
                     "/v1/usage", "/v1/analytics", "/v1/account", "/v1/history",
                     "/v1/preferences", "/v1/documents", "/v1/documents/{id}",
                     "/v1/documents/{id}/versions"):
        assert required in paths


# --- gateway serves the spec + docs -------------------------------------------

def test_gateway_serves_openapi_and_docs_publicly():
    store = Store(":memory:")
    app = make_gateway(store)

    cap = {}
    out = app({"REQUEST_METHOD": "GET", "PATH_INFO": "/v1/openapi.json"},
              lambda s, h: cap.update(status=s, headers=dict(h)))
    assert cap["status"].startswith("200")
    assert "application/json" in cap["headers"]["Content-Type"]
    assert json.loads(b"".join(out))["openapi"] == "3.1.0"

    cap = {}
    out = app({"REQUEST_METHOD": "GET", "PATH_INFO": "/v1/docs"},
              lambda s, h: cap.update(status=s, headers=dict(h)))
    assert cap["status"].startswith("200")
    assert "text/html" in cap["headers"]["Content-Type"]
    store.close()
