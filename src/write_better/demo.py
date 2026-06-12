"""The hero demo backend: a rate-limited, fallback-safe one-shot improve.

The landing page hero runs a *real* call against the engine — services
``correct`` + ``tighten`` with a change summary on — so visitors see the actual
product, not a mock. To keep the public, unauthenticated page cheap and
abuse-resistant, calls are capped per client IP in a fixed window. Over the cap
(or when the server has no API key, or the engine errors) the response is a
**canned sample**, clearly flagged so the UI can label it "sample result" and
never pass it off as a live model call.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .engine import Request

# Pre-filled flawed text for the hero, and the services it runs. Kept here so
# the page, the real call, and the canned fallback all share one source.
DEMO_INPUT = (
    "Their going too the store on tuesday, but they forgot they're wallet and "
    "the shop dont open untill nine oclock."
)
DEMO_SERVICES = ("correct", "tighten")

# A human-written example of correct+tighten on DEMO_INPUT. Shown only as a
# labelled sample when a live call isn't available — never presented as live.
FALLBACK_OUTPUT = (
    "They're going to the store on Tuesday, but they forgot their wallet, and "
    "the shop doesn't open until nine o'clock."
)


class RateLimiter:
    """Fixed-window per-IP cap. In-memory (per process); good enough to blunt
    casual abuse of the public demo without any external dependency."""

    def __init__(self, limit: int = 5, window: float = 3600.0, clock=time.time):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    def allow(self, ip: str) -> bool:
        now = self._clock()
        cutoff = now - self.window
        hits = [t for t in self._hits.get(ip, ()) if t > cutoff]
        if len(hits) >= self.limit:
            self._hits[ip] = hits
            return False
        hits.append(now)
        self._hits[ip] = hits
        return True


@dataclass
class DemoResult:
    text: str
    input: str
    model: str
    services: list[str]
    fallback: bool
    reason: str | None = None

    def payload(self) -> dict:
        return asdict(self)


def _fallback(reason: str) -> DemoResult:
    return DemoResult(
        text=FALLBACK_OUTPUT,
        input=DEMO_INPUT,
        model="sample",
        services=list(DEMO_SERVICES),
        fallback=True,
        reason=reason,
    )


def run_demo(text: str, ip: str, *, limiter: RateLimiter, improve_fn, key_present: bool) -> DemoResult:
    """Run the hero demo. Returns a real result when possible, else a labelled
    canned sample. ``improve_fn``/``key_present`` are injected so the whole path
    is testable offline."""
    text = (text or "").strip()
    if not text:
        return _fallback("empty")
    if not key_present:
        return _fallback("no_key")
    if not limiter.allow(ip):
        return _fallback("rate_limited")
    try:
        result = improve_fn(Request(
            text=text,
            services=list(DEMO_SERVICES),
            output_format="plain",
            show_changes=True,
            effort="low",
        ))
    except Exception:
        return _fallback("error")
    return DemoResult(
        text=result.text,
        input=text,
        model=result.model,
        services=[m.name for m in result.services],
        fallback=False,
    )
