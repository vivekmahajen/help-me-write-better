"""The top-level app adds standard security headers to every response."""

import app as app_module


def _headers(path="/_status", method="GET"):
    cap = {}

    def sr(status, headers, exc_info=None):
        cap["status"] = status
        cap["headers"] = {k: v for k, v in headers}

    body = app_module.app(
        {"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_ACCEPT": "application/json",
         "QUERY_STRING": ""}, sr)
    list(body)
    return cap


def test_security_headers_on_status():
    h = _headers("/_status")["headers"]
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in h
    csp = h["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp and "default-src 'self'" in csp


def test_security_headers_on_landing_and_no_clobber():
    h = _headers("/")["headers"]
    assert h["X-Content-Type-Options"] == "nosniff"
    # the wrapper must not drop the response's own content-type
    assert any(k.lower() == "content-type" for k in h)
