"""M3xA Souls v3 — layered, classifier-routed soul composition."""
from .tokens import estimate_tokens
from .router import route
from .assembler import assemble

__all__ = ["estimate_tokens", "route", "assemble"]
__version__ = "3.0.0"
