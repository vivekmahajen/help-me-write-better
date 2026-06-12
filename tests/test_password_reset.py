"""Login plus the email-based password-reset flow (forgot -> email -> reset)."""

import io
import json

from write_better.platform import accounts
from write_better.platform.mailer import ConsoleMailer
from write_better.platform.store import Store
from write_better.platform.webauth import SESSION_COOKIE, make_webauth


def _store():
    return Store(":memory:")


def _call(app, method, path, body=None, cookie=None, query=""):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}
    if cookie:
        environ["HTTP_COOKIE"] = cookie
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=h))
    return cap["status"], cap.get("headers", []), b"".join(out)


def _token_from_mail(mailer):
    body = mailer.sent[-1].body
    # token appears as ...reset?token=<hex>
    return body.split("token=")[1].split()[0].strip()


# --- accounts-level -----------------------------------------------------------

def test_reset_changes_password_and_is_single_use():
    store = _store()
    user = accounts.create_user(store, "a@b.com", "originalpass")
    token, u = accounts.create_password_reset(store, "a@b.com")
    assert u["id"] == user["id"]

    changed = accounts.reset_password(store, token, "brandnewpass")
    assert changed["id"] == user["id"]
    # old password no longer works, new one does
    assert accounts.verify_login(store, "a@b.com", "originalpass") is None
    assert accounts.verify_login(store, "a@b.com", "brandnewpass")["id"] == user["id"]
    # token can't be reused
    assert accounts.reset_password(store, token, "anotherpass") is None


def test_reset_for_unknown_email_returns_none():
    store = _store()
    token, user = accounts.create_password_reset(store, "ghost@nowhere.com")
    assert token is None and user is None


def test_reset_invalidates_existing_sessions():
    store = _store()
    user = accounts.create_user(store, "a@b.com", "originalpass")
    session = accounts.create_session(store, user["id"])
    token, _ = accounts.create_password_reset(store, "a@b.com")
    accounts.reset_password(store, token, "brandnewpass")
    assert accounts.authenticate_session(store, session) is None


def test_reset_rejects_short_password_without_consuming_token():
    store = _store()
    accounts.create_user(store, "a@b.com", "originalpass")
    token, _ = accounts.create_password_reset(store, "a@b.com")
    try:
        accounts.reset_password(store, token, "short")
        assert False, "expected ValueError"
    except ValueError:
        pass
    # token survived the failed attempt
    assert accounts.reset_password(store, token, "valid-new-pass")["email"] == "a@b.com"


# --- HTTP surface -------------------------------------------------------------

def test_forgot_then_reset_over_http_signs_user_in():
    store = _store()
    accounts.create_user(store, "a@b.com", "originalpass")
    mailer = ConsoleMailer()
    app = make_webauth(store, mailer=mailer, base_url="https://app.test")

    status, _, body = _call(app, "POST", "/auth/forgot", {"email": "a@b.com"})
    assert status.startswith("200")
    assert len(mailer.sent) == 1 and mailer.sent[0].to == "a@b.com"

    token = _token_from_mail(mailer)
    status, headers, body = _call(app, "POST", "/auth/reset",
                                  {"token": token, "password": "brandnewpass"})
    assert status.startswith("200")
    # a session cookie is set
    assert any(k == "Set-Cookie" and v.startswith(SESSION_COOKIE + "=")
               for k, v in headers)
    # and we can now log in with the new password
    status, _, _ = _call(app, "POST", "/auth/login",
                         {"email": "a@b.com", "password": "brandnewpass"})
    assert status.startswith("200")


def test_forgot_is_silent_for_unknown_email():
    store = _store()
    mailer = ConsoleMailer()
    app = make_webauth(store, mailer=mailer)
    status, _, body = _call(app, "POST", "/auth/forgot", {"email": "ghost@nowhere.com"})
    # same 200 + message, but no email actually sent (no enumeration)
    assert status.startswith("200")
    assert mailer.sent == []


def test_reset_with_bad_token_is_400():
    store = _store()
    app = make_webauth(store)
    status, _, body = _call(app, "POST", "/auth/reset",
                            {"token": "deadbeef", "password": "brandnewpass"})
    assert status.startswith("400")
    assert "invalid or expired" in json.loads(body)["error"]


def test_login_response_marks_admin():
    store = _store()
    accounts.create_user(store, "vmahajans@yahoo.com", "supersecret")
    app = make_webauth(store)
    status, _, body = _call(app, "POST", "/auth/login",
                            {"email": "vmahajans@yahoo.com", "password": "supersecret"})
    assert status.startswith("200")
    user = json.loads(body)["user"]
    assert user["admin"] is True
    # a normal user is not admin
    accounts.create_user(store, "n@u.com", "supersecret")
    _, _, body2 = _call(app, "POST", "/auth/login",
                        {"email": "n@u.com", "password": "supersecret"})
    assert json.loads(body2)["user"]["admin"] is False
