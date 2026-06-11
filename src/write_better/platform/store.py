"""SQLite-backed storage for the platform layer.

Stdlib-only (``sqlite3``), to match the repo's zero-framework style. The schema
is the data model from the spec (#6): users, api_keys, and usage_events (which
double as the metering + analytics event log). Saved documents/versions are a
later phase; this slice persists identity + metering, never document bodies.

For production you'd point this at a managed Postgres (serverless filesystems are
ephemeral); the DAO surface here is deliberately small so the backend can be
swapped without touching callers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT,                          -- null for OAuth-only (later)
    plan          TEXT NOT NULL DEFAULT 'free',
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    name         TEXT NOT NULL DEFAULT 'default',
    prefix       TEXT NOT NULL,                  -- shown in UI, e.g. wbk_ab12cd34
    key_hash     TEXT UNIQUE NOT NULL,           -- sha256 of the full key
    created_at   INTEGER NOT NULL,
    last_used_at INTEGER,
    revoked      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usage_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    ts            INTEGER NOT NULL,
    services      TEXT NOT NULL,                 -- comma-separated service names
    model         TEXT NOT NULL,
    premium       INTEGER NOT NULL DEFAULT 0,    -- consumed a premium generation?
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    words         INTEGER NOT NULL DEFAULT 0,    -- analytics: words in the input
    suggestions   INTEGER NOT NULL DEFAULT 0,    -- analytics: issues found (check)
    issue_types   TEXT NOT NULL DEFAULT '{}'     -- analytics: {type: count} JSON
);
CREATE INDEX IF NOT EXISTS ix_usage_user_ts ON usage_events(user_id, ts);

-- Saved documents. Bodies live ONLY here, and ONLY when a user explicitly saves
-- (default behaviour stores no document text — see metering/history).
CREATE TABLE IF NOT EXISTS documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL DEFAULT 'Untitled',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_documents_user ON documents(user_id);

CREATE TABLE IF NOT EXISTS document_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    content     TEXT NOT NULL,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_versions_doc ON document_versions(document_id);

-- Synced per-user preferences (default tone/audience/dialect, etc.) as a JSON blob.
CREATE TABLE IF NOT EXISTS preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    data    TEXT NOT NULL DEFAULT '{}'
);

-- Web/desktop/mobile sessions (cookie-based). Stored as a hash of the token.
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT UNIQUE NOT NULL,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);

-- Linked OAuth identities (Google/Microsoft). One row per (provider, subject).
CREATE TABLE IF NOT EXISTS oauth_identities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    provider   TEXT NOT NULL,
    subject    TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(provider, subject)
);
"""

# Columns added after the initial release; applied as idempotent migrations.
_MIGRATIONS = [
    ("users", "stripe_customer_id", "TEXT"),
    ("usage_events", "words", "INTEGER NOT NULL DEFAULT 0"),
    ("usage_events", "suggestions", "INTEGER NOT NULL DEFAULT 0"),
    ("usage_events", "issue_types", "TEXT NOT NULL DEFAULT '{}'"),
]


