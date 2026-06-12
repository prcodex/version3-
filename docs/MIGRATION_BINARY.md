# Design — Binary Domain Split (m3xa vs m3xabr)

> Status: **design rationale**, not an active deployment plan.
> Captures the thinking behind why the domain decision should be
> a fully binary, deterministic split at the bot/retrieval layer
> rather than something the LLM classifier handles.

The domain decision is **binary and deterministic**, driven by which
Telegram bot received the query. This removes one redundant LLM call,
removes one soul-level filter rule (structural now), and shrinks every
retrieval set to the sources actually relevant for that product.

## The end state

```
@M3xA_bot   → product=m3xa    → retrieval scope: classification='macro'  (472 sources)
@M3xabr_bot → product=m3xabr  → retrieval scope: classification='brazil' (200 sources)
```

No `manager_agent` override. No mixed filters. No soul-level "BRAZIL INVISIBLE"
post-filter. Every cross-product query gets the "I don't have data" response
in the wrong product, which is the correct behavior — users move to the
other bot.

## Why this works on the existing data

Confirmed against `/home/ubuntu/argus/newspaper_project/source_classifications.db`
(2026-06-12):

- `classification` column is **already binary in the data** — `macro` (472)
  and `brazil` (200). The schema comment mentions `'both'` and `'unset'` but
  zero rows use either.
- `codex` is **not a classification** — it's a `source_type` value (41 rows,
  all macro-classified) for email-research subscriptions (Goldman Macro,
  GS Rates, Tooze, Authers, El-Erian, etc.).
- The bot's current `filters=['macro','brazil','codex']` vocabulary mixes
  classification names and source_type names — a historical sloppiness that
  this migration cleans up.

## What changes (4 steps, ordered by risk)

### Step 1 — Add a single retrieval helper (additive, zero risk)

**Where:** `m3xa_rag_8550.py` on R6G, near `get_sources_by_classification`
(currently at line ~860).

**Add a new function** alongside the existing one; do not remove the old yet:

```python
def sources_for_product(product: str) -> list[str]:
    """Binary product → classification lookup. m3xa = macro, m3xabr = brazil."""
    cls = 'macro' if product == 'm3xa' else 'brazil'
    with sqlite3.connect(SOURCE_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT source_id FROM source_classifications WHERE classification = ?",
            (cls,),
        ).fetchall()
    return [r[0] for r in rows]
```

**Verify:**
```
python3 -c "from m3xa_rag_8550 import sources_for_product;
print('m3xa:', len(sources_for_product('m3xa')),
      'm3xabr:', len(sources_for_product('m3xabr')))"
# Expected: m3xa: 472  m3xabr: 200
```

**Rollback:** delete the function. Old code paths untouched.

### Step 2 — Wire the new helper into the retrieval path

**Where:** `m3xa_rag_8550.py` on R6G — `rag_query()`, around line ~1737-1965
where `filters` and `manager_agent.get_query_classification` are consulted.

**Change:**
```python
# OLD
filters = data.get('filters', ['macro', 'brazil', 'codex'])
# ... manager_agent.get_query_classification(query) for ambiguous cases ...
# ... _brazil_only = 'brazil' in filters and 'macro' not in filters ...

# NEW
product = 'm3xabr' if 'brazil' in filters and 'macro' not in filters else 'm3xa'
allowed_sources = set(sources_for_product(product))
# downstream code that scoped by filters now scopes by allowed_sources
```

The `product` variable replaces `_brazil_only`, `_query_scope`, and
`soul_variant`. The `allowed_sources` set is the binary retrieval filter.

**Verify (canary):** dual-run for 24h. Log both the old `soul_variant`
and the new `product` per query. Compare. Disagreements are the queries
where `manager_agent` was overriding — review them, confirm the new
behavior (no override) is acceptable.

**Rollback:** keep the old `soul_variant` logic active, ignore the new
`product` variable. Easy revert.

### Step 3 — Drop the BRAZIL INVISIBLE soul-level filter

**Where:** `m3xa/souls/overlay.md` in this repo.

**Change:** delete the "HARD FILTER — BRAZIL INVISIBLE" section
(currently ~5 lines, ~40 tok). Once retrieval is binary at the DB level,
no Brazil source can leak into m3xa's context — the prompt-level guard
is no longer needed. The "Brazil hard-filter" label in the README diagram
also needs updating to reflect this.

**Verify:** `python -m m3xa_souls.validate` (budget room frees up), then
run the eval against the new binary retrieval (Phase 2 of the existing
MIGRATION.md). NEW prompts should match or beat OLD on Brazil filter
compliance — should be trivially true since Brazil sources are now
structurally absent.

