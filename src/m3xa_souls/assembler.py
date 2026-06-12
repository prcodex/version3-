"""Position-aware soul assembly for one product (m3xa | m3xabr).

Plain-text order: core -> overlay -> examples -> conditional modules
-> [data placeholder] -> output format (LAST: recency effect).

bedrock_payload() additionally returns cache-aware system blocks:
  block 1 = everything BEFORE the data placeholder, marked cache_control
            (ephemeral, ttl from routing.yaml). Cache key varies only by the
            small set of tag combinations, so each combo warms once per TTL.
  block 2 = output-format module (uncached tail).
Data context goes in the USER message, never in the cached system prefix.
If a matched module declares structured_output, the payload includes the
schema path + output_config for Bedrock constrained decoding.
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import pathlib

from .config import REPO_ROOT, load_routing
from .router import route, pick_model
from .tokens import estimate_tokens

DATA_PLACEHOLDER = "{{AGENT_AND_DATA_CONTEXT}}"


@dataclasses.dataclass
class AssemblyReport:
    product: str
    model: str
    files: list[str]
    tokens_per_file: dict[str, int]
    total_tokens: int
    over_budget: bool
    structured_output_schema: str | None


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8").strip()


def _plan(product: str, tags: list[str], routing: dict | None = None):
    cfg = routing or load_routing(product)
    mods = route(product, tags, cfg)
    prefix_files = list(cfg["always"]) + [m["file"] for m in mods]
    last_files = list(cfg["last"])
    schema = next((m["structured_output"] for m in mods if m.get("structured_output")), None)
    return cfg, prefix_files, last_files, schema


def assemble(product: str, tags: list[str] | None = None,
             include_data_placeholder: bool = True,
             routing: dict | None = None) -> tuple[str, AssemblyReport]:
    tags = tags or []
    cfg, prefix_files, last_files, schema = _plan(product, tags, routing)
    parts = [_read(p) for p in prefix_files]
    if include_data_placeholder:
        parts.append(DATA_PLACEHOLDER)
    parts += [_read(p) for p in last_files]
    files = prefix_files + last_files
    per_file = {p: estimate_tokens(_read(p)) for p in files}
    total = sum(per_file.values())
    report = AssemblyReport(
        product=product,
        model=pick_model(product, tags, cfg),
        files=files,
        tokens_per_file=per_file,
        total_tokens=total,
        over_budget=total > cfg["budgets"]["total"],
        structured_output_schema=schema,
    )
    return "\n\n---\n\n".join(parts), report


def bedrock_payload(product: str, tags: list[str] | None = None,
                    routing: dict | None = None) -> dict:
    """Gateway-ready dict: cached system blocks + model + optional output_config."""
    tags = tags or []
    cfg, prefix_files, last_files, schema = _plan(product, tags, routing)
    cache = cfg.get("cache", {})
    prefix_text = "\n\n---\n\n".join(_read(p) for p in prefix_files)
    tail_text = "\n\n---\n\n".join(_read(p) for p in last_files)
    system_blocks = [{"type": "text", "text": prefix_text}]
    if cache.get("enabled"):
        system_blocks[0]["cache_control"] = {"type": "ephemeral", "ttl": cache.get("ttl", "1h")}
    system_blocks.append({"type": "text", "text": tail_text})
    payload = {
        "product": product,
        "model": pick_model(product, tags, cfg),
        "system": system_blocks,
        "data_context_goes_in": "user_message",
    }
    if schema:
        payload["output_config"] = {
            "format": {"type": "json_schema",
                       "json_schema": json.loads(_read(schema))}
        }
        payload["render_with"] = "m3xa_souls.renderer"
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble a soul prompt")
    ap.add_argument("--product", required=True, choices=["m3xa", "m3xabr"])
    ap.add_argument("--tags", default="", help="comma-separated classifier tags")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--bedrock-json", action="store_true",
                    help="emit Gateway-ready payload with cache blocks")
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()
    tags = [t for t in args.tags.split(",") if t]
    if args.bedrock_json:
        print(json.dumps(bedrock_payload(args.product, tags), ensure_ascii=False, indent=2)[:4000])
        return
    prompt, report = assemble(args.product, tags)
    if args.out:
        args.out.write_text(prompt, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(prompt)
    if args.report:
        print("\n== ASSEMBLY REPORT ==")
        print(f"  product={report.product}  model={report.model}  "
              f"schema={report.structured_output_schema or '-'}")
        for f, t in report.tokens_per_file.items():
            print(f"  {t:>5} tok  {f}")
        flag = "OVER BUDGET!" if report.over_budget else "ok"
        print(f"  TOTAL {report.total_tokens} tok ({flag})")


if __name__ == "__main__":
    main()
