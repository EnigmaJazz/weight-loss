# Duolingo-style art pass (fox, island, plants, quest icons)
Objective: restyle every visual asset to one flat, outline-free, Duolingo-like cartoon style and make the island richer.
Branch: feat/r2a-island-polish · Delivery: ask-on-risk (chain question deferred to PR time) · Runners: `.venv/bin/python -m pytest -q`, `node --test tests/frontend/*.test.mjs`, `tests/smoke-ui.sh`

## Specs
- S1: Fox redraw — "the main fox image does not look like a cartoon fox as intended, the artistic style is meant to be similar to duolingo". Head symbol for header + PWA icon, full-body pose on the island; icon generator stays in lockstep.
- S2: "do a similar pass over all the existing icons and island to match the style" — island trees/sprout/bushes/flowers restyled flat, outline-free, with Duolingo-style shading.
- S3: "can we make the island more interesting with some baseline scenery items" — scenery present at every stage (e.g. clouds, beach, rocks, waves).
- S4: "and a background that is more intersting" — richer sky/sea backdrop (layers, distant hills/islands, sun treatment), token fills only, both themes.
- S5: "a similar pass over all the existing icons" — the 16 collectible plants restyled outline-free (shared by the island and the Journey shelf); locked silhouettes still work.
- S6: "a similar pass over all the existing icons" — the 9 quest domain icons redrawn as colourful flat icons (token colours, no hex, still currentColor-compatible per existing tests).
- Constraints (existing gates): token-only fills (no hex in island/ip-* rules or SVG), 5 ordered stage groups with the fox in each, 16 unique plant keys, World panel ships exactly one SVG, reduced-motion kills island motion.

## Tasks
- T1 [S1] inline — fox head + full body + SVG-parsing icon generator — commit: pending
- T2 [S2,S3,S4] inline — island backdrop, scenery, restyled trees — commit: pending
- T3 [S5] inline — 16 plants outline-free — commit: pending
- T4 [S6] inline — 9 quest icons colourful — commit: pending

## Log
- L1 (2026-10-16): "Can we run a quality pass over the existing visual assets. In particular the main fox image does not look like a cartoon fox as intended, the artistic style is meant to be similar to duolingo"
- L2 (2026-10-16): "Yes do a similar pass over all the existing icons and island to match the style, can we make the island more interesting with some baseline scenery items and a background that is more intersting"
- L3: T1 verified before commit: pytest 650 passed, node 153 passed, smoke 124/0 (after fixing the stale pre-existing mascot smoke check), pyright 0 errors on changed Python. Route: all inline (no writer trigger: units share index.html/style.css).
