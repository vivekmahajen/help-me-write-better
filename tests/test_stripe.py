import hashlib
import hmac
import io
import json
import time

import pytest

from write_better.platform import accounts
from write_better.platform.billing import (
    LocalBillingProvider,
    StripeBillingProvider,
    StripeError,
)
from write_better.platform.billing_web import make_billing
from write_better.platform.store import Store
from write_better.platform.webauth import make_webauth


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


PRICES = {"starter": "price_starter", "pro": "price_pro", "business": "price_biz"}


def _stripe(transport=None, webhook_secret="whsec_test"):
    return StripeBillingProvider(api_key="sk_test", webhook_secret=webhook_secret,
                                 price_ids=PRICES, transport=transport or (lambda *a: {}))


def _sign(secret, payload: bytes, ts=None):
    ts = ts or int(time.time())
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


# --- guards -------------------------------------------------------------------

def test_requires_api_key():
    with pytest.raises(RuntimeError):
        StripeBillingProvider(api_key=None)


# --- checkout / portal (fake transport) ---------------------------------------

def test_checkout_url_posts_price_and_returns_url():
    calls = []

    def transport(method, url, headers, data):
        calls.append((url, data.decode()))
        return {"url": "https://checkout.stripe.com/c/sess_123"}

    provider = _stripe(transport)
    url = provider.checkout_url({"id": 1, "email": "a@b.com"}, "pro")
    assert url == "https://checkout.stripe.com/c/sess_123"
    posted_url, body = calls[0]
    assert posted_url.endswith("/checkout/sessions")
    assert "price_pro" in body and "user_id" in body


def test_checkout_invalid_plan_errors():
    # an unknown plan is a validation error
    with pytest.raises(ValueError):
        _stripe().checkout_url({"id": 1, "email": "a@b.com"}, "platinum")


def test_checkout_valid_plan_without_price_errors():
    # a real plan with no configured Stripe price is a StripeError
    provider = StripeBillingProvider(api_key="sk_test", price_ids={"starter": "price_s"},
                                     transport=lambda *a: {})
    with pytest.raises(StripeError):
        provider.checkout_url({"id": 1, "email": "a@b.com"}, "pro")


# --- webhook signature --------------------------------------------------------

def test_construct_event_verifies_signature():
    provider = _stripe()
    payload = json.dumps({"type": "ping", "data": {"object": {}}}).encode()
    event = provider.construct_event(payload, _sign("whsec_test", payload))
    assert event["type"] == "ping"


def test_construct_event_rejects_bad_signature():
    provider = _stripe()
    payload = b'{"type":"ping"}'
    with pytest.raises(StripeError):
        provider.construct_event(payload, "t=123,v1=deadbeef", tolerance=None)


def test_construct_event_rejects_old_timestamp():
    provider = _stripe()
    payload = b'{"type":"ping"}'
    old = _sign("whsec_test", payload, ts=int(time.time()) - 10_000)
    with pytest.raises(StripeError):
        provider.construct_event(payload, old)


# --- webhook handlers ---------------------------------------------------------

def test_checkout_completed_sets_customer_and_plan(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")  # free
    provider = _stripe()
    provider.handle_webhook(store, "checkout.session.completed", {
        "customer": "cus_1",
        "metadata": {"user_id": str(user["id"]), "plan": "pro"},
    })
    refreshed = store.get_user(user["id"])
    assert refreshed["plan"] == "pro"
    assert store.get_user_by_stripe_customer("cus_1")["id"] == user["id"]


def test_subscription_updated_maps_price_to_plan(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    store.set_stripe_customer(user["id"], "cus_9")
    provider = _stripe()
    provider.handle_webhook(store, "customer.subscription.updated", {
        "customer": "cus_9",
        "items": {"data": [{"price": {"id": "price_biz"}}]},
    })
    assert store.get_user(user["id"])["plan"] == "business"


def test_payment_failed_downgrades_to_free(store):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    store.set_stripe_customer(user["id"], "cus_5")
    provider = _stripe()
    provider.handle_webhook(store, "invoice.payment_failed", {"customer": "cus_5"})
    assert store.get_user(user["id"])["plan"] == "free"


# --- billing web surface ------------------------------------------------------

def _call(app, method, path, body=None, cookie=None, headers=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": ""}
    if cookie:
        environ["HTTP_COOKIE"] = cookie
    for k, v in (headers or {}).items():
        environ[k] = v
    if body is not None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def test_plans_endpoint_is_public(store):
    app = make_billing(store, LocalBillingProvider())
    status, data = _call(app, "GET", "/billing/plans")
    assert status.startswith("200")
    assert {p["plan"] for p in data["plans"]} == {"free", "starter", "pro", "business"}


def test_checkout_requires_session(store):
    app = make_billing(store, LocalBillingProvider())
    status, _ = _call(app, "POST", "/billing/checkout", body={"plan": "pro"})
    assert status.startswith("401")


def test_checkout_local_provider_returns_stub_url(store):
    auth = make_webauth(store)
    _, headers, _ = _signup(auth, store)
    cookie = headers
    bill = make_billing(store, LocalBillingProvider())
    status, data = _call(bill, "POST", "/billing/checkout", body={"plan": "pro"}, cookie=cookie)
    assert status.startswith("200")
    assert data["url"].startswith("local://checkout")


def test_webhook_endpoint_applies_plan_change(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    provider = _stripe()
    app = make_billing(store, provider)
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_x",
                            "metadata": {"user_id": str(user["id"]), "plan": "starter"}}},
    }).encode()
    status, data = _call(app, "POST", "/billing/webhook", body=payload,
                         headers={"HTTP_STRIPE_SIGNATURE": _sign("whsec_test", payload)})
    assert status.startswith("200") and data["received"] is True
    assert store.get_user(user["id"])["plan"] == "starter"


def test_webhook_unavailable_on_local_provider(store):
    app = make_billing(store, LocalBillingProvider())
    status, _ = _call(app, "POST", "/billing/webhook", body=b"{}")
    assert status.startswith("501")


# helper: sign a user up and return the session cookie string
def _signup(auth_app, store):
    raw = json.dumps({"email": "a@b.com", "password": "supersecret"}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/auth/signup",
               "QUERY_STRING": "", "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw)}
    cap = {}
    auth_app(environ, lambda s, h: cap.update(status=s, headers=h))
    cookie = next(v.split(";")[0] for k, v in cap["headers"]
                  if k == "Set-Cookie" and v.startswith("wb_session="))
    return cap["status"], cookie, None
