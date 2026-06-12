# M3xA Souls v3 — Layered Composition Architecture

Modular, classifier-routed soul system for M3xA response agents (Haiku 4.5 via Bedrock).
Replaces monolithic `soul_global.md` / `soul_brazil.md` (~5K tokens, 60+ directives) with
position-aware layered assembly targeting ≤2.6K instruction tokens worst case.

## Why v3
- Instruction compliance decays ~exponentially with directive count ("curse of instructions").
- Reasoning degrades past ~3K input tokens; Haiku needs minimal high-signal context.
- Rules in the middle of long prompts get lost (primacy/recency); v3 places hard rules
  first and output format last, adjacent to generation.
- Few canonical examples replace rule laundry-lists (Anthropic context-engineering guidance).

## Architecture

```mermaid
%%{init: {'theme': 'default', 'themeVariables': {'fontSize': '22px', 'fontFamily': 'Inter, system-ui, -apple-system, sans-serif'}, 'flowchart': {'htmlLabels': true, 'curve': 'basis', 'nodeSpacing': 55, 'rankSpacing': 90, 'padding': 20}}}%%
flowchart TB
    subgraph RUNTIME["<b>⚡ Runtime — per query (Gateway)</b>"]
        direction TB
        U(["<b>👤 User query</b><br/><b>Telegram / Web</b>"]) --> CLS["<b>soul_classifier</b><br/><b>emits product + tags</b><br/>m3xa · m3xabr<br/>iran · polymarket_data · price_action"]
        CLS --> RTR["<b>router.py</b><br/><b>tags → modules</b><br/>priority: geo &gt; brief &gt; pm &gt; charts<br/><b>max 2 modules</b>"]
        RTR --> ASM["<b>assembler.py</b><br/><b>position-aware concatenation</b><br/>+ token report"]
        ENT["<b>entity_*.md cards</b><br/><b>JIT injection</b> — only sources<br/>present in retrieved data"] --> FEED
        FEED[("<b>FeedCache / LanceDB</b><br/><b>118K+ rows</b><br/>AGENT + DATA CONTEXT")] --> ASM
        ASM --> HAIKU["<b>🧠 Claude Haiku 4.5</b><br/><b>via Bedrock</b>"]
        HAIKU --> TG(["<b>📱 Telegram response</b>"])
    end

    subgraph ORDER["<b>🧩 Assembly order — worst case 2,130 tok m3xa / 1,853 tok m3xabr (budget 2,600)</b>"]
        direction TB
        C1["<b>1. {product}/souls/core.md</b><br/><b>m3xa 830 · m3xabr 835 tok</b><br/>identity · grounding · proactive patterns<br/>time · citation"]
        C2["<b>2. {product}/souls/overlay.md</b><br/><b>m3xa 468 · m3xabr 489 tok</b><br/>source tiers (named + cited)<br/>Brazil hard filter · identity rules"]
        C3["<b>3. conditional modules — max 2</b><br/>geo 336 (m3xa only, schema-constrained)<br/>polymarket 139 · charts 112<br/>(brazilbrief disabled)"]
        C4["<b>4. {product}/souls/examples.md</b><br/><b>m3xa 196 · m3xabr 160 tok</b><br/>3 canonical few-shots"]
        C5["<b>5. AGENT_AND_DATA_CONTEXT</b><br/>placeholder<br/>Gateway inserts live feed here"]
        C6["<b>6. {product}/souls/output.md</b><br/><b>m3xa 161 · m3xabr 142 tok</b><br/><b>format rules LAST</b> — recency effect"]
        C1 --> C2 --> C3 --> C4 --> C5 --> C6
    end
    ASM -. <b>builds</b> .-> C1

    subgraph CI["<b>🔁 Build · eval · governance</b>"]
        direction TB
        GH["<b>GitHub</b><br/>prcodex/version3-"] --> ACT["<b>GitHub Actions CI</b>"]
        ACT --> VAL["<b>validate.py</b><br/>budgets · duplicate rules<br/>forbidden patterns"]
        ACT --> TST["<b>pytest</b><br/>14 tests"]
        ACT --> CMP["<b>compiler.py → dist/</b><br/>soul_m3xa_compiled ~2.1K tok<br/>soul_m3xabr_compiled ~1.8K tok"]
        CMP --> DEP["<b>deploy</b><br/>sync dist/ → House store<br/>bridge mode until Gateway<br/>assembles natively"]
        RC["<b>rubric-collector</b><br/>auto-detections"] --> CAND["<b>corrections/candidates.jsonl</b><br/>status: candidate<br/><b>NEVER touches a live soul</b>"]
        CAND -- "<b>human PROMOTE</b><br/>→ positive rule" --> MODS["<b>owning module</b><br/>in souls/"]
        CAND -- "<b>REJECT</b>" --> HIST["<b>corrections/history.jsonl</b>"]
        EVQ["<b>eval/queries.yaml</b><br/>12 pinned queries"] --> EVR["<b>run_eval.py — OLD vs NEW</b><br/>scored with evaluator_rubric.md"]
        EVR -- "<b>cutover:</b><br/>NEW ≥ OLD everywhere" --> DEP
    end
    DEP -. <b>loaded by</b> .-> ASM
    MODS -. <b>re-validate + recompile</b> .-> ACT

    C6 ~~~ GH

    click C1 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/core.md" _blank
    click C2 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/overlay.md" _blank
    click C3 "https://github.com/prcodex/version3-/tree/main/m3xa/souls/modules" _blank
    click C4 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/examples.md" _blank
    click C6 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/output.md" _blank
    click RTR "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/router.py" _blank
    click ASM "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/assembler.py" _blank
    click VAL "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/validate.py" _blank
    click CMP "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/compiler.py" _blank
    click CAND "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/corrections.py" _blank
    click EVQ "https://github.com/prcodex/version3-/blob/main/eval/queries.yaml" _blank
    click EVR "https://github.com/prcodex/version3-/blob/main/eval/run_eval.py" _blank
    click GH "https://github.com/prcodex/version3-" _blank
    click ACT "https://github.com/prcodex/version3-/blob/main/.github/workflows/ci.yml" _blank

    style RUNTIME fill:#dbeafe,stroke:#1e40af,stroke-width:3px,color:#0f172a
    style ORDER fill:#dcfce7,stroke:#166534,stroke-width:3px,color:#0f172a
    style CI fill:#f3e8ff,stroke:#7e22ce,stroke-width:3px,color:#0f172a
    style HAIKU fill:#fed7aa,stroke:#c2410c,stroke-width:4px,color:#7c2d12
    style C5 fill:#f1f5f9,stroke:#94a3b8,stroke-width:2px,stroke-dasharray:6 4,color:#0f172a
    style FEED fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#0f172a
    style ENT fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#0f172a
    style CAND fill:#fee2e2,stroke:#b91c1c,stroke-width:2px,color:#0f172a
    style MODS fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#0f172a
    style DEP fill:#ddd6fe,stroke:#6d28d9,stroke-width:2px,color:#0f172a
```

