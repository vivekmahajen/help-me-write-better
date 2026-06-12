"""Top-level Vercel entrypoint — exposes the Write Better app over HTTP.

Vercel's native Python builder auto-detects a top-level ``app.py`` and serves the
module-level ``app`` (a WSGI application) for all routes.

Which app is served depends on whether a *persistent* database is configured:

  * a Postgres URL in the environment (``WB_DB_URL`` / ``DATABASE_URL`` /
    ``POSTGRES_URL`` …) -> the full platform (``platform.wsgi``): accounts +
    login at ``/auth/*``, the metered gateway at ``/v1/*``, billing at
    ``/billing/*``, and the landing/editor for everything else. This is what
    makes login (and the admin account) work.
  * otherwise -> the engine-only app (landing, ``/app``, ``/demo``, the JSON
    API). Serverless filesystems are ephemeral, so SQLite isn't durable here;
    we don't pretend accounts work without a real database.

``GET /_status`` returns a small JSON diagnostic (no secrets) so you can see, on
the live deployment, which mode is active and — if the platform failed to start
— why.

The package uses a src-layout, so we make it importable two ways for robustness:
prefer a bundled ``src/`` tree if present, otherwise fall back to the installed
package.
"""

import json
import os
import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


from write_better.dbenv import PG_ENV_VARS, has_persistent_db, is_postgres_url  # noqa: E402

_has_persistent_db = has_persistent_db  # backwards-compatible alias

# Filled in by _select_app(): a secrets-free snapshot of how routing was decided.
_DIAG: dict = {}


def _diagnostics(env=os.environ) -> dict:
    """A secrets-free view of the deploy config (env var *names* only)."""
    present = [v for v in PG_ENV_VARS if is_postgres_url(env.get(v))]
    return {
        "persistent_db_detected": bool(present),
        "db_source_env": present[0] if present else None,
        "postgres_env_present": present,
        "anthropic_key_present": bool(env.get("ANTHROPIC_API_KEY")),
        "base_url": env.get("WB_BASE_URL") or None,
    }


def _select_app():
    """The full platform when a Postgres DB is configured, else engine-only.

    If a database *is* configured but the platform can't start (driver missing,
    DB unreachable), fall back to the engine app and record why — a working
    marketing site beats a white-screened deploy, and the reason shows in
    ``/_status`` and the logs.
    """
    _DIAG.update(_diagnostics())
    if _has_persistent_db():
        try:
            from write_better.platform.wsgi import app as selected  # full platform
            _DIAG["mode"] = "platform"
            return selected
        except Exception as exc:  # pragma: no cover - deploy-time/driver issues
            _DIAG["mode"] = "engine"
            _DIAG["platform_error"] = f"{type(exc).__name__}: {exc}"
            sys.stderr.write(
                f"[app] database configured but platform failed to start "
                f"({exc!r}); serving engine-only. Check psycopg is installed and "
                f"the DB is reachable.\n"
            )
    else:
        _DIAG["mode"] = "engine"
    from write_better.web import app as selected                  # engine-only
    return selected


def _make_app(selected):
    """Wrap the selected WSGI app with a ``GET /_status`` diagnostic route."""
    def app(environ, start_response):
        if (environ.get("REQUEST_METHOD", "GET").upper() == "GET"
                and (environ.get("PATH_INFO", "/") or "/").rstrip("/") == "/_status"):
            body = json.dumps(_DIAG).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Access-Control-Allow-Origin", "*"),
            ])
            return [body]
        return selected(environ, start_response)
    return app


# Top-level binding so Vercel's static entrypoint scan finds ``app`` (a nested
# import inside an if/else is invisible to it).
app = _make_app(_select_app())

__all__ = ["app", "_has_persistent_db", "_select_app", "_diagnostics", "_DIAG"]
