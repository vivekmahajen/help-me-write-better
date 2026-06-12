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

from ..plans import is_admin
from .store import Store

_PBKDF2_ITERATIONS = 120_000
_KEY_PREFIX = "wbk_"
_SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days
_RESET_TTL_SECONDS = 3600              # password-reset link valid for 1 hour


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
    # Owner/admin accounts start on the top tier for a complete UI; their caps
    # are lifted entirely at enforcement time regardless of the stored plan.
    if plan == "free" and is_admin(email):
        plan = "business"
    return store.insert_user(email, hash_password(password), plan)


def verify_login(store: Store, email: str, password: str) -> Optional[dict]:
    user = store.get_user_by_email(email)
    if user and verify_password(password, user.get("password_hash")):
        return user
    return None


# --- password reset (email flow) ---------------------------------------------

def create_password_reset(store: Store, email: str) -> tuple[Optional[str], Optional[dict]]:
    """Issue a single-use reset token for ``email`` if such a user exists.

    Returns ``(token, user)`` or ``(None, None)`` when there's no such user. The
    caller emails the token and ALWAYS responds the same way, so the endpoint
    never reveals whether an address is registered.
    """
    user = store.get_user_by_email(email)
    if not user:
        return None, None
    token = secrets.token_hex(24)
    store.insert_password_reset(user["id"], _hash_key(token), _RESET_TTL_SECONDS)
    return token, user


def reset_password(store: Store, token: Optional[str], new_password: str) -> Optional[dict]:
    """Consume a reset token and set a new password.

    Returns the user on success, or None if the token is missing/expired/used.
    Raises ``ValueError`` if the new password fails policy (too short) — the
    token is left unconsumed so the user can retry. Existing sessions are
    invalidated on success.
    """
    if not token:
        return None
    record = store.get_password_reset(_hash_key(token))
    if not record:
        return None
    encoded = hash_password(new_password)        # validates length; may raise ValueError
    store.set_password_hash(record["user_id"], encoded)
    store.use_password_reset(record["id"])
    store.delete_user_sessions(record["user_id"])
    return store.get_user(record["user_id"])


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


# --- sessions (web/desktop/mobile cookie auth) --------------------------------

def create_session(store: Store, user_id: int) -> str:
    """Create a session and return its opaque token (store keeps only a hash)."""
    token = secrets.token_hex(24)
    store.insert_session(user_id, _hash_key(token), _SESSION_TTL_SECONDS)
    return token


def authenticate_session(store: Store, token: Optional[str]) -> Optional[dict]:
    """Resolve a session token to its user, or None if missing/expired."""
    if not token:
        return None
    return store.get_session_user(_hash_key(token))


def destroy_session(store: Store, token: Optional[str]) -> None:
    if token:
        store.delete_session(_hash_key(token))


# --- OAuth account linking ----------------------------------------------------

def get_or_create_oauth_user(store: Store, provider: str, subject: str,
                             email: str) -> dict:
    """Find the user for this OAuth identity, linking or creating as needed.

    Resolution: (1) existing identity -> that user; (2) existing email -> link
    the identity to it; (3) otherwise create a passwordless user and link.
    """
    user = store.get_user_by_oauth(provider, subject)
    if user:
        return user
    user = store.get_user_by_email(email)
    if user is None:
        user = store.insert_user(email, password_hash=None)  # passwordless (OAuth-only)
    store.link_oauth_identity(user["id"], provider, subject)
    return user
