# Souls v3 Proposal — Layered Composition

## Problem
soul_global.md (~5K tok, 60+ directives) and soul_brazil.md (~4K tok) run on
Haiku 4.5. Instruction compliance decays roughly exponentially with directive
count ("curse of instructions", Harada et al. 2024); reasoning degrades past
~3K input tokens; rules buried mid-prompt suffer the lost-in-the-middle effect.
Symptoms observed in production: duplicated rules (Polymarket silence stated
3x), mistake-log sections re-stating codified rules, and rubric-collector
auto-detections appended unreviewed — including one that instructs the agent
to promise monitoring implementation (a hallucination generator).

## Design principles (Anthropic context-engineering guidance)
1. Smallest set of high-signal tokens. 2. Canonical examples over rule
laundry-lists. 3. Just-in-time context (entity cards injected only when the
source appears in retrieved data). 4. Right altitude: heuristics, not scripts.
5. Position-aware: hard rules first, output format last.

## Architecture
core (always) -> locale overlay -> conditional modules (classifier-routed,
max 2, priority geo > brazilbrief > polymarket > charts) -> examples ->
[AGENT+DATA CONTEXT] -> output format (always last).

Measured budgets (chars/3.6): worst case 1,886 tok; typical 1,445 tok;
old monoliths ~5,000 tok. Gate: validate.py fails CI on budget breach,
duplicate rules, or forbidden patterns.

## Corrections pipeline
Auto-detections -> corrections/candidates.jsonl (status: candidate).
Human promote -> rewritten as a positive rule appended to the owning module
+ logged to corrections/history.jsonl. Reject -> logged with reason.
Deleted on migration: global #18/#19 (system-level), brazil auto-entry
(promises implementation timelines). Global #20 partially folded into
core grounding rule 6.

## Gateway integration
Native mode: call assemble(locale, tags) per query (preferred; preserves
routing). Bridge mode: CI compiles dist/soul_{locale}_compiled.md monoliths —
Gateway keeps loading one file, still gains dedup + ordering (~2.0K/2.2K tok).
Future Gateway change wanted: inject only the roster of agents that returned
data (the static agents table was removed from core).

## Eval & cutover
12 pinned-context queries (eval/queries.yaml), OLD vs NEW, both scored with
evaluator_rubric.md. Cutover: NEW >= OLD everywhere, strictly better on
format compliance + grounding. Old souls kept as .bak for 1 week.


## v3.1 Addendum (Jun 2026)
1. Two self-contained products (m3xa, m3xabr) routed upfront — no shared locale
   parameter; each has its own core/identity, routing.yaml, budgets, language.
2. Bedrock prompt caching (1h TTL, GA on Haiku 4.5 Jan-2026): assembler emits
   cache_control on the static system prefix; data context in the user message.
   Compiled monoliths are fully cacheable => ~0.1x input price on reads.
3. Structured outputs (GA on Bedrock Feb-2026): geo responses constrained to
   schemas/geo_response.schema.json; renderer.py builds Telegram HTML. Format
   rules move from prompt to decoder + code (Polymarket silence is structural:
   empty array => section omitted).
4. Model tiering per tag in routing.yaml (broad/deep -> Sonnet 4.6).
5. brazilbrief deprioritized: module retained, enabled: false.
Next candidates (not yet implemented): GEPA module evolution on top of the
Phase-2 eval harness, using evaluator_rubric feedback as ASI.
