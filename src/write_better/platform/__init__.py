"""Platform layer for help-me-write-better.

Wraps the stateless engine with identity, storage, metering, and billing — the
"one backend hub" every product surface calls. The engine itself is untouched;
this package only adds a platform around it.

Slice 1 (this module set): SQLite storage, accounts + API keys, server-side
metering & cap enforcement (tied to ``write_better.plans``), a versioned ``/v1``
gateway that wraps the engine, and billing behind an interface (local provider +
stubbed Stripe). Deferred to later phases: OAuth/SSO, real Stripe wiring, the
real-time check path, teams, analytics dashboards, and all client surfaces.
"""

from .store import Store
from .accounts import (
    create_user,
    verify_login,
    create_api_key,
    authenticate_key,
)
from .metering import quota, check_allowed, record
from .billing import BillingProvider, LocalBillingProvider, StripeBillingProvider
from .gateway import make_gateway

__all__ = [
    "Store",
    "create_user",
    "verify_login",
    "create_api_key",
    "authenticate_key",
    "quota",
    "check_allowed",
    "record",
    "BillingProvider",
    "LocalBillingProvider",
    "StripeBillingProvider",
    "make_gateway",
]
