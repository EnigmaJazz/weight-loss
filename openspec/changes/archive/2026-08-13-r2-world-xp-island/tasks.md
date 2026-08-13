# Tasks: R2 World v1 — XP Island

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~550–700 total (~150 / ~280 / ~200 per slice) |
| 400-line budget risk | Per-slice Low/Medium/Medium; High as one PR |
| Chained PRs recommended | Yes |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| 1 | Pure stage contract | 1 | `node --test tests/frontend/world.test.mjs` | N/A — pure fns | Revert `format.js` + `world.test.mjs` |
| 2 | Static island + gates | 2 | `pytest tests/test_spa_gate.py` | Scratch server + smoke | Revert markup, CSS, gate, smoke pin |
| 3 | Live behavior + smoke | 3 | `pytest tests/test_spa_gate.py` | Scratch server + full smoke | Revert app.js, CSS, smoke |


## Slice 1: Pure Contract (PR 1)

- [x] 1.1 RED — Create `tests/frontend/world.test.mjs`: pin `worldStage` 0/699/700/2699/2700/10449/10450/23199/23200 → 1,1,2,2,3,3,4,4,5 (Boundary mapping).
- [x] 1.2 RED — Pin `stageChanged` — fire only prev→prev+1; suppress null/undefined, equal, lower, failed (World stage diff).
- [x] 1.3 GREEN — `static/format.js`: add `worldStage(totalXp)` (bands 0/700/2700/10450/23200) + `stageChanged(previous, current)`; register on `WeightFormat`.
- [x] 1.4 Verify — `node --test tests/frontend/world.test.mjs`, full node suite; commit `feat(format): derive world island stages from total XP`.

## Slice 2: Static Island (PR 2)

- [x] 2.1 RED — `tests/test_spa_gate.py`: replace placeholder test with `test_index_html_world_panel_ships_xp_island` — pins `#world-card`, `#world-island` svg, five `data-stage` groups, fox only at 5, token fills, no placeholder copy.
- [x] 2.2 GREEN — `static/index.html`: swap `.world-placeholder` for `#world-card` (SVG groups sprout→sapling→tree→lush→thriving, fox at 5), `#world-stage-name`, `#world-progress`.
- [x] 2.3 GREEN — `static/style.css`: token-only island fills, one-stage visibility selector, responsive sizing, island-motion kill in reduced-motion block; no `@starting-style`.
- [x] 2.4 GREEN — `tests/smoke-ui.sh`: replace placeholder pin with island-visible + placeholder-absent.
- [x] 2.5 Verify — `pytest tests/test_spa_gate.py`, pyright, scratch-server smoke; commit `feat(world): static island markup, tokens, motion gate`.

## Slice 3: Live Behavior (PR 3)

- [x] 3.1 RED — `tests/test_spa_gate.py`: pin app.js wiring — `renderWorld`, `worldStage` destructured, `let prevWorldStage = null`, `stageChanged` in fulfilled `/api/xp` branch of `loadQuestsAndXp()`.
- [x] 3.2 GREEN — `static/app.js`: `renderWorld(xpPayload)` sets `data-stage`; progress (stage 1: `xp_into_next / (next_level_at - thresholdForLevel(level))`; 2–4 normalized; 5 "Island fully evolved"); update `prevWorldStage` on success only; `fireConfetti()` on stage-up.
- [x] 3.3 GREEN — `static/style.css`: progress bar/label token rules + progress-transition neutralization.
- [x] 3.4 Verify — full pytest, `node --test tests/frontend/*.test.mjs`, pyright.
- [x] 3.5 GREEN — `tests/smoke-ui.sh`: World pins — "Sprout Isle" + `0 / 100` progress, one visible stage, both themes, placeholder absent.
- [x] 3.6 Verify — scratch-server smoke; commit `feat(world): live island render, stage-up confetti, smoke`.

## Commit Guidance

Conventional commits, no `Co-Authored-By`. Stacked to main: rebase each PR after the prior merges; PR body shows 📍 dependency diagram. Tests ride with their unit; each slice diff ≤400.
