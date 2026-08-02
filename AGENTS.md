# AGENTS.md — Code Review Rules for the Weight Loss Tracker

This file is consumed by the `gga` pre-commit hook (`.gga`, `RULES_FILE="AGENTS.md"`).
It is the prompt context for the AI review provider. Keep rules short, concrete, and
project-specific.

## Stack

- Python 3.14, FastAPI 0.141.x, uvloop event loop
- pytest + pytest-asyncio (strict mode) — async tests need `@pytest.mark.asyncio`
- httpx ASGITransport for in-process API tests
- dataclasses for internal state objects (WeightEntry, RewardMilestone, etc.)
- SQLite (`weight_loss.db`) via the stdlib `sqlite3` module
- Web Push via `pywebpush` + `py_vapid` (VAPID keys persisted to `vapid_keys.json`)

## Module map

- `main.py` — FastAPI app factory (`create_app`) + lifespan wiring + `init_app_state`
- `routes.py` — all `/api/*` endpoints, request-body validation, serialization
- `database.py` — SQLite schema, `Database` class (single connection + lock), row → dataclass mapping, `run_db` thread helper
- `rewards.py` — pure milestone logic: `compute_baseline`, `compute_lost`, `milestone_levels`, `next_milestone`
- `notifications.py` — VAPID load/generate/persist, `send_push`, `send_to_all` (pywebpush)
- `scheduler.py` — asyncio background loop, daily due-check, dedupe via `notifications_sent`
- `constants.py` — logger factory (`get_logger`), defaults, DB path, VAPID path, notification messages
- `models.py` — dataclasses: `WeightEntry`, `PushSubscription`, `RewardMilestone`, `AppSettings`
- `static/` — vanilla JS SPA (index.html, app.js, style.css, sw.js, manifest.webmanifest)
- `tests/` — conftest harness + weight/rewards/api/scheduler regression tests

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
