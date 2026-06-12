# Flow — From a Question to an Answer

End-to-end narrative: how a user's Telegram message becomes a response, and
how the soul `.md` files in this repo are organized to support each step
of the journey. Read this if you want the **conceptual model** behind the
v3.1 architecture without diving into Python.

## The journey at a glance

```
        ┌─────────────────────────────────────────────────────────┐
        │  USER  types a question in @M3xA_bot or @M3xabr_bot      │
        └─────────────────────────────────────────────────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
        ┌──────────────┐                   ┌──────────────┐
        │  STAGE 1     │                   │  STAGE 1     │
        │  Bot picks   │                   │  Bot picks   │
        │  product     │                   │  product     │
        │  = m3xa      │                   │  = m3xabr    │
        │  (binary)    │                   │  (binary)    │
        └──────────────┘                   └──────────────┘
                │                                   │
                ▼                                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 2 — Two parallel things happen                    │
        │                                                          │
        │  (a) Retrieval — LanceDB filtered to this product's      │
        │      source set (macro for m3xa, brazil for m3xabr)      │
        │      → AGENT + DATA CONTEXT                              │
        │                                                          │
        │  (b) Classification — one Haiku call (soul_classifier)   │
        │      → JSON: tags, model, thinking_budget, agents        │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 3 — Routing                                        │
        │  router.route(product, tags) → conditional module files  │
        │  (max 2 modules, priority order)                          │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 4 — Assembly                                       │
        │                                                          │
        │  core.md  →  overlay.md  →  examples.md  →  modules  →   │
        │                                                          │
        │  [AGENT + DATA CONTEXT — inserted in user message]       │
        │                                                          │
        │  →  output.md  (always LAST — recency effect)            │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 5 — Generation                                     │
        │  Bedrock invokes Claude (Haiku 4.5 by default;            │
        │  Sonnet 4.6 for broad/deep) with the assembled prompt.    │
        │  geo queries are schema-constrained                       │
        │  (schemas/geo_response.schema.json).                      │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 6 — Rendering                                      │
        │  If the response came back as structured JSON (geo),      │
        │  renderer.render_geo() converts it to Telegram HTML.      │
        │  Otherwise, the model's markdown is sent as-is.           │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                            ┌──────────────┐
                            │  USER reads  │
                            │  in Telegram │
                            └──────────────┘
```

Six stages. **All the soul logic lives in Stage 4** — that's where the `.md`
files become the system prompt. Everything before is selection (what to load),
everything after is execution and packaging.

## How the .md files are organized

Two top-level product folders, each fully self-contained. **Nothing is shared
between them at the prompt layer** — m3xa never reads m3xabr's files and
vice versa. (The Python code is shared. The prompts are not.)

```
m3xa/                                m3xabr/
├── routing.yaml                     ├── routing.yaml
└── souls/                           └── souls/
    ├── core.md       ← identity        ├── core.md       ← identidade
    ├── overlay.md    ← source tiers    ├── overlay.md    ← tiers de fontes
    ├── examples.md   ← few-shots       ├── examples.md   ← exemplos
    ├── output.md     ← format          ├── output.md     ← formato
    └── modules/                        └── modules/
        ├── geo.md                          ├── polymarket.md
        ├── polymarket.md                   ├── charts.md
        └── charts.md                       └── brazilbrief.md
                                            (enabled: false)
```

The folder structure mirrors the assembly order. **The reader of the prompt
(Haiku) sees the files in this exact sequence**, separated by `\n\n---\n\n`:

1. `core.md` — who am I, how do I cite, how do I treat time
2. `overlay.md` — what sources matter, in what order, with what handling rules
3. `examples.md` — three canonical few-shots
4. **conditional modules** — only the 0-2 that match the query's tags
5. **AGENT + DATA CONTEXT** — what we just retrieved from LanceDB (this is
   actually placed in the user message, not the system prompt, so it's the
   freshest possible content)
6. `output.md` — format rules, last thing the model sees before generating

Why this order matters: instruction compliance decays with directive count
and with position-in-prompt. Putting identity at the top and format at the
bottom is the position-aware fix: hard rules anchor early, the format spec
sits adjacent to generation.

## Stage 1 — Binary domain split (the question's lane)

Which bot received the message decides product:

| Bot | Product | Retrieval scope | Soul folder |
|---|---|---|---|
| @M3xA_bot | `m3xa` | `classification = 'macro'` (472 sources) | `m3xa/souls/` |
| @M3xabr_bot | `m3xabr` | `classification = 'brazil'` (200 sources) | `m3xabr/souls/` |

