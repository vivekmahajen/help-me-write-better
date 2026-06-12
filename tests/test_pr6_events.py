"""PR-6: named analytics events for feature adoption."""
import io
import json

from write_better.platform import accounts, analytics, metering
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.platform.vendors import PlagiarismVendor
from write_better.engine import Result
from write_better.modes import resolve_services


class _FakeVendor(PlagiarismVendor):
    name = "fake"

    def scan(self, text, modes):
        return {"plagiarism": {"overall_match_pct": 1.0, "sources": []}}


def _engine(req):
    return Result(text="ok", model="claude-opus-4-8",
                  services=resolve_services(req.services), input_tokens=1, output_tokens=1)


def _call(app, path, token, body):
    raw = json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_AUTHORIZATION": f"Bearer {token}",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def _setup(plan="pro"):
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret", plan=plan)
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, engine=_engine, vendor=_FakeVendor(),
                       citation_http=lambda url, h: '{"message":{"title":["X"],"author":[]}}')
    return store, user, token, app


def _services(store, user):
    return analytics.summarize(store, user["id"], 0)["by_service"]


def test_scan_emits_scan_completed_event():
    store, user, token, app = _setup()
    _call(app, "/v1/scan", token, {"text": "word " * 60, "check": {"modes": ["plagiarism"]}})
    assert "scan_completed" in _services(store, user)


def test_cite_emits_citation_generated_event():
    store, user, token, app = _setup()
    _call(app, "/v1/cite", token, {"cite": {"inputs": ["Some ref (2020)."], "style": "apa"}})
    assert "citation_generated" in _services(store, user)


def test_template_emits_template_used_with_id():
    store, user, token, app = _setup()
    _call(app, "/v1/improve", token, {
        "template": "cold-email-b2b",
        "template_fields": {"product": "x", "audience": "y", "cta": "z"}})
    summary = analytics.summarize(store, user["id"], 0)
    assert "template_used" in summary["by_service"]
    assert "cold-email-b2b" in summary["by_issue_type"]   # template id captured
