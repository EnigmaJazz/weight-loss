# Apply Progress — game-appearance (Phases 1–2 / PRs 1–2)

- **Change**: game-appearance
- **Phases**: 1 — Foundation (PR 1); 2 — Components (PR 2 of stacked-to-main chain)
- **Branches**: `feat/game-appearance-s1` (from `main` @ 76ccd16) → `feat/game-appearance-s2` (from s1 tip `367c2f3`)
- **Mode**: Strict TDD (pytest runner)
- **Artifact store**: openspec (+ engram fallback)
- **Date**: 2026-08-08

## Workload / PR boundary

- Delivery strategy: `auto-chain`; chain strategy: `stacked-to-main` (slice 1 = Phase 1, slice 2 = Phase 2 only)
- Phase 2 boundary: components (mascot, wizard indicator, streaks/flame, rewards, forms, charts, focus, mobile) — tasks 2.1–2.5. Phase 3 (motion/confetti) is OUT of scope for this batch.
- Phase 2 review budget: 320 insertions / 41 deletions across 4 files (app.js 90, style.css 185, index.html 8, test_spa_gate.py 92) → ~361 changed lines, at the edge of but within the 400-line budget. Combined with Phase 1 (~141), the chain keeps each slice reviewable.

## Completed tasks (cumulative)

### Phase 1 (PR 1)

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | `tests/test_palette_lockstep.py` drift-guard: style.css `--accent`, index.html theme-color, manifest theme_color, make_icons.py BG all equal `#2f7d54` | [x] |
| 1.2 | `tests/test_spa_gate.py` extended: `:root` tokens (`--fox`, `--gold`, `--radius-*`, `--shadow-*`, `--space-*`, `--font-display`, `--font-body`), Baloo 2 @font-face + woff2 filenames, fox favicon (no diamond `M32 8l14 22`), `?v=` stamps on all four CSS/JS tuples, manifest theme_color `#2f7d54` | [x] |
| 1.3 | `static/style.css`: `:root` token block (radius/shadow/space/fox/gold/`--font-display`/`--font-body`) + `@font-face` Baloo 2 400/600 (font-display: swap, versioned woff2 URLs) | [x] |
| 1.4 | `static/fonts/baloo2-400.v1.woff2` + `baloo2-600.v1.woff2` committed (Baloo 2 variable font, woff2, SIL OFL 1.1) + `static/fonts/OFL.txt` | [x] |
| 1.5 | `static/index.html`: line-8 favicon data URI replaced with fox glyph drawn from make_icons.py geometry (pixel-verified 0/4096 mismatches); diamond path removed; theme-color stays `#2f7d54` | [x] |

### Phase 2 (PR 2)

