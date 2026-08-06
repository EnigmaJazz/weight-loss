# Tasks: Activity Logging — Exercise & Meal Streaks

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950–1000 additions across 11 files |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 engine → PR 2 CRUD backend → PR 3 endpoint + SPA |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (resolved) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Pure streak engine | PR 1 | `.venv/bin/python -m pytest tests/test_streaks.py` | N/A — pure, no I/O | Revert streaks.py, models.py, test_streaks.py |
| 2 | Exercise/meal CRUD backend | PR 2 | `.venv/bin/python -m pytest tests/test_activity_api.py` | N/A — ASGITransport tests prove API | Revert 3 backend files + test_activity_api.py; `DROP TABLE` optional |
| 3 | Streaks endpoint + SPA | PR 3 | `.venv/bin/python -m pytest tests/test_spa_gate.py tests/test_activity_api.py -k streak` | `uvicorn main:app`; verify tiles update | Revert static/*, streaks route, appended tests |

## Phase 1: Streak Engine (work unit 1)

- [x] 1.1 Add `ExerciseEntry`, `MealEntry`, `StreakState` dataclasses to `models.py`
- [x] 1.2 RED: create `tests/test_streaks.py` — empty→0, single→1, gap break, pending partial (1 / 2-vs-3 / meal), multi-meal day, ISO rollover (2026-12-28→2027-W1), deletion changes next read
- [x] 1.3 Create `streaks.py`: `prev_iso_week`, `_run_backward` (min_count 1/3/1), `weight_streak`, `exercise_streak`, `meal_streak`, `streak_state`
- [x] 1.4 GREEN: pass all `tests/test_streaks.py` — current partial never breaks; elapsed empty breaks

## Phase 2: Activity CRUD Backend (work unit 2)

- [ ] 2.1 Add `exercise_entries` + `meal_entries` `CREATE TABLE IF NOT EXISTS` to `SCHEMA_STATEMENTS` in `database.py` (no uniqueness, no migration)
- [ ] 2.2 Add `EXERCISE_TYPES = ("walk","run","gym","cycling","swim","other")` to `constants.py`
- [ ] 2.3 RED: create `tests/test_activity_api.py` — CRUD round-trips, 201, 422 (bad date, ≤0 duration/calories, unknown type, extra field), 401, cross-user 404, isolation, rewards weight-only
- [ ] 2.4 Add 6 `Database` methods + `_exercise_from_row`/`_meal_from_row` to `database.py` (user_id-first, explicit `_local_now()`, ownership in DELETE WHERE)
- [ ] 2.5 GREEN: add `ExerciseIn`/`MealIn` (extra="forbid", `_valid_date`, `Field(gt=0)`, allowlist) + GET/POST/DELETE `/api/exercise[/{id}]` and `/api/meals[/{id}]` in `routes.py` (INSERT→201, newest-first by id)

## Phase 3: Streaks Endpoint + SPA (work unit 3)

- [ ] 3.1 RED: append `GET /api/streaks` envelope tests (three counts; 401) to `tests/test_activity_api.py`
- [ ] 3.2 GREEN: add `GET /api/streaks` → `streak_state(...)` via `run_db` in `routes.py`; return `asdict(StreakState)`
- [ ] 3.3 Drift guard: `tests/test_spa_gate.py` — served `/static/app.js` EXERCISE_TYPES literal == `constants.EXERCISE_TYPES`
- [ ] 3.4 Add exercise/meal forms, history `<ul>`s, 3 streak tiles to `static/index.html`
- [ ] 3.5 Add `render*`/`delete*`/`add*` handlers + 3 fetches in `loadData()` to `static/app.js`
- [ ] 3.6 Style new forms/lists/tiles in `static/style.css` matching weight UI

## Phase 4: Verification

- [ ] 4.1 Full suite: `.venv/bin/python -m pytest` + `node --test tests/frontend/` — 37 tests unchanged
- [ ] 4.2 pyright clean on changed files; no `print()`, no bare except
- [ ] 4.3 Commit per unit (conventional commits, no AI attribution)
