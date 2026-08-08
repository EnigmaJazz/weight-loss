# Tasks: Goals Dashboard

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 480–650; each slice <400 |
| 400-line budget risk | High |
| Suggested split | S1 → S2 → S3 |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| PR | Goal | Test command | Harness | Rollback |
|----|------|-------------|---------|----------|
| PR 1 (S1) | format.js helpers + goals.test.mjs + container | `node --test tests/frontend/goals.test.mjs` && `pytest -q tests/test_spa_gate.py` | N/A — gate in-process | Revert format.js/index.html additions (unused) |
| PR 2 (S2) | renderGoalRing + wiring + ring/streak CSS + smoke | `pytest -q tests/test_spa_gate.py` && `node --test tests/frontend/` | `tests/smoke-ui.sh` (tmp DB) — ring visible | Revert ring app.js/CSS + container |
| PR 3 (S3) | milestone-grid rewrite + CSS + smoke + audit | `pytest -q` && `node --test tests/frontend/` | `tests/smoke-ui.sh` — 5 cards | Revert renderRewards + milestone CSS |

## Phase 1: S1 — Helpers + Foundation

- [x] 1.1 RED: create `tests/frontend/goals.test.mjs` — goalProgress 0.5 (100,90,80), null nulls/b≤t, clamp 1.0; checkpointThresholds pin (100,80)→[98,95,90,85,80], [] nulls/t≥b; kgToImperial 82.5→{lb,stone,stoneLb}, null→null
- [x] 1.2 GREEN: add 3 helpers + api registration to `static/format.js`; `node --test tests/frontend/goals.test.mjs` green
- [x] 1.3 `static/index.html`: insert `<div class="goal-ring" id="goal-ring" aria-hidden="true"></div>` after h2 in #summary-card
- [x] 1.4 gate: `tests/test_spa_gate.py` adds test_format_js_ships_goal_helpers + test_index_html_ships_goal_ring_container
- [x] 1.5 verify: `pytest -q` + `node --test tests/frontend/` green

## Phase 2: S2 — Ring + Streaks

- [x] 2.1 RED gate: `tests/test_spa_gate.py` adds test_app_js_ships_goal_ring_renderer (renderGoalRing, stroke-dashoffset, url(#goalGrad)) + test_index_html_ships_ring_empty_state_copy ("Set a target weight to start tracking.")
- [x] 2.2 RED smoke: add ring-visible eval (`.goal-ring svg` non-zero dashoffset) to `tests/smoke-ui.sh`
- [x] 2.3 GREEN: add `renderGoalRing(summary)` to `static/app.js` — SVG 140×140, r=60, C≈376.991, dashoffset=C·(1−pct); null pct → no arc + empty copy; overlay pct + remaining via weightImperial
- [x] 2.4 wire `renderGoalRing(chartData.weightSummary)` in `loadData` after `renderSummary`
- [x] 2.5 CSS: `.goal-ring` + `#goalGrad` (var(--fox)→var(--accent)), track var(--border); `.goal-ring-progress{transition:none}` in reduced-motion block; `.flame` 1.7rem + tile value 1.3rem
- [x] 2.6 verify: pytest + node + smoke green

## Phase 3: S3 — Milestone Track

- [x] 3.1 AUDIT (pre-rewrite): smoke+gate baseline; none pin .rewards-next/.checkpoint-list/.progress-track — audited: smoke "checkpoints section visible" + "streak tiles render flames"; gate test_app_js_ships_component_hooks, test_style_css_ships_confetti_and_flame_motion, test_style_css_ships_reduced_motion_block_without_starting_style
- [x] 3.2 RED gate: test_app_js_ships_milestone_grid (.milestone-grid/.milestone-card in served app.js) + test_style_css_gold_is_fill_only (`.is-100.is-earned` background gradient; no gold text)
- [x] 3.3 RED smoke: `.milestone-card` count == 5
- [x] 3.4 GREEN: rewrite `renderRewards` — keep `.rewards-count` + `.progress-track`; drop `.rewards-next` + `.checkpoint-list`; emit 5 `.milestone-card` (data-percent, emoji 🚶🏃🔥🏆🎯, pct, threshold via weightLabel(kgToImperial), when YYYY-MM-DD|pending): is-earned (∈ active set), is-next (next_checkpoint.percent else first pending), is-recently-earned (max earned_at, date-granular), is-100
- [x] 3.5 CSS: `.milestone-grid` grid + `.milestone-card` states (is-next ring, is-recently-earned highlight); `.is-100.is-earned` background linear-gradient(var(--gold),var(--gold-deep)), text var(--text)/var(--accent-dark)
- [x] 3.6 verify: pytest 413 + node 110 + smoke 36 green

## Phase 4: Final Verification

- [x] 4.1 additions-only: no edits to routes.py/database.py/rewards.py/main.py (tuples stamped); pinned ids/strings unchanged; full pytest 413 + node 110 + smoke 36 green
