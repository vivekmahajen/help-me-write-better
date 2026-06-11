"""Composed WSGI app: the platform gateway under /v1, the demo engine app elsewhere.

This is the "one backend hub" assembled for deployment — ``/v1/*`` routes to the
authenticated, metered gateway; everything else serves the existing demo UI/API
(``write_better.web``). It is NOT yet the Vercel default entrypoint (the gateway
needs a persistent database; serverless filesystems are ephemeral). Point a
deployment with a real DB (set WB_DB_PATH / a managed Postgres adapter) at
``write_better.platform.wsgi:app`` when ready.
"""

from __future__ import annotations

import os

from ..web import app as engine_app
from .billing import LocalBillingProvider, StripeBillingProvider
from .billing_web import make_billing
from .gateway import make_gateway
from .oauth import providers_from_env
from .store import Store
from .webauth import make_webauth

_BASE_URL = os.environ.get("WB_BASE_URL", "http://localhost")
_store = Store(os.environ.get("WB_DB_PATH", "wb.db"))
_gateway = make_gateway(_store)
_webauth = make_webauth(_store, oauth_providers=providers_from_env(), base_url=_BASE_URL)


def _billing_provider():
    """Stripe when configured, else the keyless local provider."""
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return LocalBillingProvider()
    price_ids = {p: os.environ.get(f"STRIPE_PRICE_{p.upper()}")
                 for p in ("starter", "pro", "business")}
    return StripeBillingProvider(
        api_key=api_key,
        webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        price_ids={k: v for k, v in price_ids.items() if v},
    )


_billing = make_billing(_store, _billing_provider(), base_url=_BASE_URL)


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/v1" or path.startswith("/v1/"):
        return _gateway(environ, start_response)
    if path == "/auth" or path.startswith("/auth/"):
        return _webauth(environ, start_response)
    if path == "/billing" or path.startswith("/billing/"):
        return _billing(environ, start_response)
    return engine_app(environ, start_response)
