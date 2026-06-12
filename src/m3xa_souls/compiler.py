"""Materialize compiled monolith souls per PRODUCT for single-file Gateway mode.

dist/soul_m3xa_compiled.md and dist/soul_m3xabr_compiled.md include all
ENABLED conditional modules. With Bedrock 1h prompt caching, the compiled
monolith is byte-identical across queries => fully cacheable static prefix:
cache write once per hour, reads at ~0.1x input price afterwards.
"""
from __future__ import annotations
import argparse
import pathlib

from .assembler import assemble
from .config import PRODUCTS, load_routing


def compile_product(product: str, out_dir: pathlib.Path) -> pathlib.Path:
    cfg = load_routing(product)
    all_tags = sorted({t for m in cfg["conditional"].values()
                       if m.get("enabled", True) for t in m["tags"]})
    cfg_all = dict(cfg)
    cfg_all["max_conditional"] = len(cfg["conditional"])
    prompt, report = assemble(product, all_tags, include_data_placeholder=False, routing=cfg_all)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"soul_{product}_compiled.md"
    header = (
        f"<!-- COMPILED by m3xa_souls.compiler — DO NOT EDIT BY HAND.\n"
        f"     Product: {product}. Source: {product}/souls/. ~{report.total_tokens} tokens.\n"
        f"     Cache: mark this entire block with cache_control ephemeral ttl=1h. -->\n\n"
    )
    out.write_text(header + prompt, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("dist"))
    args = ap.parse_args()
    for product in PRODUCTS:
        print(f"compiled {compile_product(product, args.out)}")


if __name__ == "__main__":
    main()
