from __future__ import annotations
import pathlib
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTING_FILE = REPO_ROOT / "routing" / "routing.yaml"


def load_routing(path: pathlib.Path | None = None) -> dict:
    with open(path or ROUTING_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
