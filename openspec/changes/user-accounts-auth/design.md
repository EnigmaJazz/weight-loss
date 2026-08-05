# Design: User Accounts and Authentication

## Technical Approach

Add revocable cookie sessions within the module-per-concern architecture. `auth.py` performs no I/O; `database.py` owns identity, migration, and scoped persistence; async routes offload scrypt with `asyncio.to_thread` and SQLite with `run_db`. Every existing API route passes its authenticated user ID to required DB parameters.

## Architecture Decisions

| Decision | Alternatives | Rationale |
|---|---|---|
| HttpOnly cookie plus SQLite session | JWT; HTTP Basic | Supports revocation, avoids localStorage XSS exposure and new dependencies. |
| stdlib scrypt (`n=2**14,r=8,p=1,dklen=32`) with independent 16-byte salts | Argon2; PBKDF2 | Memory-hard and dependency-free; parameters remain centralized and testable. |
| First registrant starts empty; legacy rows discarded | Admin claim flow; preserve as defaults | Legacy pre-auth rows were smoke-test artifacts, not real user data; every account sets its own values. |
| `SameSite=Lax` plus same-origin, JSON-only mutations | CSRF token | Adequate for this local/same-origin SPA: cross-site forms cannot issue JSON/DELETE and cross-site POST cookies are blocked. Hardened cross-origin deployments must add CSRF tokens. |

## Data Flow

```text
SPA -> register/login -> scrypt -> users + hashed session -> HttpOnly cookie
SPA -> require_user(cookie -> SHA-256 -> session/user) -> scoped DB -> response
Scheduler -> users -> settings/dedupe/subscriptions(user_id) -> push
```

## File Changes

| File | Action | Description |
|---|---|---|
| `auth.py` | Create | Salt, scrypt, token, and token-hash helpers. |
| `models.py`, `constants.py` | Modify | Add `User`/`Session` and auth configuration. |
| `database.py` | Modify | Atomic migration, users/sessions, scoped queries and reward reconciliation. |
| `routes.py` | Modify | Auth dependency/routes and ownership propagation. |
| `scheduler.py`, `main.py` | Modify | Per-user due checks and startup reconciliation. |
| `static/index.html`, `static/app.js`, `static/style.css` | Modify | Auth gate, logout, and 401 handling. |
| `tests/` | Modify/Create | Auth, isolation, migration, scheduler, and startup regressions. |

## Interfaces / Contracts

```python
generate_password_salt() -> str
hash_password(password: str, salt: str) -> str
verify_password(password: str, salt: str, expected_hash: str) -> bool
generate_session_token() -> str              # secrets.token_urlsafe(32)
hash_session_token(token: str) -> str         # SHA-256 hex
require_user(request: Request, db: Database = Depends(get_db)) -> User

create_user(username: str, password_hash: str, salt: str) -> User
get_user_by_username(username: str) -> Optional[User]
list_users() -> list[User]
create_session(user_id: int, token_hash: str, expires_at: str) -> Session
get_user_by_session(token_hash: str) -> Optional[User]
delete_session(token_hash: str) -> bool
delete_expired_sessions(now: str) -> int
```

Use `hmac.compare_digest`. `users(id, username UNIQUE lowercased, password_hash, salt, created_at)` and `sessions(id, user_id REFERENCES users(id) ON DELETE CASCADE, token_hash UNIQUE, created_at, expires_at)` use UTC timestamps; enable `PRAGMA foreign_keys=ON`.

Required leading `user_id` is added to `list_entries`, `get_entry_by_date`, `upsert_entry`, `delete_entry`, `list_active_rewards`, `get_settings`, `_settings_from_conn` (before `conn`), `update_settings`, `add_subscription`, `list_subscriptions`, `remove_subscription`, `is_notification_sent`, and `mark_notification_sent`. Session lookup excludes expired rows; creation opportunistically deletes them.

`POST /api/auth/register|login|logout` and `GET /api/auth/me` return only public identity fields. Register/login set a 30-day cookie with `HttpOnly`, `SameSite=Lax`, `Path=/`, configured `Secure`, `Max-Age`, and `Expires`; logout deletes the hashed row and cookie. Missing/invalid/expired sessions return 401; cross-owner IDs return 404.

## Migration / Rollout

Back up `weight_loss.db`. `init_schema` inspects `PRAGMA table_info`; fresh databases create the target schema directly. Legacy migration uses one `BEGIN IMMEDIATE` and individual `conn.execute` calls—not `executescript`, which can disrupt explicit boundaries with `isolation_level=None`. Rebuild `weight_entries` with `UNIQUE(user_id,date)`, `active_rewards` with `PRIMARY KEY(user_id,checkpoint_percent)`, `notifications_sent` with `PRIMARY KEY(user_id,date,type)`, and `settings` with `PRIMARY KEY(user_id,key)`: create `_new`, discard legacy rows (no copy), drop old, rename. Add `push_subscriptions.user_id NOT NULL DEFAULT 0` then delete legacy subscriptions; endpoint stays globally unique and conflict reassigns ownership. No backfill: every account starts empty. Startup reconciles every `list_users()` result.

The scheduler loops users; settings, subscriptions, and dedupe are scoped, and zero subscriptions consume no key. The SPA calls `/api/auth/me` before `loadData`, gates on 401, and logs out through the API. Fetch already defaults credentials to `same-origin`; the wrapper centralizes 401 handling without forcing `include`.

Rollback: stop the app, revert code, and restore the pre-migration DB backup; do not reverse rebuilt tables in place. Delete `sessions` after suspected token exposure.

## Testing Strategy

| Layer | Coverage |
|---|---|
| Unit | New `tests/test_auth.py`: scrypt round-trip/wrong password, salt uniqueness, token hashing. |
| Integration | `tests/conftest.py`: `unauthenticated_client`, authenticated `client`, `register_user`, `login_user`, `make_user`; new `test_auth_api.py`, `test_user_isolation.py`, and seeded-legacy `test_auth_migration.py`; update `test_weight.py` startup and `test_scheduler.py` for two users, disabled schedules, independent dedupe, and zero-subscriber behavior. |
| E2E | No harness exists; API/HTML assertions plus manual same-origin cookie/gate smoke test. |

## Threat Matrix

| Boundary | Applicability |
|---|---|
| Documentation-like paths | N/A: no executable classification. |
| Git repository selection | N/A: no VCS integration. |
| Commit state | N/A: no commit automation. |
| Push state | N/A: Web Push is application data, not VCS push/process execution. |
| PR commands | N/A: no PR or shell composition. |

HTTP routing changes, but no execution/VCS matrix boundary is crossed; no matrix RED tests apply.

## Open Questions

None.