## Layout
Two self-contained products, routed UPFRONT by the Gateway — no shared locale switch:

```
m3xa/         Global macro agent (English)
  souls/      core.md · overlay.md · examples.md · output.md · modules/{geo,polymarket,charts}.md
  routing.yaml  tag→module map, model tiering, cache config, token budgets
m3xabr/       Brazil agent (PT-BR) — own core, own identity, own routing
  souls/      core.md · overlay.md · examples.md · output.md · modules/{polymarket,charts,brazilbrief*}.md
  routing.yaml  (*brazilbrief present but enabled: false — deprioritized)
schemas/      geo_response.schema.json — Bedrock structured-output grammar
src/          assembler (cache-aware bedrock_payload), router, renderer, compiler, validator, corrections
eval/         12-query old-vs-new harness scored against evaluator_rubric
tests/        pytest suite; CI enforces budgets and lint on every PR
```

## Per-product detail

Two products, two diagrams — same assembly grammar, different content. Each block is the **actual token count** in the repo as of `e1fbf45`.

### m3xa — Global Macro (English)

```mermaid
%%{init: {'theme': 'default', 'themeVariables': {'fontSize': '22px', 'fontFamily': 'Inter, system-ui, -apple-system, sans-serif'}, 'flowchart': {'htmlLabels': true, 'curve': 'basis', 'nodeSpacing': 55, 'rankSpacing': 80, 'padding': 18}}}%%
flowchart TB
    BOT(["<b>👤 @M3xA_bot · web</b><br/>English query"]) --> CLS["<b>soul_classifier</b><br/>product = <b>m3xa</b><br/>tags ⊂ {iran · polymarket_data · price_action · trend · performance}"]
    CLS --> RTR["<b>router</b> (m3xa/routing.yaml)<br/>priority: geo &gt; polymarket &gt; charts<br/><b>max 2 modules</b>"]

    subgraph ALWAYS["<b>🟦 ALWAYS LOADED · 1,494 tok</b>"]
        direction TB
        A1["<b>core.md · 830 tok</b><br/>identity · grounding · proactive patterns<br/>time · citation"]
        A2["<b>overlay.md · 468 tok</b><br/>T1/T2/T3 source tiers (named + cited)<br/><b>Brazil hard-filter</b>"]
        A3["<b>examples.md · 196 tok</b><br/>3 canonical few-shots"]
        A1 --> A2 --> A3
    end

    subgraph COND["<b>🟨 CONDITIONAL · classifier-routed · max 2</b>"]
        direction TB
        G["<b>geo.md · 336 tok</b> · priority 1<br/>tags: iran · war · geopolitics<br/>conflict · hormuz<br/><b>📐 schema: geo_response.schema.json</b><br/>(structured output via constrained decoding)"]
        P["<b>polymarket.md · 139 tok</b> · priority 2<br/>tag: <b>polymarket_data</b><br/>(set by Gateway when PM data in context)"]
        CH["<b>charts.md · 112 tok</b> · priority 3<br/>tags: price_action · trend · performance"]
    end

    subgraph OUTBLK["<b>🟩 OUTPUT · always LAST</b>"]
        direction TB
        OUT["<b>output.md · 161 tok</b><br/>Telegram format<br/>&lt;pre&gt; blocks · no pipe tables"]
    end

    RTR --> ALWAYS
    ALWAYS --> COND
    COND --> OUTBLK
    OUTBLK --> MODEL["<b>🧠 Model</b><br/>default: <b>Claude Haiku 4.5</b><br/>override: <b>broad/deep → Sonnet 4.6</b>"]
    MODEL --> CACHE["<b>💾 Bedrock prompt cache</b><br/>1h TTL · cache_control on static prefix<br/>data context rides in user message"]
    CACHE --> GEN(["<b>📤 Telegram response</b><br/>via renderer.render_geo() when schema fires"])

    META["<b>📊 Budget profile</b><br/>WORST CASE (iran + polymarket_data): <b>2,130 tok</b><br/>TYPICAL (no tags): 1,655 tok<br/>BUDGET: 2,600 tok"]
    GEN -.-> META

    click A1 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/core.md" _blank
    click A2 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/overlay.md" _blank
    click A3 "https://github.com/prcodex/version3-/blob/main/m3xa/souls/examples.md" _blank
    click G "https://github.com/prcodex/version3-/blob/main/m3xa/souls/modules/geo.md" _blank
    click P "https://github.com/prcodex/version3-/blob/main/m3xa/souls/modules/polymarket.md" _blank
    click CH "https://github.com/prcodex/version3-/blob/main/m3xa/souls/modules/charts.md" _blank
    click OUT "https://github.com/prcodex/version3-/blob/main/m3xa/souls/output.md" _blank
    click RTR "https://github.com/prcodex/version3-/blob/main/m3xa/routing.yaml" _blank
    click CLS "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/router.py" _blank

    style ALWAYS fill:#dbeafe,stroke:#1e40af,stroke-width:3px,color:#0f172a
    style COND fill:#fef3c7,stroke:#b45309,stroke-width:3px,color:#0f172a
    style OUTBLK fill:#dcfce7,stroke:#166534,stroke-width:3px,color:#0f172a
    style MODEL fill:#fed7aa,stroke:#c2410c,stroke-width:3px,color:#7c2d12
    style CACHE fill:#ddd6fe,stroke:#6d28d9,stroke-width:3px,color:#0f172a
    style META fill:#f1f5f9,stroke:#475569,stroke-width:2px,stroke-dasharray:6 4,color:#0f172a
    style G fill:#fef9c3,stroke:#b45309,stroke-width:2px,color:#0f172a
    style P fill:#fef9c3,stroke:#b45309,stroke-width:2px,color:#0f172a
    style CH fill:#fef9c3,stroke:#b45309,stroke-width:2px,color:#0f172a
```

