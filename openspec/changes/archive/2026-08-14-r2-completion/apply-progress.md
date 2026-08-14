# Apply Progress — r2-completion

Change: r2-completion (Quest Icons, Weekly Objectives, Collectibles, Celebrations)
Status: ALL SLICES COMPLETE (S1–S6) — ready for verify
strict_tdd: true

## Slice 1: Quest Icons + Cartoon Fox (PR #58)

Frontend lane (frontend-dev → frontend-apply), branch `feat/r2-completion-s1`.

### TDD Cycle Evidence

| Task | RED test | GREEN implementation | Evidence |
| --- | --- | --- | --- |
| 1.1 | `tests/frontend/icons.test.mjs` (new) | `static/format.js` — `QUEST_DOMAIN_ICONS` array-of-pairs + `iconForDomain` fail-loud, registered on `WeightFormat` | node 3/3 pass |
| 1.2 | `tests/test_spa_gate.py` drift-guard pins | renderers consume `iconForDomain` with `aria-hidden` | pytest gate pass |
| 1.3 | (covered by 1.1) | icons literal ast.literal_eval-parseable (design decision B) | pyright clean |
| 1.4 | `tests/test_icons.py` byte/pixel pins | `static/icons/make_icons.py` cartoon-fox face shape; PNGs regenerated | pytest 51/51 pass |
| 1.5 | (covered by 1.4) | `static/index.html` favicon data-URI + `.mascot` + island stage-5 `.island-fox` group | visual verification (screenshots in `artifacts/r2-s1-*.png`) |
| 1.6 | (covered by 1.2) | `static/app.js` renderQuests/renderQuestHistory icons, reduced-motion block | gate pass |
| 1.7 | `tests/smoke-ui.sh` icon + mascot + placeholder pins | — | scratch smoke: new pins pass |
| 1.8 | — | commit `feat(icons): nine-domain quest icons and cartoon fox rework` (6df2b7c) | 341 changed lines ≤ 400 |

### Verification results (S1)

- `node --test tests/frontend/icons.test.mjs`: 3/3 pass
- `.venv/bin/python -m pytest tests/test_icons.py tests/test_spa_gate.py`: 51/51 pass
- pyright: clean
- Browser smoke (scratch port): 80 passed; 4 pre-existing zero-XP assertions fail IDENTICALLY on pristine base (R1 XP drift — streak_alive grants 20 XP; not slice-caused)
- Attempt ledger: r2c-s1-apply-2 settled `passed` (token d0228561…, complete)

## Slice 2: Weekly Objectives Backend (PR #59)

Backend lane (sdd-apply), branch `feat/r2-completion-s2` (stacked on S1).

### TDD Cycle Evidence

| Task | RED test | GREEN implementation | Evidence |
| --- | --- | --- | --- |
| 2.1 | `tests/test_weekly.py` (new, pure): week_start Mon–Sun + ISO rollover, 10/3 met, 9/2 unmet, Spark excluded, mid-week activation exemption | — | pytest pass |
| 2.2 | (covered by 2.1) | `weekly.py` (pure, no I/O): week identity, targets, met-ness, exemption | pytest pass |
| 2.3 | `tests/test_api.py` + `tests/test_user_isolation.py`: 401, two-user activation independence, first-read stamp, met flip once, no double-pay (≤80/week) | — | pytest pass |
| 2.4 | `tests/test_xp.py`: 20+40 done + one 40 award = 100; per-user isolation | — | pytest pass |
| 2.5 | (covered by 2.3/2.4) | `models.py` WeeklyState/WeeklyGoalState; `database.py` weekly_awards + weekly_activation (CREATE IF NOT EXISTS, composite PK, CHECK goal IN ('quests','good_days') AND xp_awarded=40 — NOT reward_events), weekly_snapshot, `_reconcile_weekly_awards`, activation stamp | pytest pass |
| 2.6 | (covered by 2.3) | `routes.py` GET /api/weekly (met_flips:[goal], 12-week cap); `main.py` startup reconcile; `xp.py` contract → quests + weekly awards | pytest pass |
| 2.7 | — | commit `feat(weekly): objectives engine, exactly-once awards, activation, XP sum` (8947866) | 943 lines — maintainer-approved size:exception |

