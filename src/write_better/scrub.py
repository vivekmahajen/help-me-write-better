"""Confidentiality scrub: find and redact sensitive data before you share text.

Deterministic and **offline** (regex + Luhn, no model call) — the scan itself
never sends your text anywhere, which is the point for a confidentiality check.
Detects emails, phone numbers, credit-card numbers (Luhn-validated), US SSNs,
IPv4 addresses, and common secret/API-key formats. :func:`redact` swaps each
finding for a typed placeholder.

For names, addresses, and context-dependent confidential references (which
regex can't reliably catch), use the ``confidential`` engine service, which
complements this deterministic pass.
"""

from __future__ import annotations

import re

# Order matters: earlier, more specific patterns win overlaps (see _resolve).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("api_key", re.compile(
        r"\b("
        r"sk-[A-Za-z0-9]{20,}"           # OpenAI-style
        r"|sk-ant-[A-Za-z0-9\-]{20,}"     # Anthropic-style
        r"|AKIA[0-9A-Z]{16}"              # AWS access key id
        r"|ghp_[A-Za-z0-9]{36}"           # GitHub PAT
        r"|xox[baprs]-[A-Za-z0-9\-]{10,}" # Slack token
        r"|AIza[0-9A-Za-z\-_]{35}"        # Google API key
        r")\b")),
    ("ip", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    # Card-like digit runs (13-19 digits, optional space/dash groups); Luhn-checked below.
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?<![ -])")),
    # Phone: optional country code, area code, 7-digit local with separators.
    ("phone", re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}(?!\d)")),
]

_PLACEHOLDERS = {
    "email": "[EMAIL]", "ssn": "[SSN]", "api_key": "[API_KEY]", "ip": "[IP]",
    "credit_card": "[CREDIT_CARD]", "phone": "[PHONE]",
}


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not (13 <= len(nums) <= 19):
        return False
    total, parity = 0, len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def scan(text: str) -> list[dict]:
    """All sensitive findings as ``{type, value, start, end}``, sorted, non-overlapping."""
    text = text or ""
    raw: list[dict] = []
    for kind, pat in _PATTERNS:
        for m in pat.finditer(text):
            value = m.group(0)
            if kind == "credit_card" and not _luhn_ok(value):
                continue
            raw.append({"type": kind, "value": value, "start": m.start(), "end": m.end()})
    return _resolve(raw)


def _resolve(found: list[dict]) -> list[dict]:
    """Drop overlapping matches, keeping the earlier-listed (more specific) one."""
    found.sort(key=lambda f: (f["start"], -(f["end"] - f["start"])))
    kept: list[dict] = []
    last_end = -1
    for f in found:
        if f["start"] >= last_end:
            kept.append(f)
            last_end = f["end"]
    return kept


def redact(text: str, types: set[str] | None = None) -> str:
    """Return ``text`` with each finding replaced by a typed placeholder."""
    findings = [f for f in scan(text) if types is None or f["type"] in types]
    out = text or ""
    for f in sorted(findings, key=lambda f: f["start"], reverse=True):
        out = out[:f["start"]] + _PLACEHOLDERS[f["type"]] + out[f["end"]:]
    return out


def summarize(text: str) -> dict:
    """Findings + per-type counts + a redacted copy — the API/UI shape."""
    findings = scan(text)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["type"]] = counts.get(f["type"], 0) + 1
    return {"findings": findings, "counts": counts,
            "redacted": redact(text), "clean": not findings}