### m3xabr — Brazil (PT-BR)

```mermaid
%%{init: {'theme': 'default', 'themeVariables': {'fontSize': '22px', 'fontFamily': 'Inter, system-ui, -apple-system, sans-serif'}, 'flowchart': {'htmlLabels': true, 'curve': 'basis', 'nodeSpacing': 55, 'rankSpacing': 80, 'padding': 18}}}%%
flowchart TB
    BOT(["<b>👤 @M3xabr_bot · web</b><br/>Pergunta em PT-BR"]) --> CLS["<b>soul_classifier</b><br/>product = <b>m3xabr</b><br/>tags ⊂ {polymarket_data · price_action · trend · performance}"]
    CLS --> RTR["<b>router</b> (m3xabr/routing.yaml)<br/>priority: polymarket &gt; charts<br/><b>max 2 modules</b>"]

    subgraph ALWAYS["<b>🟦 SEMPRE CARREGADO · 1,484 tok</b>"]
        direction TB
        A1["<b>core.md · 835 tok</b><br/>identidade (PT-BR) · fundamentação<br/><b>POLÍTICA BRASILEIRA (Exec/Leg/Judic)</b><br/>tempo · citação"]
        A2["<b>overlay.md · 489 tok</b><br/>Tiers de fontes T1/T2/T3 (nomes + templates)<br/>regras rígidas de identidade<br/>câmbio · pesquisas (metodologia)"]
        A3["<b>examples.md · 160 tok</b><br/>exemplos canônicos em PT-BR"]
        A1 --> A2 --> A3
    end

    subgraph COND["<b>🟨 CONDICIONAL · roteado pelo classificador · max 2</b>"]
        direction TB
        P["<b>polymarket.md · 119 tok</b> · priority 1<br/>tag: <b>polymarket_data</b><br/>(definido pelo Gateway quando há dados PM)"]
        CH["<b>charts.md · 108 tok</b> · priority 2<br/>tags: price_action · trend · performance"]
        BB["<b>brazilbrief.md · 320 tok budget</b> · priority 3<br/><b>⚠️ enabled: false — DEPRIORITIZED</b><br/>no repo mas nunca carregado"]
    end

    subgraph OUTBLK["<b>🟩 SAÍDA · sempre por ÚLTIMO</b>"]
        direction TB
        OUT["<b>output.md · 142 tok</b><br/>formato Telegram BR<br/>tabelas &lt;pre&gt; max 30 chars · sem ## headers"]
    end

    RTR --> ALWAYS
    ALWAYS --> COND
    COND --> OUTBLK
    OUTBLK --> MODEL["<b>🧠 Modelo</b><br/>default: <b>Claude Haiku 4.5</b><br/>overrides: {} (nenhum por enquanto)"]
    MODEL --> CACHE["<b>💾 Bedrock prompt cache</b><br/>1h TTL · cache_control no prefixo estático<br/>data context vai na user message"]
    CACHE --> GEN(["<b>📤 Resposta no Telegram</b>"])

    META["<b>📊 Perfil de orçamento</b><br/>WORST CASE (polymarket + charts): <b>1,853 tok</b><br/>TÍPICO (sem tags): 1,626 tok<br/>BUDGET: 2,600 tok"]
    GEN -.-> META

    NOTE["<b>📌 Notas específicas do m3xabr</b><br/>• Sem módulo geo — geo queries roteadas pra m3xa<br/>• Sem schema estruturado — Haiku livre<br/>• brazilbrief mantido por spec, mas <b>NÃO carregado</b><br/>(bastidores narrativo voltará via Sonnet override)"]
    META -.-> NOTE

    click A1 "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/core.md" _blank
    click A2 "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/overlay.md" _blank
    click A3 "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/examples.md" _blank
    click P "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/modules/polymarket.md" _blank
    click CH "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/modules/charts.md" _blank
    click BB "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/modules/brazilbrief.md" _blank
    click OUT "https://github.com/prcodex/version3-/blob/main/m3xabr/souls/output.md" _blank
    click RTR "https://github.com/prcodex/version3-/blob/main/m3xabr/routing.yaml" _blank
    click CLS "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/router.py" _blank

    style ALWAYS fill:#dbeafe,stroke:#1e40af,stroke-width:3px,color:#0f172a
    style COND fill:#fef3c7,stroke:#b45309,stroke-width:3px,color:#0f172a
    style OUTBLK fill:#dcfce7,stroke:#166534,stroke-width:3px,color:#0f172a
    style MODEL fill:#fed7aa,stroke:#c2410c,stroke-width:3px,color:#7c2d12
    style CACHE fill:#ddd6fe,stroke:#6d28d9,stroke-width:3px,color:#0f172a
    style META fill:#f1f5f9,stroke:#475569,stroke-width:2px,stroke-dasharray:6 4,color:#0f172a
    style NOTE fill:#fae8ff,stroke:#a21caf,stroke-width:2px,stroke-dasharray:6 4,color:#0f172a
    style P fill:#fef9c3,stroke:#b45309,stroke-width:2px,color:#0f172a
    style CH fill:#fef9c3,stroke:#b45309,stroke-width:2px,color:#0f172a
    style BB fill:#e5e7eb,stroke:#9ca3af,stroke-width:2px,stroke-dasharray:5 5,color:#475569
```

