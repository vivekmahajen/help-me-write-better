"""External plagiarism + AI-detection vendor behind an interface (ADR-001).

The real Originality.ai integration lives here (real endpoints/params over stdlib
HTTP via the injectable transport — no SDK dependency, tests never hit the
network). A missing key or a vendor outage raises ``VendorUnavailable`` so the
gateway can return a structured ``feature_unavailable`` error — never a fake
heuristic result.

Swapping to Copyleaks (webhook-driven) is a new ``PlagiarismVendor`` adapter, not
a rewrite: the gateway, ``scans`` storage, caching, and metering are
vendor-agnostic.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional

from .oauth import Transport, urllib_transport

VALID_MODES = ("plagiarism", "ai_detection")


class VendorUnavailable(Exception):
    """The vendor is unconfigured or unreachable; degrade gracefully."""

    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message)
        self.retry_after = retry_after


class PlagiarismVendor(ABC):
    name = "vendor"

    @abstractmethod
    def scan(self, text: str, modes: list[str]) -> dict:
        """Return a normalized result keyed by mode, e.g.::

            {"plagiarism": {"overall_match_pct": .., "sources": [..], "scanned_words": ..},
             "ai_detection": {"score": .., "per_section": [..]}}
        """


class OriginalityVendor(PlagiarismVendor):
    name = "originality"
    BASE = "https://api.originality.ai/api/v1"

    def __init__(self, api_key: str, transport: Transport = urllib_transport):
        if not api_key:
            raise VendorUnavailable("ORIGINALITY_API_KEY not configured")
        self.api_key = api_key
        self._http = transport

    def _post(self, path: str, payload: dict) -> dict:
        try:
            return self._http("POST", f"{self.BASE}{path}",
                              {"X-OAI-API-KEY": self.api_key,
                               "Content-Type": "application/json"},
                              json.dumps(payload).encode())
        except VendorUnavailable:
            raise
        except Exception as exc:  # network / parse error -> degrade
            raise VendorUnavailable(f"vendor request failed: {exc}") from exc

    def scan(self, text: str, modes: list[str]) -> dict:
        out: dict = {}
        if "plagiarism" in modes:
            data = self._post("/scan/plagiarism", {"content": text, "storeScan": False})
            out["plagiarism"] = _normalize_plagiarism(data)
        if "ai_detection" in modes:
            data = self._post("/scan/ai", {"content": text, "storeScan": False})
            out["ai_detection"] = _normalize_ai(data)
        return out


def _normalize_plagiarism(data: dict) -> dict:
    results = data.get("results") or data
    sources = []
    for s in (results.get("sources") or []):
        sources.append({
            "url": s.get("url"),
            "title": s.get("title") or s.get("url"),
            "match_pct": round(float(s.get("score", s.get("matchPercentage", 0)) or 0), 1),
            "spans": s.get("spans") or [],
        })
    return {
        "overall_match_pct": round(float(results.get("score",
                                    results.get("totalTextScore", 0)) or 0), 1),
        "sources": sources,
    }


def _normalize_ai(data: dict) -> dict:
    ai = (data.get("ai") or data.get("results") or {})
    score = float(ai.get("confidence", ai.get("score", 0)) or 0)
    if score > 1:  # vendor may return 0-100
        score = score / 100.0
    return {
        "score": round(score, 4),
        "per_section": data.get("per_section") or data.get("blocks") or [],
    }


def vendor_from_env(transport: Transport = urllib_transport) -> Optional[PlagiarismVendor]:
    """The configured vendor, or None when no key is set."""
    key = os.environ.get("ORIGINALITY_API_KEY")
    if not key:
        return None
    return OriginalityVendor(key, transport)
