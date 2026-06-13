"""Cultural communication registers for the ``localize-tone`` service.

A deliberately small, honestly-scoped launch set. This is a **register/style
shift** — directness, formality, politeness softeners, rhythm — **not**
translation and **not** cultural consultation. Output stays in English.
"""

from __future__ import annotations

CULTURES: dict[str, str] = {
    "en-US-direct": (
        "American English: direct, warm, results-first. Short sentences, plain "
        "words, get to the point, confident calls to action."),
    "en-GB-understated": (
        "British English: understated, polite, and indirect. Softeners "
        "('perhaps', 'rather', 'it might be worth'), dry register, "
        "less overt enthusiasm."),
    "en-formal-jp": (
        "English for a Japanese business context: formal, humble, and "
        "group-oriented. Deferential, hierarchy-aware politeness, careful "
        "hedging, gratitude and apology where appropriate."),
}


def ids() -> list[str]:
    return list(CULTURES)


def is_supported(culture) -> bool:
    return isinstance(culture, str) and culture in CULTURES


def augment(free_form: str | None, culture: str) -> str:
    """Fold the chosen register into the engine's free-form REQUEST line."""
    clause = f"CULTURE = {culture} — {CULTURES[culture]}"
    return f"{free_form}\n{clause}" if free_form else clause