## v3.1 upgrades
- **Two products**: `assemble("m3xa"|"m3xabr", tags)` — fully isolated soul stacks.
- **Prompt caching (Bedrock, 1h TTL)**: `bedrock_payload()` returns system blocks with
  `cache_control` on the static prefix; data context always rides in the user message.
  Compiled monoliths are byte-identical per product => fully cacheable (~0.1x reads).
- **Structured outputs**: geo queries generate JSON under `schemas/geo_response.schema.json`
  via constrained decoding; `m3xa_souls.renderer.render_geo()` builds the Telegram HTML.
  Format compliance lives in code, not prompt rules.
- **Model tiering**: per-tag override in routing.yaml (e.g. `broad → claude-sonnet-4-6`).

## Quick start
```bash
pip install -e ".[dev]"
make validate          # lint all souls: budgets, forbidden patterns, duplicate rules
make compile           # materialize compiled souls for single-file gateways
pytest
python -m m3xa_souls.assembler --product m3xa --tags iran,polymarket_data --report
python -m m3xa_souls.assembler --product m3xa --tags iran --bedrock-json   # cache blocks + schema
```

## Gateway integration (two modes)
1. **Native**: Gateway calls `assemble(product, tags)` / `bedrock_payload(product, tags)` per query (preferred).
2. **Pre-compiled**: `compiler.py` materializes `dist/soul_m3xa_compiled.md` and
   `dist/soul_m3xabr_compiled.md` on every merge to main; Gateway keeps loading one file.
   (Bridge mode until Gateway supports multi-file assembly.)

## Routing & classification

See **[docs/ROUTING.md](docs/ROUTING.md)** for the full classification +
routing pipeline: how the soul_classifier (Haiku, JSON output) and
`router.py` (deterministic Python) work together, the tag vocabulary,
worked examples, and failure modes.

See **[docs/MIGRATION_BINARY.md](docs/MIGRATION_BINARY.md)** for the
planned binary-domain migration: making the m3xa vs m3xabr split fully
deterministic at the retrieval layer (drops one LLM call, drops the
soul-level "BRAZIL INVISIBLE" rule, simplifies failure modes).

## Corrections pipeline
Rubric-collector auto-detections land in `corrections/candidates.jsonl` — never in a live
soul. Promotion requires human approval and rewrites the lesson as a POSITIVE rule in the
owning module via `python -m m3xa_souls.corrections promote <id> --module modules/geo.md`.
