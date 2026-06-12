"""Soul linter — gates CI. Iterates BOTH products (m3xa, m3xabr).

Checks per product:
  1. Per-file token budgets (each product's routing.yaml).
  2. Forbidden patterns (auto-detected leftovers, mistake-log style, pipe tables).
  3. Duplicate-rule detection WITHIN a product (cross-product duplication is
     expected: same convention in EN and PT are different strings anyway).
  4. structured_output schema paths exist and parse as JSON.
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict

from .config import REPO_ROOT, PRODUCTS, load_routing
from .tokens import estimate_tokens

FORBIDDEN = [
    (re.compile(r"\[Auto-detected\]", re.I), "auto-detected correction leaked into a soul"),
    (re.compile(r"WHAT I HAVE GOTTEN WRONG", re.I), "mistake-log section (belongs in corrections history)"),
    (re.compile(r"^\s*\|.*\|.*\|\s*$", re.M), "markdown pipe table (Telegram cannot render)"),
]


def _normalize(line: str) -> str:
    return re.sub(r"[^a-z0-9á-úà-ãç ]", "", line.lower()).strip()


def validate() -> int:
    errors: list[str] = []
    n_files = 0
    for product in PRODUCTS:
        cfg = load_routing(product)
        budgets = cfg["budgets"]
        line_owners: dict[str, list[str]] = defaultdict(list)
        soul_files = sorted(str(p.relative_to(REPO_ROOT))
                            for p in (REPO_ROOT / product / "souls").rglob("*.md"))
        n_files += len(soul_files)
        for rel in soul_files:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            tokens = estimate_tokens(text)
            budget = budgets.get(rel)
            if budget is None:
                errors.append(f"{rel}: no budget defined in {product}/routing.yaml")
            elif tokens > budget:
                errors.append(f"{rel}: {tokens} tok exceeds budget {budget}")
            for pat, why in FORBIDDEN:
                if pat.search(text):
                    errors.append(f"{rel}: forbidden pattern — {why}")
            for line in text.splitlines():
                norm = _normalize(line)
                if len(norm) > 60:
                    line_owners[norm].append(rel)
        for norm, owners in line_owners.items():
            if len(set(owners)) > 1:
                errors.append(f"[{product}] duplicate rule across {sorted(set(owners))}: \"{norm[:70]}...\"")
        for name, mod in cfg["conditional"].items():
            schema = mod.get("structured_output")
            if schema:
                p = REPO_ROOT / schema
                if not p.exists():
                    errors.append(f"[{product}] {name}: schema not found: {schema}")
                else:
                    try:
                        json.loads(p.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as e:
                        errors.append(f"[{product}] {name}: invalid schema JSON: {e}")
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK — {n_files} soul files across {len(PRODUCTS)} products validated; "
          f"budgets met, no duplicates, schemas parse.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
