"""SEO surface: head metadata, structured data, robots, sitemap, and an OG image.

All derived from real facts — pricing comes from ``plans.py`` and there is no
fabricated ``aggregateRating`` (no reviews exist, so none is claimed). Absolute
URLs use ``WB_BASE_URL`` (the deployment's public origin).
"""

from __future__ import annotations

import json
import os

from .plans import PLANS

SITE_NAME = "Help Me Write Better"
# Title ≤ 60 chars, description ≤ 155 — checked by tests.
TITLE = "Help Me Write Better — clear writing, with an API"
DESCRIPTION = (
    "Improve and format text with Claude while keeping your meaning and voice — "
    "a live editor, an open JSON API, and composable services."
)


def base_url(env=None) -> str:
    """The deployment's public origin (no trailing slash), or '' if unset."""
    env = os.environ if env is None else env
    return (env.get("WB_BASE_URL") or "").strip().rstrip("/")


def _abs(base: str, path: str) -> str:
    return f"{base}{path}" if base else path


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _structured_data(base: str) -> str:
    offers = [
        {"@type": "Offer", "name": p.name, "price": f"{p.monthly_price:.0f}",
         "priceCurrency": "USD"}
        for p in PLANS
    ]
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": SITE_NAME,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "description": DESCRIPTION,
        "url": _abs(base, "/") or "/",
        "offers": offers,
        # No aggregateRating: there are no real reviews to cite.
    }
    return json.dumps(data, separators=(",", ":"))


def head(base: str | None = None) -> str:
    """The full SEO ``<head>`` block for the landing page (title → JSON-LD)."""
    base = base_url() if base is None else base
    canonical = _abs(base, "/") or "/"
    og_image = _abs(base, "/og.svg") or "/og.svg"
    t, d = _esc(TITLE), _esc(DESCRIPTION)
    return f"""<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{_esc(SITE_NAME)}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{_esc(SITE_NAME)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{og_image}">
<script type="application/ld+json">{_structured_data(base)}</script>"""


def robots_txt(base: str | None = None) -> str:
    base = base_url() if base is None else base
    lines = [
        "User-agent: *",
        "Allow: /$",
        "Allow: /app",
        # App/API surfaces aren't indexable content:
        "Disallow: /v1/",
        "Disallow: /auth/",
        "Disallow: /billing/",
        "Disallow: /_status",
    ]
    if base:
        lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines) + "\n"


# Public, indexable pages (the editor is a real entry point).
_SITEMAP_PATHS = ("/", "/app")


def sitemap_xml(base: str | None = None) -> str:
    base = base_url() if base is None else base
    urls = "".join(
        f"<url><loc>{_esc(_abs(base, p) or p)}</loc></url>" for p in _SITEMAP_PATHS
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{urls}</urlset>")


# A self-contained 1200×630 OpenGraph card (brand colours, no external assets).
OG_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0E2A47"/>
  <rect x="0" y="0" width="1200" height="12" fill="#1FA37A"/>
  <text x="80" y="250" fill="#FFFFFF" font-family="Georgia, 'Times New Roman', serif"
        font-size="76" font-weight="700">Help Me Write Better</text>
  <text x="80" y="330" fill="#9DC7C6" font-family="system-ui, Arial, sans-serif"
        font-size="38">Clear writing, with an API behind it</text>
  <text x="80" y="540" fill="#1FA37A" font-family="ui-monospace, Menlo, monospace"
        font-size="28">POST /  ·  open JSON API  ·  model routing</text>
</svg>
"""
