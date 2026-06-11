"""Billing surface (#7): plans, Checkout, customer portal, and the Stripe webhook.

  GET  /billing/plans     -> tiers + prices (public)
  POST /billing/checkout  -> Checkout URL for a plan        [session auth]
  POST /billing/portal    -> customer portal URL            [session auth]
  POST /billing/webhook   -> verify signature, apply change [Stripe-signed]

Backed by a ``BillingProvider``. With ``LocalBillingProvider`` (no Stripe keys)
checkout returns a local stub URL and the webhook is unavailable — local dev
works without Stripe, exactly as the margin model assumes.
"""

from __future__ import annotations

import json

from ..plans import PLANS
from . import webauth
from .billing import StripeError


def _json(start_response, status, payload):
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                            ("Content-Length", str(len(body)))])
    return [body]


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b""
    return raw


def make_billing(store, provider, base_url="http://localhost"):
    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        parts = [p for p in environ.get("PATH_INFO", "/").split("/") if p]
        if parts[:1] != ["billing"]:
            return _json(start_response, "404 Not Found", {"error": "not found"})
        rest = parts[1:]

        if rest == ["plans"] and method == "GET":
            plans = [{"plan": p.name.lower(), "monthly_price": p.monthly_price,
                      "annual_monthly": p.annual_monthly, "seats": p.seats}
                     for p in PLANS]
            return _json(start_response, "200 OK", {"plans": plans})

        if rest == ["checkout"] and method == "POST":
            return _checkout(store, provider, environ, start_response)

        if rest == ["portal"] and method == "POST":
            return _portal(store, provider, base_url, environ, start_response)

        if rest == ["webhook"] and method == "POST":
            return _webhook(store, provider, environ, start_response)

        return _json(start_response, "404 Not Found", {"error": "no such endpoint"})

    return app


def _checkout(store, provider, environ, start_response):
    user = webauth.current_user(store, environ)
    if not user:
        return _json(start_response, "401 Unauthorized", {"error": "not signed in"})
    try:
        data = json.loads(_read_json(environ) or b"{}")
    except ValueError:
        return _json(start_response, "400 Bad Request", {"error": "invalid JSON"})
    plan = (data.get("plan") or "").lower()
    try:
        url = provider.checkout_url(user, plan)
    except (ValueError, StripeError) as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})
    return _json(start_response, "200 OK", {"url": url})


def _portal(store, provider, base_url, environ, start_response):
    user = webauth.current_user(store, environ)
    if not user:
        return _json(start_response, "401 Unauthorized", {"error": "not signed in"})
    customer = user.get("stripe_customer_id")
    if not customer or not hasattr(provider, "portal_url"):
        return _json(start_response, "400 Bad Request",
                     {"error": "no active billing customer"})
    try:
        url = provider.portal_url(customer, f"{base_url.rstrip('/')}/account")
    except StripeError as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})
    return _json(start_response, "200 OK", {"url": url})


def _webhook(store, provider, environ, start_response):
    if not hasattr(provider, "construct_event"):
        return _json(start_response, "501 Not Implemented",
                     {"error": "webhooks require the Stripe provider"})
    payload = _read_json(environ)
    sig = environ.get("HTTP_STRIPE_SIGNATURE")
    try:
        event = provider.construct_event(payload, sig)
    except StripeError as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})
    obj = (event.get("data") or {}).get("object") or {}
    provider.handle_webhook(store, event.get("type", ""), obj)
    return _json(start_response, "200 OK", {"received": True})
