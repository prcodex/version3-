"""Map classifier tags -> conditional modules, honoring priority and cap."""
from __future__ import annotations
from .config import load_routing


def route(locale: str, tags: list[str], routing: dict | None = None) -> list[str]:
    """Return ordered list of conditional module file paths for this query."""
    cfg = routing or load_routing()
    if locale not in cfg["locales"]:
        raise ValueError(f"unknown locale: {locale!r} (valid: {cfg['locales']})")
    tagset = {t.strip().lower() for t in tags if t.strip()}
    matched = []
    for name, mod in cfg["conditional"].items():
        if "locales" in mod and locale not in mod["locales"]:
            continue
        if tagset & {t.lower() for t in mod["tags"]}:
            matched.append((mod["priority"], mod["file"]))
    matched.sort()
    cap = cfg.get("max_conditional", 2)
    return [f for _, f in matched[:cap]]
