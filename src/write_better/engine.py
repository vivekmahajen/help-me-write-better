"""The engine: route to a model, call Claude with the operator prompt, return text.

Model routing is the pricing margin lever described in the operator spec:
routine cleanup jobs go to a cheap model; generative / high-stakes rewrites go
to a premium model; everything else uses a balanced default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .modes import Mode, resolve_services
from .prompt import build_user_message, system_prompt

# Model IDs are the current Claude models (see README for the routing rationale).
PREMIUM_MODEL = "claude-opus-4-8"     # WRITE, high-stakes REWRITE
STANDARD_MODEL = "claude-sonnet-4-6"  # balanced default
ROUTINE_MODEL = "claude-haiku-4-5"    # CORRECT / CLARIFY / TIGHTEN / SUMMARIZE

# Models that accept adaptive thinking + the effort parameter. Haiku 4.5 does not
# (effort 400s on Haiku), so we only enable thinking on the Opus/Sonnet tiers.
_THINKING_MODELS = frozenset({PREMIUM_MODEL, STANDARD_MODEL})

# Streaming kicks in above this max_tokens to avoid SDK HTTP timeouts.
_MAX_TOKENS = 16000


@dataclass
class Request:
    """A single improve/format request."""

    text: str
    services: list[str] = field(default_factory=list)
    output_format: str = "markdown"
    show_changes: bool = False
    audience: str | None = None
    tone: str | None = None
    length: str | None = None
    reading_level: str | None = None
    language: str | None = None
    free_form: str | None = None
    model: str | None = None        # explicit override; otherwise routed
    effort: str = "high"            # low | medium | high | max (thinking models only)


@dataclass
class Result:
    """The engine's response."""

    text: str
    model: str
    services: list[Mode]
    input_tokens: int = 0
    output_tokens: int = 0


def route_model(modes: list[Mode]) -> str:
    """Pick a model for the requested modes.

    A premium mode anywhere in the request promotes the whole job to premium
    (you don't want a cheap model drafting). Otherwise, a job that is purely
    routine cleanup stays on the cheap model; any standard mode lifts it to the
    balanced default.
    """
    tiers = {m.tier for m in modes}
    if "premium" in tiers:
        return PREMIUM_MODEL
    if "standard" in tiers:
        return STANDARD_MODEL
    return ROUTINE_MODEL


def _build_call_kwargs(req: Request, modes: list[Mode], model: str) -> dict:
    kwargs: dict = {
        "model": model,
        "max_tokens": _MAX_TOKENS,
        "system": system_prompt(),
        "messages": [
            {
                "role": "user",
                "content": build_user_message(
                    text=req.text,
                    service_names=[m.name for m in modes],
                    output_format=req.output_format,
                    show_changes=req.show_changes,
                    audience=req.audience,
                    tone=req.tone,
                    length=req.length,
                    reading_level=req.reading_level,
                    language=req.language,
                    free_form=req.free_form,
                ),
            }
        ],
    }
    if model in _THINKING_MODELS:
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": req.effort}
    return kwargs


def improve(req: Request, *, client=None, stream_to=None) -> Result:
    """Run a request through the engine and return the polished text.

    Args:
        req: the request to process.
        client: an ``anthropic.Anthropic`` instance; created on demand if omitted.
        stream_to: optional callable receiving text deltas as they arrive (for a
            live CLI/UI). When provided, the call streams.
    """
    modes = resolve_services(req.services) if req.services else resolve_services("clarify")
    model = req.model or route_model(modes)

    if client is None:
        import anthropic  # imported lazily so tests / --dry-run don't need the SDK

        client = anthropic.Anthropic()

    kwargs = _build_call_kwargs(req, modes, model)

    if stream_to is not None:
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                stream_to(text)
            message = stream.get_final_message()
    else:
        message = client.messages.create(**kwargs)

    text = "".join(block.text for block in message.content if block.type == "text")
    return Result(
        text=text,
        model=model,
        services=modes,
        input_tokens=getattr(message.usage, "input_tokens", 0),
        output_tokens=getattr(message.usage, "output_tokens", 0),
    )


def has_api_key() -> bool:
    """True if an Anthropic credential is present in the environment."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
