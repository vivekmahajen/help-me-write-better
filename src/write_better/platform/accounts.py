"""Accounts: password hashing and API-key issuance/authentication.

Stdlib crypto only. Passwords use PBKDF2-HMAC-SHA256 with a per-user salt; API
keys are random tokens stored only as a SHA-256 hash (shown to the user once).
OAuth (Google/Microsoft) is a later phase — the schema already allows a null
password for OAuth-only users.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

from .store import Store

_PBKDF2_ITERATIONS = 120_000
_KEY_PREFIX = "wbk_"


# --- passwords ----------------------------------------------------------------

def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: Optional[str]) -> bool:
    if not encoded:
        return False
    try:
        algo, iters, salt_hex, hash_hex = encoded.split("$")
        assert algo == "pbkdf2_sha256"
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
    except (ValueError, AssertionError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# --- users --------------------------------------------------------------------

def create_user(store: Store, email: str, password: str, plan: str = "free") -> dict:
    if store.get_user_by_email(email):
        raise ValueError(f"a user with email {email!r} already exists")
    return store.insert_user(email, hash_password(password), plan)


def verify_login(store: Store, email: str, password: str) -> Optional[dict]:
    user = store.get_user_by_email(email)
    if user and verify_password(password, user.get("password_hash")):
        return user
    return None


# --- api keys -----------------------------------------------------------------

def _hash_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_api_key(store: Store, user_id: int, name: str = "default") -> tuple[str, dict]:
    """Create a key. Returns ``(plaintext_token, key_record)``.

    The plaintext is shown to the user ONCE and never stored — only its hash is.
    """
    token = _KEY_PREFIX + secrets.token_hex(24)
    record = store.insert_api_key(user_id, name, prefix=token[:12], key_hash=_hash_key(token))
    return token, record


def authenticate_key(store: Store, token: Optional[str]) -> Optional[dict]:
    """Resolve an API key token to its owning user, or None. Updates last_used."""
    if not token or not token.startswith(_KEY_PREFIX):
        return None
    record = store.get_api_key_by_hash(_hash_key(token))
    if not record:
        return None
    store.touch_api_key(record["id"])
    return store.get_user(record["user_id"])