### Verification results (S2)

- `.venv/bin/python -m pytest tests/test_weekly.py tests/test_xp.py tests/test_api.py tests/test_user_isolation.py`: 158/158 pass
- pyright: clean (0 errors)
- Sliced size 943 > 400 budget → **size:exception accepted by maintainer (one PR)**, ledger re-bound (r2c-s2-settle-3, state complete)

## Slice 3: Weekly Objectives UI (PR #60)

Frontend lane (frontend-dev → frontend-apply), branch `feat/r2-completion-s3` (stacked on S2).

### TDD Cycle Evidence

| Task | RED test | GREEN implementation | Evidence |
| --- | --- | --- | --- |
| 3.1 | `tests/test_spa_gate.py` pins: `#weekly-card` on Today (two progress rows) + Journey weekly containers | — | pytest gate pass |
| 3.2 | (covered by 3.1) | `static/index.html`: `#weekly-card` (quests + good-days rows) + Journey weekly card | gate pass |
| 3.3 | (covered by 3.1) | `static/app.js`: `/api/weekly` fetch (allSettled, card-scoped failure), counts/targets/met/exemption countdown render, `met_flips` forwarded as S6 weekly-met signal | gate pass |
| 3.4 | — | `static/style.css`: token-only bars/status, dark + mobile, reduced-motion static | visual verification |
| 3.5 | `tests/smoke-ui.sh`: both themes, exemption, met without double-XP text | — | 96/96 smoke pass |
| 3.6 | — | commit `feat(weekly): Today progress and Journey weekly history` (47cbec6) | 399 changed lines ≤ 400 |

### Verification results (S3)

- Full run: 608 pytest + 136 node + pyright clean; gate pins 49/49 (re-run by orchestrator)
- Browser smoke both themes 96/96; light/journey/dark-mobile screenshots verified visually
- Attempt ledger: r2c-s3-settle-1 `passed` → complete

## Slice 4: Collectibles Backend (PR 4)

Backend lane (sdd-apply), branch `feat/r2-completion-s4` (stacked on S3).

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4.1 | `tests/test_collectibles.py` (new) | Unit | N/A (new) | ✅ Written (ImportError on missing `CollectibleFacts`) | ✅ Passed 9/9 → merged to 4 dense functions, all pins intact | ✅ Multi-case: relock, broken runs, retroactive, empty, non-meal | ✅ (compression pass, tests stayed green) |
| 4.2 | `collectibles.py` (new) + `streaks.py` `first_run_milestones` (forward walk; `_run_backward`/`meal_streak` untouched) | Unit | ✅ 608 baseline green | ✅ (covered by 4.1 RED) | ✅ 9/9 pass | ✅ checkpoint 50→75 progression, earliest-week vs later-week | ✅ docstring/format pass, pyright clean |
| 4.3 | `tests/test_api.py` + `tests/test_user_isolation.py` | Integration | ✅ baseline green | ✅ Written (404 on missing endpoint) | ✅ 3/3 pass | ✅ shape + earned subset + 4 locked + XP-untouched; two-user isolation | ✅ one-liners, tests stayed green |
| 4.4 | `models.py` `CollectibleFacts`/`CollectibleState`; `constants.py` `COLLECTIBLE_CATALOG` (16, families derived from `ACHIEVEMENTS`); `database.py` `collectible_facts` one-`_tx` snapshot; `routes.py` GET /api/collectibles | Integration | ✅ baseline green | ✅ (covered by 4.3 RED) | ✅ 3/3 pass | ✅ per-user isolation + XP unchanged | ✅ (covered) |
| 4.5 | — | — | — | — | — | — | ✅ commit `feat(collectibles): earliest-crossing engine, catalogue, API` |

### Work Unit Evidence (S4 = one work unit)

