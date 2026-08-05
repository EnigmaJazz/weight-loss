# Tasks: User Accounts and Authentication

## Review Workload Forecast

Estimated changed lines: 900–1,300
Suggested split: PR 1 auth/schema; PR 2 scoping/scheduler; PR 3 SPA/migration polish
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Auth API, schema, sessions | PR 1 | `.venv/bin/python -m pytest tests/test_auth.py tests/test_auth_api.py` | httpx ASGITransport + auth fixture | `auth.py`, auth routes, identity schema |
| 2 | Ownership and scheduling | PR 2 | `.venv/bin/python -m pytest tests/test_user_isolation.py tests/test_scheduler.py` | authenticated clients + stubbed push sender | scoped DB/routes/scheduler changes |
| 3 | SPA and legacy rollout proof | PR 3 | `.venv/bin/python -m pytest tests/test_auth_migration.py tests/test_api.py` | HTML/API smoke; no browser harness exists | `static/` changes and migration regressions |

## Phase 1: Auth Foundation (PR 1)

- [x] 1.1 **RED:** test scrypt and tokens in `tests/test_auth.py`; **GREEN:** add typed helpers in `auth.py`; **TRIANGULATE/REFACTOR:** centralize parameters and constant-time comparison. Test: `.venv/bin/python -m pytest tests/test_auth.py`; harness: N/A, pure module; rollback: `auth.py`.
- [x] 1.2 **RED/GREEN:** add `User`/`Session`, constants, schema, and storage in `models.py`, `constants.py`, `database.py`; verify foreign keys, expiry, hashed tokens. Test: `.venv/bin/python -m pytest tests/test_auth.py`; harness: SQLite; rollback: identity schema.
- [x] 1.3 **RED/GREEN:** seed legacy tables in `tests/test_auth_migration.py`; implement transactional rebuild in `database.py` discarding legacy pre-auth rows (no backfill — every account starts empty). Test: `.venv/bin/python -m pytest tests/test_auth_migration.py`; harness: seeded SQLite boot; rollback: migration; restore DB backup in deployment.
- [x] 1.4 **RED:** test register/login/logout/me and cookies; **GREEN:** wire async routes in `routes.py` and `main.py`; **TRIANGULATE/REFACTOR:** enforce validation and JSON mutations. Test: `.venv/bin/python -m pytest tests/test_auth_api.py`; harness: ASGITransport + auth fixture; rollback: auth routes.

## Phase 2: User Scoping and Scheduler (PR 2)

- [x] 2.1 **RED:** add unauthenticated/isolation cases and auth helpers in `tests/conftest.py`, `tests/test_user_isolation.py`; **GREEN:** require user IDs and scope five tables in `database.py`. Test: `.venv/bin/python -m pytest tests/test_user_isolation.py`; harness: two ASGI clients; rollback: scoped persistence.
- [x] 2.2 **RED/GREEN:** scope protected endpoints in `routes.py` and startup reconciliation in `main.py`; enforce cross-user delete 404. Test: `.venv/bin/python -m pytest tests/test_api.py tests/test_user_isolation.py`; harness: ASGITransport + stubbed push; rollback: routes/reconciliation.
- [x] 2.3 **RED/GREEN:** test independent dedupe, disabled schedules, and zero subscribers in `tests/test_scheduler.py`; implement the per-user loop in `scheduler.py`. Test: `.venv/bin/python -m pytest tests/test_scheduler.py`; harness: fake clock + stub sender; rollback: scheduler loop.
- [x] 2.4 **TRIANGULATE/REFACTOR:** adapt DB tests and verify async boundaries. Test: `.venv/bin/python -m pytest`; harness: project conftest; rollback: test adaptations.

## Phase 3: SPA and Rollout Verification (PR 3)

- [ ] 3.1 **RED/GREEN:** assert first/later registrant backfill across five tables in `tests/test_auth_migration.py`; stabilize atomic/idempotent behavior. Test: `.venv/bin/python -m pytest tests/test_auth_migration.py`; harness: seeded DB + ASGI registration; rollback: backfill behavior.
- [ ] 3.2 **RED/GREEN:** test auth gate, 401 recovery, identity, and logout; update `static/index.html`, `static/app.js`, `static/style.css`. Test: `.venv/bin/python -m pytest tests/test_api.py`; harness: API/HTML smoke, no browser harness; rollback: SPA auth UI.
- [ ] 3.3 **TRIANGULATE/REFACTOR:** run `.venv/bin/python -m pytest`, document rollback in `design.md`, and remove compatibility paths. Harness: full suite; rollback: polish files.

Threat matrix: rows N/A; no tests apply.
