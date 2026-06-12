# AI Router — Haiku-driven routing (canonical)

> **Status:** canonical architecture as of `prcodex/version3-`.
> The Haiku prompt (`m3xa/router_prompt.md`, `m3xabr/router_prompt.md`)
> defines how routing works. `src/m3xa_souls/router.py` +
> `routing.yaml` remain as the **deterministic offline fallback** —
> they let the test suite, CI, and validate run without an LLM call.
> Production runtime calls Haiku.

## The architecture

The router is a **Haiku prompt**. It takes the user query plus a module
manifest and a few context signals, and returns the modules to load.

`src/m3xa_souls/router.py` + `routing.yaml` are the **fallback path** —
the same routing rules expressed as YAML data + 50 lines of dict-lookup
Python. They exist so the test suite, CI, and the eval harness can
exercise routing offline (no LLM call), and so the system has a
deterministic answer when Haiku is unavailable.

```
Canonical (runtime):                    Fallback (tests / offline):

  classifier+router (Haiku) ──┐           classifier (Haiku) ─┐
   (one combined call,        ├─► module                       ├─► tags ──►
    one prompt)               │   paths                        │            router (Python)
                              ▼                  routing.yaml ─┘   ───►     dict-lookup
  assembler reads paths                                                       │
  directly                                                                    ▼
                                                                      module paths
                                                                      (same shape as canonical)
```

Same number of Haiku calls per query (the classifier was already running).
What changes is **where the routing rules live**: prose in a prompt
instead of YAML + Python.

## Why Haiku and not YAML

The YAML router worked at 3 modules per product. The architecture flips
to Haiku because **module growth introduces nuances that file-level
deterministic routing handles poorly:**

1. **Sub-section composition.** Imagine a `geo.md` that grows to cover
   Iran, Russia-Ukraine, China-Taiwan, and Cold War nukes. For an Iran
   query you don't want Russia-Ukraine paragraphs eating budget. A
   Python router can't pick *parts* of a file — it's all-or-nothing.
   A Haiku router can.

2. **Context-dependent priority.** "geo > polymarket > charts" is
   currently a fixed total order. But for a query like "Brent reaction
   to OPEC announcement," charts (intraday price action) might matter
   more than polymarket (no market for OPEC outcomes). YAML priority is
   static; LLM priority can be contextual.

3. **Multi-axis filtering.** Modules might gain tags for time horizon
   (intraday / daily / weekly), depth (T1 lookup / T3 deep), or
   audience (retail / institutional). A Python router with these many
   axes becomes a giant if/else chain. An LLM router reads the manifest
   and reasons.

Even at 3 modules per product, having the prompt architecture in place
means the v2 sub-section composition step (below) is additive — no
rewrite when modules grow past file granularity.

## What stays, what goes

| Layer | Canonical (runtime) | Fallback (tests / offline) |
|---|---|---|
| `router_prompt.md` (per product) | The routing rules as prose, read by Haiku. Single source of truth. | Not used. |
| `routing.yaml` (per product) | Holds **only** budgets + model tiering + cache config. Tag/priority blocks duplicated here for the fallback path. | Tag→file mapping + priorities + max_conditional cap — same rules as the prompt, expressed as YAML. |
| `router.py` | Not called directly by the runtime. | 50 lines, dict lookup against `routing.yaml`. Used by tests, validate, and `python -m m3xa_souls.assembler --product X --tags Y`. |
| `tests/test_router.py` | — | Tests the YAML fallback. Routing-quality tests for the Haiku path live in `eval/`. |
| `assembler.py` | Reads module paths from Haiku output. | Calls `router.route(product, tags)` (the YAML path). |

## The v1 prompts (canonical)

Two prompts, one per product:

- `m3xa/router_prompt.md` — global macro/geo, 3 modules (geo / polymarket / charts)
- `m3xabr/router_prompt.md` — Brasil, 2 active modules (polymarket / charts) + 1 disabled (brazilbrief)

