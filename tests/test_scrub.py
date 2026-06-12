"""Confidentiality scrub: deterministic PII detector/redactor + the engine service."""

import io
import json

from write_better import scrub, web
from write_better.modes import resolve_one
from write_better.samples import SAMPLES


# --- deterministic detector --------------------------------------------------

def test_detects_email_phone_and_redacts():
    text = "Reach me at jane.doe@example.com or 415-555-0148 anytime."
    found = {f["type"] for f in scrub.scan(text)}
    assert "email" in found and "phone" in found
    red = scrub.redact(text)
    assert "jane.doe@example.com" not in red and "415-555-0148" not in red
    assert "[EMAIL]" in red and "[PHONE]" in red


def test_detects_ssn_ip_and_api_keys():
    text = ("SSN 123-45-6789, host 10.0.0.5, key sk-ant-abcdefGHIJKLMNOP1234567890, "
            "aws AKIAIOSFODNN7EXAMPLE")
    types = {f["type"] for f in scrub.scan(text)}
    assert {"ssn", "ip", "api_key"} <= types


def test_credit_card_requires_luhn():
    valid = "card 4111 1111 1111 1111 here"      # passes Luhn
    invalid = "num 1234 5678 9012 3456 here"      # fails Luhn
    assert any(f["type"] == "credit_card" for f in scrub.scan(valid))
    assert not any(f["type"] == "credit_card" for f in scrub.scan(invalid))


def test_summarize_shape_and_clean_flag():
    s = scrub.summarize("nothing sensitive here, just words")
    assert s["clean"] is True and s["findings"] == [] and s["counts"] == {}
    s2 = scrub.summarize("ping a@b.com and a@b.com")
    assert s2["clean"] is False and s2["counts"]["email"] == 2
    assert "[EMAIL]" in s2["redacted"]


def test_overlaps_resolved_no_double_count():
    # an email contains an '@…' that shouldn't also register as something else
    findings = scrub.scan("contact: ops@10.0.0.5xample.com")
    spans = [(f["start"], f["end"]) for f in findings]
    # no two findings overlap
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            assert a[1] <= b[0] or b[1] <= a[0]


# --- POST /scrub (no API key, no model) --------------------------------------

def _post_scrub(body):
    raw = json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/scrub",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    cap = {}
    out = web.app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], json.loads(b"".join(out))


def test_scrub_endpoint_runs_without_api_key(monkeypatch):
    monkeypatch.setattr(web, "has_api_key", lambda: False)   # no key needed
    status, data = _post_scrub({"text": "email me at x@y.com"})
    assert status == "200 OK"
    assert data["counts"]["email"] == 1
    assert "[EMAIL]" in data["redacted"]


# --- the engine service (context-aware complement) ---------------------------

def test_confidential_service_exists_and_is_analysis():
    m = resolve_one("confidential")
    assert m.tier == "standard"
    assert resolve_one("scrub").name == "confidential"
    assert "confidentiality reviewer" in m.instruction
    assert SAMPLES["confidential"].strip()
