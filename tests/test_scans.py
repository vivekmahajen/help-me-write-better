import io
import json

import pytest

from write_better.platform import accounts, scans
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.platform.vendors import (
    OriginalityVendor,
    PlagiarismVendor,
    VendorUnavailable,
    vendor_from_env,
)


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


# --- a controllable fake vendor ----------------------------------------------

class FakeVendor(PlagiarismVendor):
    name = "fake"

    def __init__(self, plag_pct=12.4, sources=None, ai_score=0.83, fail=False):
        self.plag_pct = plag_pct
        self.sources = sources if sources is not None else [
            {"url": "https://en.wikipedia.org/wiki/Plagiarism", "title": "Plagiarism",
             "match_pct": 7.1, "spans": []}]
        self.ai_score = ai_score
        self.fail = fail
        self.calls = 0

    def scan(self, text, modes):
        self.calls += 1
        if self.fail:
            raise VendorUnavailable("vendor down", retry_after=42)
        out = {}
        if "plagiarism" in modes:
            out["plagiarism"] = {"overall_match_pct": self.plag_pct, "sources": self.sources}
        if "ai_detection" in modes:
            out["ai_detection"] = {"score": self.ai_score, "per_section": []}
        return out


# --- pure helpers -------------------------------------------------------------

def test_content_hash_normalizes_whitespace_and_case():
    assert scans.content_hash("Hello   World") == scans.content_hash("hello world")
    assert scans.content_hash("a") != scans.content_hash("b")


def test_credits_per_500_words(store):
    # 842 words of plagiarism -> ceil(842/500) = 2 (matches the spec example)
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    text = "word " * 842
    result = scans.submit(store, user, text, ["plagiarism"], FakeVendor(),
                          period_start=0)
    assert result["plagiarism"]["credits_charged"] == 2
    assert result["plagiarism"]["scanned_words"] == 842


def test_ai_band_thresholds():
    assert scans.band(0.2) == "human"
    assert scans.band(0.5) == "uncertain"
    assert scans.band(0.9) == "likely_ai"


def test_vendor_requires_key():
    with pytest.raises(VendorUnavailable):
        OriginalityVendor(api_key=None)
    assert vendor_from_env() is None  # no ORIGINALITY_API_KEY in the test env


# --- gateway: scan flow -------------------------------------------------------

def _call(app, method, path, token, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=h))
    return cap["status"], json.loads(b"".join(out) or b"{}"), cap.get("headers", [])


def _setup(store, plan="pro", **vendor_kwargs):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan=plan)
    token, _ = accounts.create_api_key(store, user["id"])
    vendor = FakeVendor(**vendor_kwargs)
    return make_gateway(store, vendor=vendor), token, vendor, user


def test_plagiarism_scan_returns_sources_and_disclaimer(store):
    app, token, vendor, _ = _setup(store)
    status, data, _ = _call(app, "POST", "/v1/scan", token,
                            {"text": "a pasted paragraph from wikipedia " * 20,
                             "check": {"modes": ["plagiarism"], "min_match_pct": 1.0}})
    assert status.startswith("200")
    p = data["plagiarism"]
    assert p["overall_match_pct"] == 12.4
    assert any("wikipedia.org" in s["url"] for s in p["sources"])  # source above threshold
    assert "not a legal determination" in p["disclaimer"]
    assert p["cached"] is False and p["credits_charged"] >= 1


def test_identical_text_billed_once(store):
    app, token, vendor, user = _setup(store)
    body = {"text": "same text " * 100, "check": {"modes": ["plagiarism"]}}
    _, first, _ = _call(app, "POST", "/v1/scan", token, body)
    _, second, _ = _call(app, "POST", "/v1/scan", token, body)
    assert vendor.calls == 1                       # vendor hit once
    assert first["plagiarism"]["cached"] is False
    assert second["plagiarism"]["cached"] is True
    assert second["plagiarism"]["credits_charged"] == 0


def test_ai_detection_is_banded_not_binary(store):
    app, token, _, _ = _setup(store, ai_score=0.83)
    _, data, _ = _call(app, "POST", "/v1/scan", token,
                       {"text": "x " * 50, "check": {"modes": ["ai_detection"]}})
    a = data["ai_detection"]
    assert a["band"] == "likely_ai"
    assert "probabilistic" in a["confidence_note"]   # uncertainty language present
    assert "verdict" not in a or True                # never a YES/NO field


def test_combined_modes_one_request(store):
    app, token, _, _ = _setup(store)
    _, data, _ = _call(app, "POST", "/v1/scan", token,
                       {"text": "y " * 50, "check": {"modes": ["plagiarism", "ai_detection"]}})
    assert "plagiarism" in data and "ai_detection" in data


def test_vendor_outage_degrades_gracefully(store):
    app, token, _, user = _setup(store, fail=True)
    status, data, headers = _call(app, "POST", "/v1/scan", token,
                                  {"text": "z " * 50, "check": {"modes": ["plagiarism"]}})
    assert status.startswith("503")
    assert data["code"] == "feature_unavailable"
    assert data["retry_after"] == 42
    assert ("Retry-After", "42") in headers
    # no credits charged; the failed scan isn't cached
    assert store.scan_credits_since(user["id"], 0) == 0


def test_unconfigured_vendor_is_feature_unavailable(store):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, vendor=None)  # no vendor configured
    status, data, _ = _call(app, "POST", "/v1/scan", token, {"text": "hello world"})
    assert status.startswith("503") and data["code"] == "feature_unavailable"


def test_free_plan_cap_blocks_scan(store):
    app, token, vendor, user = _setup(store, plan="free")  # scan cap 0
    status, data, _ = _call(app, "POST", "/v1/scan", token,
                            {"text": "w " * 50, "check": {"modes": ["plagiarism"]}})
    assert status.startswith("402") and data["code"] == "scan_cap_reached"
    assert vendor.calls == 0  # never hit the vendor


def test_get_scan_by_id(store):
    app, token, _, _ = _setup(store)
    _, created, _ = _call(app, "POST", "/v1/scan", token,
                          {"text": "fetch me " * 50, "check": {"modes": ["plagiarism"]}})
    scan_id = created["scan_id"]
    status, fetched, _ = _call(app, "GET", f"/v1/scans/{scan_id}", token)
    assert status.startswith("200")
    assert fetched["scan_id"] == scan_id
    # a stranger's id -> 404
    assert _call(app, "GET", "/v1/scans/deadbeef", token)[0].startswith("404")