class Store:
    """A thin DAO over a SQLite database. One connection, guarded by a lock."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Add columns introduced after the initial release (idempotent)."""
        for table, column, decl in _MIGRATIONS:
            cols = {r["name"] for r in
                    self._conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- users ---------------------------------------------------------------

    def insert_user(self, email: str, password_hash: Optional[str],
                    plan: str = "free") -> dict:
        email = email.strip().lower()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO users(email, password_hash, plan, created_at) "
                "VALUES (?,?,?,?)",
                (email, password_hash, plan, int(time.time())),
            )
            self._conn.commit()
            return self._row("users", cur.lastrowid)

    def get_user(self, user_id: int) -> Optional[dict]:
        return self._row("users", user_id)

    def get_user_by_email(self, email: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def set_plan(self, user_id: int, plan: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
            self._conn.commit()

    # --- api keys ------------------------------------------------------------

    def insert_api_key(self, user_id: int, name: str, prefix: str, key_hash: str) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO api_keys(user_id, name, prefix, key_hash, created_at) "
                "VALUES (?,?,?,?,?)",
                (user_id, name, prefix, key_hash, int(time.time())),
            )
            self._conn.commit()
            return self._row("api_keys", cur.lastrowid)

    def get_api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0", (key_hash,)
        ).fetchone()
        return dict(row) if row else None

    def touch_api_key(self, key_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (int(time.time()), key_id),
            )
            self._conn.commit()

    def revoke_api_key(self, key_id: int) -> None:
        with self._lock:
            self._conn.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
            self._conn.commit()

    def list_api_keys(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM api_keys WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # --- usage events --------------------------------------------------------

    def insert_usage(self, user_id: int, services: str, model: str, premium: bool,
                     input_tokens: int, output_tokens: int, ts: Optional[int] = None,
                     words: int = 0, suggestions: int = 0,
                     issue_types: Optional[dict] = None) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usage_events(user_id, ts, services, model, premium, "
                "input_tokens, output_tokens, words, suggestions, issue_types) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (user_id, ts or int(time.time()), services, model,
                 1 if premium else 0, input_tokens, output_tokens,
                 words, suggestions, json.dumps(issue_types or {})),
            )
            self._conn.commit()
            return self._row("usage_events", cur.lastrowid)

    def events_between(self, user_id: int, since_ts: int,
                       until_ts: Optional[int] = None) -> list[dict]:
        """Raw events in [since_ts, until_ts) for analytics aggregation."""
        if until_ts is None:
            rows = self._conn.execute(
                "SELECT ts, services, model, premium, input_tokens, output_tokens, "
                "words, suggestions, issue_types FROM usage_events "
                "WHERE user_id = ? AND ts >= ? ORDER BY ts",
                (user_id, since_ts),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT ts, services, model, premium, input_tokens, output_tokens, "
                "words, suggestions, issue_types FROM usage_events "
                "WHERE user_id = ? AND ts >= ? AND ts < ? ORDER BY ts",
                (user_id, since_ts, until_ts),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_premium_since(self, user_id: int, since_ts: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM usage_events "
            "WHERE user_id = ? AND premium = 1 AND ts >= ?",
            (user_id, since_ts),
        ).fetchone()
        return int(row["n"])

    def usage_since(self, user_id: int, since_ts: int) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS calls, "
            "       COALESCE(SUM(premium),0) AS premium_calls, "
            "       COALESCE(SUM(input_tokens),0) AS input_tokens, "
            "       COALESCE(SUM(output_tokens),0) AS output_tokens "
            "FROM usage_events WHERE user_id = ? AND ts >= ?",
            (user_id, since_ts),
        ).fetchone()
        return dict(row)

    def history(self, user_id: int, limit: int = 50) -> list[dict]:
        """Recent per-request history (metadata only — no document bodies)."""
        rows = self._conn.execute(
            "SELECT id, ts, services, model, premium, input_tokens, output_tokens "
            "FROM usage_events WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(limit, 500))),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- documents -----------------------------------------------------------

    def _owns_document(self, user_id: int, document_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        return row is not None

    def create_document(self, user_id: int, title: str, content: str) -> dict:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO documents(user_id, title, created_at, updated_at) "
                "VALUES (?,?,?,?)",
                (user_id, title or "Untitled", now, now),
            )
            doc_id = cur.lastrowid
            self._conn.execute(
                "INSERT INTO document_versions(document_id, user_id, content, created_at) "
                "VALUES (?,?,?,?)",
                (doc_id, user_id, content, now),
            )
            self._conn.commit()
        return self.get_document(user_id, doc_id)

    def add_document_version(self, user_id: int, document_id: int,
                             content: str) -> Optional[dict]:
        if not self._owns_document(user_id, document_id):
            return None
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "INSERT INTO document_versions(document_id, user_id, content, created_at) "
                "VALUES (?,?,?,?)",
                (document_id, user_id, content, now),
            )
            self._conn.execute(
                "UPDATE documents SET updated_at = ? WHERE id = ?", (now, document_id)
            )
            self._conn.commit()
        return self.get_document(user_id, document_id)

    def rename_document(self, user_id: int, document_id: int, title: str) -> Optional[dict]:
        if not self._owns_document(user_id, document_id):
            return None
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET title = ?, updated_at = ? WHERE id = ?",
                (title or "Untitled", int(time.time()), document_id),
            )
            self._conn.commit()
        return self.get_document(user_id, document_id)

    def delete_document(self, user_id: int, document_id: int) -> bool:
        if not self._owns_document(user_id, document_id):
            return False
        with self._lock:
            self._conn.execute(
                "DELETE FROM document_versions WHERE document_id = ?", (document_id,)
            )
            self._conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self._conn.commit()
        return True

    def list_documents(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT d.id, d.title, d.created_at, d.updated_at, "
            "       COUNT(v.id) AS versions "
            "FROM documents d LEFT JOIN document_versions v ON v.document_id = d.id "
            "WHERE d.user_id = ? GROUP BY d.id ORDER BY d.updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_document(self, user_id: int, document_id: int) -> Optional[dict]:
        doc = self._conn.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        if not doc:
            return None
        latest = self._conn.execute(
            "SELECT id, content, created_at FROM document_versions "
            "WHERE document_id = ? ORDER BY id DESC LIMIT 1",
            (document_id,),
        ).fetchone()
        count = self._conn.execute(
            "SELECT COUNT(*) AS n FROM document_versions WHERE document_id = ?",
            (document_id,),
        ).fetchone()["n"]
        result = dict(doc)
        result["content"] = latest["content"] if latest else ""
        result["latest_version_id"] = latest["id"] if latest else None
        result["versions"] = int(count)
        return result

    def list_document_versions(self, user_id: int, document_id: int) -> Optional[list[dict]]:
        if not self._owns_document(user_id, document_id):
            return None
        rows = self._conn.execute(
            "SELECT id, content, created_at FROM document_versions "
            "WHERE document_id = ? ORDER BY id DESC",
            (document_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- preferences ---------------------------------------------------------

    def get_preferences(self, user_id: int) -> dict:
        row = self._conn.execute(
            "SELECT data FROM preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["data"])
        except (ValueError, TypeError):
            return {}

    def set_preferences(self, user_id: int, data: dict) -> dict:
        blob = json.dumps(data)
        with self._lock:
            self._conn.execute(
                "INSERT INTO preferences(user_id, data) VALUES (?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
                (user_id, blob),
            )
            self._conn.commit()
        return data

    # --- sessions ------------------------------------------------------------

    def insert_session(self, user_id: int, token_hash: str, ttl_seconds: int) -> dict:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions(user_id, token_hash, created_at, expires_at) "
                "VALUES (?,?,?,?)",
                (user_id, token_hash, now, now + ttl_seconds),
            )
            self._conn.commit()
            return self._row("sessions", cur.lastrowid)

    def get_session_user(self, token_hash: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (token_hash, int(time.time())),
        ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            self._conn.commit()

    # --- oauth identities ----------------------------------------------------

    def get_user_by_oauth(self, provider: str, subject: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT u.* FROM oauth_identities o JOIN users u ON u.id = o.user_id "
            "WHERE o.provider = ? AND o.subject = ?",
            (provider, subject),
        ).fetchone()
        return dict(row) if row else None

    def link_oauth_identity(self, user_id: int, provider: str, subject: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO oauth_identities(user_id, provider, subject, created_at) "
                "VALUES (?,?,?,?)",
                (user_id, provider, subject, int(time.time())),
            )
            self._conn.commit()

    # --- stripe customer mapping ---------------------------------------------

    def set_stripe_customer(self, user_id: int, customer_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (customer_id, user_id),
            )
            self._conn.commit()

    def get_user_by_stripe_customer(self, customer_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None

    # --- internal ------------------------------------------------------------

    def _row(self, table: str, row_id: Any) -> Optional[dict]:
        row = self._conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)  # table is internal, not user input
        ).fetchone()
        return dict(row) if row else None
