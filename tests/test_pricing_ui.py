"""Post-signup plan selection: the page renders from plans.py, and /billing/select
records the chosen plan (no payment). Admin skips the step."""

import io
import json

from write_better.plans import PLANS
from write_better.platform import accounts
from write_better.platform.billing import LocalBillingProvider
from write_better.platform.billing_web import make_billing
from write_better.platform.login_ui import AUTH_PAGE
from write_better.platform.pricing_ui import render_plans_page
from write_better.platform.store import Store
from write_better.platform.webauth import SESSION_COOKIE


def _store():
    return Store(":memory:")


def _app(store):
    return make_billing(store, LocalBillingProvider(), base_url="https://app.test")


def _call(app, method, path, body=None, cookie=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if cookie:
        environ["HTTP_COOKIE"] = cookie
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], cap.get("headers", {}), b"".join(out)


# --- the page renders from plans.py -------------------------------------------

def test_plans_page_rendered_from_plans_module():
    html = render_plans_page()
    for p in PLANS:
        assert p.name in html                                   # every tier shown
        if p.monthly_price:
            assert f"${p.monthly_price}" in html                # real price, from plans.py
    # a button per plan, keyed by lowercase name
    for p in PLANS:
        assert f'data-plan="{p.name.lower()}"' in html


def test_choose_route_serves_html():
    status, headers, body = _call(_app(_store()), "GET", "/billing/choose")
    assert status.startswith("200")
    assert "text/html" in headers["Content-Type"]
    assert b"Choose your plan" in body


# --- selecting a plan (no payment) --------------------------------------------

def _signed_in(store, email="u@p.com"):
    user = accounts.create_user(store, email, "supersecret")
    token = accounts.create_session(store, user["id"])
    return user, f"{SESSION_COOKIE}={token}"


def test_select_requires_auth():
    status, _, body = _call(_app(_store()), "POST", "/billing/select", {"plan": "pro"})
    assert status.startswith("401")


def test_select_records_plan():
    store = _store()
    app = _app(store)
    user, cookie = _signed_in(store)
    assert store.get_user(user["id"])["plan"] == "free"
    status, _, body = _call(app, "POST", "/billing/select", {"plan": "pro"}, cookie=cookie)
    assert status.startswith("200")
    assert json.loads(body) == {"ok": True, "plan": "pro"}
    assert store.get_user(user["id"])["plan"] == "pro"          # applied immediately


def test_select_rejects_unknown_plan():
    store = _store()
    user, cookie = _signed_in(store)
    status, _, body = _call(_app(store), "POST", "/billing/select",
                            {"plan": "platinum"}, cookie=cookie)
    assert status.startswith("400")
    assert "unknown plan" in json.loads(body)["error"]


def test_free_is_a_valid_choice():
    store = _store()
    user, cookie = _signed_in(store)
    status, _, _ = _call(_app(store), "POST", "/billing/select",
                         {"plan": "free"}, cookie=cookie)
    assert status.startswith("200")


# --- signup routes new users to the plan page; admin skips it -----------------

def test_signup_page_routes_new_users_to_plan_page_admin_skips():
    # The auth page's signup handler sends non-admins to /billing/choose and
    # the admin/owner straight to the editor.
    assert "/billing/choose" in AUTH_PAGE
    assert "user.admin" in AUTH_PAGE and "'/app'" in AUTH_PAGE
