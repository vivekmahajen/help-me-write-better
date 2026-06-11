import io
import json

import pytest

from write_better.platform import accounts, metering
from write_better.platform.billing import (
    LocalBillingProvider,
    StripeBillingProvider,
)
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


# --- accounts -----------------------------------------------------------------

def test_password_hash_roundtrip():
    enc = accounts.hash_password("supersecret")
    assert accounts.verify_password("supersecret", enc)
    assert not accounts.verify_password("wrong", enc)
    assert not accounts.verify_password("supersecret", None)


def test_short_password_rejected():
    with pytest.raises(ValueError):
        accounts.hash_password("short")


def test_create_user_and_duplicate(store):
    user = accounts.create_user(store, "A@B.com", "supersecret")
    assert user["email"] == "a@b.com"  # normalized
    assert user["plan"] == "free"
    with pytest.raises(ValueError):
        accounts.create_user(store, "a@b.com", "supersecret")


def test_login(store):
    accounts.create_user(store, "a@b.com", "supersecret")
    assert accounts.verify_login(store, "a@b.com", "supersecret")
    assert accounts.verify_login(store, "a@b.com", "nope") is None


def test_api_key_issue_and_authenticate(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, rec = accounts.create_api_key(store, user["id"], "ci")
    assert token.startswith("wbk_")
    assert rec["prefix"] == token[:12]
    who = accounts.authenticate_key(store, token)
    assert who["id"] == user["id"]
    assert accounts.authenticate_key(store, "wbk_bogus") is None
    assert accounts.authenticate_key(store, None) is None


def test_revoked_key_fails_auth(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, rec = accounts.create_api_key(store, user["id"])
    store.revoke_api_key(rec["id"])
    assert accounts.authenticate_key(store, token) is None


# --- metering -----------------------------------------------------------------

def test_premium_request_detection():
    assert metering.consumes_premium(resolve_services("write")) is True
    assert metering.consumes_premium(resolve_services("humanize")) is True
    assert metering.consumes_premium(resolve_services("correct")) is False


def test_free_plan_blocks_premium_immediately(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")  # free, cap 0
    allowed, q = metering.check_allowed(store, user, resolve_services("write"))
    assert allowed is False
    assert q["premium_cap"] == 0
    # but a routine service is always allowed on free
    allowed2, _ = metering.check_allowed(store, user, resolve_services("correct"))
    assert allowed2 is True


def test_cap_enforced_after_usage(store):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="starter")  # cap 100
    q = metering.quota(store, user)
    assert q["premium_cap"] == 100 and q["premium_remaining"] == 100
    # record 100 premium calls -> cap reached
    for _ in range(100):
        metering.record(store, user, resolve_services("write"), "claude-opus-4-8", 10, 5)
    allowed, q = metering.check_allowed(store, user, resolve_services("write"))
    assert allowed is False
    assert q["premium_used"] == 100 and q["premium_remaining"] == 0
    # routine still fine
    assert metering.check_allowed(store, user, resolve_services("tighten"))[0] is True


# --- billing ------------------------------------------------------------------

def test_local_billing_changes_plan(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    LocalBillingProvider().change_plan(store, user["id"], "pro")
    assert store.get_user(user["id"])["plan"] == "pro"


def test_local_billing_rejects_unknown_plan(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    with pytest.raises(ValueError):
        LocalBillingProvider().change_plan(store, user["id"], "platinum")


def test_stripe_provider_requires_key():
    with pytest.raises(RuntimeError):
        StripeBillingProvider(api_key=None)


# --- gateway (end-to-end with a fake engine, no network) ----------------------

def _fake_engine(req):
    return Result(text="POLISHED", model="claude-haiku-4-5",
                  services=resolve_services(req.services), input_tokens=12, output_tokens=4)


def _call(app, method, path, token=None, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    captured = {}
    chunks = app(environ, lambda s, h: captured.update(status=s, headers=h))
    return captured["status"], b"".join(chunks)


@pytest.fixture
def signed_in(store):
    user = accounts.create_user(store, "dev@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, engine=_fake_engine)
    return app, token


def test_gateway_info_is_public(store):
    app = make_gateway(store, engine=_fake_engine)
    status, data = _call(app, "GET", "/v1")
    assert status.startswith("200")
    assert json.loads(data)["api_version"] == "v1"


def test_gateway_requires_auth(store):
    app = make_gateway(store, engine=_fake_engine)
    status, data = _call(app, "POST", "/v1/improve", body={"text": "hi"})
    assert status.startswith("401")


def test_gateway_improve_meters_usage(signed_in, store):
    app, token = signed_in
    status, data = _call(app, "POST", "/v1/improve",
                         token=token, body={"text": "make it better", "services": "tighten"})
    assert status.startswith("200")
    payload = json.loads(data)
    assert payload["text"] == "POLISHED"
    assert payload["quota"]["plan"] == "pro"
    # one usage event recorded (tighten is not premium)
    user = store.get_user_by_email("dev@b.com")
    summary = store.usage_since(user["id"], metering.period_start())
    assert summary["calls"] == 1
    assert summary["premium_calls"] == 0


def test_gateway_blocks_at_cap(store):
    user = accounts.create_user(store, "f@b.com", "supersecret")  # free, premium cap 0
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, engine=_fake_engine)
    status, data = _call(app, "POST", "/v1/improve",
                         token=token, body={"text": "draft this", "services": "write"})
    assert status.startswith("402")
    assert json.loads(data)["code"] == "cap_reached"
    # engine was never called -> no usage recorded
    assert store.usage_since(user["id"], metering.period_start())["calls"] == 0


def test_gateway_account_and_usage_endpoints(signed_in):
    app, token = signed_in
    status, data = _call(app, "GET", "/v1/account", token=token)
    assert status.startswith("200")
    assert json.loads(data)["email"] == "dev@b.com"

    status, data = _call(app, "GET", "/v1/usage", token=token)
    assert status.startswith("200")
    assert json.loads(data)["quota"]["plan"] == "pro"