| Task | Description | Status |
|------|-------------|--------|
| 2.1 | `tests/test_spa_gate.py` extended: `prefers-reduced-motion` block present in style.css (must actually neutralize motion, not be a stub), NO `@starting-style` anywhere; plus gate tests for the mascot + wizard-indicator markup and the app.js component hooks / token-driven chart palette | [x] |
| 2.2 | `static/index.html`: mascot `<span class="mascot" aria-hidden="true">` (inline fox SVG, reuses favicon glyph) inside `.header-row` before the h1; `<ol class="wizard-indicator">` with 5 `<li data-step>` (height/weight/target/units/notifications, dots-only per D3) inside `#onboarding-screen` before the form. No id changes, no copy changes | [x] |
| 2.3 | `static/app.js`: `renderStreaks` adds flame `<span class="flame">🔥</span>` + `tile.dataset.streakActive = String(s[key] > 0)`; `showWizardStep` toggles `.is-current` on the indicator `<li>`s + `aria-current="step"`; `toast()` adds `.is-visible` class-swap via requestAnimationFrame (reveal animates) while keeping the `[hidden]` toggle — no `@starting-style` | [x] |
| 2.4 | `static/app.js`: `CHART_COLORS` + `CHART_FONT`/`CHART_FONT_LARGE` read ONCE via `getComputedStyle` (line `--accent`, grid `--border`, muted `--muted`, tooltip `--text`, tooltip text `--card`; font = computed body font-family with system fallback); hardcoded hex + font strings removed from `drawChart`, `drawExerciseChart`, `drawMealChart`, `drawBars` | [x] |
| 2.5 | `static/style.css` component pass: header mascot lockup + playful h1 (`--font-display`), wizard indicator dots + `.is-current`, scoreboard tiles (`--radius-md`, `--font-display` stat values), streak flame placement styling (pulse is Phase 3), rewards chips `--radius-pill` + `chip-pop` keyframe + `--fox`→`--accent` progress fill, `button:active{transform:scale(.97)}` + min-height 48px, inputs min-height 48px + `--radius-sm` + `--font-body`, tabs/history token colors, `:focus-visible{outline:3px solid var(--fox)}` on interactive elements, mobile single-column collapse ≤480px, `@media (prefers-reduced-motion: reduce)` block neutralizing transitions/animations. `[hidden]{display:none!important}` preserved | [x] |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/test_palette_lockstep.py` | Unit (file parse) | ✅ 349/349 | ✅ Written (guard — passes day one by design, 2 cases) | ✅ 2 passed | ✅ 2 cases (per-location + lockstep set) | ✅ Clean (removed dead `_HEX_RE` const after review) |
| 1.2 | `tests/test_spa_gate.py` | Integration (served artifacts) | ✅ 349/349 | ✅ Written → confirmed RED: 2 failed (tokens/font-face, favicon) | ✅ 11 passed (full file) | ✅ Multi-case: 16 token names + 6 pinned values + 4 stamps + manifest | ✅ Clean |
| 1.3 | (via 1.2 gate) | Integration | ✅ 349/349 | ✅ (1.2 RED) | ✅ 13/13 focused passed | ✅ Values pinned per design | ➖ None needed |
| 1.4 | (via 1.2 gate + `file`) | Integration/artifact | ✅ 349/349 | ✅ (1.2 RED) | ✅ woff2 verified by `file` + fc-scan (Baloo 2, variable wght) | ✅ 400 + 600 both verified | ➖ None needed |
| 1.5 | `tests/test_spa_gate.py` favicon test | Integration | ✅ 349/349 | ✅ (1.2 RED) | ✅ 13/13 focused passed | ✅ Geometric equivalence: 4096/4096 pixels match make_icons.py | ✅ Exact coords after boundary-pixel fix (7→4→0 mismatches) |
| 2.1 | `tests/test_spa_gate.py` (4 new tests) | Integration (served artifacts) | ✅ 355/355 | ✅ Written → confirmed RED: 4 failed / 11 passed | ✅ 15/15 passed (full file) | ✅ 4 tests: reduced-motion block + no @starting-style; mascot/indicator markup; component hooks; token charts (no hardcoded hex) | ✅ Clean — comment containing the literal `@starting-style` string removed after first GREEN run flagged it |
| 2.2 | (via 2.1 mascot/indicator gate) | Integration | ✅ 355/355 | ✅ (2.1 RED) | ✅ gate 15/15 | ✅ 5 dots pinned in order + mascot-before-h1 + aria-hidden | ➖ None needed |
| 2.3 | (via 2.1 hooks gate + smoke) | Integration + E2E | ✅ 355/355 | ✅ (2.1 RED) | ✅ gate 15/15 + smoke 29/29 | ✅ flame/streakActive/is-current/aria-current/is-visible/hidden-toggle all pinned | ✅ Toast refined to rAF class-swap so the reveal transition actually animates (GREEN still green) |
| 2.4 | (via 2.1 chart gate + smoke) | Integration + E2E | ✅ 355/355 | ✅ (2.1 RED) | ✅ gate 15/15 + smoke 29/29 | ✅ 4 hardcoded chart hex/font strings pinned absent; tokens mapped per design | ✅ CHART_FONT_LARGE derived from the single computed family read |
| 2.5 | (via 2.1 reduced-motion gate + smoke) | Integration + E2E | ✅ 355/355 | ✅ (2.1 RED — reduced-motion block absent) | ✅ gate 15/15 + smoke 29/29 | ✅ Block asserted non-stub (animation/transition neutralization) + no @starting-style | ✅ Reused existing tint values via `color-mix` tokens instead of new hex |

## Work Unit Evidence (Phase 2)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → **15 passed in 0.14s** (13 → +2 net from 4 new tests, RED confirmed first at 4 failed/11 passed) |
| Runtime harness command/scenario and exact result | `tests/smoke-ui.sh http://localhost:8123` against a scratch server (`WEIGHT_LOSS_DB=/tmp/wl-smoke.db`, uvicorn port 8123) → **29 passed, 0 failed** (full signup → wizard → entries → charts → rewards → logout loop in real Chromium); ran twice (before + after toast rAF refinement), both 29/0. Charts draw with token colors, wizard indicator + mascot render, streak flames present |
| Rollback boundary | `git revert` of the 5 Phase-2 commits on `feat/game-appearance-s2` (or dropping the branch) restores the Phase-1 state; no DB, routes, manifest, main.py tuples, or smoke-ui.sh changes in this batch — nothing else to unwind. Phase-1 revert boundary unchanged (4 commits on s1 + `static/fonts/`) |

