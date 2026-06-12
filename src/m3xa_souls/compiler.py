"""Materialize compiled monolith souls for single-file Gateway mode.

Until the Gateway supports multi-file assembly, CI compiles:
  dist/soul_global_compiled.md  (core + global overlay + examples + ALL
                                 global-eligible conditional modules + output)
  dist/soul_brazil_compiled.md

Compiled mode loses per-query routing (all modules always present) but
still benefits from dedup, positive rules, and position-aware ordering.
"""
from __future__ import annotations
import argparse
import pathlib

from .assembler import assemble
from .config import load_routing


def compile_locale(locale: str, out_dir: pathlib.Path) -> pathlib.Path:
    cfg = load_routing()
    all_tags = sorted({t for m in cfg["conditional"].values() for t in m["tags"]})
    cfg_all = dict(cfg)
    cfg_all["max_conditional"] = len(cfg["conditional"])  # include everything eligible
    prompt, report = assemble(locale, all_tags, include_data_placeholder=False, routing=cfg_all)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"soul_{locale}_compiled.md"
    header = (
        f"<!-- COMPILED by m3xa_souls.compiler — DO NOT EDIT BY HAND.\n"
        f"     Source: souls/ modules. Total ~{report.total_tokens} tokens. -->\n\n"
    )
    out.write_text(header + prompt, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("dist"))
    args = ap.parse_args()
    for locale in ("global", "brazil"):
        p = compile_locale(locale, args.out)
        print(f"compiled {p}")


if __name__ == "__main__":
    main()
