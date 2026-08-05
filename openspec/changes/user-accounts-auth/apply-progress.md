# Apply Progress: user-accounts-auth (slices 1–2 of 3)

**Change**: user-accounts-auth
**Branch**: `auth/slice-1` (from `main`; stacked-to-main, PR 1 of 3 — resolved by orchestrator; tasks.md `Chain strategy: pending` superseded by the orchestrator's resolved chain)
**Mode**: Strict TDD (active, resolved from openspec/config.yaml `strict_tdd: true`)
**Status**: 3/4 Phase-1 tasks complete in this slice (1.1, 1.2, 1.4; 1.3 deferred — see Deviations). Phase 2 and Phase 3 not started.
**Test counts**: 93 passing at start → **132 passing at end** (+39 new: 20 `test_auth.py` + 19 `test_auth_api.py`) + 6 node:test (unchanged).

## Slice 1 Scope (orchestrator-assigned)

Auth API, schema, sessions only. Identity tables added; the five existing tables keep their current schemas (no `user_id`), existing endpoints keep their current behavior (not yet auth-gated — that is slice 2). Task 1.3 (transactional rebuild + first-registrant backfill) requires adding `user_id` to the five tables and is therefore NOT part of this slice despite its Phase-1 numbering.

## Completed Tasks

- [x] 1.1 `tests/test_auth.py` (unit) + `auth.py` (new pure module) — scrypt hash/salt/verify (n=2**14, r=8, p=1, dklen=32), `secrets.token_urlsafe(32)` tokens, SHA-256 token hash; parameters centralized in `constants.py`, constant-time comparison via `hmac.compare_digest`.
- [x] 1.2 `models.py` (`User`, `Session` dataclasses), `constants.py` (scrypt + cookie constants), `database.py` — `users`/`sessions` schema, `PRAGMA foreign_keys=ON`, `create_user`, `get_user_by_username`, `create_session` (with opportunistic expired-row sweep), `get_user_by_session` (excludes expired), `delete_session`, `delete_expired_sessions`, `DuplicateUsernameError`, UTC timestamps, FK-cascade verified. `init_schema` converted from `executescript` to per-statement DDL inside the explicit transaction (design's migration guidance applied to the new DDL; all-or-nothing boundary preserved).
- [x] 1.4 `routes.py` — `require_user` dependency (401, never 403), `POST /api/auth/register` (201; 3–32-char lowercased no-whitespace username, password ≥8, 422 invalid / 409 duplicate; establishes session), `POST /api/auth/login` (scrypt verify offloaded via `asyncio.to_thread`, 401 on bad creds), `GET /api/auth/me` (200 user / 401), `POST /api/auth/logout` (requires session per spec; deletes hashed row + clears cookie). Cookie: HttpOnly, SameSite=Lax, Path=/, Max-Age 30 days, Expires matched to DB row, Secure off by default / on via `WEIGHT_LOSS_COOKIE_SECURE=true`. `main.py` needed no change (auth routes ride the already-mounted router; startup reconciliation is slice 2).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | tests/test_auth.py (11 unit tests: round-trip, wrong password, determinism, salt uniqueness/format, dklen length, token urlsafe/uniqueness/hash) | Unit | N/A (new file) | ✅ 1 error at collection (`ModuleNotFoundError: No module named 'auth'`) | ✅ 20/20 on the file (with 1.2 tests) | ✅ ≥2 cases per behavior: verify True/False, salt uniqueness (64), token uniqueness (64), hash determinism, digest ≠ raw token | ✅ params centralized in `constants.py` (`SCRIPT_*`), `hmac.compare_digest` for verify; suite re-run green |
| 1.2 | tests/test_auth.py (9 DB tests: user round-trip, exact-match lookup, duplicate raises, session round-trip, expired exclusion, delete, sweep, `delete_expired_sessions` cutoff, FK cascade, 30-day constant) | Unit (SQLite) | suite (93) | ✅ collection error (same RED as 1.1) | ✅ 20/20 on the file | ✅ expired vs live session; sweep vs explicit delete; case-variant lookup; duplicate via second `create_user` | ✅ `executescript` → per-statement DDL inside `_tx()`; full suite 113 passed (no legacy regression) |
| 1.4 | tests/test_auth_api.py (19 tests: register lowercases + session, 422 ×5, 409 case-insensitive, cookie attributes + Secure config, hash-only persistence, login/me round-trip, 401 ×3, logout revokes/requires/deletes, expired rejected, per-user distinct sessions) | Integration (httpx ASGITransport + conftest client) | suite (113) | ✅ 18 failed (404 — routes absent), 1 passed incidentally | ✅ 39/39 on `test_auth.py` + `test_auth_api.py` | ✅ spec scenarios all mapped; cookie attribute matrix; expired-via-DB plant; duplicate case-insensitive | ✅ validation centralized in pydantic models (`extra="forbid"` matches project pattern); scrypt offloaded via `asyncio.to_thread`; cookie helpers extracted |

RED correction note (tests only, not implementation): two API tests initially failed on setup, not behavior — (a) `test_login_wrong_password_returns_401` asserted "no session" while the register session cookie still lived in the httpx jar; fixed by logging out first, (b) `test_expired_session_is_rejected` hit `httpx.CookieConflict` because `cookies.set()` created a second `session` entry beside the register cookie; fixed by planting the user + expired session directly via the DB and never registering through the API in that test.

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_auth.py tests/test_auth_api.py` → RED: 1 collection error + 18 failed / 1 passed; GREEN: **39 passed**. `.venv/bin/python -m pytest -q` → **132 passed in 1.24s**; `node --test tests/frontend/weight-label.test.mjs` → **6 passed / 0 failed**. `.venv/bin/pyright auth.py routes.py database.py models.py constants.py tests/test_auth.py tests/test_auth_api.py` → **0 errors, 0 warnings** |
| Runtime harness command/scenario and exact result | Live uvicorn boot (tmp DB/VAPID, port 8799, real HTTP): register `LiveUser` → **201** with `username: "liveuser"` and cookie attrs `[session, expires, HttpOnly, Max-Age, Path, SameSite]` (no Secure — correct on local HTTP); `GET /api/auth/me` → **200**; duplicate `liveuser` register → **409**; username `"ab"` → **422**; logout → **200**; me after logout → **401** (revoked); login → **200**; wrong-password login → **401**. In-process ASGITransport suite covers the same round-trip plus 409/422/401/cookie-attribute matrix. |
| Rollback boundary | Two commits: `feat(auth): add users, sessions, and auth API` (production + tests) and `docs(openspec): record user-accounts-auth slice-1 apply progress` (tasks.md + apply-progress.md). Reverting the code commit removes `auth.py`, the identity schema/methods and DDL refactor in `database.py`, the `User`/`Session` dataclasses in `models.py`, the auth constants in `constants.py`, the auth routes in `routes.py`, and `tests/test_auth*.py` — no existing-table schema changes and no existing-endpoint behavior changes are included, so unrelated work is untouched. `git revert` verified clean (see Issues). |

## Commits

| Hash | Message |
|------|---------|
| (see git log) | `feat(auth): add users, sessions, and auth API` — production + tests |
| (see git log) | `docs(openspec): record user-accounts-auth slice-1 apply progress` — tasks.md checkboxes + apply-progress.md |

## Deviations from Design

1. **Task 1.3 not implemented in this slice** (scope, not deviation from design): the orchestrator's slice-1 scope explicitly defers adding `user_id` to the five existing tables to slice 2, and task 1.3 (transactional rebuild + first-registrant backfill) requires exactly that. It stays unchecked in tasks.md; the design's migration work lands with the rebuild slice.
2. **`list_users()` omitted** (design interface, scheduler dependency): the design lists `list_users() -> list[User]` among DB identity methods, but the orchestrator's slice-1 scope enumerates only the six identity methods (create_user, get_user_by_username, create_session, get_user_by_session, delete_session, delete_expired_sessions). `list_users` is consumed by the per-user scheduler loop (slice 2) and will be added with it.
3. **`main.py` untouched**: task 1.4 text says "wire async routes in routes.py and main.py", but the router is already mounted in `create_app` (`app.include_router(router)`), so the auth routes required no main.py wiring. The only main.py change the design anticipates is per-user startup reconciliation — slice 2.
4. **Schema DDL mechanism**: design's migration note warns against `executescript` disrupting explicit transaction boundaries. Applied by converting `init_schema` to per-statement `conn.execute` inside the existing `_tx()` (all statements, including the pre-existing `DROP`/`DELETE`, now run in one all-or-nothing transaction). Behavior-equivalent for legacy tables — full suite green before and after.
5. **Salt storage format**: exploration sketched `"scrypt$16384$8$1$<salt_b64>$<hash_b64>"` as a possible encoding; the design's interface (`generate_password_salt() -> str`, `hash_password(password, salt) -> str`) was implemented as separate hex-encoded salt and hash columns (design's `users(id, username, password_hash, salt, created_at)` schema), matching the design file over the exploration sketch.

## Issues Found

1. **PR-1 size**: authored changed lines for this slice ≈ 950 (397+/44− tracked + ~510 new in `auth.py`, `tests/test_auth.py`, `tests/test_auth_api.py`). The forecast split the 900–1,300-line change into 3 PRs with the budget guard at 400; the auth foundation is inherently the largest slice (tests belong with code per work-unit-commits). If the maintainer wants PR 1 under 400 changed lines, the test matrix would have to shrink — not recommended. Flagged for the orchestrator's PR decision; the stacked-to-main chain keeps each slice's diff reviewable in isolation.
2. **httpx cookie-jar gotcha** (test-only, now documented in the tests): `client.cookies.set()` after a register creates a *second* `session` entry (host-only vs domain cookie) → `httpx.CookieConflict` and the server reads the original valid token. Tests that need a specific cookie state plant users/sessions directly via the DB instead.
3. **`datetime('now')` in SQLite is UTC** while `_local_now()` (existing helper) is host-local — a pre-existing inconsistency. Identity rows and session expiry use a new `_utc_now()` consistently, so auth is internally coherent; the legacy tables' mixed timestamps are untouched (out of slice scope).
4. **`tasks.md` chain-strategy label**: still says `Chain strategy: pending`; the orchestrator resolved `stacked-to-main` for this change. Left as-is (orchestrator-owned field), noted here for the record.

## Discoveries Worth Persisting

- `init_schema` no longer uses `executescript`; new schema statements are per-statement DDL inside `_tx()`. Any future schema change should append to `SCHEMA_STATEMENTS` — never reintroduce `executescript`, which implicitly COMMITs the explicit BEGIN.
- Session cookie expiry is computed once in the route and shared by the DB `expires_at` row and the cookie `Max-Age`/`Expires` — the two can never drift.
- `require_user` returns 401 for missing/unknown/expired uniformly (spec requirement), and `create_user` raises `DuplicateUsernameError` (wrapping `sqlite3.IntegrityError`) so the route layer never touches raw sqlite exceptions.

## Status

3/4 Phase-1 tasks complete (1.1, 1.2, 1.4); 1.3 deferred to the rebuild slice; Phase 2 and Phase 3 untouched. **132/132 pytest + 6/6 node tests green**, pyright clean. Branch `auth/slice-1` committed and ready for push/PR (orchestrator-owned). next_recommended: apply slice 2 (scoping + scheduler).

---

# Slice 2 of 3 (PR 2): per-user ownership + per-user scheduler + migration/backfill

**Change**: user-accounts-auth
**Branch**: `auth/slice-2` (from `main`; stacked-to-main — PR 1 `auth/slice-1` merged via PR #7)
**Mode**: Strict TDD (active, openspec/config.yaml `strict_tdd: true`)
**Status**: All slice-2 tasks complete (1.3, 2.1, 2.2, 2.3, 2.4). Phase 3 (SPA) untouched.
**Test counts**: 132 passing at start → **169 passing at end** (+37 new: 8 `test_auth_migration.py` + 28 `test_user_isolation.py` + 3 per-user scheduler tests in `test_scheduler.py`) + 6 node:test (unchanged).

## Completed Tasks

- [x] 1.3 **Migration + first-registrant backfill** — `database.py`: `SENTINEL_USER_ID = 0`; target schema for all five tables gains `user_id` (weight_entries `UNIQUE(user_id,date)`, push_subscriptions `endpoint` stays global UNIQUE, active_rewards PK `(user_id,checkpoint_percent)`, notifications_sent PK `(user_id,date,type)`, settings PK `(user_id,key)`). `_migrate_legacy_schema` runs after SCHEMA_STATEMENTS inside the same `_tx()`: detects legacy via `PRAGMA table_info(weight_entries)` lacking `user_id`, rebuilds the four constraint-changing tables (`_new` → copy rows with user_id=0 → drop → rename), `ALTER TABLE ADD COLUMN user_id ... DEFAULT 0` for push_subscriptions. All-or-nothing, idempotent. `create_user` claims every `user_id = 0` row in all five tables in the same transaction when the users table was empty (count == 1 guard); `DuplicateUsernameError` path rolls back before any claim.
- [x] 2.1 **Scoped DB layer** — leading `user_id` first param on `list_entries`, `get_entry_by_date`, `upsert_entry` (ON CONFLICT(user_id,date)), `delete_entry` (`WHERE id=? AND user_id=?`), `list_active_rewards`, `get_settings`/`_settings_from_conn(user_id, conn)`, `update_settings` (ON CONFLICT(user_id,key)), `add_subscription` (ON CONFLICT(endpoint) reassigns owner), `list_subscriptions`, `remove_subscription` (`WHERE endpoint AND user_id`), `is_notification_sent`, `mark_notification_sent`; `_reconcile_active_rewards(conn, user_id)`; new `list_users()`. `reconcile_active_rewards()` (startup) loops `list_users()`.
- [x] 2.2 **Scoped routes + startup reconcile** — every protected endpoint takes `Depends(require_user)` and passes `user.id`: GET/POST/DELETE `/api/weight`, GET `/api/rewards`, GET/PUT `/api/settings`, POST `/api/push/subscribe|unsubscribe|test`, POST `/api/notify/{type}`. Cross-user delete → 404 (ownership in SQL). `GET /api/push/vapid-public-key` stays public (not user data; exploration decision — locked by test). Startup reconcile is per-user inside `reconcile_active_rewards()`; `main.py` needed no change (already calls it).
- [x] 2.3 **Per-user scheduler** — `run_due_checks` loops `db.list_users()`; per user: scoped settings → per-type due check → scoped dedupe → scoped subscriptions → send → scoped `mark_notification_sent`; zero-subscriber no-dedupe preserved per (user, type); aggregated count. `_due_today`/`_due_this_week` pure and unchanged.
- [x] 2.4 **Test adaptation + harness** — `conftest.py`: `client` stays bare (auth-flow tests), new `auth_client` (registers `tester`), `pair` fixture (alice+bob on one app), `register_user`, `auth_user_id`, `make_user`. `test_api.py`/`test_weight.py` switched to `auth_client`; direct-DB calls pass `auth_user_id(app)`; `test_scheduler.py` direct-DB tests create a user and pass `user.id`; `test_weight.py::test_startup_reconciles_active_rewards` now seeds a user and exercises the per-user startup reconcile.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.3 | tests/test_auth_migration.py (8: legacy boot preserves rows, idempotent reboot, fresh-DB columns, direct DB first-user claim, later-user no-claim, API first-registrant claim, API second-registrant empty) | Integration (seeded SQLite boot + ASGI) | suite (132) | ✅ 5 failed / 1 passed (no migration, no backfill) | ✅ 8/8 on file | ✅ first vs later registrant; legacy boot vs fresh boot vs direct-DB sentinel seed | ✅ rebuild DDL centralized in `LEGACY_TABLE_REBUILDS`; sentinel constant extracted |
| 2.1 | tests/test_user_isolation.py (28 total: 11 unauthenticated-401 incl. no-mutation checks, 7 API cross-user, 10 direct-DB scoping) | Unit (SQLite) + Integration (ASGITransport) | suite (132) | ✅ 27 failed / 1 passed (unscoped DB methods + unauthenticated routes) | ✅ 28/28 on file (after routes, task 2.2) | ✅ two clients same app; same date two users; cross-user delete; same checkpoint two users; every scoped method direct | ✅ ownership-in-SQL (`WHERE user_id`); `auth_user_id`/`make_user` helpers extracted to conftest |
| 2.2 | tests/test_user_isolation.py (API half) + test_api.py (33 adapted to `auth_client`) | Integration | suite (132) | ✅ 401 contract failed (no auth on routes) | ✅ full suite green | ✅ 401-no-mutation for POST weight/settings/subscribe; vapid key stays public; delete 404 | ✅ `require_user` reused from slice 1; serializers untouched |
| 2.3 | tests/test_scheduler.py (+3 per-user: independent dedupe, disabled-schedule skip, zero-subscriber no-dedupe) | Integration (fake clock + stub sender) | suite (132) | ✅ 3 failed (global loop, no user scoping) | ✅ 12/12 on file | ✅ per-user dedupe both keys; one disabled one enabled; zero-subscriber user vs subscriber user | ✅ tick time computed once (`tick_time`) |
| 2.4 | tests/test_api.py, test_weight.py, test_scheduler.py (adaptation) | Unit/Integration | suite (169) | N/A (mechanical adaptation) | ✅ 169/169 full suite | ✅ startup reconcile per-user (seeded stale row revoked); created_at via auth user | ✅ no duplicated fixtures; direct SQL queries scoped with user_id |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_auth_migration.py tests/test_user_isolation.py tests/test_scheduler.py -q` → RED: 5+27+3 failed; GREEN: **55 passed**. `.venv/bin/python -m pytest -q` → **169 passed in 3.55s**. `node --test tests/frontend/weight-label.test.mjs` → **6 passed / 0 failed**. `.venv/bin/pyright database.py routes.py scheduler.py main.py models.py constants.py tests/*.py` → **0 errors, 0 warnings** |
| Runtime harness command/scenario and exact result | Live uvicorn boot (tmp seeded-legacy DB + tmp VAPID, port 8802, real HTTP): anon GET/POST /api/weight → **401/401**; register alice → **201** (id=1); alice settings → **target=70.0, height=175.0** (backfill claimed legacy rows); alice weight → **legacy 2026-08-01 entry visible**; alice POST weight → **201**; register bob → **201**; bob settings → **target=None** (empty); bob weight → **[]** (isolation); bob DELETE alice's entry → **404**; bob still sees **0 entries**; login alice → **alice**; alice sees both entries (preserved). 13/13 checks passed. |
| Rollback boundary | Commit `2764184` `feat(auth): scope all data and scheduler per user` (production + tests) + docs commit. Reverting the code commit removes: the five-table `user_id` schema/rebuild migration and backfill in `database.py`, the scoped methods, `list_users`, `require_user` on existing routes, the per-user scheduler loop, and the new/adapted tests — `auth.py`, identity tables, and auth routes from slice 1 are untouched (this slice does not modify them). `git revert 2764184 --no-commit` verified clean (0 conflicts) before the docs commit. |

## Commits

| Hash | Message |
|------|---------|
| 2764184 | `feat(auth): scope all data and scheduler per user` — production + tests (gga pre-commit review passed) |
| (docs commit) | `docs(openspec): record user-accounts-auth slice-2 apply progress` — tasks.md checkboxes + apply-progress.md |

## Deviations from Design

1. **`client` fixture not auto-authed** (conftest choice, not a design deviation): exploration suggested making `client` auto-auth so existing tests keep their bodies, but test_auth_api.py (slice 1) asserts user counts, session counts, and no-session 401s that are incompatible with an auto-authed client (e.g. `test_register_rejects_short_username` counts users == 0). Kept `client` bare and added `auth_client` (+ `pair`); adapted test_api.py/test_weight.py to `auth_client`. Same net effect, no auth-flow test surgery.
2. **`main.py` untouched** (task 2.2 text says "startup reconciliation in main.py"): the per-user reconcile lives in `database.reconcile_active_rewards()` which already loops `list_users()`; `init_app_state` already calls it, so no main.py edit was needed — same behavior, one less file in the diff.
3. **`push_subscriptions.user_id` via ALTER TABLE** (design says "Add push_subscriptions.user_id NOT NULL DEFAULT 0"): implemented as `ALTER TABLE ... ADD COLUMN` for legacy DBs (endpoint stays globally UNIQUE), fresh DBs create the column in the CREATE statement. Matches the design's two-path migration.
4. **Backfill guard via users count** (design: "Guarded by emptiness of users"): implemented as `COUNT(*) == 1` inside the same transaction as the INSERT — atomic with the user creation, can never re-run (later users make the count > 1).

## Issues Found

1. **PR-2 size**: authored changed lines ≈ 1742 (1425+/317−, incl. tests — tests belong with code per work-unit-commits). Slice 2 is the largest of the three. The stacked-to-main chain keeps each slice's diff reviewable in isolation; flagged for the orchestrator's PR decision.
2. **AFT LSP noise**: `Import "auth" could not be resolved [Pyright]` in routes.py/test_auth*.py — AFT's bundled LSP does not resolve the project's root-level modules; project pyright (pyrightconfig.json) reports **0 errors**. Pre-existing, not introduced by this slice.
3. **Test arithmetic bug caught by RED→GREEN**: `test_same_checkpoint_can_exist_for_two_users` initially asserted a wrong 25% threshold (92.5 instead of 95.0); the implementation's 95.0 was correct per rewards.py (`start - 0.25*(start-target)`). Fixed the test, not the code.
4. **Rollback verify note**: `git revert 2764184` on a clean tree reverts cleanly (verified via `--no-commit` + inspect + `reset --hard` before the docs commit; no conflicts with slice-1 files since this slice touches no identity/auth code).

## Discoveries Worth Persisting

- The migration is a **two-path** design: fresh DBs get `user_id` columns from SCHEMA_STATEMENTS directly; legacy DBs are detected by `PRAGMA table_info(weight_entries)` missing `user_id` and rebuilt inside the same explicit `_tx()` — all-or-nothing, idempotent, no `executescript`.
- `DELETE ... WHERE id = ? AND user_id = ?` is the ownership primitive for cross-user 404s: no separate SELECT-then-DELETE race window, no info leak.
- The scheduler's zero-subscriber no-dedupe rule is now per (user, type): each user's dedupe key is independent, and a disabled schedule only skips its owner.
- `push_subscriptions.endpoint` remains globally UNIQUE with `ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id` — one browser = one subscription; a re-subscribe reassigns ownership.

## Status

All Phase-1/Phase-2 tasks complete (1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4). **169/169 pytest + 6/6 node tests green**, pyright clean. Branch `auth/slice-2` committed and ready for push/PR (orchestrator-owned). next_recommended: apply slice 3 (SPA + rollout polish).

## Slice 2 Amendment (maintainer decision): drop the legacy backfill

**Decision**: the legacy pre-auth rows (target 70 / height 175, etc.) were smoke-test artifacts, not real per-user config. Per maintainer, the first-registrant backfill was removed: **legacy rows are discarded during migration; every account (including the first) starts empty** and sets its own target/height/schedules.

**Changes**: `LEGACY_TABLE_REBUILDS` copy steps removed (tables rebuild empty); `push_subscriptions` legacy rows deleted post-ALTER; `create_user` claim logic removed; `SENTINEL_USER_ID` removed; migration tests rewritten (`test_auth_migration.py` asserts discard + fresh-start); weight-tracking delta spec's backfill requirement replaced with "Legacy Pre-Auth Data Is Discarded on Migration".

**Evidence**: `tests/test_auth_migration.py` + `test_user_isolation.py` → 33 passed; full suite → 168 passed; pyright 0 errors.
