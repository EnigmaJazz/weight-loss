# Art library: additional islands + new plants (art only)
Objective: ready-to-wire Duolingo-style art for future upgrades — new island themes and new collectible plants — with a preview gallery; no gameplay/backend changes.
Branch: feat/art-library (stacked on feat/r2a-island-polish) · Delivery: ask-on-risk (chain question deferred to PR time) · Runners: `.venv/bin/python -m pytest -q`, `node --test tests/frontend/*.test.mjs`

## Specs
- S1: "Can we build assets for additional islands" — 5 themed islands (dune, frost, lagoon, maple, blossom) on the same 240x150 frame and mound footprint as the live island, so the fox and plant placements carry over; light + dark variants.
- S2: "and more unique plants for future upgrades" — 20 new plants (4 per island theme) in the existing 20x28 keyed `data-plant-key` format, flat Duolingo style, locked-silhouette compatible.
- S3: Scope decision (user answer): "Art library only (Recommended)" — Build new island themes and new plants as ready-to-use drawings, plus a preview gallery page. Nothing in the game changes yet, and you decide unlock rules later.
- Constraints: live page (index.html/style.css/app.js) unchanged; token-only colours (hex only in custom-property declarations); unique keys; tests pin the library's structure.

## Tasks
- [x] T1 [S1,S3] inline — static/art/library.svg islands + static/art/library.css theme tokens + gallery page — commit: e9bb813
- [x] T2 [S2,S3] inline — 20 plants in the library + gallery shelf — commit: e9bb813
- [x] T3 [S1,S2] inline — tests/test_art_library.py structure/token guard — commit: e9bb813

## Log
- L1 (2026-10-16): "Can we build assets for additional islands and more unique plants for future upgrades"
- L2 (2026-10-16): scope answer "Art library only (Recommended)".
- L3: Design: islands reuse the existing .island-* classes; each theme overrides the island custom properties via `[data-island-theme="<key>"]` (light) and `[data-theme="dark"] [data-island-theme="<key>"]` (dark) in library.css, plus theme-only scenery classes (isl-*). Route: inline (art needs one visual judge; files shared).
- L4: Verified: pytest 657 passed (7 new art-library tests), node 153 passed, pyright 0 errors; gallery rendered in a browser with no console errors, light and dark, islands with themed plants plus the earned/locked shelf. Live app files untouched.
- L5: One commit (1156 lines, mostly generated SVG/CSS asset data; the islands and plants share library.svg). The art was generated from scratch scripts, which are not committed.
