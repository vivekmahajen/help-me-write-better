"""DB-env resolution: recognise Vercel/Neon POSTGRES_URL, fall back to SQLite."""

import importlib

from write_better import dbenv


def test_explicit_urls_win():
    assert dbenv.resolve_db_url({"WB_DB_URL": "postgres://h/db"}) == "postgres://h/db"
    assert dbenv.resolve_db_url({"DATABASE_URL": "postgresql://h/db"}) == "postgresql://h/db"


def test_vercel_neon_postgres_url_is_detected():
    # Vercel Postgres / Neon set POSTGRES_URL (not DATABASE_URL) by default.
    env = {"POSTGRES_URL": "postgres://u:p@h/db?sslmode=require"}
    assert dbenv.has_persistent_db(env) is True
    assert dbenv.resolve_db_url(env) == "postgres://u:p@h/db?sslmode=require"


def test_non_pooling_preferred_over_pooled():
    env = {"POSTGRES_URL": "postgres://pooled/db",
           "POSTGRES_URL_NON_POOLING": "postgres://direct/db"}
    assert dbenv.resolve_db_url(env) == "postgres://direct/db"


def test_sqlite_path_is_not_persistent():
    assert dbenv.has_persistent_db({}) is False
    assert dbenv.has_persistent_db({"WB_DB_PATH": "wb.db"}) is False
    assert dbenv.resolve_db_url({"WB_DB_PATH": "/tmp/x.db"}) == "/tmp/x.db"


def test_non_postgres_url_ignored():
    # A stray non-postgres value doesn't count as persistent.
    assert dbenv.has_persistent_db({"DATABASE_URL": "mysql://h/db"}) is False


def test_features_platform_auto_enables_with_db(monkeypatch):
    # With a Postgres URL present, the platform feature (Log in link, sections)
    # turns on without needing WB_FEATURE_PLATFORM.
    monkeypatch.setenv("POSTGRES_URL", "postgres://u:p@h/db")
    monkeypatch.delenv("WB_FEATURE_PLATFORM", raising=False)
    features = importlib.reload(importlib.import_module("write_better.features"))
    try:
        assert features.FEATURES_LIVE["platform"] is True
    finally:
        monkeypatch.undo()
        importlib.reload(features)   # restore default (no DB) for other tests