**This is deterministic and pre-LLM.** The classifier never decides domain.
A Brazil question typed into @M3xA_bot retrieves only macro sources, loads
the m3xa soul, and answers in English with whatever the global feed has on
the topic — which for "Lula's approval rating" is essentially nothing. That's
the correct behavior: m3xa is not a Brazil specialist, no apologies, no
redirect.

See `docs/MIGRATION_BINARY.md` for the full design rationale.

## Stage 2a — Retrieval (the data side)

The Gateway queries LanceDB with the product's filter set and assembles the
**AGENT + DATA CONTEXT** block: news items, tweets, podcast transcripts,
PDF research, market snapshots, polymarket prices (if any), economic
calendar entries. This is the freshly retrieved evidence the model will
ground its answer on. It is **inserted into the user message**, not the
system prompt, so it never enters the prompt cache (it's different every
query).

## Stage 2b — Classification (the AI call)

One Haiku 4.5 call with `soul_classifier.md` as the system prompt.

Input: the user's raw query (no retrieved context yet).

Output: structured JSON. The fields relevant to v3.1 routing:

| Field | Used by | Decides |
|---|---|---|
| `v3_tags` | router | which conditional modules to load |
| `model` | Bedrock | Haiku vs Sonnet vs Opus |
| `thinking_budget` | Bedrock | 0 / 5000 / 10000 thinking tokens |
| `agent_triggers` | retrieval (Stage 2a, in practice) | which data agents to query |
| `confidence` | Gateway fallback | if `< 0.85`, drop tags (degrade gracefully) |

Two important properties:

1. **The classifier never decides product.** Stage 1 already did. The
   classifier focuses on the harder, query-content questions.
2. **The classifier never decides `polymarket_data`.** That tag is set by
   the Gateway AFTER retrieval, based on whether Polymarket data is actually
   present. The classifier sees the query only, not the retrieved data.

See `docs/ROUTING.md` for the full classifier + router pipeline reference
and the tag vocabulary.

## Stage 3 — Routing (tags become files)

`router.route(product, tags)` walks the product's `routing.yaml`, filters
out disabled or locale-mismatched modules, intersects each module's
declared tags with the emitted tags, sorts by priority, and caps at
`max_conditional` (currently 2).

50 lines of pure Python. Deterministic. No LLM. Same `(product, tags)`
always returns the same module list.

The router's only job is: **tags become file paths**. The "why" is in the
modules; the "how" is in `routing.yaml`.

## Stage 4 — Assembly (the souls become a prompt)

`assembler.assemble(product, tags)` reads the routed files in order and
joins them with `\n\n---\n\n` separators. The result is one long
system-prompt string that looks like:

```
<core.md content>

---

<overlay.md content>

---

<examples.md content>

---

<module 1 content>

---

<module 2 content>

---

{{AGENT_AND_DATA_CONTEXT}}   ← placeholder; the Gateway will replace
                              this with the retrieval block when
                              calling Bedrock

---

<output.md content>
```

Then the **Bedrock prompt cache** wraps the static prefix (everything BEFORE
the data placeholder) in a `cache_control: { type: ephemeral, ttl: 1h }`
block. Every query with the same `(product, tags)` combination warms one
cache entry per hour and pays ~0.1× on subsequent reads. The data context
sits in the user message — always different, always fresh, never cached.

## Stage 5 — Generation (Bedrock)

The Gateway calls Bedrock with:
- The assembled system prompt (with `cache_control`)
- The retrieval block + the user's query in the user message
- `model` = whatever the classifier said (Haiku default, Sonnet for
  broad/deep, etc., per `routing.yaml`)
- `thinking_budget` = same source
- `tool_use` or `response_format` = if the geo module fired, constrain the
  response to `schemas/geo_response.schema.json`

The schema constraint matters: it means the geo response **must** come back
as structured JSON with TIMELINE, ACTOR_BREAKDOWN, MARKET_REACTION,
EXPERT_ANALYSIS, PREDICTION_MARKETS, WHAT_TO_WATCH sections. There is no
freeform prose for geo queries — the structure is enforced by the decoder,
not by prompt instructions.

## Stage 6 — Rendering (geo → Telegram)

For non-geo queries: the model returns markdown, the Gateway sends it
directly to Telegram. The format rules in `output.md` enforce things like
"use `<pre>` blocks for tables, never markdown pipe tables, max 30 chars
wide for Brazil tables, MARKETS snapshot at the end of time-windowed
summaries."

For geo queries: the model returns the structured JSON.
`renderer.render_geo(json)` converts it into Telegram HTML — applying the
visual formatting that used to be in the prompt as prose instructions.
**Format compliance lives in code, not in the prompt.** This is the v3.1
upgrade that moved "TIMELINE first, no freeform intros" from a prompt rule
the model could ignore to a structural decoder constraint the model can't
disobey.

