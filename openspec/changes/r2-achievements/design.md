# Design: R2 Achievements

## Technical Approach

Add one ownership-scoped database gather, then derive all six states in a pure `achievements.py` engine. No table, schema, write-path, scheduler, or `reward_events` change is required. The Journey SPA renders the catalogue and performs a successful-read key-set diff before reusing `fireConfetti()`.

## Architecture Decisions

| Decision | Choice and rationale |
|---|---|
| Derivation | `Database.achievement_facts(user_id)` returns one snapshot from one `_tx`; `achievements.py` performs no I/O. This matches `momentum.py`/`rewards.py`, avoids unlock persistence/backfill, and keeps blocking SQLite behind one `run_db` call. |
| Facts | Add dataclasses `AchievementQuestFact(date, quest_key, domain)`, `ExerciseDayFacts(date, duration_min)`, `AchievementFacts(done_quests, momentum_days, exercise_days)`, and `AchievementState(key,title,earned,unlocked_at)` in `models.py`. Structured facts prevent route-owned dictionaries. |
| Calendar semantics | Sort local ISO dates and treat missing or replaced-only dates as neutral. Reuse `momentum.classify_day` and `is_successful`; this preserves Good/Great consistency, Spark returns, skipped assignments, and neutral breaks without duplicating tier rules. |
| Celebration | Add pure `newAchievementKeys(previous, current)` in `static/format.js`; `null` suppresses first read and set subtraction ignores unchanged/lost keys. Update prior state only after a fulfilled response and call existing `fireConfetti()` once when the diff is non-empty; its current reduced-motion gate remains authoritative. |

## Capability Design and File Changes

| Capability | Files | Design |
|---|---|---|
| Achievements | Create `achievements.py`, `tests/test_achievements.py`; modify `constants.py`, `models.py` | `ACHIEVEMENTS` preserves the six-key order. The engine selects first done quest; tenth done `exercise_10`; fifth first-seen done domain; fifth success in the earliest seven-date span; first action after an inactive run of at least three dates; and earliest daily exercise sum exceeding all strictly earlier sums. Quest unlocks use `quest.date`. |
| Facts/API | Modify `database.py`, `routes.py`, `tests/test_api.py` | Gather done quest rows, all-history momentum aggregates, and per-date exercise sums under `WHERE user_id = ?`. `GET /api/achievements` uses `Depends(require_user)` and `await run_db(...)`; serialize with `asdict`. |
| Journey/appearance | Modify `static/index.html`, `static/app.js`, `static/format.js`, `static/style.css`, `tests/frontend/achievements.test.mjs`, `tests/test_spa_gate.py`, `tests/smoke-ui.sh` | Insert `#achievements-card` immediately after `#momentum-card`; always render six earned/locked rows, dates only when earned, no progress. Fetch achievements beside momentum with `Promise.allSettled`; failure is card-scoped and preserves other Journey cards. Use existing tokens and motion rules. |

## Data and API Contracts

```text
GET /api/achievements
→ {"achievements":[{"key":str,"title":str,"earned":bool,"unlocked_at":str|null} × 6]}

require_user → run_db(Database.achievement_facts, user.id)
             → achievements.states(facts, ACHIEVEMENTS) → asdict → SPA
```

The gather is one database method/transaction, not one monolithic SQL statement. It calendarizes sparse momentum facts in the pure layer. Personal Best compares each positive daily `SUM(duration_min)` with the maximum of strictly earlier dates, starting at zero.

## Delivery Slices

| Main-targeted chain | Scope, gates, rollback |
|---|---|
| S1 (<400) | Engine, catalogue, dataclasses, unit tests. Merge to `main`; revert is pure/catalogue-only. |
| S2 (<400) | Gather, endpoint, API tests. Rebase on merged S1 and target `main`; revert removes an additive read API. |
| S3 (<400) | Card, read-diff/confetti, Node/gate/smoke pins. Rebase on merged S2 and target `main`; UI-only revert leaves API inert. |

## Test Inventory

- **Unit:** empty/order; exact quest thresholds/dates; `streak_alive` exclusion; five-in-seven with Spark/missing dates; comeback with skipped, replaced-only break, and Spark return; distinct domains; daily sums, earliest record, and re-lock after all positive evidence is removed; gather isolation.
- **API:** exact six-state shape/order, quest dates, authenticated 401, two-user isolation, and empty history.
- **Node:** first-read suppression, additions, unchanged/repeated sets, losses, and existing checkpoint `shouldCelebrate` regression.
- **SPA gate/smoke:** card order, fetch/export/render hooks, scoped failure wiring, six locked/earned rows, no partial progress, token/dark/mobile rules, reduced-motion and no-`@starting-style` pins; retain all existing Journey checks.

## Threat Matrix

| Boundary | Applicability and response |
|---|---|
| Documentation-like paths | N/A — no file classification or execution. |
| Git repository selection | N/A — no Git command integration. |
| Commit state | N/A — no commit automation. |
| Push state | N/A — no push automation. |
| PR commands | N/A — the chain is delivery guidance, not executable automation. |

The HTTP boundary expects 401 without a valid session and only `user.id`-filtered facts on success; RED API tests cover both failure and cross-user isolation.

## Migration, Rollout, Risks

No migration or backfill. Roll back S3 → S2 → S1; each slice is independently green. Full-history reads may grow, but remain one per-user SQLite snapshot. No blocking questions. Proposal drift: its broad Personal Best deletion warning is narrower under the locked rule—because the first remaining positive day qualifies, re-lock occurs only when no positive qualifying evidence remains.
