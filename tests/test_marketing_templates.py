"""The marketing template library (Gap-4 depth → 25+), pure YAML."""

from write_better import templating as t

NEW = {
    "cold-email-followup", "case-study", "press-release", "google-rsa",
    "facebook-ad", "x-thread", "youtube-metadata", "launch-announcement",
    "webinar-invite", "app-store-listing", "job-posting", "objection-faq",
    "newsletter-intro", "pricing-copy", "testimonial-polish", "value-prop",
}


def test_marketing_count_meets_depth_bar():
    mk = t.list_templates("marketing")
    assert len(mk) >= 25, f"expected 25+ marketing templates, got {len(mk)}"
    assert NEW <= {s["id"] for s in mk}


def test_all_marketing_render_cleanly():
    # Generic sweep: fill required fields with unique tokens, omit optionals,
    # and assert substitution + fully-resolved conditionals for every template.
    for s in t.list_templates("marketing"):
        tp = t.get_template(s["id"])
        assert tp.defaults.get("service") == "write"
        vals = {f["key"]: f"VAL_{f['key']}" for f in tp.fields if f.get("required")}
        out = t.validate_and_render(tp, vals)
        for key, token in vals.items():
            assert token in out, f"{s['id']}: required field {key} not substituted"
        assert "{{" not in out and "}}" not in out, f"{s['id']}: unrendered conditional"


def test_char_limited_assets_declare_their_limits():
    # The RSA / app-store assets must state their platform character limits in the
    # prompt (they pair with the strict_limit guarantee for single-string outputs).
    rsa = t.get_template("google-rsa").prompt
    assert "30 characters" in rsa and "90 characters" in rsa
    appstore = t.get_template("app-store-listing").prompt
    assert "30 characters" in appstore
