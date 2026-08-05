# Archive Report: user-accounts-auth

**Change**: user-accounts-auth
**Archived**: 2026-08-05
**Mode**: Strict TDD
**Final verdict**: PASS WITH WARNINGS — 13/13 requirements, 32/32 scenarios, 172 pytest + 33 node:test green, live runtime + browser harnesses green, review approved (0 blockers)

## Summary

Closed the user accounts and authentication change end-to-end. The tracker moved from single-user, no-auth to multi-user with scrypt password hashing, revocable HttpOnly cookie sessions, per-user data isolation across all five data domains, a user-scoped scheduler, an SPA authentication gate, and a schema migration that discards all legacy pre-auth rows (no first-registrant backfill — every account, including the first, starts empty, per maintainer decision).

Key implementation facts (verified at close):

- `auth.py` (new): stdlib scrypt with centralized parameters and independent salts; constant-time comparison; SHA-256 session-token hashing.
- `models.py` / `constants.py` / `database.py`: `User`/`Session` dataclasses, identity schema, transactional legacy-schema rebuild that discards legacy rows, user-scoped keys on weight entries, settings, subscriptions, active rewards, and dedupe rows.
- `routes.py` / `main.py`: `POST /api/auth/register|login|logout`, `GET /api/auth/me`, `require_user` 401-on-missing/invalid/expired, ownership-hidden identifiers return 404, startup reward reconciliation iterates registered users.
- `scheduler.py`: `run_due_checks` iterates users with independent settings, subscriptions, and dedupe keys.
- `static/`: SPA gates on `/api/auth/me`, shows registration/login when unauthenticated, restores the gate after logout or a protected 401.

The `apply-progress.md` miscount warning (final slice says 9 tasks) was NOT an implementation defect: the persisted `tasks.md` artifact is authoritative and records 11/11 complete; `verify-report.md` states the same. The migration-docstring warning WAS fixed post-verify in commit `6906e25` (docs(database): correct migration docstring to reflect discard behavior).

## Evidence

- Review gate: allow. A bounded 4-lens review plus a recovery successor review both approved with 0 blockers; binding recorded as `review-recover-auth-001 → user-accounts-auth` (per orchestrator final-state handoff).
- Full configured suite: `.venv/bin/python -m pytest` → 172 passed, exit 0 (`sha256:74d262e0af647c3e18b7ac0944ebdd5b06b2bfab5dc6fbcfeb36f3fd8bef9ea9`).
- Focused auth suite: 39 passed; focused migration/isolation/scheduler: 45 passed; focused SPA/migration/API: 50 passed.
- Frontend Node suite: 33 passed (`node --test`).
- Live runtime harness (uvicorn + real HTTP + production scheduler, push boundary stubbed): migration-discard, 401 matrix, register/session/me, first-and-later-account-empty, per-user isolation, cross-user delete 404, per-user scheduler keys — all PASS. 19-step `tests/smoke-ui.sh` browser run: 0 failed.
- Live browser login + session-revocation + protected-401 recovery harness: PASS (gate → tracker → gate).
- Build: `build_command: ""` per config, `build_exit_code: 0`.
- Coverage: not configured (`coverage: false`).

## Delta Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| user-authentication | Created | New main spec `openspec/specs/user-authentication/spec.md` — 5 requirements: Account Registration, Authentication API, Session Cookie Security, Protected API Authorization, SPA Authentication Gate (10 scenarios total). |
| weight-tracking | Updated | ADDED `Authenticated Weight and Settings APIs` (2 scenarios) and `Legacy Pre-Auth Data Is Discarded on Migration` (2 scenarios); MODIFIED `Canonical Weight Mutations` (now user-scoped per date, +`Reject cross-user deletion` scenario). Other requirements preserved unchanged. |
| target-progress-rewards | Updated | ADDED `Authenticated Reward Isolation` (2 scenarios) and `User-Scoped Active Rewards` (3 scenarios). All prior requirements preserved unchanged. |
| local-time-notifications | Updated | ADDED `Authenticated Notification Isolation` (2 scenarios) and `Per-User Scheduler Processing` (2 scenarios); MODIFIED `Calendar-Day Deduplication` (user-scoped key, zero-subscription behavior, +`No subscriptions yet` scenario). All other requirements preserved unchanged. |

Additive merge overall; the two MODIFIED blocks replaced their matching requirement in full with the delta's complete updated text (including preserved unchanged scenarios). No REMOVED or RENAMED sections, no destructive delta — no confirm-before-merge trigger.

## Task Completion

- 11/11 tasks complete (`tasks.md`, checked). No stale unchecked implementation tasks in the archived artifact.
- Known non-blocking doc inconsistency: `apply-progress.md` describes the task total as 9 in two slices, while the authoritative `tasks.md` records 11. `verify-report.md` flags this and is the trusted count.

## Rollback

- Code rollback: revert the auth/scope/scheduler/SPA commits; `design.md` documents restoration of the pre-migration database backup. The migration is idempotent (already-migrated schemas short-circuit), so a reverted deploy against a migrated DB does not re-run the discard.

## Follow-ups (non-blocking)

1. Promote the independent browser session-revocation check into a committed regression so protected-401 gate recovery remains continuously executable without a temporary harness (verify-report SUGGESTION, still open at close).
2. `apply-progress.md`'s 9-vs-11 task miscount should not be cited as authoritative anywhere; tasks.md is the source of truth.