| Evidence | Value |
| --- | --- |
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_collectibles.py tests/test_api.py tests/test_user_isolation.py` → 138 passed (4 pure engine tests covering all 9 pinned semantics + 2 API + 2 isolation + 130 existing) |
| Runtime harness command/scenario and exact result | N/A — httpx ASGITransport in-process tests cover the auth + per-user isolation boundaries; no external runtime boundary (backend-only slice) |
| Rollback boundary | Revert `collectibles.py` + `streaks.py` forward walk + `models.py`/`constants.py`/`database.py`/`routes.py` additions + the two test-file sections; API is additive, XP/economy untouched (R10) |

### Verification results (S4)

- `.venv/bin/python -m pytest tests/test_collectibles.py tests/test_api.py tests/test_user_isolation.py`: 138/138 pass
- Full suite: 615 pytest pass (608 baseline + 7 new test functions; 5 pure functions merged into 4 for the ≤400 budget — every pinned assertion preserved)
- Node frontend suite: 136/136 pass (untouched by this backend slice)
- pyright: 0 errors, 0 warnings (full project, .venv interpreter per pyrightconfig)
- Slice diff: 397 changed lines (additions + deletions) ≤ 400 budget
- XP/economy: collectibles read is pure derivation — `total_xp_for_user` unchanged by GET /api/collectibles (R10 pin in test_api)

## Slice 5: Collectibles UI (PR 5)

Frontend lane (frontend-dev → frontend-apply), branch `feat/r2-completion-s5` (stacked on S4).

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.1 | `tests/test_spa_gate.py` | Integration/gate | ✅ 49 gate + 136 node baseline | ✅ Written first: missing `#collectibles-card` failed (1 failed, 49 passed) | ✅ 50/50 pass | ✅ Journey-only placement + empty World slot + fetch/signal/CSS pins | ✅ Dense gate kept slice within budget |
| 5.2 | `static/index.html` | Integration/gate | ✅ baseline green | ✅ Covered by 5.1 RED | ✅ Card after achievements + hidden SVG accent slot | ✅ shelf absent from World; accent defaults empty | ✅ list class and geometric SVG artwork |
| 5.3 | `static/app.js` | Browser integration | ✅ baseline green | ✅ Covered by 5.1 RED | ✅ 16 ordered rows, DD/MM/YY latest accent, fulfilled-only S6 signal | ✅ earned/locked, month rollover, empty, failed read, first/new earn | ✅ explicit SVG hidden-attribute handling after visual RED |
| 5.4 | `static/style.css` | Visual/browser | ✅ baseline green | ✅ Covered by token/mobile/motion gate pins | ✅ token-only art, dark/mobile, reduced motion | ✅ earned medallion vs locked silhouette in both themes | ✅ CSS-only geometric marks, no emoji glyphs |
| 5.5 | `tests/smoke-ui.sh` | E2E | ✅ 96 prior smoke assertions | ✅ Visual review exposed hidden SVG accent; tightened smoke failed `visible=false` | ✅ 110/110 pass | ✅ order, states, dates, latest/empty/failure/signal, both themes | ✅ direct delimiter order comparison + real computed visibility |
| 5.6 | gate/node/pytest/pyright/smoke | Verification | ✅ all final runs | ✅ S5 regressions observed before fixes | ✅ all required runs pass | ✅ static, unit, full integration, browser and visual layers | ✅ commit `09354b3` |

### Work Unit Evidence (S5 = one work unit)