Both share the same shape:
- **Module manifest** with one paragraph per module describing what it covers and when to load it
- **Decision rules** (≤ 2 modules, priority order, schema constraints)
- **Context signals** the Gateway provides (currently just `polymarket_data_present`)
- **Return contract** — JSON with `modules` + `reasoning`

The prompts are intentionally **v1 simple**: whole-file routing only.
Sub-section composition is the v2 extension below.

## The v2 extension — sub-section composition

When ready, modules get annotated:

```markdown
<!-- SECTION:iran-conflict -->
## Iran — both sides mandatory
...
<!-- /SECTION:iran-conflict -->

<!-- SECTION:russia-ukraine -->
## Russia-Ukraine — escalation ladder
...
<!-- /SECTION:russia-ukraine -->
```

The router prompt picks up a new return shape:

```json
{
  "modules": [
    {"file": "m3xa/souls/modules/geo.md", "sections": ["iran-conflict"]},
    {"file": "m3xa/souls/modules/polymarket.md"}  // whole file, no sections
  ],
  "reasoning": "Iran-specific query → only Iran section of geo."
}
```

`assembler.py` learns to read `sections` and splice. **No structural
change to anything else** — the architecture absorbs the new capability
through the prompt + a small assembler upgrade.

That's the whole point of doing the simple prompt now: when v2 ships,
nothing about the surrounding architecture moves.

## Tradeoff matrix

| | YAML fallback (offline / tests) | Haiku v1 (runtime — canonical) | Haiku v2 (sub-sections — future) |
|---|---|---|---|
| LLM calls per query | 0 | 1 (combined with classifier) | 1 (combined) |
| Determinism | High | Medium — LLM stochasticity | Lower — more degrees of freedom |
| Module granularity | Whole file | Whole file | Section-level |
| Where rules live | `routing.yaml` (~30 lines) | `router_prompt.md` (~50 lines prose) | Same + section annotations in modules |
| Adding a module | Edit YAML + write test | Edit prompt (one paragraph) — keep YAML in sync for fallback | Same + add section markers |
| Audit per query | Trivial (deterministic) | Read `reasoning` field | Read `reasoning` field |
| Failure modes | Tag has no match → empty modules | Same + "Haiku returned bad JSON" → empty modules (graceful) | Same |
| Cost overhead | $0 | $0 (replaces 1 call with 1 call) | $0 |

## Keeping the YAML fallback honest

Because YAML is the fallback, the two paths must agree on routing
*decisions* — same `(product, query, signals)` → same module list,
under normal conditions. To keep them in sync:

1. Whenever a module is added, removed, or its trigger conditions
   change, update **both** `router_prompt.md` (canonical) and
   `routing.yaml` (fallback) in the same commit.
2. The eval harness runs both paths against the pinned-context queries
   and flags divergence. Divergence is acceptable when the Haiku path
   reasonably wins (nuanced judgment); it's a bug when the YAML wins
   (means the prompt is missing something).
3. `validate.py` already enforces budgets and duplicate-rule detection;
   add a "fallback parity" check on the eval set when it's wired.

## Open questions worth noting

- **Should the classifier remain a separate concern from the router?**
  Today's classifier emits tags + model + thinking_budget + agents + confidence.
  If we combine routing into it, the prompt has many responsibilities.
  Alternative: keep them as two sequential prompts (classifier emits tags
  and metadata; router emits modules). Two LLM calls but clearer roles.
  v1 collapses them. v2 might want to split.

- **How does the router prompt see context that doesn't exist yet?**
  `polymarket_data_present` is set by the Gateway after retrieval —
  the router gets it as a context signal. As more post-retrieval signals
  emerge (e.g., `iran_proxies_data_present`, `intraday_data_available`),
  the manifest grows. Keep the signal list small or it bloats fast.

- **Reasoning field as audit trail.** Worth logging every per-query
  `reasoning` to a small jsonl for review. Catches drift early. The
  corrections pipeline pattern applies: rubric-collector reviews
  routing-reasoning entries that look wrong.
