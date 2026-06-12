"""Database backend selection: SQLite (default) or PostgreSQL.

``open_connection(path_or_url)`` returns a connection that quacks like the stdlib
``sqlite3`` connection the ``Store`` DAO already uses, so the **SQLite path is
unchanged** (a real ``sqlite3.Connection``) and PostgreSQL is a drop-in shim — no
changes to the dozens of DAO methods.

Postgres needs ``psycopg`` (optional): ``pip install 'help-me-write-better[postgres]'``.
Select it by pointing ``WB_DB_URL`` / ``WB_DB_PATH`` at a ``postgres://…`` URL.

The SQL dialect differences are handled here (placeholders ``?``→``%s``,
``AUTOINCREMENT``→``BIGSERIAL``, ``INSERT OR IGNORE``→``ON CONFLICT DO NOTHING``,
``lastrowid`` via ``RETURNING id``, and ``PRAGMA`` → ``information_schema``).
"""

from __future__ import annotations

import re
import sqlite3

from ..dbenv import is_postgres_url  # noqa: F401  (re-exported; single source of truth)


def open_connection(path: str):
    """A sqlite3-compatible connection for ``path`` (file/``:memory:`` or PG URL)."""
    if is_postgres_url(path):
        return _PgConnection(str(path))
    return sqlite3.connect(path, check_same_thread=False)


# --- SQL translation (pure, unit-tested) --------------------------------------

def translate(sql: str) -> str:
    """Rewrite the SQLite SQL the DAO emits into PostgreSQL."""
    s = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    if s.lstrip().upper().startswith("INSERT OR IGNORE"):
        s = re.sub(r"^(\s*)INSERT OR IGNORE", r"\1INSERT", s, flags=re.IGNORECASE)
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return s.replace("?", "%s")


def wants_returning_id(sql: str) -> bool:
    """A plain INSERT into an id-keyed table — needs RETURNING id for lastrowid."""
    u = sql.lstrip().upper()
    if not u.startswith("INSERT INTO") or "ON CONFLICT" in u or "RETURNING" in u:
        return False
    m = re.match(r"\s*INSERT INTO\s+(\w+)", sql, re.IGNORECASE)
    table = m.group(1).lower() if m else ""
    return table != "preferences"  # preferences has no `id` column


# --- Postgres shim (imported lazily so SQLite users need no driver) -----------

class _NullCursor:
    lastrowid = None

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _ResultCursor:
    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class _PgConnection:
    """Minimal sqlite3.Connection-compatible wrapper over a psycopg connection."""

    row_factory = None  # accepted + ignored (psycopg returns dict rows)

    def __init__(self, url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - exercised only with PG configured
            raise RuntimeError(
                "PostgreSQL support requires psycopg: "
                "pip install 'help-me-write-better[postgres]'"
            ) from exc
        self._conn = psycopg.connect(url, row_factory=dict_row, autocommit=False)

    def execute(self, sql: str, params=()):
        up = sql.strip().upper()
        if up.startswith("PRAGMA FOREIGN_KEYS"):
            return _NullCursor()
        if up.startswith("PRAGMA TABLE_INFO"):
            table = re.search(r"\((\w+)\)", sql).group(1)
            cur = self._conn.cursor()
            cur.execute("SELECT column_name AS name FROM information_schema.columns "
                        "WHERE table_name = %s", (table,))
            return _ResultCursor(cur)

        s = translate(sql)
        wants = wants_returning_id(s)
        if wants:
            s = s.rstrip().rstrip(";") + " RETURNING id"
        cur = self._conn.cursor()
        # Only bind when there are params. Passing an empty sequence makes psycopg
        # parse the SQL for placeholders, which misfires on a literal `%`/`%s`
        # (e.g. a `?` that `translate` rewrote inside a DDL comment) — "N
        # placeholders but 0 parameters". DDL has no params, so send it verbatim.
        if params:
            cur.execute(s, tuple(params))
        else:
            cur.execute(s)
        last = None
        if wants:
            row = cur.fetchone()
            last = row["id"] if row else None
        return _ResultCursor(cur, lastrowid=last)

    def executescript(self, script: str):
        # Strip `--` line comments before splitting on `;`: a comment may itself
        # contain a semicolon (e.g. "tied to the plan; the shared guide…"), which
        # would otherwise split mid-comment and leave invalid SQL. (SQLite's
        # native executescript parses SQL; this shim splits, so it must not be
        # fooled by punctuation inside comments.)
        cleaned = re.sub(r"--[^\n]*", "", script)
        for stmt in cleaned.split(";"):
            if stmt.strip():
                self.execute(stmt)
        return _NullCursor()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()
