"""Map classifier tags -> conditional modules for ONE product (routed upfront)."""
from __future__ import annotations
from .config import load_routing


def route(product: str, tags: list[str], routing: dict | None = None) -> list[dict]:
    """Return ordered list of matched conditional module dicts (file, structured_output?)."""
    cfg = routing or load_routing(product)
    tagset = {t.strip().lower() for t in tags if t.strip()}
    matched = []
    for name, mod in cfg["conditional"].items():
        if not mod.get("enabled", True):
            continue
        if tagset & {t.lower() for t in mod["tags"]}:
            matched.append((mod["priority"], {"name": name, **mod}))
    matched.sort(key=lambda x: x[0])
    cap = cfg.get("max_conditional", 2)
    return [m for _, m in matched[:cap]]


def pick_model(product: str, tags: list[str], routing: dict | None = None) -> str:
    cfg = routing or load_routing(product)
    models = cfg.get("models", {})
    overrides = models.get("overrides") or {}
    for t in tags:
        if t in overrides:
            return overrides[t]
    return models.get("default", "claude-haiku-4-5")