**Rollback:** put the section back. Single edit.

### Step 4 — Retire the `manager_agent` override path

**Where:** `m3xa_rag_8550.py` on R6G — lines ~1737, ~1964 (the two
`from manager_agent import get_query_classification` import + call sites).

**Change:** delete both invocation blocks. They're dead code once Step 2
ships (the binary doesn't need an override).

**Verify:** `python3 -m py_compile m3xa_rag_8550.py` to confirm no
import is now orphaned. Restart RAG (pkill + systemctl). Tail logs for
a few minutes — no `manager_agent` references should appear.

**Rollback:** revert the deletions. `manager_agent.py` itself doesn't
need to change.

## What this removes (cleanup summary)

| Thing removed | Where | Why obsolete |
|---|---|---|
| `manager_agent.get_query_classification` call sites | `m3xa_rag_8550.py` ~1737, ~1964 | Binary product replaces fuzzy override |
| `_brazil_only` / `_query_scope` / `soul_variant` logic | `m3xa_rag_8550.py` ~2048-2059 | Replaced by direct `product` from filters |
| `'codex'` filter token in bot requests | Telegram bot codebase | Was conflating classification + source_type |
| "BRAZIL INVISIBLE" prompt rule | `m3xa/souls/overlay.md` | Structural now — Brazil sources never reach the prompt |
| Fuzzy `query_macro` / `query_geo` scoring in soul_classifier | `soul_classifier.md` (House store) | Domain pre-decided; classifier can shrink |

Net result: ~5 places in the code/prompts get simpler. No new tooling.
The router and assembler don't change.

## Migration order (sequenced for safety)

1. **Step 1** (additive helper) — ship anytime, zero blast radius.
2. **Step 2** (wire retrieval) with **dual-run logging** for 24h.
   Confirm no surprise overrides.
3. **Step 3** (drop BRAZIL INVISIBLE) — ship after Step 2 looks clean for 24h.
   This is a soul change; recompile `dist/`, re-run validate, push.
4. **Step 4** (remove manager_agent) — ship last, after Steps 1-3 have soaked
   for a week with no incidents.

All four steps are individually reversible. The combined migration is
reversible by reverting in opposite order (4 → 3 → 2 → 1).

## What does NOT change

- The router (`src/m3xa_souls/router.py`) is untouched.
- The assembler (`src/m3xa_souls/assembler.py`) is untouched.
- The v3.1 routing.yaml files (`m3xa/routing.yaml`, `m3xabr/routing.yaml`)
  are untouched.
- The corrections pipeline is untouched.
- The CI / eval harness is untouched.

## Soul classifier — separate (follow-up) decision

This migration says **nothing about the `v3_tags` addition** to
`soul_classifier.md`. That's the regex-vs-Haiku decision from earlier in
this conversation. It can land before, during, or after this migration —
they're orthogonal. The classifier already runs once per query regardless.

When ready to take the classifier on, the relevant edits are:

1. Add `v3_tags` field to the JSON spec in `soul_classifier.md`
2. Drop `domain` / `query_macro` / `query_geo` fields (the binary already
   answers them)
3. Update `soul_v3_tags.py` to a pass-through (delete the regex)

That's a separate PR.

## Decision — Brazil queries arriving at @M3xA_bot

**Hard cut.** m3xa is the global macro/geo agent; it's not a Brazil specialist
by design. A Brazil question reaching @M3xA_bot returns whatever the global
feed has on the topic (usually little) without any redirect text. Users who
want Brazil depth use @M3xabr_bot.

No soft-cut redirect, no keyword sniffer. The product identity is the
guarantee: "this is what m3xa knows, no apologies." A user who lands in the
wrong bot is a routing error at the human layer, not something the system
papers over.

## Verification checklist (per step)

```
Step 1:
  [ ] sources_for_product('m3xa')  → 472 sources
  [ ] sources_for_product('m3xabr') → 200 sources

Step 2:
  [ ] dual-run log shows product = m3xa when filters has 'macro'
  [ ] dual-run log shows product = m3xabr when filters has only 'brazil'
  [ ] no disagreement between soul_variant and product for >99% of queries
  [ ] disagreements (if any) reviewed and confirmed acceptable

Step 3:
  [ ] m3xa_souls.validate green (budget freed)
  [ ] eval Phase 2: NEW ≥ OLD on every rubric category
  [ ] manual spot-check: m3xa response to "Iran impact on BRL" still
      reasonable without the prompt-level Brazil filter

Step 4:
  [ ] py_compile clean after manager_agent imports removed
  [ ] RAG restart clean
  [ ] 24h logs free of manager_agent traces
```