| Evidence | Value |
| --- | --- |
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_spa_gate.py` → 50 passed; `node --test tests/frontend/*.test.mjs` → 136 passed |
| Runtime harness command/scenario and exact result | Scratch uvicorn on port 8129 + `tests/smoke-ui.sh http://127.0.0.1:8129` → 110 passed, 0 failed; exact 16-row order, earned/locked art and dates, chronological World accent, empty/failure states, S6 signal, light/dark/mobile |
| Rollback boundary | Revert `static/index.html`, `static/app.js`, `static/style.css`, and the S5 gate/smoke additions; no backend/API/economy behavior changes |

### Verification results (S5)

- Gate: 50/50 pass
- Node frontend suite: 136/136 pass
- Full pytest suite: 616/616 pass
- Pyright: 0 errors, 0 warnings
- Scratch browser smoke: 110/110 pass (both themes)
- Visual verification: `artifacts/r2-completion-s5/collectibles-journey-light.png` shows the complete readable shelf; `artifacts/r2-completion-s5/collectibles-world-dark-mobile.png` shows the latest token visibly embedded on the island. Visual review caught and fixed SVG `hidden` attribute/property drift before final acceptance.
- Slice diff: 399 changed lines (396 additions + 3 deletions) ≤ 400 budget
- Commit: `09354b3` — `feat(collectibles): Journey shelf and World latest-earn accent`

## Slice 6: Celebration Queue (PR 6)

Frontend lane on `feat/r2-completion-s6` (stacked on S5). NOTE: an intermediate lane report marked this slice "partial — 774 lines, no commit"; that note predates the final compression pass. Final state: celebration queue compressed to 346 changed lines and committed as `6a7c041`.

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6.1–6.2 | `tests/frontend/celebrations.test.mjs` (compressed 154→62 lines) | Unit | ✅ 136/136 baseline | ✅ Missing helper exports failed | ✅ 7 focused; 143/143 full node | ✅ First/changed/unchanged/failed-read and stable priority cases | ✅ Compression pass under budget |
| 6.3–6.5 | `tests/test_spa_gate.py`, `tests/smoke-ui.sh` | Gate/E2E | ✅ 50/50 gate baseline | ✅ Missing banner failed (1 failed, 50 passed) | ✅ Gate 51/51; smoke pins pass (see verification) | ✅ Reload and reduced-motion scenarios included | ✅ Smoke pins iterated post-commit (level mocks aligned with live behavior), amended into `6a7c041` |

### Verification results (S6)

- Node frontend suite: 143/143 pass (136 baseline + 7 celebration tests).
- SPA gate: 51/51 pass (baseline 50 + banner pin).
- Full pytest suite: 617/617 pass.
- Pyright: 0 errors, 0 warnings.
- Scratch browser smoke (port 8129, both themes): 108 passed, 4 failed — the 4 failures are the KNOWN pre-existing R1 XP-drift assertions (fresh account shows 20 XP from streak_alive; identical on pristine base, documented since S1). All S6 pins pass: banner after level crossing (Level N · title), achievement toast after banner (R18 order), reload shows no replay (`true|0`), reduced-motion static banner with zero confetti (R17).
- Visual review: `artifacts/r2-completion-s6/banner-today-light.png` and `banner-reduced-motion.png` show the non-blocking level banner without layout breakage.
- Slice diff: 346 changed lines (318 additions + 28 deletions) ≤ 400 budget
- Commit: `6a7c041` — `feat(celebrations): priority celebration queue with banner and toasts`

### Orchestrator post-crash note

The parent terminal rebooted after the lane's final smoke-pin iteration; the orchestrator verified the amended tree (617 pytest / 143 node / 51 gate / pyright 0 / smoke) and amended the verified pins into the S6 commit. The 4 smoke failures are pre-existing R1 XP drift, not slice-caused.

## Status: ALL SLICES COMPLETE (S1–S6) + R6 remediation committed — ready for re-verify

## Remediation: R6 immediate award

Independent verify (verify-report.md) found **1 CRITICAL**: R6's "Tenth quest
pays immediately" scenario failed because the weekly +40 XP award was paid
lazily — only by `GET /api/weekly` reads or startup reconciliation — instead
of AT THE MOMENT the quest becomes done. The runtime probe observed
`weekly_awards_before_weekly_read=0` and `xp_after_completion=240` (no +40)
after the tenth completion.

### The fix (routes.py only — database.py/weekly.py untouched)

1. `complete_quest` (POST /api/quests/{id}/complete): on the non-idempotent
   path, after `update_quest_status` and BEFORE computing `level_after`, calls
   `await run_db(db.reconcile_weekly_awards, user.id)` so `level_up` reflects
   the award. The idempotent `status == "done"` early return is unchanged.
   Docstring now states the award timing.
2. `_ensure_today_quests` (GET /api/quests): tracks whether any detection
   actually persisted (`detection_persisted` flag on the existing
   status/source/stored-status condition) and, only then, calls
   `await run_db(db.reconcile_weekly_awards, user.id)` so a read-detected
   tenth completion pays before the caller's next XP read. Plain reads stay
   read-only.
3. Bonus: `get_xp` docstring corrected (verify WARNING #4 — it claimed
   quests-only/no-ledger derivation).

The award row persists at mutation time; `reconcile_weekly_awards` is exactly
once via the `(user_id, week_start, goal)` PK and a no-op for never-activated
users, so repeats (idempotent complete, repeat weekly read, restart) never
double-pay. NOTE: because the payment now happens up front, the NEXT
`/api/weekly` read reports `met_flips: []` (the read no longer pays anything)
and shows the goal as `met + awarded`; the orchestrator's assumption that the
post-mutation SPA re-fetch surfaces the flip via `met_flips` does not hold
under the awarded-guard in `_reconcile_weekly_awards`. The timing CRITICAL is
fully resolved; the weekly-met toast signal depends on `met_flips` from a
paying read, so it should be re-verified against the S6 celebration path.

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R6 mutation timing (+40 before any weekly read) | `tests/test_api.py` `test_weekly_tenth_quest_pays_immediately` (rewritten — verify flagged the old form as CRITICAL assertion quality) | Integration | ✅ 161/161 | ✅ Failed: `assert 240 == (220+20)+40` | ✅ 6/6 pass | ✅ Non-tenth no-pay (`test_weekly_non_tenth_completion_pays_no_award`), exactly-once repeats (`test_weekly_mutation_award_exactly_once`), level-boundary crossing (`test_weekly_tenth_completion_level_up_includes_award`, `level_up` None→{from:2,to:3}) | ✅ 18-line call-site patch, flags named, docstrings updated |
| R6 detection path pays during GET /api/quests | `tests/test_api.py` `test_weekly_detected_tenth_quest_pays_during_quest_read` | Integration | ✅ 161/161 | ✅ Failed (award deferred past quest read) | ✅ Passed (+80 = quests + good_days, mood log row makes Wed a Good day) | ✅ Plain-read guard: first quests read persists nothing, pays nothing | ✅ `detection_persisted` flag keeps reads read-only |
| R6 isolation | `tests/test_user_isolation.py` `test_weekly_mutation_award_isolated_between_users` | Integration | ✅ 161/161 | ✅ Failed (alice award missing) | ✅ Passed (bob untouched, no rows) | ✅ 1/10-bob contrast case | ➖ None needed |

### Work Unit Evidence

| Evidence | Value |
| --- | --- |
| Focused test command and exact result | `.venv/bin/python -m pytest "tests/test_api.py::test_weekly_tenth_quest_pays_immediately" ... (6 new/rewritten tests)` → 6 passed, 0 failed (RED first: 5 failed / 1 passed) |
| Runtime harness command/scenario and exact result | N/A — httpx ASGITransport in-process tests cover the full request path (complete → /api/xp → /api/weekly) including auth and two-user isolation; backend-only fix, no external runtime boundary |
| Rollback boundary | Revert commit `59452ba0` (routes.py call sites + docstrings + the test sections); database.py and weekly.py are untouched |

### Verification results (remediation)

- Targeted: `.venv/bin/python -m pytest tests/test_weekly.py tests/test_xp.py tests/test_api.py tests/test_user_isolation.py -q` → 166 passed (161 baseline + 5 net new)
- Full suite: `.venv/bin/python -m pytest tests/ -q` → 622 passed (617 baseline + 5 net new)
- Pyright: 0 errors, 0 warnings
- Node suite untouched: `node --test tests/frontend/*.test.mjs` → 143/143 pass
- `git diff --check` clean; pre-commit gga review PASSED
- Changed lines: 304 (285 additions + 19 deletions) ≤ 400 budget
- Commit: `59452ba01d7585be9549fbab2d63db220f7c2a16` — `fix(weekly): pay award atomically when quest becomes done`
