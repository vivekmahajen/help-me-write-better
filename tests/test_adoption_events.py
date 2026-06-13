"""Feature-adoption analytics events (PR-7): merge_run, argument_check_run,
goal_set, cite_style — all written to the usage_events pipeline."""

import io
import json

from write_better.engine import Result
from write_better.modes import resolve_services
from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store


def _events(store, uid):
    return [r["services"] for r in store._conn.execute(
        "SELECT services FROM usage_events WHERE user_id = ?", (uid,)).fetchall()]


def _setup(engine=None):
    store = Store(":memory:")
    gw = make_gateway(store, engine=engine) if engine else make_gateway(store)
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    return store, gw, user, token


def _call(gw, method, path, token, body=None):
    raw = json.dumps(body).encode() if body is not None else b""
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = gw(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def _fake_engine(req):
    return Result(text="ok", model="claude-haiku-4-5",
                  services=resolve_services(req.services), input_tokens=1, output_tokens=1)


def test_merge_and_argument_events():
    store, gw, user, token = _setup(engine=_fake_engine)
    _call(gw, "POST", "/v1/improve", token, {"services": "merge", "texts": ["a", "b"]})
    _call(gw, "POST", "/v1/improve", token, {"text": "essay", "services": "argument-check"})
    ev = _events(store, user["id"])
    assert "merge_run" in ev and "argument_check_run" in ev


def test_goal_set_event():
    store, gw, user, token = _setup()
    _call(gw, "PUT", "/v1/goals", token, {"goals": ["grammar"]})
    assert "goal_set" in _events(store, user["id"])


def test_cite_style_event():
    store, gw, user, token = _setup()
    _call(gw, "POST", "/v1/cite", token,
          {"cite": {"inputs": ["Smith (2020). A paper."], "style": "ieee"}})
    ev = _events(store, user["id"])
    assert "cite_style" in ev and "citation_generated" in ev
    # the style is recorded in the event's issue_types for the adoption breakdown
    row = store._conn.execute(
        "SELECT issue_types FROM usage_events WHERE user_id = ? AND services = 'cite_style'",
        (user["id"],)).fetchone()
    assert "ieee" in json.loads(row["issue_types"])
