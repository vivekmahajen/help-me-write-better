"""The bundled service modes (A–M) and how user requests resolve to them.

Each mode mirrors the operator prompt's MODES section. ``tier`` drives model
routing: routine cleanup jobs are "routine" (cheap model), generative or
high-stakes rewrites are "premium", everything else is "standard".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    """One bundled service."""

    letter: str          # canonical letter, e.g. "D"
    name: str            # canonical name, e.g. "tighten"
    summary: str         # one-line description
    tier: str            # "routine" | "standard" | "premium"
    aliases: tuple[str, ...] = ()


# Order matches the operator prompt A–M.
MODES: tuple[Mode, ...] = (
    Mode("A", "write", "Draft new text from a brief, in the target tone/format/length.",
         "premium", ("draft", "compose")),
    Mode("B", "correct", "Fix grammar, spelling, punctuation, syntax (minimal, surgical touch).",
         "routine", ("grammar", "proofread", "fix")),
    Mode("C", "clarify", "Improve clarity and flow; remove ambiguity and awkward phrasing.",
         "routine", ("clarity",)),
    Mode("D", "tighten", "Make concise; cut wordiness, redundancy, and filler; prefer active voice.",
         "routine", ("concise", "trim", "shorten-wordiness")),
    Mode("E", "retone", "Adjust tone/formality/voice (professional, friendly, persuasive, …).",
         "standard", ("tone",)),
    Mode("F", "paraphrase", "Restate in fresh wording; or rewrite in a specified style/voice.",
         "premium", ("rewrite", "reword", "restate")),
    Mode("G", "level", "Raise or lower reading level / simplify or elevate for the audience.",
         "standard", ("simplify", "elevate", "reading-level")),
    Mode("H", "resize", "Expand or shorten to a target length while keeping substance.",
         "standard", ("expand", "lengthen", "shorten")),
    Mode("I", "summarize", "Condense to key points / TL;DR / abstract.",
         "routine", ("summary", "tldr", "abstract")),
    Mode("J", "translate", "Render into another language naturally and idiomatically.",
         "standard", ("translation",)),
    Mode("K", "structure", "Organize into clean structure: headings, sections, lists, tables.",
         "standard", ("organize", "outline")),
    Mode("L", "convert", "Output in a specific format (Markdown, HTML, email, report, …).",
         "standard", ("format", "reformat")),
    Mode("M", "check", "Analysis only: readability, tone, issues, and suggestions; no rewrite.",
         "standard", ("analyze", "review", "analysis")),
)


# Lookup tables, built once.
_BY_LETTER = {m.letter.lower(): m for m in MODES}
_BY_NAME = {m.name.lower(): m for m in MODES}
_BY_ALIAS = {alias.lower(): m for m in MODES for alias in m.aliases}


def resolve_one(token: str) -> Mode:
    """Resolve a single token (letter, name, or alias) to a :class:`Mode`."""
    key = token.strip().lower()
    if not key:
        raise ValueError("empty service token")
    mode = _BY_LETTER.get(key) or _BY_NAME.get(key) or _BY_ALIAS.get(key)
    if mode is None:
        valid = ", ".join(m.name for m in MODES)
        raise ValueError(f"unknown service {token!r}. Valid services: {valid}")
    return mode


def resolve_services(spec: str | list[str]) -> list[Mode]:
    """Resolve a comma/space-separated spec (or list) to ordered, de-duped modes."""
    if isinstance(spec, str):
        tokens = [t for t in spec.replace(",", " ").split() if t]
    else:
        tokens = list(spec)
    seen: dict[str, Mode] = {}
    for token in tokens:
        mode = resolve_one(token)
        seen.setdefault(mode.letter, mode)
    if not seen:
        raise ValueError("no services resolved")
    return list(seen.values())
