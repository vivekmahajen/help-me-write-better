"""The FEATURES_LIVE honesty gate: gated sections render truthfully and a page
with all flags off makes zero 'available' claims and contains zero dead links."""

import re

from write_better import landing

ALL_OFF = {
    "platform": False, "trust_layer": False,
    "extension_store_url": None, "word_addin_url": None, "docs_addin_url": None,
    "desktop_url": None, "mobile_url": None,
}


def _hrefs(html):
    return re.findall(r'href="([^"]*)"', html)


def test_single_h1_and_real_proof():
    html = landing.render(ALL_OFF)
    assert html.count("<h1>") == 1
    assert "188 automated tests" in html
    assert "45 composable services" in html


def test_all_flags_off_makes_no_available_claims():
    html = landing.render(ALL_OFF)
    # Nothing is advertised as live; every gated surface says "coming soon".
    assert "Available" not in html
    assert "Coming soon" in html
    # The trust + work sections degrade to "coming soon", not live links.
    assert "Open the tools" not in html
    assert "Open your workspace" not in html


def test_all_flags_off_has_no_dead_links():
    html = landing.render(ALL_OFF)
    for href in _hrefs(html):
        # Only internal routes / anchors are allowed when nothing external is live.
        assert href.startswith(("/", "#")), f"unexpected/dead link: {href!r}"
        assert "None" not in href


def test_platform_flag_lights_up_work_card():
    html = landing.render({**ALL_OFF, "platform": True})
    assert "Open your workspace" in html


def test_trust_flag_lights_up_trust_section():
    html = landing.render({**ALL_OFF, "trust_layer": True})
    assert "Open the tools" in html
    # Honesty rule preserved: band, never a verdict.
    assert "confidence band" in html and "never a binary verdict" in html


def test_surface_url_renders_real_link_and_available_tag():
    url = "https://chrome.example/extension"
    html = landing.render({**ALL_OFF, "extension_store_url": url})
    assert url in html
    assert "Available" in html


def test_service_chips_deep_link_into_editor():
    html = landing.render(ALL_OFF)
    for svc in ("correct", "tighten", "translate"):
        assert f'href="/app?service={svc}"' in html


def test_demo_prefill_matches_demo_input():
    # The hero textarea ships the same flawed text the fallback corrects.
    from write_better.demo import DEMO_INPUT
    html = landing.render(ALL_OFF)
    assert DEMO_INPUT.split(",")[0] in html
