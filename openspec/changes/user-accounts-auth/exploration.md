# Exploration: User accounts + authentication

Change: `user-accounts-auth`
Phase: sdd-explore
Date: 2026-08-05

## Current State

Single-user, no-auth app. **All application state is global** — no table has a
user owner. Verified live DB (`weight_loss.db`, 45 KB): 0 `weight_entries`,
0 `push_subscriptions`, 0 `active_rewards`, 3 `notifications_sent` (today's
dedupe), 6 `settings` rows (`target_weight=70.0`, `height_cm=175.0`,
`tip_time=09:00`, `reminder_time=20:00`, `exercise_time=17:00`,
`reminder_weekday=1`). The settings rows are real user config (target 70 kg /
height 175 cm) — the migration must not silently drop them.

### Data model (database.py SCHEMA, lines 16-53)

| Table | Columns / PK | Per-user? |
|---|---|---|
| `weight_entries` | `id` PK, `date` **UNIQUE**, `weight_kg`, `created_at` | YES — add `user_id`; UNIQUE must become `(user_id, date)` so two users can log the same date |
| `push_subscriptions` | `id` PK, `endpoint` UNIQUE, `p256dh`, `auth`, `created_at` | YES — add `user_id`; `endpoint` stays globally UNIQUE (one browser = one subscription; ON CONFLICT reassigns owner) |
| `active_rewards` | `checkpoint_percent` **PK**, `threshold_kg`, `earned_at` | YES — PK becomes `(user_id, checkpoint_percent)` |
| `notifications_sent` | `date`, `type`, `sent_at`, PK `(date, type)` | YES — PK becomes `(user_id, date, type)`; otherwise user A's tip send suppresses user B's |
| `settings` | `key` **PK**, `value` | YES — PK becomes `(user_id, key)`; **all 7 keys are user-level** (target_weight, height_cm, tip/reminder/exercise times, reminder_weekday, start_weight_override) |

**App-level config that stays global** (none in SQL): VAPID keys (file
`vapid_keys.json`), `DB_PATH`/`VAPID_KEYS_PATH` (env, constants.py:17-20),
`SCHEDULER_INTERVAL_SECONDS` (constants.py:64), notification message catalog
(constants.py:46-59). The whole `settings` table moves per-user.

No `users` table, no sessions, no schema versioning. Migration today is
ad-hoc statements embedded in `SCHEMA` (`DROP TABLE IF EXISTS reward_events`,
`DELETE FROM settings WHERE key='milestone_step_kg'` — database.py:17, 52),
re-run on every boot via `executescript` (database.py:85-87).

### Request path (routes.py)

`get_db` dependency (routes.py:34-35) returns `request.app.state.db`. All 12
endpoints take `Depends(get_db)`:

| Endpoint | Line | Auth treatment |
|---|---|---|
| `GET /api/weight` | 195 | protected, user-scoped |
| `POST /api/weight` | 206 | protected, user-scoped |
| `DELETE /api/weight/{entry_id}` | 219 | protected + **ownership check** (`WHERE id=? AND user_id=?`) |
| `GET /api/rewards` | 232 | protected, user-scoped |
| `GET /api/settings` | 277 | protected, user-scoped |
| `PUT /api/settings` | 283 | protected, user-scoped |
| `GET /api/push/vapid-public-key` | 297 | can stay public (non-sensitive; used only after login) — decision for proposal |
| `POST /api/push/subscribe` | 302 | protected, user-scoped |
| `POST /api/push/unsubscribe` | 313 | protected, user-scoped |
| `POST /api/push/test` | 323 | protected, user-scoped |
| `POST /api/notify/{notif_type}` | 334 | protected, user-scoped |

New endpoints: `POST /api/auth/register`, `POST /api/auth/login`,
`POST /api/auth/logout`, `GET /api/auth/me`.

`init_app_state` (main.py:27-40) opens DB → `init_schema()` →
`reconcile_active_rewards()` → VAPID. The startup reconciliation
(main.py:34) must become per-user. The scheduler is created in lifespan
(main.py:55) with `app.state` only — no request context, so it must
enumerate users itself.

### Scheduler (scheduler.py)

`run_due_checks(app_state, now)` (scheduler.py:39-78): one global
`get_settings` → for each `NOTIFICATION_TYPES` check `_due_this_week` →
global dedupe `is_notification_sent(date, type)` → global
`list_subscriptions` → `send_to_all` → `mark_notification_sent`. The
zero-subscriber no-dedupe rule (scheduler.py:52-62) must survive per-user.
`_due_today`/`_due_this_week` (scheduler.py:22-36) are pure and unchanged.
All schedule times are host-local wall-clock `"HH:MM"` strings — per-user
schedules share the host timezone (existing limitation, unchanged).

### SPA (static/)

