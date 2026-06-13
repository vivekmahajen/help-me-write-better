"""The weekly writing recap email — composed from existing analytics insights.

Rules: **explicit opt-in only** (off by default; the user sets
``weekly_email: true`` in preferences), a one-click unsubscribe link in every
send (HMAC-signed, no login needed), and plain text. Sent through the
``mailer`` provider interface (console by default; SMTP when configured) — never
hard-requires a key. Progress framing only — no streaks, no shame.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from .mailer import Email

_LESSONS = {
    "passive_voice": "Passive voice hides who acted — name the doer: 'we shipped it', not 'it was shipped'.",
    "filler_words": "Filler ('very', 'really', 'just') dilutes — cut it and the sentence gets stronger.",
    "grammar": "Read each sentence aloud; subject-verb mismatches usually surface by ear.",
    "punctuation": "A comma splice joins two sentences with a comma — use a period or a semicolon.",
    "style": "Prefer concrete nouns and active verbs over abstractions.",
    "spelling": "Keep a personal dictionary for the words you use on purpose.",
    "capitalization": "Capitalize proper nouns and sentence starts; lowercase the rest.",
}
_SUGGESTED = {
    "passive_voice": "detect-weak", "filler_words": "tighten", "style": "clarify",
    "grammar": "correct", "punctuation": "correct", "spelling": "correct",
    "capitalization": "correct",
}


def _key() -> bytes:
    return (os.environ.get("WB_CRON_SECRET") or "wb-unsubscribe").encode()


def unsubscribe_token(user_id: int) -> str:
    return hmac.new(_key(), f"unsub:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def verify_unsubscribe(user_id, token) -> bool:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(unsubscribe_token(uid), str(token or ""))


def compose(user: dict, insights: dict, base_url: str = "") -> Email:
    """Build the recap from ``analytics.weekly_insights`` output."""
    this_week = insights.get("this_week", {})
    deltas = insights.get("deltas", {})
    by_issue = this_week.get("by_issue_type", {})
    top3 = sorted(by_issue.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_cat = top3[0][0] if top3 else "style"

    improved = ("fewer flagged issues than last week" if deltas.get("suggestions", 0) < 0
                else "steady progress")
    unsub = (f"{base_url.rstrip('/')}/v1/unsubscribe?u={user['id']}"
             f"&token={unsubscribe_token(user['id'])}")

    lines = [
        f"Hi {user['email']},",
        "",
        f"This week you made {this_week.get('calls', 0)} edits across "
        f"{this_week.get('words', 0)} words.",
        "",
        "A few things to keep an eye on:",
    ]
    if top3:
        lines += [f"  - {cat.replace('_', ' ')}: {n}" for cat, n in top3]
    else:
        lines.append("  - nothing major flagged — nicely done.")
    lines += [
        "",
        f"One win: {improved}.",
        f"Lesson of the week: {_LESSONS.get(top_cat, _LESSONS['style'])}",
        f"Worth a try next: the '{_SUGGESTED.get(top_cat, 'clarify')}' service.",
        "",
        "— Help Me Write Better",
        f"Unsubscribe anytime: {unsub}",
    ]
    return Email(to=user["email"], subject="Your weekly writing recap",
                 body="\n".join(lines))
