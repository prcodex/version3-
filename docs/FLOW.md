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
        │  (b) Classification + Routing — ONE Haiku call against   │
        │      {product}/router_prompt.md                          │
        │      → JSON: { modules, model, thinking_budget,          │
        │                agents, reasoning, confidence }           │
        └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │  STAGE 3 — Modules selected (already done by 2b)         │
        │  Haiku returned conditional module file paths directly.  │
        │  Offline fallback path: router.route(product, tags) via  │
        │  routing.yaml — used by pytest / validate / dry-runs.    │
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
├── router_prompt.md  ← Haiku router ├── router_prompt.md  ← Haiku router
├── routing.yaml      ← fallback     ├── routing.yaml      ← fallback
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

## Stage 3 — Routing (Haiku picks modules)

The canonical runtime calls Haiku with `{product}/router_prompt.md` as
the system prompt, the user query as the user message, and a `signals`
block (currently `polymarket_data_present`) as context. Haiku returns
JSON with the module file paths to load and a one-line `reasoning` field
explaining the pick.

In practice this is the **same Haiku call** that does classification —
the prompt absorbs both responsibilities, so there's one model invocation
per query for the entire "what is this query and what modules cover it"
question.

`src/m3xa_souls/router.py` + `routing.yaml` are the **deterministic
offline fallback** — same rules expressed as YAML + a 50-line dict
lookup. Used by `pytest`, `validate`, `python -m m3xa_souls.assembler`,
and anywhere an LLM call is impractical (CI, eval rehearsals, debugging).

The two paths must stay in sync: any change to `router_prompt.md` needs
the matching change in `routing.yaml`. The eval harness checks parity
against the pinned-context query set.

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

### A concrete example — what Haiku actually sees

For the query **"Last 12h of the Iran war — full update"** sent to
`@M3xA_bot`, the Haiku router returns:

```json
{
  "modules": ["m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"],
  "reasoning": "Iran war timeline query + Polymarket data present in context → geo (priority 1) + polymarket (priority 2). Charts dropped (schema constraint)."
}
```

The assembler reads those files in order and emits **127 lines / 7,803
chars / 2,130 tokens** of system prompt. Here's the skeleton — full file
content lives in the linked files; each block shows the first lines as
a preview:

````markdown
# M3xA Core — Identity & Conventions          ← m3xa/souls/core.md (830 tok)

## IDENTITY
I am M3xA, a macro trading intelligence agent built for institutional-grade
financial analysis. I synthesize real-time market data, institutional research,
prediction markets, and curated news into actionable intelligence — the way an
experienced macro PM would brief their team.

## PERSONA RULES
- Never explain your internal architecture: no mention of context windows,
  injection, FeedCache, LanceDB, agents, pipelines, or prompt assembly.
[... 30 more lines: GROUNDING, TIME, DATA CONVENTIONS,
     PROACTIVE PATTERNS, CITATION ...]

---

# Global Macro Overlay                        ← m3xa/souls/overlay.md (468 tok)

LANGUAGE: English. SCOPE: global macro, US, Europe, Asia, commodities, FX, geopolitics.

## SOURCE TIERS
- T1 Institutional (cite house + date): Goldman, UBS, Gavekal, Rosenberg,
  Apollo/Slok, Exante (flow data, positioning, EM — quantitative macro lens).
- T2 Named specialists (cite by name):
  - Tony Pasquariello — cite as "Tony P (GS)" ...
[... overlay continues: HARD FILTER, BROAD QUERIES ...]

---

# Canonical Examples                          ← m3xa/souls/examples.md (196 tok)

EX1 — Source query ("any Gavekal recently?"):
"Over the past 7 days, two Gavekal notes: (1) Gavekal (Jun 8) argues China's
stimulus...; (2) Gavekal (Jun 10) sees EM FX... Sources: Gavekal_drv"
[... EX2 (contrasting houses), EX3 (table format) ...]

---

# Geo/Conflict Module                         ← m3xa/souls/modules/geo.md (336 tok)
                                                 (picked because query mentions Iran)

