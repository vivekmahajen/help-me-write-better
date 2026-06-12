"""The everyday-life templates: cover letter, complaint, condolence, resignation, …."""

import pytest

from write_better import templating as t

EXPECTED = {
    "cover-letter", "complaint", "condolence", "resignation",
    "apology", "thank-you", "recommendation",
}


def test_everyday_templates_all_load():
    tpls = t.load_templates()
    assert EXPECTED <= set(tpls)
    for tid in EXPECTED:
        tp = tpls[tid]
        assert tp.category == "everyday"
        assert tp.name and tp.description and tp.prompt
        assert tp.defaults.get("service") == "write"     # generative


def test_everyday_category_filter():
    listed = t.list_templates("everyday")
    ids = {s["id"] for s in listed}
    assert EXPECTED <= ids
    assert all(s["category"] == "everyday" for s in listed)


def test_required_fields_enforced():
    cover = t.get_template("cover-letter")
    with pytest.raises(t.MissingFields) as exc:
        t.validate_and_render(cover, {"role": "PM"})       # missing company + background
    assert "company" in exc.value.missing
    assert "background" in exc.value.missing


def test_render_substitutes_and_defaults_tone():
    out = t.validate_and_render(t.get_template("cover-letter"), {
        "role": "Product Manager", "company": "Acme",
        "background": "8 years shipping B2B SaaS",
    })
    assert "Product Manager" in out and "Acme" in out
    assert "8 years shipping B2B SaaS" in out
    assert "warm but professional" in out                  # default tone applied
    assert "{why}" not in out                              # unfilled optional section dropped


def test_optional_conditional_section_included_when_provided():
    out = t.validate_and_render(t.get_template("condolence"), {
        "recipient": "Sam", "memory": "her contagious laugh",
    })
    assert "Sam" in out
    assert "her contagious laugh" in out                   # {{#memory}} section kept
    assert "{deceased}" not in out                         # unfilled section dropped