## Files Changed (Phase 2)

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/test_spa_gate.py` | Modified | +4 tests: reduced-motion block (non-stub) + no `@starting-style`; mascot + wizard-indicator markup (5 dots in order, text-free); app.js component hooks (flame/streakActive/is-current/aria-current/is-visible + hidden toggle kept); app.js token-driven charts (CHART_COLORS/CHART_FONT/getComputedStyle present, hardcoded chart hex absent) |
| `static/index.html` | Modified | Mascot fox SVG span (`aria-hidden="true"`) before h1 in `.header-row`; `<ol class="wizard-indicator">` with 5 empty `<li data-step>` dots inside `#onboarding-screen`. No id/copy changes |
| `static/app.js` | Modified | `toast()`: rAF `.is-visible` class-swap (hidden toggling kept); `showWizardStep()`: indicator `.is-current` + `aria-current` sync; `renderStreaks()`: flame span + `dataset.streakActive`; chart section: `CHART_COLORS`/`CHART_FONT`/`CHART_FONT_LARGE` from `getComputedStyle`, hardcoded hex/fonts replaced in `drawChart`/`drawExerciseChart`/`drawMealChart`/`drawBars` |
| `static/style.css` | Modified | Component pass per design §Component Styling Plan (header lockup, h1 `--font-display`, mascot sizing, wizard dots, scoreboard/stat tiles, `.flame`, rewards chips + `chip-pop` + `--fox`→`--accent` fill, `button:active` scale + 48px min-height, inputs 48px + tokens, tab/history token colors, `:focus-visible` fox ring, ≤480px single-column grids, toast `.is-visible` reveal, `prefers-reduced-motion` block) |

## Commits (feat/game-appearance-s2)

| Hash | Subject |
|------|---------|
| `1a7f6cd` | feat(ui): add fox mascot and wizard step indicator |
| `9fa0c41` | feat(ui): add streak flames, wizard sync, and toast reveal |
| `6a26e02` | feat(ui): drive chart colors and fonts from design tokens |
| `bfe2cec` | feat(style): component pass, focus rings, and reduced-motion gate |
| `09b8372` | test: gate phase-2 components and reduced-motion block |

(Phase 1 commits on `feat/game-appearance-s1`: `eb495a8`, `20d1934`, `bb026d8`, `ddba5c6`, plus `367c2f3` openspec chore — s2 branched from `367c2f3`.)

## Verification results (Phase 2 batch)