## IRAN — BOTH SIDES MANDATORY
US/Israel side (Trump, Pentagon, IDF) + Iran side (Pezeshkian, Araghchi,
IRGC — via Anadolu, Xinhua, Al Jazeera, Marandi, Vali Nasr, Iran International,
Sentinel Defender) + mediators (Turkey, China, Qatar). If Iran's voice is in
context, cite it; if absent, say so explicitly.

## EVALUATION (3 tiers)
[... agent priority, expert voices, response structure rules ...]

---

# Polymarket Module                           ← m3xa/souls/modules/polymarket.md (139 tok)
                                                 (picked because polymarket_data_present=true)

- Supporting evidence woven into themes — never a standalone section.
- Cite ONLY market names and prices verbatim from context. Never invent markets.
- Weave trends: "surging / plunging / stable" (daily/weekly).
- TOTAL SILENCE when absent: if no Polymarket data is in context, never mention
  Polymarket — no disclaimers, no "data unavailable."

---

{{AGENT_AND_DATA_CONTEXT}}                    ← placeholder; Gateway replaces
                                                 this with the retrieved data
                                                 block (see below)

---

# Output Format (Telegram — Global)           ← m3xa/souls/output.md (161 tok)

- Rich markdown: bold, bullets, headers allowed.
- Structured data (prices, polls, calendar, odds): `<pre>` blocks, aligned
  columns, max 35 chars wide. Narrative stays OUTSIDE `<pre>`.
- NEVER: markdown pipe tables, ASCII art/sparklines, raw JSON, decorative
  characters.
- Every time-windowed summary ends with a MARKETS `<pre>` snapshot:
  S&P, Oil, Gold, DXY, 10Y + assets impacted by the news (LIVE data).
- Inline event-to-price anchoring: "Shah field fire — Brent +2.1% at $92.40."
  Template: "EVENT at TIME → ASSET $BEFORE→$AFTER (±%) — WHY."
````

### What goes into the `{{AGENT_AND_DATA_CONTEXT}}` block

The Gateway replaces the placeholder with the retrieval block — the **only
part of the prompt that's different every query, and the only part not
cached.** For this Iran query, that block might look like:

```markdown
=== MARKET SNAPSHOT (LIVE, 2026-06-12 14:07 BRT) ===
Brent      $92.40   +2.1%  (intraday high $93.10)
WTI        $88.75   +1.9%
Gold       $2,438   +0.6%
S&P 500     5,890   -0.4%
DXY         104.7   +0.2%
10Y UST     4.42%   +3bp

=== IRAN PROXIES AGENT (updated 2h ago) ===
Houthi missile fire on commercial shipping in Bab-el-Mandeb (3 incidents
last 12h, 1 vessel hit). IRGC statement via PressTV: "all options open."
Hezbollah on Israel border: 4 cross-border exchanges, no escalation signals.

=== HORMUZ MONITOR (updated 4h ago) ===
Strait of Hormuz throughput: 19.2M bpd (vs 20.4M 7-day avg, -5.9%).
Stranded vessels: 7 (vs 3 baseline). No tanker hits reported.

=== TWITTER (filtered to last 12h) ===
@DeItaone 03:14 BRT — "BREAKING: Iran fires ballistic missiles at IDF
positions in northern Israel. Brent jumps $3/bbl in pre-market."
@DeItaone 03:22 BRT — "ISRAEL: Iron Dome intercepts majority of incoming;
no casualties reported."
@JavierBlas 04:01 BRT — "Hormuz throughput already down 5% vs 7-day avg.
Tanker rates spiking. Premium being built in is real, not noise."
@vali_nasr 06:30 BRT — "Pezeshkian's choice: respond now or wait for
Russia/China mediation. Either path locks in escalation."
@s_m_marandi (Anadolu) 07:00 BRT — "Iran demands return to JCPOA terms
before any de-escalation. Araghchi statement on state TV."

=== POLYMARKET (Iran-related, Top 5 by volume) ===
"Iran-Israel direct strikes by July 1?" YES 78¢ (was 71¢ 24h ago, +7pp,
  $4.2M vol)
"Strait of Hormuz closure by Aug 31?" YES 22¢ (was 18¢, +4pp, $1.8M)
"Brent > $100 by end of June?" YES 41¢ (was 33¢, +8pp, $2.1M)
"Trump-Pezeshkian meeting by Sept 30?" YES 12¢ (was 14¢, -2pp, $0.9M)
"Ceasefire announced by July 15?" YES 19¢ (was 27¢, -8pp, $1.4M)

=== INSTITUTIONAL RESEARCH (last 7 days) ===
Goldman Sachs (Jun 8): "Iran risk premium adding $8-12/bbl to Brent.
  Base case: contained strikes, no Hormuz closure. Bear case (20% prob):
  $130 Brent on 30-day disruption."
Tony P (GS, Jun 10): "Discretionary positioning long oil + USD, short EM FX.
  Vol curves pricing 1-sigma move on any escalation headline."
JPOST (Jun 11): "IDF readying second-strike capability. Pentagon official
  on background: 'two days, maybe three' before next exchange."

=== CONFLICT TRACKER (auto-classified, last 24h) ===
Escalation score: 7.2/10 (vs 5.8 yesterday)
Missile launches: 14 (Iran→Israel: 9, Houthi→Red Sea: 3, IDF→Lebanon: 2)
Diplomatic statements: 11 (5 escalatory, 4 neutral, 2 de-escalatory)

=== USER QUERY ===
Last 12h of the Iran war — full update
```

