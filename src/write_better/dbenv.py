"""Where the database lives — resolved from the environment, dependency-free.

One place decides whether a *persistent* (Postgres) database is configured, so
the Vercel entrypoint, the composed WSGI app, and the landing page's feature
gate all agree. Kept import-light (stdlib only, no package imports) so it can be
used from anywhere without import cycles.

Recognised, in priority order:
  WB_DB_URL, DATABASE_URL                     -- explicit
  POSTGRES_URL_NON_POOLING, POSTGRES_URL,     -- set by Vercel Postgres / Neon
  POSTGRES_PRISMA_URL
Falling back to a local SQLite file (WB_DB_PATH, default ``wb.db``), which is
NOT durable on serverless — so it never counts as a "persistent" database.
"""

from __future__ import annotations

import os

# Checked in order; the first that holds a postgres URL wins. NON_POOLING is
# preferred over the pooled URL for the long-lived connection the Store opens.
PG_ENV_VARS = (
    "WB_DB_URL",
    "DATABASE_URL",
    "POSTGRES_URL_NON_POOLING",
    "POSTGRES_URL",
    "POSTGRES_PRISMA_URL",
)


def is_postgres_url(value: str | None) -> bool:
    return str(value or "").startswith(("postgres://", "postgresql://"))


def resolve_db_url(env=None) -> str:
    """The configured Postgres URL, else a local SQLite path (``wb.db``)."""
    env = os.environ if env is None else env
    for var in PG_ENV_VARS:
        val = (env.get(var) or "").strip()
        if is_postgres_url(val):
            return val
    return (env.get("WB_DB_PATH") or "wb.db").strip()


def has_persistent_db(env=None) -> bool:
    """True when a managed Postgres database is configured (accounts can persist)."""
    return is_postgres_url(resolve_db_url(env))
