# Proposal: User Accounts and Authentication

## Intent

Enable several people to use the tracker without exposing or mixing data. Preserve legacy settings by assigning them to the first account created.

## Scope

### In Scope
- Signup, login, logout, current-user APIs, and authenticated user-scoped existing APIs.
- SQLite users/sessions, user ownership, and tested legacy migration.
- Per-user scheduler and SPA login/register gate with logout.

### Out of Scope
- Roles/admin, email verification, password reset, OAuth, or cross-device management.
- Abuse controls beyond basic validation, CSRF tokens, and per-user time zones.

## Capabilities

### New Capabilities
- `user-authentication`: Self-registration and password-based session authentication with account identity.

### Modified Capabilities
- `weight-tracking`: Weight entries and settings are isolated by authenticated user.
- `target-progress-rewards`: Reward calculation and active rewards are isolated by authenticated user.
- `local-time-notifications`: Schedules, subscriptions, and day deduplication are isolated and processed per user.

## Approach

Use `hashlib.scrypt` and a random session cookie, storing only its SHA-256 hash in SQLite `sessions`. Cookies are `HttpOnly`, `SameSite=Lax`, `Path=/`, 30-day expiry, with configurable `Secure` for local HTTP. `require_user` protects existing endpoints. SameSite plus JSON-only mutations is the CSRF posture; hardened deployments may add tokens.

Add `users`/`sessions` and `user_id` to `weight_entries`, `push_subscriptions`, `active_rewards`, `notifications_sent`, and `settings`. Rebuild tables requiring composite keys. A one-shot transactional first-registration backfill assigns sentinel-owned legacy rows. The scheduler enumerates users and preserves no-dedupe-on-zero-subscriber per user.

Reject JWT (revocation needs state and client storage risks XSS), HTTP Basic (no logout, poor SPA UX), and Argon2 (new dependency).

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `auth.py`, `models.py`, `constants.py` | New/Modified | Auth helpers, state, configuration. |
| `database.py`, `routes.py`, `main.py` | Modified | Migration, scoped queries, auth routes. |
| `scheduler.py`, `static/`, `tests/` | Modified | Per-user scheduling, login UI, strict-TDD coverage. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Unscoped query leaks data | Med | Required `user_id` methods and isolation tests. |
| SQLite rebuild corrupts data | Med | Transactional, idempotent seeded-DB migration. |
| First account claims settings | Med | One-shot atomic backfill and documented ownership. |

## Rollback Plan

Back up `weight_loss.db` before deployment. If migration or isolation fails, revert code and restore the backup; do not reverse schema rebuilds in place. Delete `sessions` after suspected cookie exposure.

## Dependencies

- No new dependencies; uses stdlib `hashlib.scrypt`, SQLite, and FastAPI cookie support.

## Success Criteria

- [ ] Users can register, log in, identify themselves, and log out; unauthenticated protected APIs return 401.
- [ ] Entries, settings, rewards, subscriptions, and notification dedupe are isolated per user.
- [ ] Legacy settings are preserved for the first registrant and per-user scheduler tests pass.
