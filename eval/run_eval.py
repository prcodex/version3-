"""Old-vs-new eval harness.

Modes:
  --dry-run        Assemble NEW prompts for all queries, print token reports,
                   write prompts to eval/out/ for inspection. No API calls.
  (default)        Requires boto3 + AWS creds. For each query, calls Haiku 4.5
                   via Bedrock twice (OLD monolith vs NEW assembly) with the
                   SAME pinned data context, writes paired outputs to eval/out/
                   for rubric scoring.

Pin the data context: export a real FeedCache snapshot to eval/context/{id}.txt
so both arms see identical data. Without pinned context, comparisons are noise.
"""
from __future__ import annotations
import argparse
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from m3xa_souls.assembler import assemble, DATA_PLACEHOLDER  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
CONTEXT = HERE / "context"
OLD_SOULS = HERE / "old"   # place current soul_global.md / soul_brazil.md here
MODEL_ID = "claude-haiku-4-5"


def load_queries():
    return yaml.safe_load((HERE / "queries.yaml").read_text())["queries"]


def build_new_prompt(q) -> tuple[str, object]:
    prompt, report = assemble(q["product"], q["tags"])
    ctx_file = CONTEXT / f"{q['id']}.txt"
    ctx = ctx_file.read_text() if ctx_file.exists() else "[NO PINNED CONTEXT — dry structure only]"
    return prompt.replace(DATA_PLACEHOLDER, ctx), report


def dry_run():
    OUT.mkdir(exist_ok=True)
    for q in load_queries():
        prompt, report = build_new_prompt(q)
        (OUT / f"{q['id']}_new_prompt.md").write_text(prompt, encoding="utf-8")
        print(f"{q['id']:>7}: {report.total_tokens:>5} tok  modules={len(report.files)}  "
              f"{'OVER' if report.over_budget else 'ok'}")
    print(f"\nPrompts written to {OUT}/ — review before any live eval.")


def live_run():
    try:
        import boto3  # noqa: F401
    except ImportError:
        raise SystemExit("pip install '.[eval]' and configure AWS credentials, "
                         "or use --dry-run.")
    raise SystemExit(
        "Live mode scaffold: wire bedrock-runtime invoke_model here using your "
        "existing M3xA Bedrock client (same inference params as production), "
        "iterate queries, call OLD soul (eval/old/soul_{product}.md + context) and "
        "NEW prompt, write paired outputs to eval/out/{id}_{arm}.md, then score "
        "both with evaluator_rubric.md."
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry_run() if args.dry_run else live_run()
