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
flowchart TB
    subgraph RUNTIME["⚡ Runtime — per query (Gateway)"]
        direction TB
        U(["👤 User query — Telegram / Web"]) --> CLS["soul_classifier — emits locale + tags<br/>iran · brazilbrief · polymarket_data · price_action"]
        CLS --> RTR["router.py<br/>tags → modules · priority geo &gt; brief &gt; pm &gt; charts · max 2"]
        RTR --> ASM["assembler.py<br/>position-aware concatenation + token report"]
        ENT["entity_*.md cards — JIT injection<br/>only sources present in retrieved data"] --> FEED
        FEED[("FeedCache / LanceDB 118K+<br/>AGENT + DATA CONTEXT")] --> ASM
        ASM --> HAIKU["Claude Haiku 4.5 — Bedrock"]
        HAIKU --> TG(["📱 Telegram response"])
    end

    subgraph ORDER["🧩 Assembly order — worst case 1,886 tok measured (budget 2,600)"]
        direction TB
        C1["1. core/soul_core.md — 712 tok<br/>identity · grounding · time · citation"]
        C2["2. overlays/global.md 376 tok | overlays/brazil.md 344 tok<br/>source tiers · Brazil hard filter · identity rules"]
        C3["3. conditional modules — max 2<br/>geo 302 · polymarket 139 · brazilbrief 187 · charts 112"]
        C4["4. examples/examples.md — 196 tok<br/>3 canonical few-shots"]
        C5["5. AGENT_AND_DATA_CONTEXT placeholder<br/>Gateway inserts live feed here"]
        C6["6. output/global.md 161 | output/brazil.md 142<br/>format rules LAST — recency effect"]
        C1 --> C2 --> C3 --> C4 --> C5 --> C6
    end
    ASM -. builds .-> C1

    subgraph CI["🔁 Build · eval · governance"]
        direction TB
        GH["GitHub — prcodex/version3-"] --> ACT["GitHub Actions CI"]
        ACT --> VAL["validate.py<br/>budgets · duplicate rules · forbidden patterns"]
        ACT --> TST["pytest — 9 tests"]
        ACT --> CMP["compiler.py → dist/<br/>soul_global_compiled ~2.0K · soul_brazil_compiled ~2.2K"]
        CMP --> DEP["deploy: sync dist/ → House store<br/>bridge mode until Gateway assembles natively"]
        RC["rubric-collector auto-detections"] --> CAND["corrections/candidates.jsonl<br/>status: candidate — NEVER touches a live soul"]
        CAND -- "human PROMOTE → positive rule" --> MODS["owning module in souls/"]
        CAND -- REJECT --> HIST["corrections/history.jsonl"]
        EVQ["eval/queries.yaml — 12 pinned queries"] --> EVR["run_eval.py — OLD vs NEW<br/>scored with evaluator_rubric.md"]
        EVR -- "cutover: NEW ≥ OLD everywhere" --> DEP
    end
    DEP -. loaded by .-> ASM
    MODS -. re-validate + recompile .-> ACT

    click C1 "https://github.com/prcodex/version3-/blob/main/souls/core/soul_core.md" _blank
    click C2 "https://github.com/prcodex/version3-/tree/main/souls/overlays" _blank
    click C3 "https://github.com/prcodex/version3-/tree/main/souls/modules" _blank
    click C4 "https://github.com/prcodex/version3-/blob/main/souls/examples/examples.md" _blank
    click C6 "https://github.com/prcodex/version3-/tree/main/souls/output" _blank
    click RTR "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/router.py" _blank
    click ASM "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/assembler.py" _blank
    click VAL "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/validate.py" _blank
    click CMP "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/compiler.py" _blank
    click CAND "https://github.com/prcodex/version3-/blob/main/src/m3xa_souls/corrections.py" _blank
    click EVQ "https://github.com/prcodex/version3-/blob/main/eval/queries.yaml" _blank
    click EVR "https://github.com/prcodex/version3-/blob/main/eval/run_eval.py" _blank
    click GH "https://github.com/prcodex/version3-" _blank
    click ACT "https://github.com/prcodex/version3-/blob/main/.github/workflows/ci.yml" _blank

    style RUNTIME fill:#0b2942,stroke:#4aa3df,color:#e8f1f8
    style ORDER fill:#1c2b1c,stroke:#6abf69,color:#e9f5e9
    style CI fill:#2b1c2b,stroke:#c77dba,color:#f5e9f5
    style HAIKU fill:#d97706,stroke:#92400e,color:#fff
    style C5 fill:#374151,stroke:#9ca3af,color:#fff,stroke-dasharray: 5 5
```

## Layout
```
souls/        Markdown modules (the actual prompt content)
  core/       Always loaded — identity, grounding, citation (~0.9K tok)
  overlays/   Locale layer: global | brazil (~0.5K tok)
  modules/    Conditional, classifier-routed: geo, polymarket, brazilbrief, charts
  output/     Format rules — always assembled LAST
  examples/   Canonical few-shot examples
routing/      routing.yaml — tag→module map, priorities, token budgets
src/          Python: assembler, router, compiler, validator, corrections pipeline
eval/         12-query old-vs-new harness scored against evaluator_rubric
tests/        pytest suite; CI enforces budgets and lint on every PR
```

## Quick start
```bash
pip install -e ".[dev]"
make validate          # lint all souls: budgets, forbidden patterns, duplicate rules
make compile           # materialize compiled souls for single-file gateways
pytest
python -m m3xa_souls.assembler --locale global --tags iran,price_action --report
```

## Gateway integration (two modes)
1. **Native**: Gateway calls `assemble(locale, tags)` per query (preferred).
2. **Pre-compiled**: `compiler.py` materializes `dist/soul_global_compiled.md` and
   `dist/soul_brazil_compiled.md` on every merge to main; Gateway keeps loading one file.
   (Bridge mode until Gateway supports multi-file assembly.)

## Corrections pipeline
Rubric-collector auto-detections land in `corrections/candidates.jsonl` — never in a live
soul. Promotion requires human approval and rewrites the lesson as a POSITIVE rule in the
owning module via `python -m m3xa_souls.corrections promote <id> --module modules/geo.md`.
