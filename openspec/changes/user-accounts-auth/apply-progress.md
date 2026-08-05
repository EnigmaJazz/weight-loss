# Apply Progress: user-accounts-auth (slice 1 of 3)

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
