"""Scan orchestration: idempotent caching, credit metering, and the response
contract for plagiarism + AI-detection (Features 1 & 2).

Vendor calls go through ``vendors.PlagiarismVendor``; this module owns hashing,
caching (identical re-scans are free), per-plan credit caps, and shaping the
honest, uncertainty-carrying response.
"""

from __future__ import annotations

import hashlib
import math
import re
import secrets

from .analytics import word_count
from .store import Store
from .vendors import VALID_MODES, VendorUnavailable

# Per-plan monthly scan-credit allowances (credit = ceil(words/500) for plagiarism,
# 1 per AI-detection scan). Configurable, not hard-coded into logic.
SCAN_CAPS = {"free": 0, "starter": 20, "pro": 100, "business": 300}

# AI-detection band thresholds (config, not code): human < 0.35 ≤ uncertain < 0.70 ≤ likely_ai
AI_BANDS = {"uncertain": 0.35, "likely_ai": 0.70}

AI_CONFIDENCE_NOTE = (
    "AI detectors are probabilistic and produce false positives, especially for "
    "non-native English writers and formulaic genres. Treat this as a signal, not "
    "a verdict."
)
PLAGIARISM_DISCLAIMER = (
    "Match percentages indicate textual similarity to indexed sources, not a legal "
    "determination of plagiarism."
)


class ScanCapError(Exception):
    def __init__(self, quota: dict):
        super().__init__("scan credit cap reached")
        self.quota = quota


def normalize_modes(modes) -> list[str]:
    if isinstance(modes, str):
        modes = [modes]
    out = [m.strip().lower() for m in (modes or []) if m]
    out = [m for m in out if m in VALID_MODES]
    if not out:
        out = ["plagiarism"]
    seen = []
    for m in out:
        if m not in seen:
            seen.append(m)
    return seen


def kind_key(modes: list[str]) -> str:
    return ",".join(sorted(modes))


def content_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip()).lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def band(score: float) -> str:
    if score >= AI_BANDS["likely_ai"]:
        return "likely_ai"
    if score >= AI_BANDS["uncertain"]:
        return "uncertain"
    return "human"


def _credits(words: int, modes: list[str]) -> dict:
    c = {}
    if "plagiarism" in modes:
        c["plagiarism"] = max(1, math.ceil(words / 500))
    if "ai_detection" in modes:
        c["ai_detection"] = 1
    return c


def quota(store: Store, user: dict, since_ts: int) -> dict:
    cap = SCAN_CAPS.get(user["plan"], 0)
    used = store.scan_credits_since(user["id"], since_ts)
    return {"plan": user["plan"], "scan_cap": cap, "scan_credits_used": used,
            "scan_credits_remaining": max(cap - used, 0)}


def submit(store: Store, user: dict, text: str, modes, vendor, *,
           min_match_pct: float = 1.0, period_start: int = 0) -> dict:
    """Run (or return a cached) scan. Raises VendorUnavailable / ScanCapError."""
    modes = normalize_modes(modes)
    kind = kind_key(modes)
    chash = content_hash(text)

    cached = store.get_cached_scan(kind, chash)
    if cached:
        return _serialize(cached, cached=True)

    if vendor is None:
        raise VendorUnavailable("scanning is not configured")

    words = word_count(text)
    credits = _credits(words, modes)
    total = sum(credits.values())

    q = quota(store, user, period_start)
    if total > q["scan_credits_remaining"]:
        raise ScanCapError(q)

    scan_id = secrets.token_hex(16)
    store.insert_scan(scan_id, user["id"], kind, chash, "pending", vendor.name)
    try:
        raw = vendor.scan(text, modes)
    except VendorUnavailable:
        store.fail_scan(scan_id)
        raise

    result: dict = {}
    if "plagiarism" in modes:
        p = raw.get("plagiarism", {})
        sources = [s for s in p.get("sources", [])
                   if float(s.get("match_pct", 0)) >= min_match_pct]
        result["plagiarism"] = {
            "overall_match_pct": p.get("overall_match_pct", 0.0),
            "sources": sources, "scanned_words": words,
            "credits": credits["plagiarism"],
        }
    if "ai_detection" in modes:
        a = raw.get("ai_detection", {})
        score = float(a.get("score", 0.0))
        result["ai_detection"] = {
            "score": score, "band": band(score),
            "per_section": [{**sec, "band": band(float(sec.get("score", 0)))}
                            for sec in a.get("per_section", [])],
            "credits": credits["ai_detection"],
        }

    row = store.complete_scan(scan_id, result, total)
    return _serialize(row, cached=False)


def get(store: Store, user: dict, scan_id: str) -> dict | None:
    row = store.get_scan(user["id"], scan_id)
    if not row:
        return None
    if row["status"] == "pending":
        return {"scan_id": scan_id, "status": "pending"}
    if row["status"] == "failed":
        return {"scan_id": scan_id, "status": "failed"}
    return _serialize(row, cached=True)


def _serialize(row: dict, cached: bool) -> dict:
    import json
    result = json.loads(row["result"]) if row.get("result") else {}
    out: dict = {"scan_id": row["id"], "status": "complete"}
    if "plagiarism" in result:
        p = result["plagiarism"]
        out["plagiarism"] = {
            "status": "complete", "content_hash": row["content_hash"],
            "overall_match_pct": p["overall_match_pct"], "sources": p["sources"],
            "scanned_words": p["scanned_words"],
            "credits_charged": 0 if cached else p["credits"],
            "cached": cached, "disclaimer": PLAGIARISM_DISCLAIMER,
        }
    if "ai_detection" in result:
        a = result["ai_detection"]
        out["ai_detection"] = {
            "status": "complete", "band": a["band"], "score": a["score"],
            "confidence_note": AI_CONFIDENCE_NOTE, "per_section": a["per_section"],
            "credits_charged": 0 if cached else a["credits"], "cached": cached,
        }
    return out