1. `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → **15 passed in 0.14s**
2. `.venv/bin/python -m pytest -q` → **359 passed** (baseline 355 → +4 new gate tests)
3. `node --test tests/frontend/*.test.mjs` → **88 pass / 0 fail** (unchanged, green)
4. `.venv/bin/pyright` → **0 errors, 0 warnings, 0 informations**
5. `tests/smoke-ui.sh` (scratch server, real Chromium) → **29 passed, 0 failed** ×2
6. `git status` → clean on `feat/game-appearance-s2` (after openspec artifacts commit)

## Decisions applied (Phase 2)

- **D1**: `--font-body` = Baloo 2 400 per spec (body copy stays Baloo 2; the design open question defaulted to spec and was flagged for owner — no change).
- **D2**: `--gold` used nowhere in Phase 2 (confetti/badge fills are Phase 3); no gold body text introduced.
- **D3**: wizard indicator is dots-only — `<li data-step="..."></li>` with no visible text, keeping smoke text pins intact.

## Deviations from design

1. **Chart tooltip needs two tokens** (task 2.4): the design's `CHART_COLORS` table lists `tooltip:--text` only, but the tooltip needs a box color AND a text color. Implemented `tooltip: var(--text)` (dark box) + `tooltipText: var(--card)` (light text) — the design's own AA row 1 (`--text`/`--card` ~14:1) is exactly that pair.
2. **Toast reveal uses requestAnimationFrame** (task 2.3): the design says "add `.is-visible` class-swap for opacity/transform reveal". A same-tick `classList.add` would be batched with `hidden=false` and the transition would never paint; adding the class on the next frame makes the reveal actually animate. The `[hidden]` toggle and the gate contract are unchanged.
3. **Test additions slightly ahead of the explicit 2.1 bullet**: the 2.1 bullet enumerates only the reduced-motion + no-@starting-style CSS assertions, but strict-TDD requires a test-first anchor for every GREEN task (2.2–2.5), so the gate also pins the mascot/indicator markup, the app.js hooks, and the token-driven charts (no hardcoded hex). Same precedent as Phase 1's "slightly ahead" note.
4. **Smoke-ui.sh unchanged in this batch**: the design table assigns `.mascot`/`.flame` selector additions to Phase 3 task 3.5; the browser smoke ran unchanged and passed 29/0, validating the new components E2E without adding pins early.
5. **Commit order**: RED tests were written and demonstrated RED first (in-cycle, 4 failed/11 passed); committed after their GREEN so each commit leaves the suite green (Phase-1 precedent). The gate-test commit (`09b8372`) landed after the behaviors it verifies.
6. **`color-mix()` used for soft tint backgrounds** (task 2.5): the design's token set has no soft-accent tint tokens; existing hardcoded tints (`#eef7f1`, `#eaf3ee`, `#fdecea`, `#fafcfb`, `#eaf6ef`) were replaced with `color-mix(in srgb, var(--accent|--danger) X%, var(--card))` so no new hex enters the sheet.

## Risks

- **Baloo 2 body readability** at small sizes remains an open design question (design.md open question 1) — defaulted to Baloo 2 400 per spec, flagged for owner.
- **`color-mix()` browser support**: needs Chrome 111+/Firefox 113+/Safari 16.2+ (2023+). Acceptable for a modern Web-Push SPA, but an older mobile browser would fall back to the previous background (declaration dropped). Low risk.
- **Phase-2 changed-line budget ~361** is close to the 400-line guard; Phase 3 (~160–200) keeps the chain within budget per slice.
- **gga pre-commit hook strict-mode false negative** (Phase 1 note): not hit this batch — all 5 commits passed the hook on the first attempt.

## Next

- Phase 3 (PR 3): motion & celebration — tasks 3.1–3.5 (`shouldCelebrate` in format.js, `fireConfetti`, flame pulse keyframes, confetti pieces, smoke `.mascot`/`.flame` selectors).
- Phase 4: full verification — task 4.1.
