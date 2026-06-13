"""Load the operator system prompt and build the per-request INPUTS block."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# The operator prompt ships as package data, next to this module. Loading it by
# its on-disk neighbour works in every deployment mode (source checkout, pip-
# installed package, gunicorn, Vercel) without depending on the repo layout.
_PROMPT_PATH = Path(__file__).resolve().with_name("operator_prompt.md")

VALID_FORMATS = (
    "markdown", "html", "plain", "rich-text", "email", "report", "doc", "slide-outline",
)


@lru_cache(maxsize=1)
def system_prompt() -> str:
    """Return the operator prompt that powers the engine (cached after first read)."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise FileNotFoundError(
            f"operator prompt not found at {_PROMPT_PATH}. "
            "It should ship with the package as write_better/operator_prompt.md."
        ) from exc


def _target_block(
    audience: str | None,
    tone: str | None,
    length: str | None,
    reading_level: str | None,
    language: str | None,
) -> str:
    parts = []
    if audience:
        parts.append(f"audience: {audience}")
    if tone:
        parts.append(f"tone: {tone}")
    if length:
        parts.append(f"length: {length}")
    if reading_level:
        parts.append(f"reading level: {reading_level}")
    if language:
        parts.append(f"language: {language}")
    return "; ".join(parts) if parts else "(unspecified — keep the author's defaults)"


def build_user_message(
    *,
    text: str,
    service_names: list[str],
    output_format: str,
    show_changes: bool,
    audience: str | None = None,
    tone: str | None = None,
    length: str | None = None,
    reading_level: str | None = None,
    language: str | None = None,
    free_form: str | None = None,
    service_instructions: list[tuple[str, str]] | None = None,
    style_guide: str | None = None,
    context: str | None = None,
    protected_terms: list[str] | None = None,
    voice_profile: str | None = None,
    hard_limit: str | None = None,
) -> str:
    """Assemble the INPUTS block the engine expects, matching the operator contract."""
    services = ", ".join(service_names) if service_names else "(infer from the request)"
    target = _target_block(audience, tone, length, reading_level, language)

    lines = [
        "Apply the requested service(s) to TEXT and return the result per the OUTPUT CONTRACT.",
        "",
        f"SERVICE(S)    = {services}",
        f"TARGET        = {target}",
        f"OUTPUT_FORMAT = {output_format}",
        f"SHOW_CHANGES  = {str(show_changes).lower()}",
    ]
    if free_form:
        lines.append(f"REQUEST       = {free_form}")
    if hard_limit:
        lines.append(f"HARD LIMIT    = {hard_limit}")

    if protected_terms:
        lines.append("")
        lines.append("PROTECTED TERMS (the author's personal dictionary — each is correct and "
                     "intentional; never flag, change, re-capitalize, reword, or \"correct\" "
                     "these, and never count them as errors):")
        for term in protected_terms:
            lines.append(f"- {term}")

    if voice_profile:
        lines.append("")
        lines.append(voice_profile)

    if style_guide:
        lines.append("")
        lines.append(style_guide)

    if context:
        lines.append("")
        lines.append("CONTEXT (preceding manuscript — keep voice, facts, and canon "
                     "consistent with it; do not summarize, quote, or alter it):")
        lines.append('"""')
        lines.append(context)
        lines.append('"""')

    if service_instructions:
        lines.append("")
        lines.append("SERVICE INSTRUCTIONS (follow each precisely, within the HARD RULES):")
        for name, instruction in service_instructions:
            lines.append(f"--- {name} ---")
            lines.append(instruction)

    lines += [
        "",
        "TEXT =",
        '"""',
        text,
        '"""',
    ]
    return "\n".join(lines)
