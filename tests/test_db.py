import pytest

from write_better.platform import db
from write_better.platform.store import Store


# --- routing ------------------------------------------------------------------

def test_is_postgres_url():
    assert db.is_postgres_url("postgres://u:p@h/db")
    assert db.is_postgres_url("postgresql://h/db")
    assert not db.is_postgres_url("wb.db")
    assert not db.is_postgres_url(":memory:")


def test_open_connection_sqlite_is_native():
    conn = db.open_connection(":memory:")
    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_open_connection_postgres_without_driver_errors():
    # psycopg isn't installed in CI -> a clear, actionable error (not ImportError).
    try:
        import psycopg  # noqa: F401
        pytest.skip("psycopg is installed")
    except ImportError:
        pass
    with pytest.raises(RuntimeError, match="psycopg"):
        db.open_connection("postgresql://localhost/x")


# --- SQL translation ----------------------------------------------------------

def test_translate_autoincrement_and_placeholders():
    out = db.translate("INSERT INTO users(email) VALUES (?)")
    assert out == "INSERT INTO users(email) VALUES (%s)"
    ddl = db.translate("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, x TEXT)")
    assert "BIGSERIAL PRIMARY KEY" in ddl and "AUTOINCREMENT" not in ddl


def test_translate_insert_or_ignore():
    out = db.translate("INSERT OR IGNORE INTO oauth_identities(provider, subject) VALUES (?,?)")
    assert out.startswith("INSERT INTO oauth_identities")
    assert out.rstrip().endswith("ON CONFLICT DO NOTHING")
    assert "%s" in out and "?" not in out


def test_wants_returning_id():
    assert db.wants_returning_id("INSERT INTO users(email) VALUES (%s)")
    assert db.wants_returning_id("INSERT INTO documents(title) VALUES (%s)")
    # upserts and conflict-inserts must not append RETURNING id
    assert not db.wants_returning_id("INSERT INTO preferences(user_id, data) VALUES (%s,%s) "
                                     "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data")
    assert not db.wants_returning_id("INSERT INTO oauth_identities(...) VALUES (%s) ON CONFLICT DO NOTHING")
    # preferences has no id column
    assert not db.wants_returning_id("INSERT INTO preferences(user_id, data) VALUES (%s,%s)")
    assert not db.wants_returning_id("SELECT * FROM users")


# --- the SQLite path is unchanged (sanity: Store still round-trips) -----------

def test_store_still_works_on_sqlite(tmp_path):
    store = Store(str(tmp_path / "wb.db"))
    from write_better.platform import accounts
    u = accounts.create_user(store, "a@b.com", "supersecret")
    assert store.get_user(u["id"])["email"] == "a@b.com"
    store.close()


# --- Postgres shim: param binding (no live PG needed) -------------------------

class _FakeCursor:
    _SENTINEL = object()

    def __init__(self):
        self.calls = []

    def execute(self, sql, params=_SENTINEL):
        self.calls.append((sql, params))

    def fetchone(self):
        return {"id": 1}

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()

    def cursor(self):
        return self.cur


def _shim_with(fake):
    conn = db._PgConnection.__new__(db._PgConnection)  # skip __init__ (no psycopg)
    conn._conn = fake
    return conn


def test_paramless_ddl_is_sent_without_params():
    # A `?` rewritten to `%s` inside a DDL comment must NOT be handed to psycopg
    # as a placeholder — param-less statements are sent verbatim.
    fake = _FakeConn()
    shim = _shim_with(fake)
    shim.execute("CREATE TABLE t (premium INTEGER) -- a generation?")
    sql, params = fake.cur.calls[-1]
    assert params is _FakeCursor._SENTINEL          # called as execute(sql), no params
    assert "%s" in sql                              # the comment's ? was translated...
    # ...but since no params are bound, psycopg treats it as literal SQL.


def test_parameterized_query_still_binds():
    fake = _FakeConn()
    shim = _shim_with(fake)
    shim.execute("SELECT * FROM users WHERE email = ?", ("a@b.com",))
    sql, params = fake.cur.calls[-1]
    assert sql == "SELECT * FROM users WHERE email = %s"
    assert params == ("a@b.com",)

