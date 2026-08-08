# Apply Progress — game-appearance (Phases 1–3 / PRs 1–3)

- **Change**: game-appearance
- **Phases**: 1 — Foundation (PR 1); 2 — Components (PR 2); 3 — Motion & Celebration (PR 3, final implementation slice)
- **Branches**: `feat/game-appearance-s1` (from `main` @ 76ccd16) → `feat/game-appearance-s2` (from s1 tip `367c2f3`) → `feat/game-appearance-s3` (from s2 tip `3a0aabb`)
- **Mode**: Strict TDD (pytest + node:test runners)
- **Artifact store**: openspec (+ engram fallback)
- **Date**: 2026-08-08

## Workload / PR boundary

- Delivery strategy: `auto-chain`; chain strategy: `stacked-to-main` (slice 1 = Phase 1, slice 2 = Phase 2, slice 3 = Phase 3).
- Phase 3 boundary: motion & celebration — tasks 3.1–3.5 (`shouldCelebrate` in format.js, `fireConfetti` + `prevEarned` wiring in app.js, flame pulse + confetti CSS, smoke `.mascot`/`.flame` selectors). Phase 4 (final verification) is out of scope for this batch.
- Phase 3 review budget: 183 insertions / 7 deletions across 6 files + 1 new test file (confetti.test.mjs, 45 lines) → ~228 changed lines incl. the new test; within the ~160–200 estimate (slightly above the top of the band because the RED gate test grew by one extra anchor test) and well under the 400-line budget. Combined chain stays reviewable per slice.

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

### Phase 3 (PR 3)

| Task | Description | Status |
|------|-------------|--------|
| 3.1 | RED: `tests/frontend/confetti.test.mjs` — node:test for pure `shouldCelebrate(prevEarned, curEarned)`: null prev → "suppress" (first render); cur > prev → "fire"; cur ≤ prev → "suppress". Imports the real format.js via the established UMD pattern. Confirmed RED: `TypeError: shouldCelebrate is not a function` (5 failed) | [x] |
| 3.2 | GREEN: `static/format.js` — pure `shouldCelebrate(prevEarned, curEarned)` added to the UMD `api` export (fires only when cur > prev AND prev != null; `prevEarned == null` → suppress). 5/5 tests pass, suite 88 → 93 | [x] |
| 3.3 | GREEN: `static/app.js` — `fireConfetti()` creates 24 `.confetti-piece` spans with randomized inline vars (--x drift ±120px, --rot ±270deg, --delay 0–0.4s, --color from the token palette), removed on `animationend`; `loadData` keeps module `let prevEarned = null`, computes `shouldCelebrate(prevEarned, rewards.earned_count)` after `renderRewards`, fires on "fire", then sets `prevEarned` (first render suppressed automatically); `matchMedia('(prefers-reduced-motion: reduce)')` gate skips firing entirely | [x] |
| 3.4 | GREEN: `static/style.css` — `@keyframes flame-pulse` (scale 1→1.25, ~2s ease-in-out infinite) gated to `[data-streak-active="true"] .flame` (+ `text-shadow` glow via `color-mix` of `--fox`, no hardcoded hex); `.confetti-piece` fixed-position fall (translateY 110vh + rotate + fade via inline vars, `background: var(--color)`); BOTH neutralized inside the existing `@media (prefers-reduced-motion: reduce)` block (`display:none !important` / `animation:none !important`) | [x] |
| 3.5 | GREEN: `tests/smoke-ui.sh` — added visual selector asserts ONLY: `.mascot` visible in header (post page-load) and `.flame` count > 0 (post-wizard, streaks render 3 tiles). No text-pin changes | [x] |

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
| 3.1 | `tests/frontend/confetti.test.mjs` (new) | Unit (node:test) | ✅ 88/88 node | ✅ Written → confirmed RED: `TypeError: shouldCelebrate is not a function`, 5 failed | ✅ 5/5 passed | ✅ 6 cases: null prev, undefined prev, increase from 0 and from 2, equal, decrease (all three branches) | ➖ None needed (4-line pure fn per design) |
| 3.2 | (via 3.1 file) | Unit | ✅ 88/88 node | ✅ (3.1 RED) | ✅ 5/5 + suite 93/93 | ✅ cases above force real logic | ➖ None needed |
| 3.3 | `tests/test_spa_gate.py` `test_app_js_ships_confetti_wiring` (new) | Integration (served app.js) | ✅ 88/88 node + 15/15 gate | ✅ Written → confirmed RED: `assert 'function fireConfetti'` failed (app.js stashed to prove it) | ✅ 1/1 + gate 16/16 + node 93/93 | ✅ 4 pins: fireConfetti defined, shouldCelebrate called in loadData, prevEarned module state, matchMedia gate | ✅ Randomized inline vars named as constants (CONFETTI_COLORS/CONFETTI_COUNT) |
| 3.4 | `tests/test_spa_gate.py` `test_style_css_ships_confetti_and_flame_motion` (new) | Integration (served style.css) | ✅ 16/16 gate | ✅ Written → confirmed RED: 1 failed (no keyframes/selector) | ✅ 1/1 + gate 17/17 | ✅ 6 pins: flame-pulse keyframes, active-streak gating selector, confetti-fall keyframes, --color var binding, both neutralized in the reduced-motion block | ✅ Flame glow via `color-mix` of `--fox` (no hardcoded rgba) |
| 3.5 | `tests/smoke-ui.sh` (2 new steps) | E2E (real Chromium) | ✅ smoke 29/29 | ✅ Assertions written before running (selector-only, no text pins) | ✅ smoke 31/31 | ✅ mascot visibility (offsetParent) + flame count > 0 (3 tiles) | ➖ None needed |

