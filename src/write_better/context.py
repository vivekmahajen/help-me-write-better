"""Long-form manuscript context: typed input, token estimate, front-trim budget.

Pure + deterministic (no model call). A rewriting request may carry a CONTEXT —
the preceding manuscript, an outline, or a style reference — that the engine
injects so continuations keep voice, names, facts, and tense. Over-budget
context is trimmed from the **front** (the oldest text), keeping the most recent
material nearest the continuation point, and the trim is reported explicitly via
``context_truncated`` — never silent.
"""

from __future__ import annotations

ROLES = ("preceding_manuscript", "outline", "style_reference")

# Generous default; our models carry large windows, so this only guards extremes.
BUDGET_CHARS = 200_000

# Above this estimated size the job is treated as long-form and routed premium.
LONG_CONTEXT_TOKENS = 1500


def normalize(context) -> tuple[str, str]:
    """Accept a plain string or a ``{"text", "role"}`` dict; return (text, role)."""
    if isinstance(context, dict):
        text = str(context.get("text") or "").strip()
        role = context.get("role") or "preceding_manuscript"
    elif isinstance(context, str):
        text, role = context.strip(), "preceding_manuscript"
    else:
        text, role = "", "preceding_manuscript"
    if role not in ROLES:
        role = "preceding_manuscript"
    return text, role


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) — good enough for budgeting."""
    return (len(text or "") + 3) // 4


def is_long(text: str) -> bool:
    return estimate_tokens(text) >= LONG_CONTEXT_TOKENS


def budget(text: str, max_chars: int = BUDGET_CHARS) -> tuple[str, dict | None]:
    """Trim from the front so the most recent text is kept.

    Returns ``(kept_text, truncated)`` where ``truncated`` is
    ``{"kept_chars", "dropped_chars"}`` or ``None`` when nothing was dropped.
    """
    text = text or ""
    if len(text) <= max_chars:
        return text, None
    kept = text[-max_chars:]
    # snap the opening to a clean boundary so we don't start mid-sentence
    for sep in ("\n\n", "\n", ". "):
        idx = kept.find(sep)
        if 0 <= idx < max_chars * 0.15:
            kept = kept[idx + len(sep):]
            break
    return kept, {"kept_chars": len(kept), "dropped_chars": len(text) - len(kept)}
