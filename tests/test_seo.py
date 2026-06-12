"""SEO surface: truthful metadata, structured data, robots, sitemap."""

import json
import re

from write_better import seo
from write_better.plans import PLANS


def test_title_and_description_within_limits():
    assert len(seo.TITLE) <= 60
    assert len(seo.DESCRIPTION) <= 155


def test_head_has_canonical_og_twitter():
    h = seo.head("https://app.test")
    assert '<link rel="canonical" href="https://app.test/">' in h
    assert '<meta property="og:title"' in h
    assert '<meta property="og:image" content="https://app.test/og.svg">' in h
    assert '<meta name="twitter:card" content="summary_large_image">' in h
    assert "<title>" in h and '<meta name="description"' in h


def test_structured_data_is_truthful_software_application():
    h = seo.head("https://app.test")
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', h, re.S).group(1)
    data = json.loads(block)
    assert data["@type"] == "SoftwareApplication"
    assert data["name"] == "Help Me Write Better"
    # NO fabricated ratings — there are no real reviews.
    assert "aggregateRating" not in data
    # Offers come straight from plans.py (no invented pricing).
    prices = {o["name"]: o["price"] for o in data["offers"]}
    for p in PLANS:
        assert prices[p.name] == f"{p.monthly_price:.0f}"


def test_robots_txt_blocks_app_surfaces_and_lists_sitemap():
    txt = seo.robots_txt("https://app.test")
    assert "User-agent: *" in txt
    for path in ("/v1/", "/auth/", "/billing/", "/_status"):
        assert f"Disallow: {path}" in txt
    assert "Sitemap: https://app.test/sitemap.xml" in txt


def test_robots_omits_sitemap_without_base():
    assert "Sitemap:" not in seo.robots_txt("")


def test_sitemap_lists_public_pages():
    xml = seo.sitemap_xml("https://app.test")
    assert xml.startswith('<?xml')
    assert "<loc>https://app.test/</loc>" in xml
    assert "<loc>https://app.test/app</loc>" in xml


def test_base_url_strips_trailing_slash():
    assert seo.base_url({"WB_BASE_URL": "https://app.test/"}) == "https://app.test"
    assert seo.base_url({}) == ""