## Work Unit Evidence

| Evidence | Phase 2 required value | Phase 3 required value |
|---|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → **15 passed in 0.14s** (RED confirmed first at 4 failed/11 passed) | `node --test tests/frontend/confetti.test.mjs` → **5 passed** (RED first: 5 failed, `TypeError`); `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → **17 passed in 0.15s** (RED anchors confirmed first: 1 failed per new gate test) |
| Runtime harness command/scenario and exact result | `tests/smoke-ui.sh http://localhost:8123` against scratch server → **29 passed, 0 failed** ×2 | `tests/smoke-ui.sh http://localhost:8124` against scratch server (`WEIGHT_LOSS_DB=/tmp/wl-smoke3.db`, `WEIGHT_LOSS_VAPID_KEYS=/tmp/vapid3.json`, uvicorn port 8124) → **31 passed, 0 failed** (29 prior + `fox mascot visible in header` + `streak tiles render flames (3)`); full loop in real Chromium incl. st+lb entry crossing the 50% checkpoint (confetti fired mid-run, self-cleaned, no assert touched) |
| Rollback boundary | `git revert` of the 5 Phase-2 commits on `feat/game-appearance-s2` | `git revert` of the 6 Phase-3 commits on `feat/game-appearance-s3` (5 code/test + 1 openspec chore) restores the Phase-2 state; no DB, routes, manifest, main.py tuples, or text pins changed in this batch. `static/format.js` `shouldCelebrate` is additive to the UMD export; app.js motion block and the style.css motion section are the only production touchpoints |