Vanilla JS, no build step. `init()` (app.js:440-459) calls `loadData()` →
`fetchJson` for `/api/weight`, `/api/rewards`, `/api/settings` (app.js:42-53).
No credentials handling today (same-origin fetch sends cookies by default —
no change needed there once the session cookie is set). Push registration
(app.js:373-399) happens at user action, post-login. `sw.js` displays push
payloads only, no user data — **unchanged**.

## Affected Areas

- `database.py` — SCHEMA (2 new tables + 4 table rebuilds), every query
  method gains a `user_id` param (lines 91-288), new user/session methods,
  startup migration, `_reconcile_active_rewards` per-user (156-186),
  row mappers (296-312).
- `routes.py` — new `require_user` dependency next to `get_db` (34-35);
  all 11 protected endpoints take `user_id`; 4 new `/api/auth/*` routes;
  `delete_weight` ownership (219-226); serializers unchanged.
- `scheduler.py` — `run_due_checks` becomes per-user loop over
  `db.list_users()` (39-78); `scheduler_loop` unchanged (81-89).
- `main.py` — `init_app_state` runs schema migration + per-user reward
  reconcile (27-40); lifespan unchanged.
- `models.py` — new `User` and `Session` dataclasses; existing dataclasses
  (`WeightEntry`, `PushSubscription`, `AppSettings`, `RewardState`) need no
  user_id field — queries scope by user, dataclasses stay user-agnostic.
- `rewards.py` — **no change** (pure; receives already user-scoped entries).
- `notifications.py` — **no change** (`send_to_all` takes a subscription list).
- `units.py`, `constants.py` — constants only: session TTL, scrypt params,
  cookie name (new `AUTH_*` constants).
- `static/index.html`, `static/app.js`, `static/style.css` — login/register
  screen, app gate on `/api/auth/me`, logout button; `sw.js` unchanged.
- `tests/` — conftest auth fixture + per-user isolation tests (below).

## Approaches

### 1. Session cookie + server-side SQLite sessions (recommended)

Login sets an HttpOnly cookie holding a random token
(`secrets.token_urlsafe(32)`); the DB stores only `SHA-256(token)` in a
`sessions` table (`token_hash` PK, `user_id`, `created_at`, `expires_at`).
`require_user` dependency reads the cookie, hashes, looks up the session,
returns the user id or 401. Password hashing via **stdlib `hashlib.scrypt`**
(n=2**14, r=8, p=1, 16-byte salt, 32-byte key; `hmac.compare_digest`
verify). Zero new dependencies.

- Pros: zero new deps (fits the minimal-deps project); logout is a DELETE +
  cookie clear (real revocation); per-user session expiry; token at rest is
  hashed (DB leak ≠ session hijack); plain FastAPI dependency — no
  middleware; CSRF story adequate for a same-origin SPA (below).
- Cons: server-side session rows to manage (cleanup of expired rows); cookie
  semantics (SameSite/Secure) must be set correctly; no cross-device
  statelessness (irrelevant here).
- Effort: Medium.

### 2. JWT bearer token (PyJWT dep or hand-rolled stdlib HMAC)

Client stores a signed token, sends `Authorization: Bearer`.

- Pros: stateless (no session table); client-side expiry; PyJWT is tiny and
  pure-Python.
- Cons: adds a dependency (project prefers minimal); **logout cannot revoke**
  a token without a denylist (which reintroduces server state); hand-rolling
  HMAC-JWT with stdlib is error-prone (padding, alg confusion); token at
  rest in localStorage is XSS-stealable unless cookie-held (back to square
  one); the SPA must manage token storage/refresh. No benefit for a
  few-user, same-origin SPA.
- Effort: Medium-High.

### 3. HTTP Basic auth

`Authorization: Basic base64(user:pass)` via FastAPI's `HTTPBasic`.

- Pros: zero deps, trivially simple; browser-native dialog.
- Cons: password sent on every request (acceptable only over TLS, and
  plaintext-equivalent at the client); **no server-side logout**; browser
  prompt UX is hostile to the SPA's custom forms; credential replay on
  XSS (same as cookie+localStorage, without the HttpOnly protection).
- Effort: Low (implementation) but product-UX wrong.

### 4. Password hashing sub-options

- **`hashlib.scrypt` (stdlib)** — memory-hard, GPU-resistant, one call.
  Recommended: n=2**14, r=8, p=1, dklen=32. Works on CPython 3.14 with
  stock OpenSSL.
- `hashlib.pbkdf2_hmac("sha256", ...)` (stdlib) — ~600k iterations
  (OWASP); CPU-only, weaker against GPU/ASIC. Fine fallback if scrypt is
  unavailable.
- `argon2-cffi` dep — current gold standard, but adds a native dependency;
  overkill for a few-user app when scrypt is stdlib.
