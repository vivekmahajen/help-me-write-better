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

import os
import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _has_persistent_db(env=os.environ) -> bool:
    """True when a managed database is configured (so accounts can persist)."""
    url = (env.get("WB_DB_URL") or env.get("DATABASE_URL") or "").strip()
    return url.startswith(("postgres://", "postgresql://"))


if _has_persistent_db():
    from write_better.platform.wsgi import app  # noqa: E402  (full platform)
else:
    from write_better.web import app  # noqa: E402  (engine-only)

__all__ = ["app", "_has_persistent_db"]
