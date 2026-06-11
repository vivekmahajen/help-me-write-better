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
    output_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_usage_user_ts ON usage_events(user_id, ts);
"""


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
                     input_tokens: int, output_tokens: int, ts: Optional[int] = None) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usage_events(user_id, ts, services, model, premium, "
                "input_tokens, output_tokens) VALUES (?,?,?,?,?,?,?)",
                (user_id, ts or int(time.time()), services, model,
                 1 if premium else 0, input_tokens, output_tokens),
            )
            self._conn.commit()
            return self._row("usage_events", cur.lastrowid)

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

    # --- internal ------------------------------------------------------------

    def _row(self, table: str, row_id: Any) -> Optional[dict]:
        row = self._conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)  # table is internal, not user input
        ).fetchone()
        return dict(row) if row else None