That ~1.5K-token data block + the 2,130-token system prompt above = total
inference cost.

### Generation

Because **geo fired**, the assembler also passes
`schemas/geo_response.schema.json` as the structured output constraint.
The router prompt told Haiku to drop charts when geo loads (schema
clash), so the response is JSON in the shape:

```json
{
  "data_window": "2026-06-12 02:00 to 14:00 BRT",
  "timeline": [
    {"time": "03:14 BRT", "event": "Iran fires ballistic missiles at IDF...",
     "source": "@DeItaone"},
    ...
  ],
  "actors": [
    {"name": "Iran", "summary": "Direct missile fire ... (Araghchi statement)",
     "sources": ["s_m_marandi (Jun 12)", "Anadolu (Jun 12)"]},
    ...
  ],
  "market_reaction": {
    "assets": [
      {"ticker": "Brent", "before": 90.50, "after": 92.40, "pct": 2.1,
       "why": "Direct strike fears + Hormuz disruption"},
      ...
    ]
  },
  "experts": [...],
  "prediction_markets": [...],
  "what_to_watch": [...]
}
```

`renderer.render_geo()` then converts that JSON into Telegram HTML.
**Format compliance is structural** — Haiku can't write a freeform
introduction even if it wanted to, because the schema's first key is
`data_window`, not "prose."

### What gets cached vs not

```
   ┌─────────────────────────────────────────────────────────┐
   │ STATIC PREFIX (cache hit after first warm)              │
   │   core.md + overlay.md + examples.md +                  │
   │   geo.md + polymarket.md + output.md  = 2,130 tok       │  cached 1h TTL
   │   (cache key: m3xa + [iran, polymarket_data])           │
   └─────────────────────────────────────────────────────────┘
   ┌─────────────────────────────────────────────────────────┐
   │ DYNAMIC DATA (always fresh)                              │
   │   retrieval block + user query  ≈ 1,500 tok             │  never cached
   └─────────────────────────────────────────────────────────┘
```

For the second Iran query in the same hour, only the dynamic part incurs
full token cost. The 2,130-token system prompt is a cache hit.

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
| 3 | Haiku router (`m3xa/router_prompt.md`) returns `{modules: ['m3xa/souls/modules/charts.md'], reasoning: "price-action query on gold → charts only"}`. Offline path: `router.route('m3xa', ['price_action'])` would give the same answer via `routing.yaml`. | `m3xa/router_prompt.md`, `routing.yaml` |
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
