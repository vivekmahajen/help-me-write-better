"""Deterministic length counting + trimming for the ``strict_limit`` guarantee.

Pure (no model call), so the same counters back the UI character/word counters
and the engine's post-generation enforcement — client and server agree on what
"within the limit" means. ``trim_to_limit`` is the last-resort deterministic
fallback when the model can't hit the limit on its own.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"\S+")


def count_chars(text: str) -> int:
    return len(text or "")


def count_words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def within_limit(text: str, max_chars: int | None = None,
                 max_words: int | None = None) -> bool:
    if max_chars is not None and count_chars(text) > max_chars:
        return False
    if max_words is not None and count_words(text) > max_words:
        return False
    return True


def trim_to_limit(text: str, max_chars: int | None = None,
                  max_words: int | None = None) -> str:
    """Trim ``text`` to fit. Word limit first, then char limit; prefer cutting on
    a word boundary, falling back to a hard cut only for very tight limits."""
    out = text or ""
    if max_words is not None:
        words = _WORD.findall(out)
        if len(words) > max_words:
            out = " ".join(words[:max_words])
    if max_chars is not None and len(out) > max_chars:
        cut = out[:max_chars]
        space = cut.rfind(" ")
        # keep the word-boundary cut unless it would throw away most of the text
        out = cut[:space] if space > max_chars * 0.6 else cut
        out = out.rstrip()
    return out
