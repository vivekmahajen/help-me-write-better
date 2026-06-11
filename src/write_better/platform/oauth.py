"""OAuth 2.0 / OIDC sign-in for Google and Microsoft.

The real authorization-code flow is implemented here (real provider endpoints,
params, and the token + userinfo exchange) using stdlib ``urllib`` — no SDK
dependency. The HTTP call is behind an injectable ``transport`` so tests exercise
the full flow without hitting Google/Microsoft.

Configure with client credentials from the environment; unconfigured providers
are simply absent from the web-auth surface.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Callable, Optional

# transport(method, url, headers, data) -> parsed JSON dict
Transport = Callable[[str, str, dict, Optional[bytes]], dict]


def urllib_transport(method: str, url: str, headers: dict, data: Optional[bytes]) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - network
        return json.loads(resp.read().decode("utf-8"))


class OAuthProvider:
    """One OIDC provider. Subclasses set the three endpoints + scope."""

    name = "oauth"
    authorize_endpoint = ""
    token_endpoint = ""
    userinfo_endpoint = ""
    scope = "openid email profile"

    def __init__(self, client_id: str, client_secret: str,
                 transport: Transport = urllib_transport):
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = transport

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urllib.parse.urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "state": state,
        })
        return f"{self.authorize_endpoint}?{query}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode()
        return self._http("POST", self.token_endpoint,
                          {"Content-Type": "application/x-www-form-urlencoded",
                           "Accept": "application/json"}, body)

    def fetch_userinfo(self, access_token: str) -> dict:
        return self._http("GET", self.userinfo_endpoint,
                          {"Authorization": f"Bearer {access_token}"}, None)

    def login(self, code: str, redirect_uri: str) -> dict:
        """Run the full flow; return ``{'subject', 'email'}``."""
        tokens = self.exchange_code(code, redirect_uri)
        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("token exchange did not return an access_token")
        info = self.fetch_userinfo(access_token)
        subject = info.get("sub")
        email = info.get("email")
        if not subject or not email:
            raise ValueError("userinfo missing sub/email")
        return {"subject": str(subject), "email": str(email).lower()}


class GoogleProvider(OAuthProvider):
    name = "google"
    authorize_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    userinfo_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"


class MicrosoftProvider(OAuthProvider):
    name = "microsoft"
    authorize_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    userinfo_endpoint = "https://graph.microsoft.com/oidc/userinfo"


_PROVIDERS = {"google": GoogleProvider, "microsoft": MicrosoftProvider}


def providers_from_env(transport: Transport = urllib_transport) -> dict[str, OAuthProvider]:
    """Build the configured providers from env (GOOGLE_/MICROSOFT_ CLIENT_ID/SECRET)."""
    out: dict[str, OAuthProvider] = {}
    for name, cls in _PROVIDERS.items():
        cid = os.environ.get(f"{name.upper()}_CLIENT_ID")
        secret = os.environ.get(f"{name.upper()}_CLIENT_SECRET")
        if cid and secret:
            out[name] = cls(cid, secret, transport)
    return out
