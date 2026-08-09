# Apply Progress — r1-quests-xp S4b (PR 8 · Journey XP/momentum/quest-history cards)

**Mode**: Strict TDD (`strict_tdd: true`; runners: `.venv/bin/python -m pytest`, `node --test tests/frontend/*.test.mjs`, `tests/smoke-ui.sh`)
**Delivery**: auto-chain, stacked-to-main, PR 8 slice only (tasks 8.1–8.4) — the final implementation slice. Verify checklist (V.x) untouched.
**Branch**: `feat/r1-quests-xp-s4b` — implemented inline by the orchestrator after three delegated-apply transport failures (sdd_task_result_malformed, provider socket errors; maintainer approved inline implementation, ledger reset recorded).

## Completed Tasks

- [x] 8.1 `static/index.html`: `#xp-card` (aria-label "XP progress" + `#xp-card-content`), `#momentum-card` (aria-label "Momentum" + `#momentum-card-content`), `#quest-history-card` (aria-label "Quest history" + `#quest-history-content`) inside `#tab-journey`, after the absorbed charts/history cards.
- [x] 8.2 `static/app.js`: `loadJourneyCards(questsPayload, xpPayload)` (momentum via `Promise.allSettled`, failure-scoped — a failed momentum fetch renders a scoped error, XP/history still render from the S4a payloads); `renderJourneyXp` (title, level+total, progress bar with exact span math, recent completions newest-first); `renderMomentum` (today tier, "No momentum yet" for `none`, successful/21 count); `renderQuestHistory` (date/label/status/awarded XP; non-done = 0 XP; explicit empty state). `loadData` and `mutateQuest` both feed the S4a payloads into `loadJourneyCards`.
- [x] 8.3 `static/style.css`: token-only journey/momentum/history card rules (no hex literals), existing card layout + mobile stacking, `prefers-reduced-motion` neutralization for `.xp-card`/`.momentum-card`/`.quest-history-card`.
- [x] 8.4 Tests: `test_spa_gate.py::test_journey_progress_surfaces` (markup + hooks + allSettled momentum + token-only + reduced-motion + absorb-pin preserved); `tests/smoke-ui.sh` journey progress section (xp card title/level, momentum tier + successful/21, quest-history empty state); `test_index_html_journey_panel_absorbs_charts_and_history` unchanged and green.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 8.1/8.2/8.3 (cards) | `tests/test_spa_gate.py::test_journey_progress_surfaces` | Integration (served assets) | ✅ gate suite green | ✅ Written first (markup absent → 1 failed) | ✅ 3/3 incl. preserved absorb pin | ✅ populated vs empty history; done vs non-done XP; token-only vs reduced-motion | ➖ None needed |
| 8.4 (E2E) | `tests/smoke-ui.sh` | E2E (real Chromium) | ✅ prior smoke green | ➖ DOM RED carried by the gate test; smoke written in-unit, run against live scratch server | ✅ 62/62 | ✅ xp title/level + momentum tier/count + history empty state with XP/momentum visible | ➖ None |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `python -m pytest tests/test_spa_gate.py tests/test_xp.py tests/test_momentum.py tests/test_api.py -q` → **161 passed** (incl. new `test_journey_progress_surfaces`); RED run before implementation: **1 failed** (new pin) |
| Runtime harness command/scenario and exact result | `bash tests/smoke-ui.sh http://localhost:8129` (scratch uvicorn `WEIGHT_LOSS_DB=/tmp/wl-s4b-smoke.db`, tmp VAPID, real Chromium) → **62 passed, 0 failed** incl. xp card (Sprout, Level 1 · 40 XP), momentum (Good Day, 1 successful day in the last 21), quest-history explicit empty state |
| Rollback boundary | Revert the S4b commit on `feat/r1-quests-xp-s4b` — removes Journey cards markup, JS renderers, CSS, and their tests only; S4a/backend files untouched, no DB migration |

## Deviations from Design

1. **Rendering from S4a payloads instead of three parallel fetches** (design §Loading said "add authenticated requests for quests, XP, and momentum"). `loadJourneyCards` reuses the quests + XP payloads already fetched by `loadQuestsAndXp` (which must sequence quests→XP for the stale-chip race fix from S4a) and adds only the momentum fetch. Every payload is still fetched exactly once per load, all failure-scoped via `Promise.allSettled` — the S4a sequencing invariant is preserved and the Journey cards cannot render stale XP.
2. Quest-history card sources `history` from the `/api/quests` payload (past-day rows, newest first, bounded 10) — the dedicated `/api/xp` `recent_completions` feeds the XP card's recent-completions list, per endpoint contract.

## Issues Found

1. **Delegated apply transport failures (orchestration, not code)**: three `sdd-apply` launches for S4b died in transport (`sdd_task_result_malformed`, provider socket errors before fallback) with zero work produced. Maintainer approved inline implementation; attempt ledger reset + settled as passed on verified evidence.

## Verification (all green)

1. `python -m pytest tests/test_spa_gate.py tests/test_xp.py tests/test_momentum.py tests/test_api.py -q` → **161 passed**
2. `node --test tests/frontend/*.test.mjs` → **119 pass / 0 fail** (unchanged)
3. `python -m pytest -q` → **546 passed** (545 baseline + 1 new gate test)
4. `pyright` → **0 errors, 0 warnings**
5. `bash tests/smoke-ui.sh` (scratch server :8129, real Chromium) → **62 passed, 0 failed** (was 56 → +6 journey progress steps)
6. `tasks.md`: only 8.1–8.4 flipped to `[x]`; no other checkbox touched.
