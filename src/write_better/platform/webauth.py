"""Web/desktop/mobile authentication surface — session cookies + OAuth (#6).

End-user surfaces authenticate here (email/password or Google/Microsoft) and get
a session cookie; programmatic access uses API keys on the gateway. Both back
onto the same accounts.

Endpoints:
  GET  /auth/login | /auth/signup            -> the browser auth page (HTML)
  GET  /auth/reset?token=...                  -> set-a-new-password page (HTML)
  POST /auth/signup   {email, password}     -> set session cookie
  POST /auth/login    {email, password}     -> set session cookie
  POST /auth/logout                          -> clear session
  POST /auth/forgot   {email}                -> always 200; emails a reset link
  POST /auth/reset    {token, password}      -> set new password, sign in
  GET  /auth/me                              -> current user
  GET  /auth/oauth/{provider}/start          -> 302 to provider consent
  GET  /auth/oauth/{provider}/callback?code&state -> set session, 302 home
"""

from __future__ import annotations

import json
import secrets
from http.cookies import SimpleCookie

from ..plans import is_admin
from . import accounts
from .login_ui import AUTH_PAGE
from .mailer import ConsoleMailer, Email

SESSION_COOKIE = "wb_session"
STATE_COOKIE = "wb_oauth_state"


def _json(start_response, status, payload, extra=()):
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        *extra,
    ])
    return [body]


def _html(start_response, page, status="200 OK"):
    body = page.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b""
    if not raw:
        return {}, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "request body must be valid JSON"
    return (data, None) if isinstance(data, dict) else (None, "body must be an object")


def _cookies(environ):
    jar = SimpleCookie()
    if environ.get("HTTP_COOKIE"):
        jar.load(environ["HTTP_COOKIE"])
    return jar


def _set_cookie(name, value, *, secure, max_age=None, http_only=True):
    parts = [f"{name}={value}", "Path=/", "SameSite=Lax"]
    if http_only:
        parts.append("HttpOnly")
    if secure:
        parts.append("Secure")
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    return ("Set-Cookie", "; ".join(parts))


def _public(user):
    return {"id": user["id"], "email": user["email"], "plan": user["plan"],
            "admin": is_admin(user["email"])}


def make_webauth(store, oauth_providers=None, base_url="http://localhost", mailer=None):
    providers = oauth_providers or {}
    secure = base_url.startswith("https")
    mailer = mailer or ConsoleMailer()

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        parts = [p for p in environ.get("PATH_INFO", "/").split("/") if p]

        if parts[:1] != ["auth"]:
            return _json(start_response, "404 Not Found", {"error": "not found"})
        rest = parts[1:]

        # Browser auth page (GET): sign in / create account / forgot, and the
        # set-a-new-password view at /auth/reset?token=... from the email link.
        if rest in (["login"], ["signup"], ["reset"]) and method == "GET":
            return _html(start_response, AUTH_PAGE)

        if rest == ["signup"] and method == "POST":
            return _signup(store, environ, start_response, secure)
        if rest == ["login"] and method == "POST":
            return _login(store, environ, start_response, secure)
        if rest == ["logout"] and method == "POST":
            return _logout(store, environ, start_response, secure)
        if rest == ["forgot"] and method == "POST":
            return _forgot(store, mailer, base_url, environ, start_response)
        if rest == ["reset"] and method == "POST":
            return _reset(store, environ, start_response, secure)
        if rest == ["me"] and method == "GET":
            return _me(store, environ, start_response)
        if rest[:1] == ["oauth"] and len(rest) == 3:
            return _oauth(store, providers, base_url, secure, rest[1], rest[2],
                          environ, start_response)

        return _json(start_response, "404 Not Found", {"error": "no such endpoint"})

    return app


def _signup(store, environ, start_response, secure):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    email, password = (data.get("email") or "").strip(), data.get("password") or ""
    if not email:
        return _json(start_response, "400 Bad Request", {"error": "'email' is required"})
    try:
        user = accounts.create_user(store, email, password)
    except ValueError as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})
    token = accounts.create_session(store, user["id"])
    return _json(start_response, "201 Created", {"user": _public(user)},
                 extra=[_set_cookie(SESSION_COOKIE, token, secure=secure, max_age=2592000)])


def _login(store, environ, start_response, secure):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    user = accounts.verify_login(store, (data.get("email") or "").strip(),
                                 data.get("password") or "")
    if not user:
        return _json(start_response, "401 Unauthorized", {"error": "invalid credentials"})
    token = accounts.create_session(store, user["id"])
    return _json(start_response, "200 OK", {"user": _public(user)},
                 extra=[_set_cookie(SESSION_COOKIE, token, secure=secure, max_age=2592000)])


