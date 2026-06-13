"""Personal writing goals — pick issue categories to improve and track the trend.

Goals are stored in the user's preferences blob (no new table). Trend data is
aggregated from the same analytics issue counts the lesson events feed, expressed
as **incidence per 1,000 words** so it's comparable across busy and quiet weeks.
Framing is progress-only — no streaks, no shame mechanics (the gateway copy).
"""

from __future__ import annotations

from . import analytics

# The categories a user can target — the realtime/lesson issue types, plus two
# higher-level habits the engine surfaces.
GOAL_CATEGORIES = (
    "spelling", "grammar", "punctuation", "style", "capitalization",
    "passive_voice", "filler_words",
)

_WEEK = 7 * 86400


def normalize(goals) -> list[str]:
    """Keep only known categories, de-duplicated, order preserved."""
    seen, out = set(), []
    for g in goals or []:
        g = str(g).strip().lower()
        if g in GOAL_CATEGORIES and g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _per_1k(issue_count: int, words: int) -> float:
    return round(issue_count / max(words, 1) * 1000, 2)


def trend(store, user_id: int, goals: list[str], weeks: int = 4,
          now: float | None = None) -> dict:
    """Per-goal incidence (per 1k words), oldest→newest over the last ``weeks``."""
    import time
    now = int(now or time.time())
    series: dict[str, list[float]] = {g: [] for g in goals}
    for w in range(weeks - 1, -1, -1):                 # oldest window first
        until = now - w * _WEEK
        s = analytics.summarize(store, user_id, until - _WEEK, until)
        for g in goals:
            series[g].append(_per_1k(s["by_issue_type"].get(g, 0), s["words"]))
    # improving = latest <= first (fewer issues per 1k words)
    improving = {g: (vals[-1] <= vals[0]) for g, vals in series.items() if vals}
    return {"weeks": weeks, "series": series, "improving": improving}
