"""Soul linter — gates CI.

Checks:
  1. Per-file token budgets (routing.yaml).
  2. Forbidden patterns (auto-detected leftovers, mistake-log style,
     markdown pipe tables inside soul text).
  3. Duplicate-rule detection: identical normalized lines across files.
"""
from __future__ import annotations
import re
import sys
from collections import defaultdict

from .config import REPO_ROOT, load_routing
from .tokens import estimate_tokens

FORBIDDEN = [
    (re.compile(r"\[Auto-detected\]", re.I), "auto-detected correction leaked into a soul"),
    (re.compile(r"WHAT I HAVE GOTTEN WRONG", re.I), "mistake-log section (belongs in corrections history)"),
    (re.compile(r"^\s*\|.*\|.*\|\s*$", re.M), "markdown pipe table (Telegram cannot render)"),
]


def _normalize(line: str) -> str:
    return re.sub(r"[^a-z0-9á-úà-ãç ]", "", line.lower()).strip()


def validate() -> int:
    cfg = load_routing()
    budgets = cfg["budgets"]
    errors: list[str] = []
    line_owners: dict[str, list[str]] = defaultdict(list)

    soul_files = sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "souls").rglob("*.md"))
    for rel in soul_files:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")

        tokens = estimate_tokens(text)
        budget = budgets.get(rel)
        if budget and tokens > budget:
            errors.append(f"{rel}: {tokens} tok exceeds budget {budget}")
        if budget is None:
            errors.append(f"{rel}: no budget defined in routing.yaml")

        for pat, why in FORBIDDEN:
            if pat.search(text):
                errors.append(f"{rel}: forbidden pattern — {why}")

        for line in text.splitlines():
            norm = _normalize(line)
            if len(norm) > 60:  # only substantive rule-like lines
                line_owners[norm].append(rel)

    for norm, owners in line_owners.items():
        if len(set(owners)) > 1:
            errors.append(f"duplicate rule across {sorted(set(owners))}: \"{norm[:70]}...\"")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK — {len(soul_files)} soul files validated, all budgets met, no duplicates.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
