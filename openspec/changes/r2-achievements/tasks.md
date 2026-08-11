# Tasks: R2 Achievements

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1050 total (S1 ~400, S2 ~300, S3 ~350) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1) → PR 2 (S2) → PR 3 (S3), stacked to main |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| S1 | Pure engine + catalogue + dataclasses | PR 1 | `.venv/bin/python -m pytest tests/test_achievements.py` | N/A — pure module, no I/O; unit tests are the harness | Revert `achievements.py` + `constants.py`/`models.py` additions |
| S2 | Facts gather + achievements endpoint | PR 2 | `.venv/bin/python -m pytest tests/test_api.py` | N/A — httpx ASGITransport client covers auth + isolation in-process | Revert `database.py`/`routes.py` additions (additive API) |
| S3 | Journey card + read-diff confetti + pins | PR 3 | `node --test tests/frontend/achievements.test.mjs` + `.venv/bin/python -m pytest tests/test_spa_gate.py` | `bash tests/smoke-ui.sh` (playwright vs dev server) | Revert `static/*` + frontend tests (UI-only) |

Chain: each PR rebases on the merged predecessor and targets `main` in order (S1 → S2 → S3). S1 is the tightest slice — keep it ≤400 via parametrized tests.

## Phase 1: S1 — Engine Foundation (PR 1)

- [x] 1.1 Add `AchievementQuestFact`, `ExerciseDayFacts`, `AchievementFacts`, `AchievementState` dataclasses to `models.py`.
- [x] 1.2 Add ordered `ACHIEVEMENTS` catalog (6 keys/titles) to `constants.py`.
- [x] 1.3 RED: write `tests/test_achievements.py` — empty/order; quest thresholds/dates; `streak_alive` exclusion; five-in-seven with Spark/missing; comeback (skipped, replaced-only break, Spark return); distinct domains; daily sums/earliest/re-lock (spec scenarios).
- [x] 1.4 GREEN: create pure `achievements.py` with `states(facts, catalog)` — six predicates + earliest-earned derivation; reuse `momentum.classify_day`/`is_successful`; `quest.date`; no I/O.
- [x] 1.5 `pytest tests/test_achievements.py` green; keep S1 ≤400 changed lines (parametrize).

## Phase 2: S2 — Facts Gather + API (PR 2)

- [x] 2.1 RED: extend `tests/test_api.py` — 401 unauthenticated, two-user isolation, empty history, six-state shape/order, gather isolation (spec: isolated API response; threat-matrix HTTP boundary).
- [x] 2.2 GREEN: add `Database.achievement_facts(user_id)` to `database.py` — done quest rows, per-date momentum facts, per-date exercise sums, `WHERE user_id = ?`, one `_tx`.
- [x] 2.3 Add `GET /api/achievements` to `routes.py` — `Depends(require_user)` + `await run_db(...)` + `asdict` serialization (design contract).
- [x] 2.4 `pytest tests/test_api.py` + `.venv/bin/pyright` green.

## Phase 3: S3 — Journey UI + Confetti (PR 3)

- [ ] 3.1 RED: add `tests/frontend/achievements.test.mjs` — first-read suppress, new-key fire once, unchanged/lost sets suppress, `shouldCelebrate` regression (game-appearance scenarios).
- [ ] 3.2 GREEN: add `newAchievementKeys(previous, current)` to `static/format.js`.
- [ ] 3.3 Insert `#achievements-card` after `#momentum-card` in `static/index.html`; style in `static/style.css` (tokens, dark/mobile, reduced-motion, no `@starting-style`).
- [ ] 3.4 Wire `static/app.js`: fetch achievements beside momentum (`Promise.allSettled`, card-scoped failure), render six rows, read-diff → `fireConfetti()` once, prior set updated only on success (journey-progress-ui scenarios).
- [ ] 3.5 Update `tests/test_spa_gate.py` + `tests/smoke-ui.sh` pins: card order, six locked/earned rows, no progress, reduced-motion; keep all existing checks.
- [ ] 3.6 Run node + pytest + `bash tests/smoke-ui.sh` green.

## Phase 4: Full Verification

- [ ] 4.1 Full suite: `.venv/bin/python -m pytest` + `node --test tests/frontend/` + `.venv/bin/pyright`; all green.
