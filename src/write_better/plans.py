"""Pricing & margin model for the All-in-One AI Content Suite.

This is the code form of the pricing spreadsheet: edit the unit costs / caps /
prices here and every margin recalculates. It also links the suite's plan caps
to the engine's model-routing tiers (see :func:`cap_consumed_by`) — a request
routed to the premium model is what counts against a plan's premium-generation
cap; routine/standard text work is treated as effectively free and unlimited.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modes import Mode

# Typical share of caps a real user actually consumes (spreadsheet B16).
DEFAULT_UTILIZATION = 0.35


@dataclass(frozen=True)
class UnitCosts:
    """What each action costs YOU (the blue unit-cost cells, mid-2026 estimates)."""

    premium_generation: float = 0.030   # per generation
    ai_image: float = 0.030             # per image
    voice_minute: float = 0.015         # per minute
    transcription_minute: float = 0.006  # per minute
    plagiarism_check: float = 0.015     # per check
    infra_per_seat: float = 0.150       # per user / month
    stripe_pct: float = 0.029           # variable fee, % of price
    stripe_fixed: float = 0.300         # fixed fee, per transaction


@dataclass(frozen=True)
class Plan:
    """A pricing tier: price, seats, and the monthly metered caps."""

    name: str
    monthly_price: float
    annual_monthly: float | None  # billed-yearly equivalent ($/mo); None for Free
    seats: int
    premium_generations: int
    ai_images: int
    voice_minutes: int
    transcription_minutes: int
    plagiarism_checks: int

    @property
    def annual_total(self) -> float | None:
        """Total charged once per year on the annual plan."""
        return None if self.annual_monthly is None else round(self.annual_monthly * 12, 2)


# Tier definitions & caps (the blue tier cells).
PLANS: tuple[Plan, ...] = (
    Plan("Free", 0, None, 1, premium_generations=0, ai_images=5,
         voice_minutes=0, transcription_minutes=10, plagiarism_checks=2),
    Plan("Starter", 16, 13, 1, premium_generations=100, ai_images=80,
         voice_minutes=30, transcription_minutes=90, plagiarism_checks=40),
    Plan("Pro", 39, 32, 1, premium_generations=300, ai_images=250,
         voice_minutes=120, transcription_minutes=300, plagiarism_checks=150),
    Plan("Business", 99, 82, 5, premium_generations=700, ai_images=600,
         voice_minutes=300, transcription_minutes=800, plagiarism_checks=300),
)

PLANS_BY_NAME = {p.name.lower(): p for p in PLANS}


# ---- Cost-to-serve components -------------------------------------------------

def metered_cost(plan: Plan, unit: UnitCosts, utilization: float) -> float:
    """Usage-based cost: caps x utilization x unit cost."""
    per_month_at_full_caps = (
        plan.premium_generations * unit.premium_generation
        + plan.ai_images * unit.ai_image
        + plan.voice_minutes * unit.voice_minute
        + plan.transcription_minutes * unit.transcription_minute
        + plan.plagiarism_checks * unit.plagiarism_check
    )
    return per_month_at_full_caps * utilization


def infra_cost(plan: Plan, unit: UnitCosts) -> float:
    """Infrastructure / storage, scales with seats."""
    return plan.seats * unit.infra_per_seat


def payment_cost(plan: Plan, unit: UnitCosts) -> float:
    """Stripe fee on the monthly charge. Free plans never transact."""
    if plan.monthly_price <= 0:
        return 0.0
    return plan.monthly_price * unit.stripe_pct + unit.stripe_fixed


def cost_to_serve(plan: Plan, unit: UnitCosts | None = None,
                  utilization: float = DEFAULT_UTILIZATION) -> float:
    """Total monthly cost to serve one user on ``plan`` at ``utilization``."""
    unit = unit or UnitCosts()
    return metered_cost(plan, unit, utilization) + infra_cost(plan, unit) + payment_cost(plan, unit)


def gross_margin(plan: Plan, unit: UnitCosts | None = None,
                 utilization: float = DEFAULT_UTILIZATION) -> float | None:
    """Gross margin as a fraction (0-1). None for Free (no price)."""
    if plan.monthly_price <= 0:
        return None
    cost = cost_to_serve(plan, unit, utilization)
    return (plan.monthly_price - cost) / plan.monthly_price


# ---- Free-tier sustainability -------------------------------------------------

@dataclass(frozen=True)
class FreeTierTest:
    free_cost_per_user: float
    total_free_cost: float
    conversions: int
    conversion_revenue: float
    net: float
    break_even_rate: float


def free_tier_test(*, free_users: int = 10_000, conversion_rate: float = 0.03,
                   upgrade_to: str = "Starter", unit: UnitCosts | None = None,
                   utilization: float = DEFAULT_UTILIZATION) -> FreeTierTest:
    """Does paid conversion cover the cost of carrying free users?"""
    unit = unit or UnitCosts()
    free = PLANS_BY_NAME["free"]
    target = PLANS_BY_NAME[upgrade_to.lower()]
    per_user = cost_to_serve(free, unit, utilization)
    total = per_user * free_users
    conversions = round(free_users * conversion_rate)
    revenue = conversions * target.monthly_price
    break_even = total / (free_users * target.monthly_price)
    return FreeTierTest(
        free_cost_per_user=per_user,
        total_free_cost=total,
        conversions=conversions,
        conversion_revenue=revenue,
        net=revenue - total,
        break_even_rate=break_even,
    )


# ---- Link to engine routing ---------------------------------------------------

#: Which plan cap each routing tier draws down. Routine/standard text work is
#: effectively free + unlimited (folded into infrastructure), so only the
#: premium tier consumes a metered cap.
TIER_TO_CAP = {
    "premium": "premium_generations",
    "standard": None,
    "routine": None,
}


def cap_consumed_by(modes: list[Mode]) -> str | None:
    """Return the plan cap a request of these modes draws down, or None.

    A premium-routed request (Opus tier) counts as one premium generation; pure
    routine/standard text editing does not consume a metered cap.
    """
    if any(m.tier == "premium" for m in modes):
        return TIER_TO_CAP["premium"]
    return None


# ---- Pretty print -------------------------------------------------------------

def margin_table(unit: UnitCosts | None = None,
                 utilization: float = DEFAULT_UTILIZATION) -> str:
    """Render the recommended pricing + margins as a plain-text table."""
    unit = unit or UnitCosts()
    rows = ["Plan       Monthly  Annual/mo  Seats  Cost(typ)  Margin(typ)  Margin(floor)"]
    for p in PLANS:
        cost = cost_to_serve(p, unit, utilization)
        m_typ = gross_margin(p, unit, utilization)
        m_floor = gross_margin(p, unit, 1.0)
        price = f"${p.monthly_price:.0f}" if p.monthly_price else "$0"
        annual = f"${p.annual_monthly:.0f}" if p.annual_monthly else "—"
        m_typ_s = f"{m_typ * 100:.1f}%" if m_typ is not None else "n/a"
        m_floor_s = f"{m_floor * 100:.1f}%" if m_floor is not None else "n/a"
        rows.append(
            f"{p.name:<10} {price:>6}  {annual:>8}  {p.seats:>5}  "
            f"${cost:>7.2f}  {m_typ_s:>10}  {m_floor_s:>12}"
        )
    return "\n".join(rows)


if __name__ == "__main__":  # pragma: no cover
    print(margin_table())