## Files Changed (Phase 3)

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/frontend/confetti.test.mjs` | Created | node:test for `shouldCelebrate` (6 cases across all three branches: null/undefined prev → suppress, increase → fire, equal/decrease → suppress); imports the real format.js UMD |
| `static/format.js` | Modified | Added pure `shouldCelebrate(prevEarned, curEarned)` → `"fire" | "suppress"` to the `api` export (UMD); null/undefined previous count always suppresses |
| `static/app.js` | Modified | Added `shouldCelebrate` to the WeightFormat destructure; module `let prevEarned = null`; `fireConfetti()` (24 `.confetti-piece` spans, randomized `--x`/`--rot`/`--delay`/`--color` inline vars, `animationend` removal, `matchMedia` reduced-motion gate); `loadData` fires on `shouldCelebrate === "fire"` then records `prevEarned = earned_count` |
| `static/style.css` | Modified | `@keyframes flame-pulse` + `[data-streak-active="true"] .flame` gated rule (scale + `text-shadow` glow via `color-mix` of `--fox`); `.confetti-piece` fixed fall + `@keyframes confetti-fall` (translateY 110vh + rotate + fade via inline vars, `background: var(--color)`); both neutralized in the existing `prefers-reduced-motion` block |
| `tests/smoke-ui.sh` | Modified | +2 visual selector steps: `.mascot` visible in header (offsetParent check, post page-load) and `.flame` count > 0 (post-wizard). No text-pin changes |
| `tests/test_spa_gate.py` | Modified | +2 gate tests: `test_app_js_ships_confetti_wiring` (fireConfetti/shouldCelebrate/prevEarned/matchMedia pins) and `test_style_css_ships_confetti_and_flame_motion` (flame-pulse keyframes + active-streak gating, confetti-fall + `--color` binding, both neutralized in the reduced-motion block) |
| `openspec/changes/game-appearance/tasks.md` | Modified | 3.1–3.5 marked `[x]` |

## Commits (feat/game-appearance-s3)

| Hash | Subject |
|------|---------|
| `75b527f` | feat(frontend): add shouldCelebrate confetti gate with node tests |
| `7c73f46` | feat(ui): fire confetti on newly-earned checkpoints |
| `e24823a` | feat(style): pulse streak flames and fall confetti pieces |
| `65c3f39` | test(smoke): assert mascot and streak flame render |
| `689df73` | test: gate phase-3 confetti wiring and motion css |
| *(chain tip — this chore commit)* | chore(openspec): mark Phase 3 game-appearance tasks complete with apply progress |

(Phase 1 commits on `feat/game-appearance-s1`: `eb495a8`, `20d1934`, `bb026d8`, `ddba5c6`, plus `367c2f3` openspec chore. Phase 2 commits on `feat/game-appearance-s2`: `1a7f6cd`, `9fa0c41`, `6a26e02`, `bfe2cec`, `09b8372`, plus `3a0aabb` openspec chore. s3 branched from `3a0aabb`.)

## Verification results (Phase 3 batch)

1. `node --test tests/frontend/*.test.mjs` → **93 pass / 0 fail** (88 baseline + 5 new confetti tests; 90+ expected)
2. `.venv/bin/python -m pytest -q` → **361 passed in 16.54s** (359 baseline + 2 new gate tests)
3. `.venv/bin/pyright` → **0 errors, 0 warnings, 0 informations**
4. `tests/smoke-ui.sh` (scratch server, real Chromium) → **31 passed, 0 failed** (`fox mascot visible in header` + `streak tiles render flames (3)` added; all 29 prior steps green — no text-pin drift)
5. `git status` → clean on `feat/game-appearance-s3` (after the openspec chore commit)

## Decisions applied (Phase 3)

- **Confetti palette**: task text says colors come from `--fox, --gold, --accent, --danger-safe`. The token palette has no `--danger-safe`; interpreted as the existing `--danger` token (#c0392b) used as a NON-TEXT decorative fill only (same AA exemption as `--gold`). Flagged for owner.
- **Confetti container**: pieces appended directly to `document.body` with `position: fixed` — no wrapper element needed (keeps DOM minimal; CSS owns placement). Design allowed "a fixed container (or body)".
- **Flame glow**: `text-shadow: 0 0 6px color-mix(in srgb, var(--fox) 55%, transparent)` — no hardcoded hex enters the sheet (spec: new CSS MUST NOT hardcode palette hex).
- **RED anchors for DOM-coupled tasks**: per the Phase-2 precedent, tasks 3.3/3.4 got gate tests in `tests/test_spa_gate.py` as their test-first anchors (the pure helper was anchored by 3.1's node tests). The app.js wiring gate was demonstrated RED by stashing the app.js changes before writing the test.
- **`--danger-safe` no-token resolution**: see first bullet — no `--danger-safe` token exists; `--danger` used as confetti fill.

## Deviations from design

1. **No `--danger-safe` token** (task 3.3): the palette declares `--danger` only. Used `var(--danger)` as the fourth confetti fill color; confetti is decorative non-text, so the AA text rule does not apply (same exemption the design grants `--gold`).
2. **Confetti pieces appended to body, not a fixed container** (task 3.3): design says "in a fixed container (or body)" — chose body + `position: fixed` to avoid an extra wrapper element; the CSS `.confetti-piece` rule owns placement.
3. **Gate tests slightly ahead of the explicit 3.3/3.4 bullets**: the bullets don't name test files for the app.js/CSS motion work, but strict TDD requires a test-first anchor for every GREEN task; followed the Phase-2 precedent (`test_app_js_ships_confetti_wiring`, `test_style_css_ships_confetti_and_flame_motion`). Same pattern as Phase 1's "slightly ahead" note.
4. **Flame pulse glow uses `color-mix` + `text-shadow`**: design's Component Styling Plan says "gentle scale/glow" without prescribing a technique; `text-shadow` with a token-derived `color-mix` keeps the no-hardcoded-hex rule.
5. **Commit order**: RED tests were demonstrated RED first (in-cycle: node 5-fail, gate-test stash dance); committed after their GREEN so each commit leaves the suite green (Phase-1/2 precedent). The gate-test commit (`689df73`) landed after the behaviors it verifies.

## Issues found (Phase 3)

- **gga pre-commit hook strict-mode false negative (hit twice)**: `STRICT_MODE=true` (global config `/home/james/.config/gga/config`) requires `STATUS: PASSED|FAILED` within the first 30 lines of the review provider's output; when the provider's preamble is long, the hook fails the commit despite the review content passing ("All files comply"). Commits B and E each needed one retry; every run's review verdict was PASSED. Options for the owner: retry on flake, or set a project `.gga` with `STRICT_MODE=false` (still fails on genuine FAILED). Not changed by this batch — global config is gentle-ai-managed, and a project override is a review-policy decision.
- **Pre-existing chart tooltip quirk** (flagged by the gga reviewer, NOT introduced by this change): in `drawChart`'s hover handler, `if (best > w / points.length) { ctx.clearRect(...); return; }` blanks the whole chart without redrawing when the pointer is farther than one slot from the nearest point — mid-canvas hover with many entries blanks until `mouseleave`. Out of scope for game-appearance; worth a follow-up fix.

## Risks

- **gga strict-mode flake**: now demonstrated twice on s3; retries worked, but a burst of long provider responses could stall a commit. Owner may want the project-level `STRICT_MODE` decision recorded.
- **Confetti DOM churn**: 24 spans per fire, removed on `animationend` (~2s); rapid repeated fires are possible but bounded (each burst self-cleans). Low risk.
- **`color-mix()` browser support** (Phase 2 note, extended to the flame glow): Chrome 111+/Firefox 113+/Safari 16.2+. The glow degrades to no-shadow on older browsers; the pulse still animates. Low risk.
- **Baloo 2 body readability** remains an open design question (design.md open question 1) — defaulted to Baloo 2 400 per spec, flagged for owner.
- **Changed-line budget**: Phase 3 ~228 changed lines incl. the new test file — within the slice estimate and under the 400-line guard.

## Next

- Phase 4 (PR 3 tip): full verification — task 4.1 (full pytest + node:test + smoke-ui.sh; all green per the Gates-green scenario). Then archive.
