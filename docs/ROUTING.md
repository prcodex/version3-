# Routing — how a query reaches the right soul

This doc explains the **classification + routing pipeline** that decides
which v3.1 product and which modules a given query loads. The canonical
runtime is a single Haiku call against a per-product router prompt
(`m3xa/router_prompt.md` / `m3xabr/router_prompt.md`) that returns module
paths directly. `src/m3xa_souls/router.py` + `routing.yaml` remain as the
**deterministic offline fallback** for tests, CI, and dry-runs without
an LLM call. See `docs/AI_ROUTER.md` for the rationale of that split.

## The pipeline at a glance

```
                ┌─────────────────────────────────┐
USER QUERY ───▶ │  soul_classifier  (Haiku 4.5)   │ ──┐
                │  prompt: soul_classifier.md     │   │  JSON:
                │  emits ONE structured JSON      │   │  { domain, tier,
                └─────────────────────────────────┘   │    v3_tags, model,
                                                       │    confidence, ... }
   bot routing   ┌─────────────────────────────────┐   │
@M3xA_bot ─────▶│  product = 'm3xa'                │   │
@M3xabr_bot ───▶│  product = 'm3xabr'              │   │
                └─────────────────────────────────┘   │
                                                       ▼
                ┌─────────────────────────────────────────────────────┐
                │  Gateway post-retrieval augmentation                │
                │  tags = classifier.v3_tags                          │
                │  if pm_data_in_context: tags += ['polymarket_data'] │
                └─────────────────────────────────────────────────────┘
                                       │
                                       ▼
                ┌─────────────────────────────────────────────────────┐
                │  router.route(product, tags) → [module paths]       │
                │  - filter modules by `tags ∩ module.tags`           │
                │  - sort by priority                                 │
                │  - cap at routing.yaml `max_conditional` (=2)       │
                └─────────────────────────────────────────────────────┘
                                       │
                                       ▼
                ┌─────────────────────────────────────────────────────┐
                │  assembler.assemble(product, tags)                  │
                │  prompt = core ▸ overlay ▸ examples ▸ modules ▸     │
                │            DATA ▸ output                            │
                └─────────────────────────────────────────────────────┘
                                       │
                                       ▼
                            Haiku 4.5 generation
                          (schema-constrained for geo)
                                       │
                                       ▼
                            renderer.render_geo()
                          (only when schema fired)
                                       │
                                       ▼
                              Telegram response
```

## Component 1 — soul_classifier (the Haiku call)

**Where it lives:** the system prompt is `soul_classifier.md` in the
m3xa House store. The RAG (`m3xa_rag_8550.py` on R6G) loads it, sends
the user query, and parses the JSON response.

**What it returns** (subset relevant to v3.1 routing):

```json
{
  "domain":        "macro | geo | brazil | mixed_macro_geo | mixed_macro_brazil",
  "tier":          "T1 | T2 | T3",
  "v3_tags":       ["iran", "price_action", ...],
  "model":         "haiku | sonnet | opus",
  "thinking_budget": 0,
  "confidence":    0.95,
  "reasoning":     "one sentence"
}
```

`v3_tags` is the field the v3.1 router consumes. The classifier should
emit any subset of the **tag vocabulary** below.

**Confidence floor:** if `confidence < 0.85` the Gateway falls back to
empty tags (no conditional modules load — the response runs on
core + overlay + examples + output only).

## Component 2 — the Haiku router (canonical)

**Where it lives:** the system prompt is `m3xa/router_prompt.md` /
`m3xabr/router_prompt.md` in this repo — one per product.

**What it does:** given the user query, a module manifest baked into the
prompt, and a handful of context signals from the Gateway (currently just
`polymarket_data_present`), it returns the module paths to load.

The runtime calls Haiku with the prompt + the query + the signals as
context, and parses the JSON response. The output shape:

```json
{
  "modules": ["m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"],
  "reasoning": "Iran war timeline + Polymarket data present → geo + polymarket."
}
```

The same Haiku call that does classification also picks modules — there
is no separate "Stage 2 → Stage 3" call. One prompt, one response.

## Component 2 (fallback) — `router.py` + `routing.yaml`

**Where it lives:** `src/m3xa_souls/router.py` and the per-product
`routing.yaml` files.

**What it does:** same job as the Haiku router, but as a deterministic
dict-lookup. Given `(product, tags)` it returns the same module list every
time — used by `pytest`, `validate`, `python -m m3xa_souls.assembler`, and
any context where an LLM call is impractical or undesirable.

```python
from m3xa_souls.router import route
route("m3xa", ["iran", "polymarket_data"])
# → ["m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"]
```

