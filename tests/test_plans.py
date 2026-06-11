"""Verify the pricing model reproduces the spreadsheet figures."""

import pytest

from write_better import plans
from write_better.modes import resolve_services


# (plan name, typical cost, typical margin %, max-use floor margin %) from the model.
EXPECTED = [
    ("Free", 0.23, None, None),
    ("Starter", 3.36, 79.0, 50.6),
    ("Pro", 9.40, 75.9, 38.6),
    ("Business", 22.40, 77.4, 42.7),
]


@pytest.mark.parametrize("name, cost_typ, margin_typ, margin_floor", EXPECTED)
def test_cost_and_margins_match_spreadsheet(name, cost_typ, margin_typ, margin_floor):
    plan = plans.PLANS_BY_NAME[name.lower()]

    assert round(plans.cost_to_serve(plan), 2) == cost_typ

    if margin_typ is None:
        assert plans.gross_margin(plan) is None
    else:
        assert round(plans.gross_margin(plan) * 100, 1) == margin_typ
        assert round(plans.gross_margin(plan, utilization=1.0) * 100, 1) == margin_floor


def test_max_use_starter_cost():
    starter = plans.PLANS_BY_NAME["starter"]
    assert round(plans.cost_to_serve(starter, utilization=1.0), 2) == 7.90


def test_free_tier_test_reproduces_model():
    t = plans.free_tier_test()
    assert round(t.total_free_cost) == 2340
    assert t.conversions == 300
    assert round(t.conversion_revenue) == 4800
    assert round(t.net) == 2460
    assert round(t.break_even_rate * 100, 1) == 1.5


def test_annual_totals():
    starter = plans.PLANS_BY_NAME["starter"]
    assert starter.annual_total == 156.0
    assert plans.PLANS_BY_NAME["free"].annual_total is None


def test_premium_request_consumes_premium_cap():
    # write / paraphrase route premium -> draws down the premium-generation cap
    assert plans.cap_consumed_by(resolve_services("write")) == "premium_generations"
    assert plans.cap_consumed_by(resolve_services("correct,paraphrase")) == "premium_generations"


def test_routine_and_standard_requests_consume_no_metered_cap():
    assert plans.cap_consumed_by(resolve_services("correct")) is None
    assert plans.cap_consumed_by(resolve_services("translate,structure")) is None


def test_editing_unit_cost_changes_margin():
    cheap_images = plans.UnitCosts(ai_image=0.005)
    pro = plans.PLANS_BY_NAME["pro"]
    base = plans.gross_margin(pro)
    improved = plans.gross_margin(pro, unit=cheap_images)
    assert improved > base  # cheaper image model lifts margin, per the model's notes
