# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read `AGENTS.md` first.** It holds the hard coding rules (async request path, `run_db`, type hints, dataclasses in `models.py`, no globals outside `app.state`, no `print`, no bare `except`) and is also the review prompt for the `gga` pre-commit hook, so violations block commits. This file does not repeat those rules.

## Commands

```bash
.venv/bin/python -m pytest -q                                   # full backend suite (asyncio_mode=strict, pythonpath=.)
.venv/bin/python -m pytest tests/test_api.py::test_name -q      # single test
.venv/bin/python -m pytest tests/test_activity_api.py -k streak # by keyword
node --test tests/frontend/*.test.mjs                           # frontend unit tests (use the glob; a bare dir fails on Node 26)
tests/smoke-ui.sh http://127.0.0.1:8129                         # browser smoke via playwright-cli; registers a user + writes entries
```

Run a scratch server for smoke/manual checks, never against the real DB on port 8000:

```bash
setsid -f env WEIGHT_LOSS_DB=/tmp/wl-scratch.db WEIGHT_LOSS_VAPID_KEYS=/tmp/wl-scratch-vapid.json .venv/bin/python -m uvicorn main:app --port 8129
```

Stop it with `pkill -f "uvicorn main:app --port 8129"`. Restart it **after committing**: the asset cache-bust stamp is the git short SHA read once at startup.

Type checking: `pyright` (config in `pyrightconfig.json`, pinned to `.venv`, Python 3.14). CI (`.github/workflows/ci.yml`) runs pytest, node tests, and the browser smoke.

## Architecture

FastAPI backend + vanilla-JS PWA, single process, SQLite.

- **App wiring** — `main.py:create_app()` builds the app; the lifespan calls `init_app_state()` which opens the `Database`, runs schema creation and reconciliation (`reconcile_active_rewards`, `reconcile_all_weekly_awards`), loads/generates VAPID keys, and precomputes `index.html` with `?v=<stamp>` injected into script/style URLs. All shared state lives on `app.state` (`db`, `vapid`, `vapid_public_key`, `index_html`). `/sw.js` is served from the web root so the service worker's scope covers `/`.
- **Request path** — `routes.py` holds every `/api/*` endpoint plus request validation (`_valid_*` helpers) and serialization (`_*_dict` / `_*_view` helpers). Auth is cookie sessions: `require_user` dependency resolves the user; every data table is scoped by `user_id` (legacy single-user rows use `user_id=0`). `tests/test_user_isolation.py` guards cross-user leakage.
- **Storage** — `database.py` is one `Database` class over a single `sqlite3` connection guarded by a lock; schema + migrations live there. Its methods are synchronous; async callers go through `await run_db(db.method, ...)` (`asyncio.to_thread`).
- **Pure domain modules** — gamification and calculations are kept I/O-free so they unit-test without a DB: `rewards.py` (checkpoint rewards), `quests.py` + `xp.py` (daily quests / XP), `achievements.py`, `streaks.py`, `momentum.py`, `weekly.py`, `collectibles.py`, `units.py` (raw kg/lb/st/BMI; rounding is the SPA's job), `auth.py` (scrypt hashing, session/reset tokens). Routes fetch data via the DB, then call these.
- **Side effects** — `notifications.py` (Web Push via pywebpush), `mailer.py` (SMTP password reset), `scheduler.py` (background asyncio loop started in lifespan, dedupes via `notifications_sent`).
- **Config** — `constants.py` loads `.env`, and holds tunables, allowlists (e.g. `ACCENT_COLORS`, `QUEST_POOL`), and env vars: `WEIGHT_LOSS_DB`, `WEIGHT_LOSS_VAPID_KEYS`, `WEIGHT_LOSS_COOKIE_SECURE`, `WEIGHT_LOSS_SMTP_*`, public URL.
- **Frontend** — `static/index.html` (also contains inline SVG symbols such as the island fox), `app.js` (the SPA, tabbed: Journey/World/Me), `auth.js` (login gate), `format.js` (pure formatting helpers tested by `tests/frontend/*.test.mjs`), `sw.js`, `style.css`.

## Testing harness

`tests/conftest.py` builds a per-test app on a `tmp_path` DB with the scheduler disabled and `send_to_all` stubbed. Use the provided fixtures: `client` (no session), `auth_client` (registered + logged in), `onboarded_client` (settings + first weight done). It forces `WEIGHT_LOSS_COOKIE_SECURE` off because httpx talks plain `http://test`.

## Cross-file invariants (tests enforce them)

- **Brand accent lockstep** — `tests/test_palette_lockstep.py` requires the accent to match across `style.css` `--accent`, `index.html` theme-color meta, `manifest.webmanifest`, and `static/icons/make_icons.py`, and forbids stray hex literals for accents. New accents go in `constants.ACCENT_COLORS`.
- **Icons** — `static/icons/make_icons.py` rasterizes the fox `<symbol>` from `index.html`; regenerate the PNGs with it whenever that symbol changes, together with `tests/test_icons.py`.

## Workflow context

- Planning/history: `docs/strategy.md` (product spec), `docs/backlog.md`, `docs/plans/`, `docs/solutions/` (documented past fixes), `openspec/changes/archive/` (prior SDD cycles, with verify/apply notes).
- PRs target `main`. Conventional commits; per-slice diffs aim for ~400 lines.
