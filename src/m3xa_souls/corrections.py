"""Corrections pipeline — replaces 'WHAT I HAVE GOTTEN WRONG' sections.

Rubric-collector auto-detections land here as CANDIDATES (jsonl).
They NEVER touch a live soul. Promotion is a human action that rewrites
the lesson as a POSITIVE rule in the owning module, then logs to history.

CLI:
  python -m m3xa_souls.corrections add "lesson text" --source rubric-collector
  python -m m3xa_souls.corrections list
  python -m m3xa_souls.corrections promote <id> --module souls/modules/geo.md \
      --rule "Positive-form rule text to append"
  python -m m3xa_souls.corrections reject <id> --reason "system-level concern"
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import uuid

from .config import REPO_ROOT

CANDIDATES = REPO_ROOT / "corrections" / "candidates.jsonl"
HISTORY = REPO_ROOT / "corrections" / "history.jsonl"


def _load(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def add(text: str, source: str) -> str:
    rows = _load(CANDIDATES)
    cid = uuid.uuid4().hex[:8]
    rows.append({
        "id": cid, "text": text, "source": source, "status": "candidate",
        "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    _save(CANDIDATES, rows)
    return cid


def promote(cid: str, module: str, rule: str) -> None:
    rows = _load(CANDIDATES)
    row = next((r for r in rows if r["id"] == cid), None)
    if row is None:
        raise SystemExit(f"no candidate {cid}")
    mod_path = REPO_ROOT / module
    if not mod_path.exists():
        raise SystemExit(f"module not found: {module}")
    with open(mod_path, "a", encoding="utf-8") as f:
        f.write(f"\n- {rule.strip()}\n")
    row["status"] = "promoted"
    row["module"] = module
    row["rule"] = rule
    _save(CANDIDATES, [r for r in rows if r["id"] != cid])
    hist = _load(HISTORY)
    hist.append(row)
    _save(HISTORY, hist)
    print(f"promoted {cid} -> {module} (re-run validate: budgets may need adjusting)")


def reject(cid: str, reason: str) -> None:
    rows = _load(CANDIDATES)
    row = next((r for r in rows if r["id"] == cid), None)
    if row is None:
        raise SystemExit(f"no candidate {cid}")
    row["status"] = "rejected"
    row["reason"] = reason
    _save(CANDIDATES, [r for r in rows if r["id"] != cid])
    hist = _load(HISTORY)
    hist.append(row)
    _save(HISTORY, hist)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("text"); a.add_argument("--source", default="manual")
    sub.add_parser("list")
    p = sub.add_parser("promote"); p.add_argument("id"); p.add_argument("--module", required=True); p.add_argument("--rule", required=True)
    r = sub.add_parser("reject"); r.add_argument("id"); r.add_argument("--reason", required=True)
    args = ap.parse_args()
    if args.cmd == "add":
        print(add(args.text, args.source))
    elif args.cmd == "list":
        for row in _load(CANDIDATES):
            print(f"{row['id']}  [{row['source']}]  {row['text'][:90]}")
    elif args.cmd == "promote":
        promote(args.id, args.module, args.rule)
    elif args.cmd == "reject":
        reject(args.id, args.reason)


if __name__ == "__main__":
    main()
