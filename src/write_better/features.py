"""The honesty gate: which surfaces are actually live at *this* deployment.

The landing page must be truthful before and after the platform cutover. A
surface is only advertised as available when its flag/URL is set here (via
environment), otherwise the page renders it as "coming soon" with no dead link.
Flipping a flag lights the section up with **zero copy rewrites**.

Nothing in this module claims a feature is live on its own — it only reflects
configuration. Defaults are all *off*: a fresh deploy advertises only what is
genuinely reachable at its URL (the editor and the JSON API), nothing more.
"""

from __future__ import annotations

import os


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _url(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None


# The live-state of every gated surface. Booleans gate whole sections; URL
# values both gate *and* supply the link. All default off/None.
FEATURES_LIVE: dict[str, object] = {
    # Accounts, API keys, metering, billing gateway reachable at this URL?
    "platform": _flag("WB_FEATURE_PLATFORM"),
    # Trust Layer (plagiarism / AI detection / citations) live behind the gateway?
    "trust_layer": _flag("WB_FEATURE_TRUST"),
    # Distribution surfaces — a URL means "shipped, link to it"; None means "coming soon".
    "extension_store_url": _url("WB_URL_EXTENSION"),
    "word_addin_url": _url("WB_URL_WORD"),
    "docs_addin_url": _url("WB_URL_DOCS"),
    "desktop_url": _url("WB_URL_DESKTOP"),
    "mobile_url": _url("WB_URL_MOBILE"),
}

# The "everywhere you write" strip. Each entry's `key` points at a URL flag above.
SURFACES: tuple[dict[str, str], ...] = (
    {"key": "extension_store_url", "name": "Browser extension",
     "blurb": "Fix text in any tab."},
    {"key": "word_addin_url", "name": "Microsoft Word",
     "blurb": "An add-in inside your document."},
    {"key": "docs_addin_url", "name": "Google Docs",
     "blurb": "A sidebar where you draft."},
    {"key": "desktop_url", "name": "Desktop app",
     "blurb": "A focused window on your machine."},
    {"key": "mobile_url", "name": "Mobile app",
     "blurb": "Polish on the go."},
)


def surface_states(flags: dict | None = None) -> list[dict]:
    """Each surface annotated with whether it's live and where it links."""
    f = FEATURES_LIVE if flags is None else flags
    out = []
    for s in SURFACES:
        url = f.get(s["key"])
        out.append({**s, "live": bool(url), "url": url or None})
    return out
