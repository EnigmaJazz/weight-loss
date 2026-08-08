# Tasks: Game-Like Appearance (Duolingo-style for Adults)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~610–730 total: S1 ~150, S2 ~320–380, S3 ~160–200 (fonts binary, excluded) |
| 400-line budget risk | High (total); Medium per slice |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 foundation → PR 2 components → PR 3 motion |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: tokens, fonts, fox favicon, lockstep guard | PR 1 | `.venv/bin/python -m pytest -q tests/test_palette_lockstep.py tests/test_spa_gate.py` | smoke-ui.sh regression + manual favicon/font check | revert style.css/index.html; rm fonts/ → system-ui fallback |
| 2 | Components: mascot, wizard dots, streaks/flame attr, rewards, forms, charts, focus, mobile | PR 2 | `.venv/bin/python -m pytest -q tests/test_spa_gate.py` | smoke-ui.sh regression + manual narrow-viewport/keyboard check | revert component edits in style.css/index.html/app.js |
| 3 | Motion: shouldCelebrate, confetti wiring, flame pulse, smoke selectors | PR 3 | `node --test tests/frontend/confetti.test.mjs && .venv/bin/python -m pytest -q` | smoke-ui.sh with new .mascot/.flame asserts | revert format.js/app.js/style.css motion blocks |

### Decisions (design open questions — defaults spec-backed, confirm in apply)
- **D1**: `--font-body` = Baloo 2 400 (spec pins Baloo 2; Nunito rejected).
- **D2**: `--gold` #f5c518 non-text only (confetti/badge fills); never body text.
- **D3**: wizard indicator dots-only (`<li data-step>`, no "Step n/5") to keep smoke text pins.

## Phase 1: Foundation (PR 1)

- [x] 1.1 RED: create `tests/test_palette_lockstep.py` (drift-guard) — parse style.css `:root`, index.html theme-color, manifest.webmanifest, make_icons.py BG; assert all equal `#2f7d54`.
- [x] 1.2 RED: extend `tests/test_spa_gate.py` — assert `:root` tokens (`--fox`, `--gold`, `--radius-*`, `--font-*`), fox favicon (no `M32 8l14 22`), `?v=` stamps on CSS/JS tuples.
- [x] 1.3 GREEN: `static/style.css` — add `:root` token block (radius/shadow/space/fox/gold/`--font-display`/`--font-body`) + `@font-face` Baloo 2 400/600.
- [x] 1.4 GREEN: commit `static/fonts/baloo2-400.v1.woff2` + `baloo2-600.v1.woff2` (OFL).
- [x] 1.5 GREEN: `static/index.html` — replace line-8 favicon data URI with fox glyph (drop diamond path); keep theme-color `#2f7d54`. Manifest untouched; main.py untouched (style.css extended, no new JS) — both asserted.

## Phase 2: Components (PR 2)

- [x] 2.1 RED: extend `tests/test_spa_gate.py` — assert `prefers-reduced-motion` block present in style.css and no `@starting-style`.
- [x] 2.2 GREEN: `static/index.html` — mascot `<span class="mascot" aria-hidden="true">` in `.header-row`; `<ol class="wizard-indicator">` with 5 `<li data-step>` in onboarding-screen.
- [x] 2.3 GREEN: `static/app.js` — `renderStreaks`: flame `<span class="flame">` + `tile.dataset.streakActive`; `showWizardStep`: toggle `.is-current`; toast: `.is-visible` class-swap, keep `hidden`.
- [x] 2.4 GREEN: `static/app.js` — `CHART_COLORS`/`CHART_FONT` via `getComputedStyle` tokens; drop hardcoded hex in drawChart/drawExerciseChart/drawBars.
- [x] 2.5 GREEN: `static/style.css` — components: header/mascot, wizard indicator, scoreboard, streak tiles, rewards chips pop-in + track fill, `button:active{transform:scale(.97)}`, inputs min-height 48px, tabs, history, `:focus-visible{outline:3px solid var(--fox)}`, mobile single-column collapse, reduced-motion block.

## Phase 3: Motion & Celebration (PR 3)

- [x] 3.1 RED: create `tests/frontend/confetti.test.mjs` — `shouldCelebrate`: null prev → suppress; cur > prev → fire; cur ≤ prev → suppress.
- [x] 3.2 GREEN: `static/format.js` — add pure `shouldCelebrate(prevEarned, curEarned)` to `api` export.
- [x] 3.3 GREEN: `static/app.js` — `fireConfetti()` (spans + animationend cleanup); `loadData` keeps `prevEarned`, fires only on increase, suppresses first render; skip under `matchMedia('(prefers-reduced-motion: reduce)')`.
- [x] 3.4 GREEN: `static/style.css` — flame pulse keyframes gated `[data-streak-active="true"] .flame`; `.confetti-piece` fall; both neutralized in reduced-motion block.
- [x] 3.5 GREEN: `tests/smoke-ui.sh` — add `.mascot` + `.flame` visual selector asserts only (no text pins).

## Phase 4: Verification (final)

- [ ] 4.1 Run full `.venv/bin/python -m pytest -q` + `node --test tests/frontend/*.test.mjs` + `tests/smoke-ui.sh`; all green per Gates-green scenario.
