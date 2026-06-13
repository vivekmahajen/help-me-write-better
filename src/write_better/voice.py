"""Personal voice profile — "sounds like me".

Derives a deterministic style descriptor from a user's own writing samples
(reusing :func:`realtime.style_fingerprint`) and renders it as a VOICE PROFILE
block the engine uses to match the author's natural voice instead of flattening
into generic prose. Pure + offline (no model call), so it's testable and shared
by the open API and the platform gateway alike.
"""

from __future__ import annotations

from .realtime import style_fingerprint

# How much of the author's own writing to quote back to the model.
_EXCERPT_CHARS = 600


def describe_fingerprint(fp: dict) -> str:
    """A short, human-readable summary of the measured style."""
    sl = fp.get("sentence_length", {})
    dist = sl.get("distribution", {})
    n = max(fp.get("sentences", 0), 1)

    def pct(key: str) -> int:
        return round(100 * dist.get(key, 0) / n)

    parts = [
        f"average sentence length ~{sl.get('mean', 0)} words "
        f"({pct('short_<10')}% short, {pct('medium_10_20')}% medium, "
        f"{pct('long_>20')}% long)",
        f"adverb density {fp.get('adverb_density', 0)}",
    ]
    if fp.get("dialogue_ratio", 0) > 0.05:
        parts.append(f"uses dialogue (ratio {fp['dialogue_ratio']})")
    top = (fp.get("filter_words") or {}).get("top") or []
    if top:
        parts.append("habitual words: " + ", ".join(top))
    return "; ".join(parts)


def build_profile(samples: str) -> dict:
    """A profile view for the API: the stored samples + fingerprint + descriptor."""
    samples = (samples or "").strip()
    if not samples:
        return {"samples": "", "fingerprint": {}, "descriptor": ""}
    fp = style_fingerprint(samples)
    return {"samples": samples, "fingerprint": fp, "descriptor": describe_fingerprint(fp)}


def voice_drift(reference: str, sample: str) -> dict:
    """A deterministic voice-drift signal between a reference (e.g. the preceding
    manuscript) and new text, from :func:`realtime.style_fingerprint` metrics.
    Returns metric deltas + a coarse verdict (low | medium | high)."""
    a = style_fingerprint(reference or "")
    b = style_fingerprint(sample or "")
    deltas = {
        "mean_sentence_len": round(
            b["sentence_length"]["mean"] - a["sentence_length"]["mean"], 1),
        "adverb_density": round(b["adverb_density"] - a["adverb_density"], 3),
        "dialogue_ratio": round(b["dialogue_ratio"] - a["dialogue_ratio"], 3),
    }
    score = (abs(deltas["mean_sentence_len"]) / 8
             + abs(deltas["adverb_density"]) * 20
             + abs(deltas["dialogue_ratio"]) * 5)
    verdict = "low" if score < 1 else "medium" if score < 2.5 else "high"
    return {"deltas": deltas, "drift": verdict}


def render_voice_profile(samples: str | None) -> str | None:
    """A VOICE PROFILE prompt block, or ``None`` when there's nothing usable."""
    samples = (samples or "").strip()
    if not samples:
        return None
    fp = style_fingerprint(samples)
    excerpt = samples[:_EXCERPT_CHARS]
    return (
        "VOICE PROFILE (write in THIS author's voice — match their natural rhythm, "
        "diction, and personality; do not flatten into generic 'AI' prose, and do not "
        "copy the sample's content). "
        f"Measured style: {describe_fingerprint(fp)}.\n"
        "Representative sample of the author's own writing:\n"
        '"""\n' + excerpt + '\n"""'
    )
