"""The shared real-time check engine (#1).

A low-latency path for "as you type" checking — deliberately NOT the full engine
per keystroke. Techniques from the spec:

* **Local rules pass** — obvious grammar/spelling/punctuation issues are caught
  with deterministic rules, no API round-trip and ~0 cost (keeps cost-per-active-
  user well inside the margin model). A model pass can be layered on later via the
  ``deep_check`` hook.
* **Changed-sentence diff** — given the previous text, only re-check sentences
  that actually changed.
* **Per-span cache** — results are cached per sentence, so unchanged spans are free.

Every surface (extension, add-ins, desktop, mobile, web) renders the SAME
normalized suggestion: ``{range, type, severity, message, replacements}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional


@dataclass(frozen=True)
class Suggestion:
    start: int                 # char offset into the text (inclusive)
    end: int                   # char offset (exclusive)
    type: str                  # spelling|grammar|punctuation|style|capitalization
    severity: str              # low|medium|high
    message: str
    replacements: tuple[str, ...]

    def shifted(self, delta: int) -> "Suggestion":
        return Suggestion(self.start + delta, self.end + delta, self.type,
                          self.severity, self.message, self.replacements)

    def to_dict(self) -> dict:
        return {
            "range": {"start": self.start, "end": self.end},
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "replacements": list(self.replacements),
        }


# --- word-substitution tables -------------------------------------------------

_MISSPELLINGS = {
    "teh": "the", "recieve": "receive", "seperate": "separate",
    "definately": "definitely", "occured": "occurred", "untill": "until",
    "wich": "which", "becuase": "because", "thier": "their", "tommorow": "tomorrow",
    "alot": "a lot", "accross": "across", "wierd": "weird", "neccessary": "necessary",
    "begining": "beginning", "beleive": "believe", "calender": "calendar",
    "enviroment": "environment", "goverment": "government", "occassion": "occasion",
}

_CONTRACTIONS = {
    "dont": "don't", "cant": "can't", "wont": "won't", "isnt": "isn't",
    "wasnt": "wasn't", "didnt": "didn't", "doesnt": "doesn't", "couldnt": "couldn't",
    "shouldnt": "shouldn't", "wouldnt": "wouldn't", "havent": "haven't",
    "hasnt": "hasn't", "im": "I'm", "ive": "I've", "youre": "you're",
    "theyre": "they're", "thats": "that's", "lets": "let's",
}


def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _word_table_rule(text, table, type_, severity, message):
    pattern = r"\b(" + "|".join(re.escape(w) for w in table) + r")\b"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        repl = _preserve_case(m.group(0), table[m.group(0).lower()])
        if repl == m.group(0):
            continue
        yield Suggestion(m.start(), m.end(), type_, severity, message, (repl,))


# --- individual rules ---------------------------------------------------------

def _rule_repeated_word(text):
    for m in re.finditer(r"\b(\w+)(\s+)(\1)\b", text, re.IGNORECASE):
        yield Suggestion(m.start(), m.end(), "grammar", "medium",
                         "Repeated word.", (m.group(1),))


def _rule_double_space(text):
    for m in re.finditer(r"[ \t]{2,}", text):
        yield Suggestion(m.start(), m.end(), "style", "low",
                         "Remove the extra space.", (" ",))


def _rule_space_before_punct(text):
    for m in re.finditer(r"[ \t]+([,.;:!?])", text):
        yield Suggestion(m.start(), m.end(), "punctuation", "low",
                         "Remove the space before punctuation.", (m.group(1),))


def _rule_missing_space_after_punct(text):
    for m in re.finditer(r"([,;:])([A-Za-z])", text):
        yield Suggestion(m.start(), m.end(), "punctuation", "low",
                         "Add a space after punctuation.",
                         (f"{m.group(1)} {m.group(2)}",))


def _rule_excessive_punct(text):
    for m in re.finditer(r"([!?])\1+", text):
        yield Suggestion(m.start(), m.end(), "style", "low",
                         "Excessive punctuation.", (m.group(1),))


def _rule_lowercase_i(text):
    for m in re.finditer(r"\bi\b", text):
        yield Suggestion(m.start(), m.end(), "capitalization", "medium",
                         "Capitalize the pronoun “I”.", ("I",))


def _rule_sentence_capital(text):
    # The span IS a sentence; capitalize its first alphabetic character.
    m = re.search(r"[A-Za-z]", text)
    if m and text[m.start()].islower():
        yield Suggestion(m.start(), m.start() + 1, "capitalization", "medium",
                         "Start the sentence with a capital letter.",
                         (text[m.start()].upper(),))


def _rule_misspellings(text):
    yield from _word_table_rule(text, _MISSPELLINGS, "spelling", "high",
                                "Possible misspelling.")


def _rule_contractions(text):
    yield from _word_table_rule(text, _CONTRACTIONS, "grammar", "medium",
                                "Missing apostrophe.")


_RULES = (
    _rule_repeated_word, _rule_double_space, _rule_space_before_punct,
    _rule_missing_space_after_punct, _rule_excessive_punct, _rule_lowercase_i,
    _rule_sentence_capital, _rule_misspellings, _rule_contractions,
)


# --- span checking (cached) ---------------------------------------------------

@lru_cache(maxsize=4096)
def check_span(span: str) -> tuple[Suggestion, ...]:
    """Run all local rules over a single sentence; offsets are span-relative.

    Cached so unchanged sentences cost nothing on subsequent keystrokes.
    """
    found: list[Suggestion] = []
    for rule in _RULES:
        found.extend(rule(span))
    return _dedupe_sort(found)


def _dedupe_sort(suggestions):
    seen = set()
    out = []
    for s in sorted(suggestions, key=lambda s: (s.start, s.end, s.type)):
        key = (s.start, s.end, s.type)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return tuple(out)


# --- sentence segmentation + diff ---------------------------------------------

def sentences(text: str) -> list[tuple[int, int, str]]:
    """Split into (start, end, text) spans, preserving offsets."""
    spans = []
    start = 0
    for m in re.finditer(r"[.!?]+(?:\s+|$)", text):
        spans.append((start, m.end(), text[start:m.end()]))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text), text[start:]))
    return spans


def check_text(text: str, previous: Optional[str] = None,
               deep_check: Optional[Callable[[str], list[Suggestion]]] = None) -> list[Suggestion]:
    """Return suggestions for ``text``.

    If ``previous`` is given, only changed sentences are re-checked (the rest are
    assumed unchanged). ``deep_check`` is an optional per-sentence hook (e.g. a
    cheap-model pass) returning span-relative suggestions — omitted by default so
    the path stays local and free.
    """
    unchanged = set()
    if previous is not None:
        unchanged = {span.strip() for _, _, span in sentences(previous)}

    out: list[Suggestion] = []
    for start, _end, span in sentences(text):
        if previous is not None and span.strip() in unchanged:
            continue
        for sug in check_span(span):
            out.append(sug.shifted(start))
        if deep_check is not None:
            for sug in deep_check(span):
                out.append(sug.shifted(start))
    return list(_dedupe_sort(out))