def _logout(store, environ, start_response, secure):
    jar = _cookies(environ)
    if SESSION_COOKIE in jar:
        accounts.destroy_session(store, jar[SESSION_COOKIE].value)
    return _json(start_response, "200 OK", {"ok": True},
                 extra=[_set_cookie(SESSION_COOKIE, "", secure=secure, max_age=0)])


# Same response whether or not the email exists — never leak which addresses
# are registered.
_FORGOT_OK = {"ok": True,
              "message": "If that email is registered, a reset link is on its way."}


def _forgot(store, mailer, base_url, environ, start_response):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    email = (data.get("email") or "").strip()
    if email:
        token, user = accounts.create_password_reset(store, email)
        if token and user:
            link = f"{base_url.rstrip('/')}/auth/reset?token={token}"
            mailer.send(Email(
                to=user["email"],
                subject="Reset your Help Me Write Better password",
                body=(
                    "We received a request to reset your password.\n\n"
                    f"Use this link within the hour:\n  {link}\n\n"
                    f"Or POST {{\"token\": \"{token}\", \"password\": \"<new>\"}} "
                    "to /auth/reset.\n\n"
                    "If you didn't ask for this, you can ignore this email — your "
                    "password won't change."
                ),
            ))
    return _json(start_response, "200 OK", _FORGOT_OK)


def _reset(store, environ, start_response, secure):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    token = (data.get("token") or "").strip()
    password = data.get("password") or ""
    try:
        user = accounts.reset_password(store, token, password)
    except ValueError as exc:                       # password too short, etc.
        return _json(start_response, "400 Bad Request", {"error": str(exc)})
    if not user:
        return _json(start_response, "400 Bad Request",
                     {"error": "invalid or expired reset token"})
    # Sign the user in on success (old sessions were invalidated by the reset).
    session = accounts.create_session(store, user["id"])
    return _json(start_response, "200 OK", {"user": _public(user)},
                 extra=[_set_cookie(SESSION_COOKIE, session, secure=secure, max_age=2592000)])


def current_user(store, environ):
    """The signed-in user for this request (from the session cookie), or None.

    Public helper reused by other surfaces (e.g. billing) that authenticate via
    the same session cookie.
    """
    jar = _cookies(environ)
    if SESSION_COOKIE not in jar:
        return None
    return accounts.authenticate_session(store, jar[SESSION_COOKIE].value)


_current_user = current_user  # backwards-compatible alias


def _me(store, environ, start_response):
    user = _current_user(store, environ)
    if not user:
        return _json(start_response, "401 Unauthorized", {"error": "not signed in"})
    return _json(start_response, "200 OK", {"user": _public(user)})


def _oauth(store, providers, base_url, secure, name, action, environ, start_response):
    provider = providers.get(name)
    if provider is None:
        return _json(start_response, "404 Not Found",
                     {"error": f"oauth provider {name!r} not configured"})
    redirect_uri = f"{base_url.rstrip('/')}/auth/oauth/{name}/callback"

    if action == "start" and environ.get("REQUEST_METHOD", "GET").upper() == "GET":
        state = secrets.token_hex(16)
        url = provider.authorize_url(state, redirect_uri)
        return start_response("302 Found", [
            ("Location", url),
            _set_cookie(STATE_COOKIE, state, secure=secure, max_age=600),
        ]) or [b""]

    if action == "callback" and environ.get("REQUEST_METHOD", "GET").upper() == "GET":
        from urllib.parse import parse_qs
        params = parse_qs(environ.get("QUERY_STRING", ""))
        code = (params.get("code") or [""])[0]
        state = (params.get("state") or [""])[0]
        jar = _cookies(environ)
        expected = jar[STATE_COOKIE].value if STATE_COOKIE in jar else None
        if not code or not state or not expected or not secrets.compare_digest(state, expected):
            return _json(start_response, "400 Bad Request", {"error": "invalid oauth state"})
        try:
            identity = provider.login(code, redirect_uri)
        except Exception as exc:
            return _json(start_response, "502 Bad Gateway", {"error": f"oauth failed: {exc}"})
        user = accounts.get_or_create_oauth_user(store, name, identity["subject"],
                                                 identity["email"])
        token = accounts.create_session(store, user["id"])
        return start_response("302 Found", [
            ("Location", base_url),
            _set_cookie(SESSION_COOKIE, token, secure=secure, max_age=2592000),
            _set_cookie(STATE_COOKIE, "", secure=secure, max_age=0),
        ]) or [b""]

    return _json(start_response, "404 Not Found", {"error": "no such endpoint"})
