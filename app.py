"""Top-level Vercel entrypoint — exposes the Write Better engine as an HTTP app.

Vercel's native Python builder auto-detects a top-level ``app.py`` and serves the
module-level ``app`` (a WSGI application) for all routes.

The package uses a src-layout, so we make it importable two ways for robustness:
prefer a bundled ``src/`` tree if present, otherwise fall back to the installed
package (the operator prompt ships as package data in both cases).
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from write_better.web import app  # noqa: E402

__all__ = ["app"]