## The role of each `.md` file in the flow

| File | Stage where it fires | What it controls |
|---|---|---|
| `core.md` | Always (Stage 4) | Identity, persona, grounding rules, time/freshness, citation, data conventions, proactive patterns (DeItaone / podcast transcript scans) |
| `overlay.md` | Always (Stage 4) | Source tiers (T1/T2/T3) with specific names and when-to-use, hard filters, broad-query rules |
| `examples.md` | Always (Stage 4) | Three canonical few-shots showing the style (source query, contrasting houses, table format) |
| `modules/geo.md` | Conditional, m3xa only (Stage 4) | Iran both-sides rules, agent priority, content rules referenced by the geo schema |
| `modules/polymarket.md` | Conditional, both products (Stage 4) | "TOTAL SILENCE when absent" + how to weave market data into themes |
| `modules/charts.md` | Conditional, both products (Stage 4) | Chart-tag template `<!--CHART:TICKER:RANGE:TYPE-->` and when to emit it |
| `modules/brazilbrief.md` | m3xabr only, **enabled: false** | Spec preserved for the #brazilbrief command; not currently loaded |
| `output.md` | Always, LAST (Stage 4) | Telegram format rules: `<pre>` blocks, max widths, no pipe tables, MARKETS snapshot rule |

## Why this organization — design rationale

Three principles drove the v3.0 → v3.1 split:

1. **Position-aware prompting.** Hard rules first (core), output format last
   (output.md). The model's compliance is highest at the prompt boundaries.
2. **Smallest set of high-signal tokens.** v3 compressed the original
   5K-token monoliths to ~2K worst case by replacing rule laundry-lists with
   canonical examples and moving lessons to a corrections pipeline.
3. **Just-in-time context.** Only the modules the query needs are loaded.
   No "BRAZILBRIEF rules" in an Iran response.

The binary product split (v3.1) adds a fourth principle:

4. **Hard architectural boundaries beat soft filters.** The "BRAZIL INVISIBLE"
   rule in v3.0 was a prompt-level guard that said "if Brazil content leaks
   in, silently skip it." v3.1 removes the leak at the data layer instead —
   Brazil sources never enter m3xa's retrieval scope, so the prompt-level
   filter becomes obsolete. Structure beats instruction.

## A worked example — top to bottom

User in @M3xA_bot types: **"How has gold performed this month?"**

| Stage | What happens | Soul touched |
|---|---|---|
| 1 | Bot = @M3xA_bot → `product = 'm3xa'`, retrieval scope = macro sources only | — |
| 2a | LanceDB query: gold-tagged items from last 30 days, plus MARKETS LIVE snapshot for `GC=F` | — |
| 2b | Classifier: `{v3_tags: ['price_action'], model: 'haiku', thinking_budget: 0, confidence: 0.94}` | — |
| 3 | `router.route('m3xa', ['price_action'])` → `['m3xa/souls/modules/charts.md']` | `routing.yaml` |
| 4 | Assemble: `core.md` + `overlay.md` + `examples.md` + `charts.md` + DATA + `output.md` → 1,545 tok system prompt | `core.md`, `overlay.md`, `examples.md`, `charts.md`, `output.md` |
| 5 | Bedrock Haiku 4.5 generates: markdown narrative on gold's last 30 days, ending with a MARKETS `<pre>` block, plus a `<!--CHART:GC=F:1mo:candlestick-->` tag at the end | — |
| 6 | Telegram receives markdown + the chart tag triggers the chart image renderer | — |

Total: 1 Haiku call (classifier) + 1 Haiku call (generation) ≈ $0.001, ~3 seconds.

## The corollary — what's NOT in the flow

Things v3.1 deliberately removed compared to v3.0 or earlier:

- **No domain override LLM call** — Stage 1 is deterministic.
- **No "BRAZIL INVISIBLE" prompt rule** — Stage 2a is structural.
- **No "WHAT I HAVE GOTTEN WRONG" mistake-log section in souls** — moved to
  `corrections/candidates.jsonl` (see `docs/PROPOSAL.md`).
- **No static agents/data tables in soul** — entity context is just-in-time
  via retrieval.
- **No freeform geo response prose rules** — replaced by schema + renderer.

Each removal made the souls smaller, the failure modes simpler, and the
behavior more predictable.

## Where to go next

- `docs/ROUTING.md` — classifier + router deep dive
- `docs/MIGRATION_BINARY.md` — design rationale for the binary domain split
- `docs/PROPOSAL.md` — original v3 architecture proposal (compression goals)
- `docs/MIGRATION.md` — v3.0 → v3.1 phased migration plan
