# Apply Progress — r1-quests-xp S4a (PR 7 · Today quests card + XP chip)

**Mode**: Strict TDD (`strict_tdd: true`; runners: `.venv/bin/python -m pytest`, `node --test tests/frontend/*.test.mjs`, `tests/smoke-ui.sh`)
**Delivery**: auto-chain, stacked-to-main, PR 7 slice only (tasks 7.1–7.5). S4b (8.x) untouched.
**Branch**: `feat/r1-quests-xp-s4a` — commit `4c9595d` `feat(today): surface quests and xp`

## Completed Tasks

- [x] 7.1 `static/index.html`: `#quests-card` + `#xp-summary-chip` on Today (chip card with `#xp-chip-content`; quests card with `#quests-list` + `#quests-error` role=alert).
- [x] 7.2 `static/app.js`: `loadQuestsAndXp` (Promise.allSettled, failure-scoped), `renderQuests`, `buildQuestActions`, `mutateQuest` (disable-while-pending, error feedback, never removes card, 409 leaves assignment), `renderXpChip`, delegated `#quests-list` click wiring in `init()`.
- [x] 7.3 `static/format.js`: pure mirrors `thresholdForLevel`, `levelFromXp`, `xpIntoNext` (constants 100/50 embedded; `levelFromXp` uses floor(sqrt) mirror of Python isqrt).
- [x] 7.4 `static/style.css`: token-only quest/chip rules (no hex), dark-mode via vars, 48px targets preserved, focus-visible inherited, transitions neutralized in `prefers-reduced-motion` block.
- [x] 7.5 Tests: `tests/frontend/xp.test.mjs` (99/100/250 + full boundary/progress vectors), `test_spa_gate.py::test_today_quest_surface` (markup + mirrors + hooks + allSettled + token-only + reduced-motion), `tests/smoke-ui.sh` quest selectors/actions (surface + replace→409→complete, 56 steps).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 7.3/7.5 (mirrors) | `tests/frontend/xp.test.mjs` | Unit (node:test) | ✅ 113/0 node, 178 pytest | ✅ Written first (`xpIntoNext is not a function` → fail) | ✅ 6/6 | ✅ 99/100/250 + boundaries + progress vectors | ➖ None needed (backend-mirroring kept minimal) |
| 7.1/7.2/7.4 | `tests/test_spa_gate.py::test_today_quest_surface` | Integration (served assets) | ✅ gate suite green | ✅ Written first (markup absent → fail) | ✅ 41/41 gate | ✅ open-row actions vs terminal no-controls; token-only vs reduced-motion | ✅ Race fix (see Issues) |
| 7.5 (E2E) | `tests/smoke-ui.sh` | E2E (real Chromium) | ✅ prior smoke 36-step green (S5b run) | ➖ DOM RED carried by the gate test; smoke additions written in-unit, run against live scratch server | ✅ 56/56 (was 55/56 → selector + race fixes → 56/56) | ✅ replace→409→complete with live XP-delta assert | ✅ Fixed smoke selectors (id→class) |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `node --test tests/frontend/xp.test.mjs` → **6 pass / 0 fail**; `.venv/bin/python -m pytest tests/test_spa_gate.py tests/test_quests.py tests/test_xp.py tests/test_api.py -q` → **179 passed** |
| Runtime harness command/scenario and exact result | `tests/smoke-ui.sh http://127.0.0.1:8131` (scratch uvicorn, tmp DB/VAPID, real Chromium) → **56 passed, 0 failed** incl. quests card surface, XP chip, replace→409→complete with live XP delta |
| Rollback boundary | Revert commit `4c9595d` on `feat/r1-quests-xp-s4a` — removes Today quests/chip markup, JS, CSS, mirrors, and their tests only; backend and S4b files untouched |

## Deviations from Design

1. **Sequencing of quests/XP fetches** (design §Loading said use `Promise.allSettled` for R1 requests). Kept `Promise.allSettled` failure-scoping, but the `/api/xp` fetch now awaits the `/api/quests` fetch: `/api/quests` reconciles/persists read-detected completions and `/api/xp` derives its total from those rows, so racing them rendered a stale chip total (reproduced live in smoke; fixed). Noted in `static/app.js` comment.
2. Chip progress bar denominator is the level span (`next_level_at - thresholdForLevel(level)`), not the absolute `next_level_at` — uses the new mirror, matching the spec's "progress to next_level_at".

## Issues Found

1. **Stale XP chip race (real bug, fixed)**: concurrent `/api/quests` + `/api/xp` let XP be computed before the quests reconcile persisted auto-detections (reproduced in smoke: replace landed streak_alive → chip showed 0 XP until the next refresh). Fixed by sequencing.
2. **Smoke script selector bug (test-side)**: chip inner elements are classes (`.xp-chip-level` etc.), initially queried with `#` id selectors → 'undefined'. Fixed in `tests/smoke-ui.sh`.
3. Smoke weekday robustness: mutation steps only rely on the always-open `mood_checkin` row (minimum 1 open row on any weekday); no wizard reminder_weekday change needed.

## Verification (all green)

1. `.venv/bin/python -m pytest tests/test_spa_gate.py tests/test_quests.py tests/test_xp.py tests/test_api.py -q` → **179 passed**
2. `node --test tests/frontend/*.test.mjs` → **119 pass / 0 fail** (113 baseline + 6 new)
3. `.venv/bin/python -m pytest -q` → **545 passed**
4. `.venv/bin/pyright` → **0 errors, 0 warnings**
5. `bash tests/smoke-ui.sh` (scratch server :8131, real Chromium) → **56 passed, 0 failed**
6. `tasks.md`: only 7.1–7.5 flipped to `[x]`; no other checkbox touched.
