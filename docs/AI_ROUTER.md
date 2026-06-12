# AI Router — moving routing from Python to Haiku

> **Status:** design draft. Not implemented. The Python `router.py` still
> serves production. This doc captures the architectural direction and the
> two draft router prompts (`m3xa/router_prompt.md`, `m3xabr/router_prompt.md`)
> that will eventually drive the swap.

## The shift

Today's router is **pure Python** — a 50-line `router.py` that reads
`routing.yaml`, intersects tag sets, sorts by priority, caps at 2 modules,
and returns file paths. Deterministic, fast, auditable. Works perfectly
for the current 3-module-per-product setup.

The proposal: replace the Python router with a **Haiku prompt** that takes
the user query and a module manifest, and returns the modules to load.

```
Today:                                  Proposed:
                                        
  classifier (Haiku) ─┐                   classifier+router (Haiku) ──┐
                      ├─► tags ──►          (combined call,           ├─► module paths
  routing.yaml ───────┤   router (Python)    one prompt)              │
                      └─► modules                                     │
                          (file paths)                                ▼
                                          assembler reads paths directly
                                          (no router.route() call)
```

Same number of Haiku calls per query (the classifier was already running).
What changes is **where the routing rules live**: prose in a prompt
instead of YAML + Python.

## Why move now

The current router does its job. The argument for swapping is forward-
looking — **future module growth introduces nuances that file-level
deterministic routing can't handle gracefully:**

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

None of these matter at 3 modules per product. They start mattering at
10+. Starting the prompt architecture now means the migration to
sub-section composition is additive, not a rewrite.

## What stays, what goes

| Layer | Today | Proposed |
|---|---|---|
| `routing.yaml` (per product) | Tag→file mapping + priorities + budgets + model config | **Shrinks** — keeps budgets + model tiering + cache config. Tag/priority blocks move into the router prompt. |
| `router.py` | 50 lines, dict lookup | **Thin shim** — validates Haiku's output (file paths exist, ≤ max_conditional), dedupes, returns. Maybe 15 lines. |
| `router_prompt.md` (per product) | Doesn't exist | **New.** The routing rules as prose, read by Haiku. |
| `tests/test_router.py` | Tests dict-lookup logic | **Becomes a "shim contract" test** — given a stubbed Haiku response, assembler reads it correctly. The "routing accuracy" tests move to eval (since LLM is stochastic, you measure with cases, not asserts). |
| `assembler.py` | Calls `router.route(product, tags)` | Calls `router.route(product, query, signals)` — same function name, body uses Haiku now. |

## The v1 prompt (today's deliverable)

Two draft prompts shipped alongside this doc:

- `m3xa/router_prompt.md` — global macro/geo, 3 modules (geo / polymarket / charts)
- `m3xabr/router_prompt.md` — Brasil, 2 active modules (polymarket / charts) + 1 disabled (brazilbrief)

Both share the same shape:
- **Module manifest** with one paragraph per module describing what it covers and when to load it
- **Decision rules** (≤ 2 modules, priority order, schema constraints)
- **Context signals** the Gateway provides (currently just `polymarket_data_present`)
- **Return contract** — JSON with `modules` + `reasoning`

The prompts are intentionally **v1 simple**: whole-file routing only.
Sub-section composition is reserved for v2.

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

| | Python router (today) | Haiku v1 (this draft) | Haiku v2 (sub-sections) |
|---|---|---|---|
| LLM calls per query | 1 (classifier) | 1 (combined) | 1 (combined) |
| Determinism | High | Medium — LLM stochasticity | Lower — more degrees of freedom |
| Module granularity | Whole file | Whole file | Section-level |
| Where rules live | `routing.yaml` (~30 lines) | `router_prompt.md` (~50 lines prose) | Same + section annotations in modules |
| Adding a module | Edit YAML, write tests | Edit prompt (one paragraph) | Same + add section markers |
| Audit per query | Trivial (deterministic) | Read `reasoning` field | Read `reasoning` field |
| Failure modes | Tag has no match → empty modules | Same + "Haiku returned bad JSON" → empty modules (graceful) | Same |
| Cost vs today | $0 extra | $0 extra (replaces 1 call with 1 call) | $0 extra |

## When to implement

Not now. The v1 prompts in this commit are **design artifacts** — they
sit in the repo so:
- They can be read, reviewed, and iterated as prose.
- A future implementer (or future-you) has a concrete contract to wire up.
- The architecture is documented before any code change happens.

Implementation gates:
- v3.1 souls finalize (mostly done).
- A second module per product gets added (would make Python router's
  cap+priority logic start hurting — natural trigger for the swap).
- OR: eval results show file-level routing missing nuances that
  sub-section composition would catch.

When the time comes, the swap is roughly:
1. Add `router.route()` Haiku-driven variant (the old code path stays).
2. Dual-run for a week: log Python-router decision vs Haiku-router decision,
   compare to eval-set expected modules.
3. Cut over once Haiku matches or beats Python on the eval set.
4. Delete Python router + `routing.yaml` tag blocks (keep budgets/model/cache).

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
