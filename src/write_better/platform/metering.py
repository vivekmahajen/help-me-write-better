"""Server-side metering and cap enforcement (hard rule #3).

Every engine call is attributed to a user + plan; the engine's returned ``usage``
is recorded; premium-model generations are metered against the plan's monthly cap
from ``write_better.plans``. Routine/standard text work is uncapped (it's the
cheap path the margin model treats as effectively free). This same event log
feeds analytics later (#9).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from ..modes import Mode
from ..plans import PLANS_BY_NAME, cap_consumed_by
from .store import Store

# Plans that may exceed their cap and be billed for overage instead of blocked.
# Default: nobody — block at cap, exactly as the margin model assumes (Free hard
# caps the expensive paths). Wire overage billing per plan in a later phase.
ALLOW_OVERAGE: dict[str, bool] = {}


def period_start(now: float | None = None) -> int:
    """Epoch seconds for the start of the current UTC calendar month."""
    dt = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc)
    return int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp())


def consumes_premium(modes: list[Mode]) -> bool:
    """Whether a request of these modes draws down the premium-generation cap."""
    return cap_consumed_by(modes) == "premium_generations"


def quota(store: Store, user: dict, now: float | None = None) -> dict:
    """Current-period premium usage vs the plan's cap."""
    plan = PLANS_BY_NAME.get(user["plan"], PLANS_BY_NAME["free"])
    cap = plan.premium_generations
    used = store.count_premium_since(user["id"], period_start(now))
    return {
        "plan": user["plan"],
        "premium_cap": cap,
        "premium_used": used,
        "premium_remaining": max(cap - used, 0),
        "period_start": period_start(now),
    }


def check_allowed(store: Store, user: dict, modes: list[Mode],
                  now: float | None = None) -> tuple[bool, dict]:
    """Return ``(allowed, quota)``. Denied only when a premium request would
    exceed the cap and the plan doesn't allow overage."""
    q = quota(store, user, now)
    if not consumes_premium(modes):
        return True, q
    if q["premium_remaining"] > 0 or ALLOW_OVERAGE.get(user["plan"], False):
        return True, q
    return False, q


def record(store: Store, user: dict, services: list[Mode], model: str,
           input_tokens: int, output_tokens: int) -> dict:
    """Record a completed engine call for metering + analytics."""
    return store.insert_usage(
        user_id=user["id"],
        services=",".join(m.name for m in services),
        model=model,
        premium=consumes_premium(services),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
