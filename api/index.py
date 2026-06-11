"""Vercel serverless entrypoint — exposes the Write Better engine as an HTTP API.

Vercel's Python runtime serves the module-level ``app`` (a WSGI application).
The package lives under ``src/`` (src-layout), so we put it on the path before
importing. The actual app lives in ``write_better.web`` so it stays unit-testable.
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from write_better.web import app  # noqa: E402

__all__ = ["app"]
