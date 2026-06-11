"""Billing behind an interface (#7).

Two implementations:

* ``LocalBillingProvider`` — no external dependency. Plan changes are applied
  directly in the store. This is what runs in local dev and tests, so the spec's
  "local dev works without Stripe keys" holds.
* ``StripeBillingProvider`` — the real integration, intentionally **stubbed**, not
  fabricated. Each method documents the Stripe call it must make and raises until
  wired with real keys. Mapping plans.py tiers -> Stripe products/prices,
  Checkout, the customer portal, and webhook handling (invoice.paid /
  payment_failed) land in the billing phase.

The gateway depends only on the ``BillingProvider`` interface, so swapping local
for Stripe is a one-line change.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from abc import ABC, abstractmethod

from ..plans import PLANS_BY_NAME
from .oauth import Transport, urllib_transport
from .store import Store


def _validate_plan(plan: str) -> str:
    plan = plan.lower()
    if plan not in PLANS_BY_NAME:
        raise ValueError(f"unknown plan {plan!r}; valid: {', '.join(PLANS_BY_NAME)}")
    return plan


class BillingProvider(ABC):
    """Maps platform plans to a payment backend and applies plan changes."""

    @abstractmethod
    def change_plan(self, store: Store, user_id: int, plan: str) -> None:
        """Move a user to ``plan`` (cap raises/lowers take effect immediately)."""

    @abstractmethod
    def checkout_url(self, user: dict, plan: str) -> str:
        """A URL where the user completes payment for ``plan``."""

    @abstractmethod
    def handle_webhook(self, store: Store, event_type: str, payload: dict) -> None:
        """Process a provider webhook (e.g. invoice.paid, payment_failed)."""


class LocalBillingProvider(BillingProvider):
    """No-payment provider for local dev/tests; plan changes hit the store."""

    def change_plan(self, store: Store, user_id: int, plan: str) -> None:
        store.set_plan(user_id, _validate_plan(plan))

    def checkout_url(self, user: dict, plan: str) -> str:
        _validate_plan(plan)
        # No real checkout locally — caller applies change_plan directly.
        return f"local://checkout?user={user['id']}&plan={plan}"

    def handle_webhook(self, store: Store, event_type: str, payload: dict) -> None:
        # No external webhooks in local mode.
        return None


class StripeError(Exception):
    """Stripe webhook/signature or API error."""


class StripeBillingProvider(BillingProvider):
    """Real Stripe integration over the REST API (stdlib HTTP, no SDK dependency).

    Maps `plans.py` tiers to Stripe Price IDs. Provides Checkout + customer portal
    session creation and webhook signature verification + handling. The HTTP call
    is behind an injectable ``transport`` so the flow is testable offline.

    Source of truth for a user's plan is Stripe webhooks: checkout completion and
    subscription create/update set the plan; subscription deletion and a failed
    payment downgrade to Free (paid features restricted; Free still works).
    """

    API_BASE = "https://api.stripe.com/v1"

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None,
                 price_ids: dict[str, str] | None = None,
                 success_url: str = "https://app/billing/success",
                 cancel_url: str = "https://app/billing/cancel",
                 transport: Transport = urllib_transport):
        if not api_key:
            raise RuntimeError(
                "StripeBillingProvider requires a Stripe API key. "
                "Use LocalBillingProvider for local dev, or supply STRIPE_API_KEY."
            )
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.price_ids = {k.lower(): v for k, v in (price_ids or {}).items()}
        self.price_to_plan = {v: k for k, v in self.price_ids.items()}
        self.success_url = success_url
        self.cancel_url = cancel_url
        self._http = transport

    # --- HTTP ----------------------------------------------------------------

    def _post(self, path: str, params: dict) -> dict:
        body = urllib.parse.urlencode(params, doseq=True).encode()
        return self._http("POST", f"{self.API_BASE}{path}",
                          {"Authorization": f"Bearer {self.api_key}",
                           "Content-Type": "application/x-www-form-urlencoded"}, body)

    def _price_for(self, plan: str) -> str:
        plan = _validate_plan(plan)
        price = self.price_ids.get(plan)
        if not price:
            raise StripeError(f"no Stripe price configured for plan {plan!r}")
        return price

    # --- BillingProvider interface ------------------------------------------

    def change_plan(self, store: Store, user_id: int, plan: str) -> None:
        # Plan changes are applied from verified webhooks; this records the change.
        store.set_plan(user_id, _validate_plan(plan))

    def checkout_url(self, user: dict, plan: str) -> str:
        price = self._price_for(plan)
        session = self._post("/checkout/sessions", {
            "mode": "subscription",
            "line_items[0][price]": price,
            "line_items[0][quantity]": 1,
            "success_url": self.success_url,
            "cancel_url": self.cancel_url,
            "customer_email": user["email"],
            "client_reference_id": user["id"],
            "metadata[user_id]": user["id"],
            "metadata[plan]": _validate_plan(plan),
        })
        url = session.get("url")
        if not url:
            raise StripeError("Stripe did not return a Checkout URL")
        return url

    def portal_url(self, customer_id: str, return_url: str) -> str:
        session = self._post("/billing_portal/sessions",
                             {"customer": customer_id, "return_url": return_url})
        url = session.get("url")
        if not url:
            raise StripeError("Stripe did not return a portal URL")
        return url

    # --- webhooks ------------------------------------------------------------

    def construct_event(self, payload: bytes, sig_header: str | None,
                        tolerance: int | None = 300) -> dict:
        """Verify the Stripe-Signature header and return the parsed event."""
        if not self.webhook_secret:
            raise StripeError("no webhook secret configured")
        if not sig_header:
            raise StripeError("missing Stripe-Signature header")
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        timestamp = parts.get("t")
        signatures = [v for k, v in (p.split("=", 1) for p in sig_header.split(",")
                                     if "=" in p) if k == "v1"]
        if not timestamp or not signatures:
            raise StripeError("malformed Stripe-Signature header")
        if tolerance is not None and abs(int(time.time()) - int(timestamp)) > tolerance:
            raise StripeError("webhook timestamp outside tolerance")
        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            raise StripeError("signature verification failed")
        return json.loads(payload.decode("utf-8"))

    def handle_webhook(self, store: Store, event_type: str, obj: dict) -> None:
        if event_type == "checkout.session.completed":
            user_id = (obj.get("metadata") or {}).get("user_id")
            plan = (obj.get("metadata") or {}).get("plan")
            customer = obj.get("customer")
            if user_id and customer:
                store.set_stripe_customer(int(user_id), customer)
            if user_id and plan:
                self.change_plan(store, int(user_id), plan)

        elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
            user = store.get_user_by_stripe_customer(obj.get("customer", ""))
            if user:
                plan = self._plan_from_subscription(obj)
                if plan:
                    self.change_plan(store, user["id"], plan)

        elif event_type in ("customer.subscription.deleted", "invoice.payment_failed"):
            user = store.get_user_by_stripe_customer(obj.get("customer", ""))
            if user:
                self.change_plan(store, user["id"], "free")  # restrict paid features

    def _plan_from_subscription(self, obj: dict) -> str | None:
        try:
            price_id = obj["items"]["data"][0]["price"]["id"]
        except (KeyError, IndexError, TypeError):
            return None
        return self.price_to_plan.get(price_id)
