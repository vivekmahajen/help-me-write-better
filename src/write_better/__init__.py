"""Write Better + Format — a bundled writing and formatting engine built on Claude.

Public API:
    from write_better import improve, Request
    result = improve(Request(text="...", services=["tighten"]))
"""

from .modes import MODES, Mode, resolve_services
from .engine import Request, Result, improve, route_model

__all__ = [
    "MODES",
    "Mode",
    "resolve_services",
    "Request",
    "Result",
    "improve",
    "route_model",
]

__version__ = "0.1.0"
