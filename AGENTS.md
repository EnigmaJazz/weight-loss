# AGENTS.md — Code Review Rules for the Weight Loss Tracker

This file is consumed by the `gga` pre-commit hook (`.gga`, `RULES_FILE="AGENTS.md"`).
It is the prompt context for the AI review provider. Keep rules short, concrete, and
project-specific.

## Stack

- Python 3.14, FastAPI 0.141.x, uvloop event loop
- pytest + pytest-asyncio (strict mode) — async tests need `@pytest.mark.asyncio`
- httpx ASGITransport for in-process API tests
- dataclasses for internal state objects (WeightEntry, ActiveCheckpoint, RewardState, etc.)
- SQLite (`weight_loss.db`) via the stdlib `sqlite3` module
- Web Push via `pywebpush` + `py_vapid` (VAPID keys persisted to `vapid_keys.json`)

## Module map

- `main.py` — FastAPI app factory (`create_app`) + lifespan wiring + `init_app_state`
- `routes.py` — all `/api/*` endpoints, request-body validation, serialization, `require_user` session dependency
- `auth.py` — pure password (scrypt) + session/reset token helpers, no I/O
- `database.py` — SQLite schema, `Database` class (single connection + lock), row → dataclass mapping, `run_db` thread helper, `_local_now` wall-clock timestamps, `active_rewards` reconciliation
- `units.py` — pure conversions: `kg_to_lb`, `kg_to_stone`, `calculate_bmi`, `weight_display` (returns raw values; rounding for display is the SPA's job)
- `rewards.py` — checkpoint rewards: `CHECKPOINTS` (10/25/50/75/100), `checkpoint_thresholds`, `active_checkpoints`, `next_checkpoint`, `progress_to_next_checkpoint`, `reward_state`, `compute_baseline`/`compute_current`/`compute_lost`, `remaining_to_target`
- `quests.py` — daily quest generation/replacement/completion (`generate_quests`, `mark_done`)
- `xp.py` — XP levels and titles (`level_from_xp`, `level_progress`, `title_for_level`)
- `achievements.py` — achievement unlock-date detection from `AchievementFacts`
- `streaks.py` — weight/exercise/meal streaks and first-run milestones (`streak_state`)
- `momentum.py` — rolling-window day classification (`momentum_state`)
- `weekly.py` — weekly goals and good-day counts (`goal_state`)
- `collectibles.py` — island collectible states from checkpoint/weekly-token dates
- `mailer.py` — SMTP password-reset email (`smtp_configured`, `send_reset_email`)
- `notifications.py` — VAPID load/generate/persist (persisted payload loads via `_vapid_from_payload`), `send_push`, `send_to_all` (pywebpush)
- `scheduler.py` — asyncio background loop, daily due-check, dedupe via `notifications_sent`
- `constants.py` — `.env` loading, logger factory (`get_logger`), env-driven paths/SMTP/cookie config, defaults, allowlists (`ACCENT_COLORS`, `QUEST_POOL`), notification messages
- `models.py` — all dataclasses: users/sessions (`User`, `Session`, `ResetToken`), entries (`WeightEntry`, `ExerciseEntry`, `MealEntry`, `MoodEntry`, `HabitEntry`), `AppSettings`, and the `*Facts` / `*State` pairs feeding and returned by the pure domain modules
- `static/` — vanilla JS SPA (index.html, app.js, auth.js, format.js, style.css, sw.js, manifest.webmanifest, icons/make_icons.py); formats the API's raw kg/lb/st/BMI values
- `tests/` — conftest harness (`client`/`auth_client`/`onboarded_client`), per-module pytest suites, `frontend/*.test.mjs` (node --test), `smoke-ui.sh` browser smoke
- `pyrightconfig.json` — pyright config pinned to the `.venv` interpreter (pythonPlatform linux)

## Hard rules

1. **Async everywhere in the request path**: routes are `async def`, the DB dependency is
   `async`, and all blocking DB/network work is awaited. Sync SQLite calls MUST be wrapped
   with `await run_db(...)` (database.py). Sync code in the request path is a bug.

2. **Type hints required**: function signatures must have type hints. Use
   `Optional[X]` for nullable, `tuple[...]` / `dict[...]` / `list[...]` (not
   `Tuple`/`Dict`/`List` from typing unless Python 3.9 compat is needed).

3. **Dataclasses for structured state**: new state objects use `@dataclass`, not dicts.
   Add them to `models.py`, not to routes.

4. **No global state outside `fastapi app.state`**: the DB and VAPID keys live on
   `app.state.*`. Module-level mutable globals are forbidden except cached constants
   in `constants.py`.

5. **Tests**: new code paths MUST have a regression test. Use the harness in
   `tests/conftest.py` (tmp_path DB, scheduler disabled, `send_to_all` stubbed so no
   real push is ever sent). Async fixtures use `@pytest_asyncio.fixture`; async tests
   use `@pytest.mark.asyncio` (NOT plain `@pytest.fixture` for async fixtures).

6. **No AI attribution in commits**: `Co-Authored-By:` trailers are forbidden.
   Use conventional commits: `type(scope): subject`.

7. **No `print()`**: use `get_logger(name)` from constants.py.

8. **No bare `except:`**: catch specific exceptions. `except Exception` is OK only at
   process boundaries: lifespan, the scheduler loop, and the per-push send boundary
   (network failures must not kill a batch).

## Scope conventions

- Bug fixes: `fix(scope): subject` — e.g. `fix(routes): reject zero weight on upsert`
- Features: `feat(scope): subject` — e.g. `feat(scheduler): daily tip notification`
- Housekeeping: `chore: subject` — e.g. `chore: update requirements.txt`

## Reference docs

- `AGENTS.md` — this file, consumed by `.gga` as review rules
- `docs/solutions/` — documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`); relevant when implementing or debugging in documented areas
