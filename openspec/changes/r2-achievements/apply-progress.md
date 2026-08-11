# Apply Progress: r2-achievements

Cumulative progress for the R2 achievements change. All three slices implemented
and merged to main (stacked-to-main chain).

## S1 — Engine Foundation (PR 1, commit 815b726, merged as f1e34dd)

- [x] 1.1 `AchievementQuestFact`, `ExerciseDayFacts`, `AchievementFacts`, `AchievementState` dataclasses added to `models.py`
- [x] 1.2 Ordered `ACHIEVEMENTS` catalog (6 keys/titles) added to `constants.py`
- [x] 1.3 RED: `tests/test_achievements.py` written first — 17 parametrized cases (empty/order; quest thresholds/dates; `streak_alive` exclusion; five-in-seven with Spark/missing; comeback with skipped, replaced-only break, Spark return; distinct domains; daily sums/earliest/re-lock)
- [x] 1.4 GREEN: pure `achievements.py` with `states(facts, catalog)` — six predicates + earliest-earned derivation; reuses `momentum.classify_day`/`is_successful`/`action_count`; `quest.date`; no I/O
- [x] 1.5 Focused + full suites green; code diff 399 ≤ 400 changed lines (parametrized)

### TDD Cycle Evidence (S1)

| Task | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----|-------|-------------|----------|
| 1.1/1.2 | ✅ written (structural) | ✅ passed | ➖ structural (dataclasses/pin) | ✅ clean |
| 1.3 | ✅ written — collection error (module absent) | ✅ 17 passed | ✅ 17 parametrized cases | ✅ clean |
| 1.4 | ✅ (proven via 1.3) | ✅ 17 passed | ✅ covered by cases | ✅ clean (unused import removed) |
| 1.5 | n/a | ✅ 567 passed | n/a | ✅ 399 lines ≤ 400 |

### Work Unit Evidence (S1)

- Focused: `.venv/bin/python -m pytest tests/test_achievements.py -q` → `17 passed in 0.03s`
- Runtime harness: N/A — pure module, no I/O, no runtime boundary; unit tests are the harness
- Rollback: revert `achievements.py` + `constants.py`/`models.py` additions and delete `tests/test_achievements.py`

## S2 — Facts Gather + API (PR 2, commit bfcf8f4, merged as 56cc1fe)

- [x] 2.1 RED: `tests/test_api.py` — 401 unauthenticated, two-user isolation, empty history, six-state shape/order, gather isolation
- [x] 2.2 GREEN: `Database.achievement_facts(user_id)` — done quest rows, per-date momentum facts, per-date exercise sums, `WHERE user_id = ?`, one `_tx`
- [x] 2.3 `GET /api/achievements` — `Depends(require_user)` + `await run_db(...)` + `asdict` serialization (`{"achievements": [...]}`; entry shape `{key, title, earned, unlocked_at}`)
- [x] 2.4 Focused pytest + pyright green

### TDD Cycle Evidence (S2)

| Task | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----|-------|-------------|----------|
| 2.1 | ✅ 5 tests failed (404/KeyError) | ✅ 93 passed | ✅ 5 API scenarios | ✅ helper extraction |
| 2.2 | ✅ (endpoint missing → 404) | ✅ 93 passed | ✅ 2 gather paths | ✅ `_momentum_day_rows` shared |
| 2.3 | ✅ (route missing → 404) | ✅ 93 passed | ✅ same 5 scenarios | ➖ none needed |
| 2.4 | — | pyright 0 errors; focused 110 passed | — | ✅ `params` annotation fix |

### Work Unit Evidence (S2)

- Focused: `.venv/bin/python -m pytest tests/test_api.py tests/test_achievements.py -q` → `110 passed in 4.83s`
- Runtime harness: httpx ASGITransport in-process client (auth + isolation through the real request path)
- Rollback: revert commit `bfcf8f4` only — additive read API; S1 files untouched

## S3 — Journey UI + Confetti (PR 3, commit 2762f7c, branch feat/r2-achievements-s3)

- [x] 3.1 RED: `tests/frontend/achievements.test.mjs` — first-read suppress, new-key fire once, unchanged/lost sets suppress, `shouldCelebrate` regression
- [x] 3.2 GREEN: `newAchievementKeys(previous, current)` in `static/format.js` (null previous → `[]`, Set-subtraction over `(current ?? [])`)
- [x] 3.3 `#achievements-card` (aria-label "Achievements") after `#momentum-card`, before `#quest-history-card`; token-only CSS (dark/mobile, reduced-motion, no `@starting-style`)
- [x] 3.4 `static/app.js`: `loadJourneyCards` allSettled batch `[momentum, achievements]`, six-row render (earned + unlock date / locked, no progress), read-diff → `fireConfetti()` once, prior set updated only on fulfilled response
- [x] 3.5 `tests/test_spa_gate.py` (`test_journey_achievements_surface`) + `tests/smoke-ui.sh` pins; all existing checks retained
- [x] 3.6 node + pytest + pyright + smoke green

### TDD Cycle Evidence (S3)

| Task | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----|-------|-------------|----------|
| 3.1/3.2 | ✅ 7/7 failed (`newAchievementKeys is not a function`) | ✅ 7/7 pass | ✅ 9 scenarios | ➖ none |
| 3.3/3.4 | ✅ gate pin failed (missing `#achievements-card`) | ✅ 43/43 pass | ✅ 12 distinct pins | ➖ none |
| 3.5/3.6 | n/a (E2E post-implementation) | ✅ smoke 68/68 | ✅ 6 new checks | ➖ none |
| 3.2 regression | n/a | ✅ confetti 5/5 | ✅ unchanged | ➖ none |

### Work Unit Evidence (S3)

- Focused: `node --test tests/frontend/achievements.test.mjs` → 7 pass; `pytest tests/test_spa_gate.py -q` → 43 passed
- Runtime harness: `bash tests/smoke-ui.sh http://localhost:8129` vs scratch uvicorn (`WEIGHT_LOSS_DB=/tmp/wl-s3-smoke.db`, port 8129) → `68 passed, 0 failed — UI smoke test PASSED`
- Rollback: revert commit `2762f7c` only — `static/*` + frontend tests + gate/smoke pins; S1/S2 files untouched

## Cumulative Verification

- `node --test tests/frontend/*.test.mjs` → 126 pass (119 + 7)
- `.venv/bin/python -m pytest -q` → 573 passed
- `.venv/bin/pyright` → 0 errors, 0 warnings
- Changed lines: S1 409 (399 code), S2 282, S3 322 — all slices within budget; no `size:exception`

## Remaining

- [ ] 4.1 Phase 4 full verification (sdd-verify)
