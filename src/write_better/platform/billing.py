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

from abc import ABC, abstractmethod

from ..plans import PLANS_BY_NAME
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


class StripeBillingProvider(BillingProvider):
    """Real Stripe integration — STUBBED until wired with credentials.

    Required when implemented (billing phase):
      * map PLANS_BY_NAME -> Stripe Product/Price IDs
      * change_plan: create/update the Subscription (or send to Checkout)
      * checkout_url: stripe.checkout.Session.create(...).url
      * handle_webhook: verify signature; on invoice.paid refill allowances /
        confirm plan; on payment_failed start dunning + restrict paid features
        (Free still works).
    """

    def __init__(self, api_key: str | None = None, price_ids: dict[str, str] | None = None):
        if not api_key:
            raise RuntimeError(
                "StripeBillingProvider requires a Stripe API key. "
                "Use LocalBillingProvider for local dev, or supply STRIPE_API_KEY."
            )
        self.api_key = api_key
        self.price_ids = price_ids or {}

    def change_plan(self, store: Store, user_id: int, plan: str) -> None:  # pragma: no cover
        raise NotImplementedError("Stripe subscription update not yet wired")

    def checkout_url(self, user: dict, plan: str) -> str:  # pragma: no cover
        raise NotImplementedError("Stripe Checkout session not yet wired")

    def handle_webhook(self, store: Store, event_type: str, payload: dict) -> None:  # pragma: no cover
        raise NotImplementedError("Stripe webhook handling not yet wired")
