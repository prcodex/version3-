from __future__ import annotations
import pathlib
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PRODUCTS = ("m3xa", "m3xabr")


def load_routing(product: str) -> dict:
    if product not in PRODUCTS:
        raise ValueError(f"unknown product: {product!r} (valid: {PRODUCTS})")
    with open(REPO_ROOT / product / "routing.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
