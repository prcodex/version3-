# Migration Plan

Phase 0 — Repo live (this commit). `make validate && pytest` green.
Phase 1 — Pin contexts: export one real FeedCache snapshot per eval query to
  eval/context/{id}.txt; copy current soul_global.md/soul_brazil.md to eval/old/.
Phase 2 — Wire live eval (eval/run_eval.py) to the existing M3xA Bedrock
  client; run both arms; score with evaluator_rubric.md; record in repo.
Phase 3 — Gateway: EITHER (a) add multi-file assemble() call, OR (b) point the
  soul loader at dist/soul_{locale}_compiled.md and add a deploy step that
  syncs dist/ to the House store on merge to main.
Phase 4 — Classifier: extend soul_classifier to emit the routing tags
  (iran/war/geopolitics, polymarket_data [set by Gateway when Polymarket
  data is in context], price_action, broad/deep (model tiering); brazilbrief deferred).
Phase 5 — Rubric-collector: redirect output from soul appends to
  `python -m m3xa_souls.corrections add --source rubric-collector`.
Phase 6 — Cutover per eval criterion; archive old souls as .bak in the House
  store; monitor 1 week; delete .bak.

Rollback: repoint Gateway soul loader at the .bak monoliths (single config change).

Phase 3b — Gateway adopts bedrock_payload(): cache_control blocks + output_config
  for geo; route Telegram rendering of geo JSON through m3xa_souls.renderer.