- `passlib` — **avoid**: unmaintained (CVE-2023-49083), wraps the above.

## Recommendation

**Approach 1**: HttpOnly session cookie + server-side SQLite `sessions`
table + stdlib `hashlib.scrypt`. It is the only option with real logout and
revocation, adds zero dependencies, and slots into the existing architecture
exactly: `Session`/`User` dataclasses in `models.py`, session queries
through `Database` + `run_db` (async path preserved), and a
`require_user` dependency composed beside `get_db`.

Cookie: `name="session"`, `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure`
behind TLS only (configurable via env for local HTTP dev), TTL 30 days
(expiry enforced on lookup; expired rows swept on login/lookup). CSRF:
`SameSite=Lax` blocks cross-site cookie sending on POST in modern browsers,
and every mutating endpoint requires `application/json` bodies with pydantic
`extra="forbid"` (cross-site forms cannot send JSON without a CORS preflight
the server never allows) — sufficient for this threat model; note in the
design that a stricter deployment would add a CSRF token.

Schema for the two new tables:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,   -- "scrypt$16384$8$1$<salt_b64>$<hash_b64>"
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,   -- SHA-256 hex of the cookie token
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
```

Username policy (proposal detail): case-insensitive uniqueness (store
lowercased), 3-32 chars, no whitespace; password min length 8.

## Per-User Blast Radius

Every Database method signature gains a leading `user_id` (or a scoped
variant), and every protected route resolves `user_id` from the session:

- `list_entries(user_id)`, `get_entry_by_date(user_id, date)`,
  `upsert_entry(user_id, date, weight_kg)` (adds `user_id` to the INSERT
  and the reconcile), `delete_entry(user_id, entry_id)`.
- `_reconcile_active_rewards` scoped: `WHERE user_id = ?` on the entries
  read and the `active_rewards` read/write; `reconcile_active_rewards()`
  loops users at startup; `update_settings(user_id, updates)`.
- `add_subscription(user_id, ...)` (ON CONFLICT also sets owner),
  `list_subscriptions(user_id)`, `remove_subscription(user_id, endpoint)`.
- `is_notification_sent(user_id, date, type)`,
  `mark_notification_sent(user_id, date, type, sent_at)`.
- New: `create_user`, `get_user_by_username`, `verify_password` (or the
  hashing lives in a new `auth.py` pure module — cleaner: hashing helpers
  are pure, like `rewards.py`), `create_session`, `get_session`,
  `delete_session`, `list_users`.
- Routes: every existing endpoint passes `user_id` through;
  `DELETE /api/weight/{id}` uses `DELETE ... WHERE id=? AND user_id=?`
  (404 on cross-user id — no information leak).
- Scheduler: `run_due_checks` enumerates `db.list_users()`; per user:
  settings → per-type due check → per-user dedupe → per-user subscriptions →
  send → mark. The zero-subscriber no-dedupe rule applies per (user, type).
  Return aggregated count.

## Migration (SQLite, existing single-user DB)

Constraint changes (UNIQUE/PK) cannot be done via `ALTER TABLE` in SQLite —
the four tables must be rebuilt (create new → `INSERT ... SELECT` → drop →
rename, inside one transaction; project uses `isolation_level=None` +
explicit BEGIN, database.py:66, 74-83). `push_subscriptions` only needs
`ADD COLUMN user_id` (endpoint stays UNIQUE). Idempotent detection:
`PRAGMA table_info(weight_entries)` lacks `user_id`, or no `users` table.

The production DB has **no weight entries and no subscriptions** — the only
real data is 6 `settings` rows + 3 dedupe rows. Two viable paths:

1. **First-registrant claims legacy data (recommended)** — migration adds
   `user_id INTEGER NOT NULL DEFAULT 0` (0 = unowned sentinel, not a real
   FK row) and rebuilds the four tables. `POST /api/auth/register` runs a
   one-shot backfill when it creates the **first** user (users table was
   empty): `UPDATE <table> SET user_id = :uid WHERE user_id = 0` for all
   five tables. The original single user keeps their config by registering
   first — which is exactly what will happen. Guarded by emptiness of
   `users`, so it can never double-run.
2. **Fresh start** — since there are zero weight entries, simply create
   `users` and leave legacy rows orphaned/cleared. Loses target 70 kg /
   height 175 cm (trivial to re-enter) — acceptable only if the operator
   confirms the settings don't matter.

Recommend 1; it is ~25 lines, preserves real config, and matches the
self-signup product decision (no admin ceremony, no claim flow needed).

## SPA Change

- New auth section in `index.html`: username/password form with
  Login/Register modes (toggle), and a logout button in the header once
  authenticated.
- `init()` gate (app.js:440): first call `GET /api/auth/me`
  (`fetch` sends same-origin cookies by default — no credentials option
  change needed). 401 → show login, hide the app sections; 200 → loadData()
  as today. On login/register success → `loadData()`; on 401 from any
  `loadData` call → return to login (session expiry).
- Push subscribe/unsubscribe/test buttons already live behind user action —
  they work unchanged once the session cookie exists.
- `sw.js` untouched. No per-user UI beyond a "logged in as {username}"
  indicator.

## Test Impact

93 tests collected. Auth becomes mandatory for every API test:

- `tests/conftest.py` — add a `register+login` helper and make the `client`
  fixture auto-auth a fresh test user (per-test isolation: register a unique
  username, login via `POST /api/auth/login`, keep the cookie in the
  client). Existing tests then keep their bodies and pass unchanged —
  only the fixture setup changes. Direct-DB tests (test_scheduler,
  test_weight) need a `make_user(db, username)` helper returning a user id
  to pass to the now-scoped methods.
- `tests/test_api.py` (33 tests) — all covered by the authed client
  fixture; `test_push_subscribe_unsubscribe` uses `app.state.db`
  directly (lines 166-178) → must pass the user id.
- `tests/test_scheduler.py` — direct calls to `add_subscription`,
  `update_settings`, `is_notification_sent`, `mark_notification_sent`
  (lines 28-30, 66-68, 78-84, 137, 163, 193-194, 223, 294-295) gain a
  user id; `run_due_checks` per-user.
- `tests/test_weight.py` — `test_startup_reconciles_active_rewards`
  (lines 90-111) seeds a DB directly then boots the app: must create a
  user and exercise the migration/backfill path.
- `tests/test_notifications.py`, `tests/test_rewards.py`, `tests/test_units.py`
  — pure, unaffected.
- New tests (strict TDD): register/login/logout/me round-trip; duplicate
  username 409/422; wrong password 401; protected endpoints 401 without
  cookie; **per-user isolation** (A cannot read/update/delete B's entries,
  settings, subscriptions, rewards, dedupe); delete-cross-user → 404;
  scrypt hash round-trip + reject on wrong password; migration backfill
  assigns legacy settings to the first registrant; scheduler: user A's send
  does not consume user B's dedupe, and per-user disabled schedules.
- Harness note: password hashing with scrypt n=2**14 is ~50-100 ms — fine
  for tests; keep params in one `auth.py` constant so tests could lower n
  if the suite slows.

## Risks

- **CRITICAL (ownership bugs)**: a single unscoped query or an upsert that
  drops `user_id` silently leaks or mixes data between users. Mitigation:
  every DB method takes `user_id` as a required first parameter (no
  overloads without it), plus dedicated per-user-isolation regression tests
  (the strict-TDD spec must enumerate them).
- **CRITICAL (UNIQUE constraints)**: `weight_entries.date` UNIQUE and
  `settings.key` PK cannot survive multi-user without the rebuild —
  forgetting either breaks same-date logging or settings isolation. The
  migration must be a tested path (startup on a seeded legacy DB).
- **WARNING (migration data)**: legacy `settings` (target 70 / height 175)
  are real config; the first-registrant backfill must be one-shot and
  atomic. If the operator registers a throwaway account first, the config
  lands on it — document in the proposal (or offer Approach 2 if the user
  says the DB is disposable).
- **WARNING (cookie security)**: session cookie must be `HttpOnly` +
  `SameSite=Lax`; `Secure` must be configurable (local dev is HTTP).
  Forgetting `HttpOnly` exposes sessions to the SPA's XSS surface.
- **WARNING (CSRF)**: `SameSite=Lax` + JSON-only bodies + `extra="forbid"`
  is adequate for this threat model; a hardened deployment would add a CSRF
  token. Record as an explicit decision in the design, not an accident.
- **INFO (timezone)**: per-user schedules remain host-local wall-clock;
  users in different timezones share the host clock (unchanged behavior).
- **INFO (auth code home)**: put pure hashing/session-token helpers in a new
  `auth.py` (like `rewards.py`), keeping `database.py` storage-only — fits
  AGENTS.md module conventions and keeps `auth.py` unit-testable without a DB.

## Ready for Proposal

**Yes.** The shape is fully mapped: session-cookie auth (zero new deps,
stdlib scrypt), per-user scoping of all five tables + 11 endpoints, per-user
scheduler loop, one-shot first-registrant migration preserving the legacy
settings, and an enumerated test plan (authed client fixture + isolation
tests). The orchestrator should tell the user: "Recommended: HttpOnly
session cookies + stdlib scrypt — no new dependencies. All five tables and
all 11 API endpoints become per-user; the scheduler loops users; the
existing DB's settings migrate to the first account that registers. The one
product question for the proposal: is the first account that registers
allowed to inherit the current settings (recommended), or should the DB
start clean?"
