"""Position-aware soul assembly.

Order: hard rules (core) -> locale overlay -> conditional modules
-> examples -> [Gateway inserts AGENT/DATA CONTEXT here] -> output format.

Output format goes LAST so it sits adjacent to generation (recency effect).
"""
from __future__ import annotations
import argparse
import dataclasses
import pathlib

from .config import REPO_ROOT, load_routing
from .router import route
from .tokens import estimate_tokens

DATA_PLACEHOLDER = "{{AGENT_AND_DATA_CONTEXT}}"


@dataclasses.dataclass
class AssemblyReport:
    files: list[str]
    tokens_per_file: dict[str, int]
    total_tokens: int
    over_budget: bool


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8").strip()


def assemble(
    locale: str,
    tags: list[str] | None = None,
    include_data_placeholder: bool = True,
    routing: dict | None = None,
) -> tuple[str, AssemblyReport]:
    cfg = routing or load_routing()
    tags = tags or []

    ordered: list[str] = []
    ordered += [p.format(locale=locale) for p in cfg["always"]]
    ordered += route(locale, tags, cfg)
    last = [p.format(locale=locale) for p in cfg["last"]]

    parts = [_read(p) for p in ordered]
    if include_data_placeholder:
        parts.append(DATA_PLACEHOLDER)
    parts += [_read(p) for p in last]

    files = ordered + last
    prompt = "\n\n---\n\n".join(parts)

    per_file = {p: estimate_tokens(_read(p)) for p in files}
    total = sum(per_file.values())
    report = AssemblyReport(
        files=files,
        tokens_per_file=per_file,
        total_tokens=total,
        over_budget=total > cfg["budgets"]["total"],
    )
    return prompt, report


def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble a soul prompt")
    ap.add_argument("--locale", required=True, choices=["global", "brazil"])
    ap.add_argument("--tags", default="", help="comma-separated classifier tags")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()

    tags = [t for t in args.tags.split(",") if t]
    prompt, report = assemble(args.locale, tags)

    if args.out:
        args.out.write_text(prompt, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(prompt)
    if args.report:
        print("\n== ASSEMBLY REPORT ==")
        for f, t in report.tokens_per_file.items():
            print(f"  {t:>5} tok  {f}")
        flag = "OVER BUDGET!" if report.over_budget else "ok"
        print(f"  TOTAL {report.total_tokens} tok ({flag})")


if __name__ == "__main__":
    main()