**How it resolves:**
1. Iterate `routing.yaml → conditional` blocks for the product.
2. Skip any module with `enabled: false` (e.g. `brazilbrief` in m3xabr).
3. Skip any module whose `locales` field excludes the product.
4. Match: if `tags ∩ module.tags` is non-empty, the module is a candidate.
5. Sort candidates by `priority` (ascending — lower number wins).
6. Cap at `max_conditional` (currently 2).

The fallback path is **fully deterministic**. The routing rules in
`routing.yaml` must stay in sync with `router_prompt.md` — any change to
one needs the matching change in the other in the same commit.

## Tag vocabulary

| Tag | Emitter | Fires when... | Module triggered |
|---|---|---|---|
| `iran` | soul_classifier (Haiku) | query mentions Iran/Israel/Hormuz/IDF/IRGC/Pezeshkian/Araghchi/Houthis/Hezbollah/Iranian nuclear program | `geo.md` (m3xa only) |
| `war` / `conflict` / `geopolitics` / `hormuz` | soul_classifier (Haiku) | broader geo content adjacent to but not specifically Iran | `geo.md` (m3xa only) |
| `brazilbrief` | soul_classifier (Haiku) — literal hashtag match | the user query contains `#brazilbrief` or `#brazilbrief<N>` | `brazilbrief.md` (m3xabr only, currently `enabled: false`) |
| `polymarket_data` | **Gateway**, post-retrieval | the retrieved context contains Polymarket data (`pm_text` non-empty) | `polymarket.md` |
| `price_action` / `trend` / `performance` | soul_classifier (Haiku) | query asks about price moves, percent changes, "how has X done", chart-shaped questions on tickers (gold/oil/S&P/DXY/BRL/Ibov/etc.) | `charts.md` |

### Why `polymarket_data` comes from the Gateway, not the LLM

The classifier sees only the user query — it doesn't know whether the
data agents actually returned Polymarket rows for this query. The
polymarket module's hard rule is "**TOTAL SILENCE when absent**" — to
enforce that, we need to know if data is in the prompt, not whether the
user asked about prediction markets. So the Gateway sets this tag after
retrieval, based on the live data, never the query.

## Per-product priority chains

m3xa:
```
geo (1)  >  polymarket (2)  >  charts (3)        max 2 loaded
```

m3xabr:
```
polymarket (1)  >  charts (2)  >  brazilbrief (3, OFF)   max 2 loaded
```

m3xabr has **no `geo` module** — geo queries route to m3xa instead
(the Gateway product split is upfront, before this router runs).

## Worked examples

```python
# global macro, conflict + retrieved Polymarket data
route("m3xa", ["iran", "polymarket_data"])
# → ["m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"]

# global macro, chart query + Polymarket retrieved
route("m3xa", ["price_action", "polymarket_data"])
# → ["m3xa/souls/modules/polymarket.md", "m3xa/souls/modules/charts.md"]
# (charts kept — priority 3 — because polymarket fills slot 2)

# global macro, conflict + chart + Polymarket → max 2, geo wins
route("m3xa", ["iran", "price_action", "polymarket_data"])
# → ["m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"]
# (charts dropped: priority 3, cap hit)

# brazil chart query, no Polymarket data
route("m3xabr", ["price_action"])
# → ["m3xabr/souls/modules/charts.md"]

# brazilbrief hashtag — module is OFF, so nothing loads
route("m3xabr", ["brazilbrief"])
# → []
```

## Failure modes

| Scenario | Behavior |
|---|---|
| Classifier returns `confidence < 0.85` | Gateway drops `v3_tags`; assembler loads core + overlay + examples + output only |
| Classifier JSON parse fails | Same as above — empty tags fallback |
| Classifier emits an unknown tag | Router silently ignores it (no match in any module's `tags`) |
| Classifier emits a tag for a module that's disabled | Router silently drops it (see m3xabr brazilbrief) |
| Classifier emits a tag for a module that doesn't exist in this product | Router silently drops it (m3xabr never loads `geo` even if `iran` is emitted, because m3xabr/routing.yaml has no `geo` block) |

All failure modes are non-fatal: the response degrades to the
always-loaded prefix (core + overlay + examples + output), never errors.

## File map

| File | Role |
|---|---|
| `soul_classifier.md` (House store, not in this repo) | Haiku prompt — emits classification JSON |
| `src/m3xa_souls/router.py` | Pure Python, deterministic tag → module routing |
| `m3xa/routing.yaml`, `m3xabr/routing.yaml` | Per-product tag→module map, priorities, budgets, model tiering, cache config |
| `src/m3xa_souls/assembler.py` | Calls `router.route()`, reads files, builds the final prompt |
| `soul_v3_tags.py` (R6G integration glue, not in this repo) | Bridge between the existing classifier and `assemble()` — passes through `v3_tags` and adds `polymarket_data` post-retrieval |
