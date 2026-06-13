"""The everyday-life templates: cover letter, complaint, condolence, resignation, …."""

import pytest

from write_better import templating as t

EXPECTED = {
    "cover-letter", "complaint", "condolence", "resignation",
    "apology", "thank-you", "recommendation",
    # Gap-4 depth additions:
    "reference-request", "performance-review", "self-review", "wedding-toast",
    "congratulations", "dispute-charge", "rental-application", "teacher-note",
    "dating-profile",
}

# Golden seed inputs (required fields only) for the snapshot sweep. Distinctive
# values so the assertions are meaningful.
FIXTURES = {
    "cover-letter": {"role": "Product Manager", "company": "Acme",
                     "background": "8 years shipping B2B SaaS"},
    "complaint": {"issue": "the laptop arrived cracked", "resolution": "a free replacement"},
    "condolence": {"recipient": "Sam"},
    "apology": {"what": "missing the deadline"},
    "thank-you": {"reason": "the thoughtful housewarming gift"},
    "recommendation": {"candidate": "Jordan Lee", "purpose": "a senior nurse role",
                       "strengths": "calm under pressure, mentors juniors"},
    "resignation": {"role": "Staff Engineer", "last_day": "June 30"},
    "reference-request": {"person": "Dr. Okafor", "purpose": "a grad school application"},
    "performance-review": {"name": "Priya", "strengths": "shipped the billing rewrite",
                           "growth": "delegate more on small tasks"},
    "self-review": {"role": "Designer", "accomplishments": "led the onboarding redesign"},
    "wedding-toast": {"couple": "Mara and Ines", "relationship": "best friend",
                      "stories": "the road trip where they got hopelessly lost"},
    "congratulations": {"occasion": "the new baby"},
    "dispute-charge": {"charge": "$49.99 on March 3 from CloudCo",
                       "reason": "I cancelled in February", "resolution": "a full refund"},
    "rental-application": {"property": "12 Birch Lane, Unit 4",
                           "about": "a nurse with steady income and no pets"},
    "teacher-note": {"purpose": "my daughter will miss Friday for a medical appointment"},
    "dating-profile": {"about": "a climber and amateur baker who codes for fun"},
}


def test_everyday_count_meets_depth_bar():
    everyday = t.list_templates("everyday")
    assert len(everyday) >= 15, f"expected 15+ everyday templates, got {len(everyday)}"


def test_everyday_templates_all_load():
    tpls = t.load_templates()
    assert EXPECTED <= set(tpls)
    for tid in EXPECTED:
        tp = tpls[tid]
        assert tp.category == "everyday"
        assert tp.name and tp.description and tp.prompt
        assert tp.defaults.get("service") == "write"     # generative


def test_every_everyday_template_has_a_fixture():
    # Keep the golden sweep honest: a new template must bring a seed input.
    assert EXPECTED <= set(FIXTURES)


def test_snapshot_each_template_renders_required_fields():
    for tid in EXPECTED:
        tp = t.get_template(tid)
        vals = FIXTURES[tid]
        out = t.validate_and_render(tp, vals)
        # every required field's value appears in the rendered prompt
        for f in tp.fields:
            if f.get("required"):
                assert str(vals[f["key"]]) in out, f"{tid}: missing required {f['key']}"
        # no unresolved {token} braces leak through for omitted optionals
        assert "{{" not in out and "}}" not in out, f"{tid}: unrendered conditional"


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
