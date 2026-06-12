"""Top-level Vercel entrypoint — exposes the Write Better app over HTTP.

Vercel's native Python builder auto-detects a top-level ``app.py`` and serves the
module-level ``app`` (a WSGI application) for all routes.

Which app is served depends on whether a *persistent* database is configured:

  * ``DATABASE_URL`` / ``WB_DB_URL`` set (a ``postgres://`` URL)  -> the full
    platform (``platform.wsgi``): accounts + login at ``/auth/*``, the metered
    gateway at ``/v1/*``, billing at ``/billing/*``, and the landing/editor for
    everything else. This is what makes login (and the admin account) work.
  * otherwise -> the engine-only app (landing, ``/app``, ``/demo``, the JSON
    API). Serverless filesystems are ephemeral, so SQLite isn't durable here;
    we don't pretend accounts work without a real database.

The package uses a src-layout, so we make it importable two ways for robustness:
prefer a bundled ``src/`` tree if present, otherwise fall back to the installed
package.
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


from write_better.dbenv import has_persistent_db as _has_persistent_db  # noqa: E402


def _select_app():
    """The full platform when a Postgres DB is configured, else engine-only.

    If a database *is* configured but the platform can't start (driver missing,
    DB unreachable), fall back to the engine app and log why — a working
    marketing site beats a white-screened deploy, and the reason shows in logs.
    """
    if _has_persistent_db():
        try:
            from write_better.platform.wsgi import app as selected  # full platform
            return selected
        except Exception as exc:  # pragma: no cover - deploy-time/driver issues
            sys.stderr.write(
                f"[app] database configured but platform failed to start "
                f"({exc!r}); serving engine-only. Check psycopg is installed and "
                f"the DB is reachable.\n"
            )
    from write_better.web import app as selected                  # engine-only
    return selected


# Top-level binding so Vercel's static entrypoint scan finds ``app`` (a nested
# import inside an if/else is invisible to it).
app = _select_app()

__all__ = ["app", "_has_persistent_db", "_select_app"]
