"""Writing analytics over time (#9).

Aggregates the ``usage_events`` log (the same events metering writes) into
user-facing insights — **aggregate metrics only, never document bodies**:
words written, services used, issues found by type, activity by day, an estimated
time-saved figure, and week-over-week trends. ``rollup`` produces the team view
(adoption + top issues) over a set of users; it plugs into Teams (#8) once orgs
exist.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone

from .store import Store

SECONDS_PER_ISSUE = 20  # rough manual find-and-fix time, for the time-saved estimate
_WEEK = 7 * 86400


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def summarize(store: Store, user_id: int, since_ts: int,
              until_ts: int | None = None) -> dict:
    events = store.events_between(user_id, since_ts, until_ts)
    by_service: Counter = Counter()
    by_issue: Counter = Counter()
    by_day: dict[str, dict] = {}
    total_words = total_suggestions = 0

    for e in events:
        total_words += e["words"]
        total_suggestions += e["suggestions"]
        for svc in (e["services"] or "").split(","):
            svc = svc.strip()
            if svc:
                by_service[svc] += 1
        try:
            for k, v in json.loads(e["issue_types"] or "{}").items():
                by_issue[k] += v
        except (ValueError, TypeError):
            pass
        slot = by_day.setdefault(_day(e["ts"]), {"calls": 0, "words": 0})
        slot["calls"] += 1
        slot["words"] += e["words"]

    return {
        "window": {"since": since_ts, "until": until_ts},
        "calls": len(events),
        "words": total_words,
        "suggestions": total_suggestions,
        "by_service": dict(by_service.most_common()),
        "by_issue_type": dict(by_issue.most_common()),
        "by_day": dict(sorted(by_day.items())),
        "estimated_minutes_saved": round(total_suggestions * SECONDS_PER_ISSUE / 60, 1),
    }


def weekly_insights(store: Store, user_id: int, now: float | None = None) -> dict:
    """This week vs last week, with deltas."""
    now = int(now or time.time())
    this_week = summarize(store, user_id, now - _WEEK, now)
    last_week = summarize(store, user_id, now - 2 * _WEEK, now - _WEEK)
    return {
        "this_week": this_week,
        "last_week": last_week,
        "deltas": {
            "calls": this_week["calls"] - last_week["calls"],
            "words": this_week["words"] - last_week["words"],
            "suggestions": this_week["suggestions"] - last_week["suggestions"],
        },
    }


def rollup(store: Store, user_ids: list[int], since_ts: int) -> dict:
    """Team view over a set of users: adoption + top issues + per-member activity."""
    top_issues: Counter = Counter()
    activity = []
    total_calls = total_words = active = 0
    for uid in user_ids:
        s = summarize(store, uid, since_ts)
        if s["calls"] > 0:
            active += 1
        total_calls += s["calls"]
        total_words += s["words"]
        for k, v in s["by_issue_type"].items():
            top_issues[k] += v
        activity.append({"user_id": uid, "calls": s["calls"], "words": s["words"]})
    return {
        "members": len(user_ids),
        "active_users": active,
        "total_calls": total_calls,
        "total_words": total_words,
        "top_issues": dict(top_issues.most_common(10)),
        "activity": activity,
    }
