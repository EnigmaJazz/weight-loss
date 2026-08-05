```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:48a041209c69e8ae952b6dd8e85ec27ce4901749409dc5b9acd347f8f63f16ab
verdict: pass
blockers: 0
critical_findings: 0
requirements: 13/13
scenarios: 32/32
test_command: .venv/bin/python -m pytest
test_exit_code: 0
test_output_hash: sha256:74d262e0af647c3e18b7ac0944ebdd5b06b2bfab5dc6fbcfeb36f3fd8bef9ea9
build_command: ""
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: user-accounts-auth  
**Version**: N/A  
**Mode**: Strict TDD  
**Revision**: `1ef2f28710cafe4e65012c3e81c5479956b0873f`  
**Final verdict**: **PASS WITH WARNINGS**

All 13 requirements and 32 scenarios are compliant. The configured Python suite passes with 172 tests, three focused Python runs pass with 39, 45, and 50 tests, the frontend Node suite passes with 33 tests, and independent live runtime harnesses prove migration discard, authentication, authorization, user isolation, scheduler isolation, browser login, and protected-401 recovery. No build step is configured.

### Completeness

| Metric | Value |
|--------|-------|
| Requirements | 13/13 complete |
| Scenarios | 32/32 compliant |
| Tasks total | 11 |
| Tasks complete | 11 |
| Tasks incomplete | 0 |

All 11 checkboxes in `tasks.md` are complete and have implementation plus runtime evidence. `apply-progress.md` twice describes the total as nine tasks, but the authoritative task artifact contains 11 tasks: four in Phase 1, four in Phase 2, and three in Phase 3.

### Build & Tests Execution

**Configured build**: ✅ No build step configured

```text
build_command: ""
build_exit_code: 0
build_output: <empty>
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

`openspec/config.yaml` declares `build_command: ""`; no build or pyright command was executed. The empty output hashes to the value above.

**Full configured Python suite**: ✅ 172 passed

```text
$ .venv/bin/python -m pytest
collected 172 items
tests/test_api.py .........................................              [ 23%]
tests/test_auth.py ....................                                  [ 35%]
tests/test_auth_api.py ...................                               [ 46%]
tests/test_auth_migration.py .....                                       [ 49%]
tests/test_notifications.py ....                                         [ 51%]
tests/test_rewards.py .....................                              [ 63%]
tests/test_scheduler.py ............                                     [ 70%]
tests/test_spa_gate.py ....                                              [ 73%]
tests/test_units.py .........                                            [ 78%]
tests/test_user_isolation.py ............................                [ 94%]
tests/test_weight.py .........                                           [100%]
172 passed in 3.57s
exit: 0
sha256: 74d262e0af647c3e18b7ac0944ebdd5b06b2bfab5dc6fbcfeb36f3fd8bef9ea9
```

**Focused authentication suite**: ✅ 39 passed

```text
$ .venv/bin/python -m pytest tests/test_auth.py tests/test_auth_api.py
collected 39 items
tests/test_auth.py ....................                                  [ 51%]
tests/test_auth_api.py ...................                               [100%]
39 passed in 0.87s
exit: 0
sha256: 6a079f15b5c54945b5cb2bb9338c37dbd96918eacbc850233e756eb26811046d
```

**Focused migration, isolation, and scheduler suite**: ✅ 45 passed

```text
$ .venv/bin/python -m pytest tests/test_auth_migration.py tests/test_user_isolation.py tests/test_scheduler.py
collected 45 items
tests/test_auth_migration.py .....                                       [ 11%]
tests/test_user_isolation.py ............................                [ 73%]
tests/test_scheduler.py ............                                     [100%]
45 passed in 0.92s
exit: 0
sha256: 49e877cde4d9edf997a06af035fd99edc5a7121b374f651941f28f457427e93d
```

**Focused SPA, migration, and API suite**: ✅ 50 passed

```text
$ .venv/bin/python -m pytest tests/test_spa_gate.py tests/test_auth_migration.py tests/test_api.py
collected 50 items
tests/test_spa_gate.py ....                                              [  8%]
tests/test_auth_migration.py .....                                       [ 18%]
tests/test_api.py .........................................              [100%]
50 passed in 1.69s
exit: 0
sha256: 31f722a1ca66b1f0a22aa976821cd36f7ee79271c5c1a2e3ad9ae9bd07c87650
```

**Frontend Node suite**: ✅ 33 passed

```text
$ node --test tests/frontend/auth-form.test.mjs tests/frontend/unit-input.test.mjs tests/frontend/weight-label.test.mjs
tests: 33
suites: 0
pass: 33
fail: 0
cancelled: 0
skipped: 0
todo: 0
duration_ms: 101.533714
exit: 0
sha256: 0c685d2cb549a62c898a20328150c02b9fd818736bf61326dc0017a8c1d9d021
```

**Coverage**: ➖ Not available. `openspec/config.yaml` declares `coverage: false` and a threshold of 0.

### Runtime Sanity

**Live API, migration, isolation, and scheduler harness**: ✅ Passed

A temporary seeded legacy SQLite database was booted through the current FastAPI application under uvicorn. The harness used real HTTP clients, inspected the migrated database, and invoked the production scheduler with only the external push boundary stubbed.

```text
PASS migration-discard: all five legacy data tables contained 0 rows
PASS unauthenticated-read: GET /api/weight -> 401
PASS unauthenticated-no-mutation: POST /api/weight -> 401, rows 0->0
PASS spa-delivery-gate-first: GET / -> 200, gate present, tracker hidden
PASS register-session: Alice -> 201, lowercased identity, session cookie present
PASS cookie-security: HttpOnly, SameSite=Lax, Path=/, Max-Age=2592000, Expires
PASS session-hash-only: persisted 64-character SHA-256 digest differs from cookie secret
PASS authenticated-me: GET /api/auth/me -> 200 alice
PASS first-account-empty: no migrated weight/settings inherited
PASS second-account-empty: Bob -> 201 with empty dataset
PASS per-user-isolation: Alice and Bob retained distinct weights and targets
PASS cross-user-delete-hidden: Bob deleting Alice's entry -> 404; entry preserved
PASS per-user-scheduler: two scoped endpoints sent and two independent keys persisted
api_exit_code: 0
sha256: a9d8ac6ef28f664aa74bf9c143b8638dfcf178ad150d122f69dcdda9c456277f
```

The same live application then ran `tests/smoke-ui.sh http://127.0.0.1:8810` against the scratch database: **19 browser steps passed, 0 failed**. It proved the unauthenticated gate, signup-to-tracker transition, protected tracker operations, logout, and return to the gate. Its output is included in the runtime hash above.

**Live browser login and protected-401 recovery harness**: ✅ Passed

```text
gate_before_login=true tracker_before_login=false
gate_after_login=false tracker_after_login=true
gate_after_protected_401=true tracker_after_protected_401=false
SPA LOGIN/401 RECOVERY HARNESS PASSED: gate -> tracker -> gate
exit: 0
sha256: dc5643e3eeb3d5ce5bc38b86e79c2c7a016b99cac80352663e97d527182b9c01
```

The browser logged into a pre-created account, verified that the tracker replaced the gate, had its persisted session revoked directly, submitted a protected settings request, received 401, and verified that the production SPA hid the tracker and restored the authentication gate.

### Spec Compliance Matrix

| Requirement | Scenario | Runtime evidence | Result |
|-------------|----------|------------------|--------|
| Account Registration | Register a valid account | `tests/test_auth_api.py::test_register_creates_lowercased_user_and_session`; live register/session harness | ✅ COMPLIANT |
| Account Registration | Reject invalid credentials | `test_register_rejects_short_username`, `test_register_rejects_long_username`, `test_register_rejects_username_with_whitespace`, `test_register_rejects_short_password`, `test_register_rejects_unknown_fields` | ✅ COMPLIANT |
| Account Registration | Reject a duplicate username | `tests/test_auth_api.py::test_register_duplicate_username_conflicts_case_insensitively` | ✅ COMPLIANT |
| Authentication API | Login and identify the account | `tests/test_auth_api.py::test_login_then_me_round_trip`; live browser login harness | ✅ COMPLIANT |
| Authentication API | Reject incorrect credentials | `tests/test_auth_api.py::test_login_wrong_password_returns_401` and `test_login_unknown_user_returns_401` | ✅ COMPLIANT |
| Authentication API | Logout revokes access | `tests/test_auth_api.py::test_logout_revokes_the_session` and `test_logout_deletes_the_session_row`; 19-step browser smoke | ✅ COMPLIANT |
| Session Cookie Security | Issue a secure session | `test_session_cookie_carries_secure_attributes`, `test_session_cookie_secure_flag_follows_configuration`, `test_session_persists_only_the_token_hash`; live cookie/hash checks | ✅ COMPLIANT |
| Session Cookie Security | Reject an expired session | `tests/test_auth_api.py::test_expired_session_is_rejected` | ✅ COMPLIANT |
| Protected API Authorization | Access without a session | `tests/test_user_isolation.py::test_401_on_weight_get` plus weight/settings/push/no-mutation 401 matrix; live 401/no-mutation checks | ✅ COMPLIANT |
| Protected API Authorization | Address another user's resource | `tests/test_user_isolation.py::test_cross_user_delete_returns_404_and_preserves_entry`; live cross-user delete | ✅ COMPLIANT |
| SPA Authentication Gate | Open the SPA without authentication | `tests/test_spa_gate.py::test_index_html_ships_auth_gate_and_hidden_tracker`; live browser gate | ✅ COMPLIANT |
| SPA Authentication Gate | Session expires during use | Live browser login/session-revocation/protected-401 harness | ✅ COMPLIANT |
| Authenticated Weight and Settings APIs | Reject unauthenticated weight access | `test_401_on_weight_get`, `test_401_on_weight_post_does_not_create_entry`, `test_401_on_weight_delete`, `test_401_on_settings_get`, `test_401_on_settings_put_does_not_mutate` | ✅ COMPLIANT |
| Authenticated Weight and Settings APIs | Keep two users isolated | `tests/test_user_isolation.py::test_entries_are_isolated_between_users` and `test_settings_are_isolated_between_users`; live Alice/Bob harness | ✅ COMPLIANT |
| Legacy Pre-Auth Data Is Discarded on Migration | First account starts empty after migration | `tests/test_auth_migration.py::test_boot_migrates_legacy_schema_discarding_rows`, `test_first_user_starts_empty`, and live seeded migration | ✅ COMPLIANT |
| Legacy Pre-Auth Data Is Discarded on Migration | Later accounts also start empty | `tests/test_auth_migration.py::test_registered_users_start_empty_after_migration`; live Bob registration | ✅ COMPLIANT |
| Canonical Weight Mutations | Create and update one date | `tests/test_weight.py::test_update_on_duplicate_date`; `tests/test_user_isolation.py::test_same_date_allowed_for_two_users` | ✅ COMPLIANT |
| Canonical Weight Mutations | Delete an entry | `tests/test_weight.py::test_delete_entry` | ✅ COMPLIANT |
| Canonical Weight Mutations | Reject cross-user deletion | `tests/test_user_isolation.py::test_cross_user_delete_returns_404_and_preserves_entry`; live harness | ✅ COMPLIANT |
| Authenticated Reward Isolation | Derive rewards for one user | `tests/test_user_isolation.py::test_rewards_derive_only_from_own_data` | ✅ COMPLIANT |
| Authenticated Reward Isolation | Reject unauthenticated reward access | `tests/test_user_isolation.py::test_401_on_rewards` | ✅ COMPLIANT |
| User-Scoped Active Rewards | Reconcile one user's mutation | `tests/test_user_isolation.py::test_db_upsert_reconciles_only_own_rewards` | ✅ COMPLIANT |
| User-Scoped Active Rewards | Store the same checkpoint for two users | `tests/test_user_isolation.py::test_same_checkpoint_can_exist_for_two_users` | ✅ COMPLIANT |
| User-Scoped Active Rewards | Reconcile all users at startup | `tests/test_user_isolation.py::test_db_startup_reconcile_is_per_user`; `tests/test_weight.py::test_startup_reconciles_active_rewards` | ✅ COMPLIANT |
| Authenticated Notification Isolation | Keep subscriptions isolated | `test_push_test_targets_only_own_subscriptions`, `test_manual_notify_targets_only_own_subscriptions`, `test_unsubscribe_only_removes_own_subscription` | ✅ COMPLIANT |
| Authenticated Notification Isolation | Reject unauthenticated subscription mutation | `test_401_on_push_subscribe` and `test_401_on_push_unsubscribe` | ✅ COMPLIANT |
| Per-User Scheduler Processing | Send due notifications per user | `tests/test_scheduler.py::test_per_user_dedupe_is_independent`; live scheduler harness | ✅ COMPLIANT |
| Per-User Scheduler Processing | Skip one user's disabled schedule | `tests/test_scheduler.py::test_per_user_disabled_schedule_skips_only_that_user` | ✅ COMPLIANT |
| Calendar-Day Deduplication | Repeated DST hour | `tests/test_scheduler.py::test_dst_repeated_hour_sends_once` | ✅ COMPLIANT |
| Calendar-Day Deduplication | Skipped DST time | `tests/test_scheduler.py::test_dst_skipped_time_fires_on_next_tick` | ✅ COMPLIANT |
| Calendar-Day Deduplication | Next local day | `tests/test_scheduler.py::test_due_checks_fire_once_then_dedupe` | ✅ COMPLIANT |
| Calendar-Day Deduplication | No subscriptions yet | `tests/test_scheduler.py::test_per_user_zero_subscribers_consume_no_dedupe` and `test_due_checks_fires_after_subscriber_joins` | ✅ COMPLIANT |

**Compliance summary**: 32/32 scenarios compliant; 13/13 requirements complete.

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Account Registration | ✅ Implemented | Typed validation normalizes usernames; scrypt uses independent salts; registration creates a hashed-token session. |
| Authentication API | ✅ Implemented | Login verifies scrypt off-thread; `me` resolves identity; logout deletes the hashed session and cookie. |
| Session Cookie Security | ✅ Implemented | Cookie helper sets all required attributes; only SHA-256 token hashes are stored; lookup excludes expired sessions. |
| Protected API Authorization | ✅ Implemented | `require_user` uniformly returns 401; route and SQL ownership checks hide cross-user identifiers with 404. |
| SPA Authentication Gate | ✅ Implemented | Initialization calls `/api/auth/me` before `loadData`; centralized 401 handling returns to the gate. |
| Authenticated Weight and Settings APIs | ✅ Implemented | Every read and mutation passes the authenticated `user.id` into scoped database methods. |
| Legacy Pre-Auth Data Is Discarded on Migration | ✅ Implemented | Legacy tables are rebuilt empty in the schema transaction; legacy subscriptions are deleted; migrated schemas short-circuit. |
| Canonical Weight Mutations | ✅ Implemented | Uniqueness is `(user_id, date)`; upsert conflict and delete ownership are user-scoped; reward reconciliation receives that user only. |
| Authenticated Reward Isolation | ✅ Implemented | Reward responses derive from the authenticated user's entries, settings, and active rows. |
| User-Scoped Active Rewards | ✅ Implemented | Active-reward primary keys and reconciliation are user-scoped; startup iterates registered users. |
| Authenticated Notification Isolation | ✅ Implemented | Subscription CRUD and sends pass the authenticated user ID; subscription queries are scoped. |
| Per-User Scheduler Processing | ✅ Implemented | `run_due_checks` iterates users and applies each user's settings, subscriptions, and dedupe keys independently. |
| Calendar-Day Deduplication | ✅ Implemented | Dedupe key operations include user, local date, and type; zero-subscription checks do not write keys. |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| HttpOnly revocable SQLite sessions | ✅ Yes | Session secrets remain in cookies; only hashes are persisted and logout revokes rows. |
| stdlib scrypt with centralized parameters and independent salts | ✅ Yes | `auth.py` remains pure and tests cover round-trip, incorrect passwords, uniqueness, and token hashing. |
| Discard legacy pre-auth data | ✅ Yes | Migration rebuilds the five data domains without assigning legacy rows to any account. |
| SameSite=Lax, same-origin JSON mutations | ✅ Yes | Cookie and served-SPA tests enforce the designed posture. |
| Async request path | ✅ Yes | Scrypt uses `asyncio.to_thread`; database calls in routes use `await run_db(...)`. |
| User-scoped persistence and scheduler | ✅ Yes | Database keys, route propagation, reward reconciliation, and scheduler iteration carry `user_id`. |
| SPA `/api/auth/me` gate and centralized 401 recovery | ✅ Yes | Static source inspection and live browser execution confirm both paths. |
| Rollback plan | ✅ Yes | `design.md` documents code rollback plus restoration of the pre-migration database backup. |

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD evidence reported | ✅ | `apply-progress.md` contains RED/GREEN/triangulation/safety-net tables for all three slices. |
| All tasks have tests | ✅ | 11/11 task checkboxes link to existing focused test files or the browser smoke harness. |
| RED confirmed (tests exist) | ✅ | Every evidence-linked test file exists; behavior tasks record concrete pre-implementation failures. Task 2.4 is mechanical adaptation and task 3.1 reuses the earlier migration RED. |
| GREEN confirmed (tests pass) | ✅ | All current focused files pass, the full suite passes, and both independent browser/runtime harnesses pass. |
| Triangulation adequate | ✅ | Boundaries, invalid inputs, multiple users, mutation/no-mutation paths, migration idempotency, DST cases, and zero-subscriber behavior vary expectations. |
| Safety net for modified files | ✅ | Apply records 93, 132, and 168-test slice baselines; current verification independently passes 172 tests. |

**TDD Compliance**: 6/6 checks passed.

### Test Layer Distribution

| Layer | Tests / checks | Files | Tools |
|-------|----------------|-------|-------|
| Unit | 36 | 2 | pytest (`test_auth.py`) + node:test (`auth-form.test.mjs`) |
| Integration | 118 | 7 | pytest + httpx ASGITransport + temporary SQLite |
| E2E / browser | 22 runtime steps | 1 committed script + 1 temporary harness | playwright-cli + live uvicorn |
| **Automated changed-file test total** | **154 tests + 22 browser steps** | **11 evidence sources** | |

The frontend command additionally passed 17 unchanged unit-input and weight-label tests, producing the command total of 33 Node tests.

### Changed File Coverage

Coverage analysis skipped — no coverage tool is configured.

### Assertion Quality

**Assertion quality**: ✅ All change-related assertions call production behavior and verify meaningful values, persisted state, ownership, mutation/no-mutation, delivery targets, and UI visibility. Empty-collection assertions have companion seeded or non-empty paths. Fixed-collection loops are non-empty, and scheduler fake-send loops receive explicitly created subscriptions. No tautologies, assertion-free paths, ghost loops, smoke-only assertions, implementation-detail class assertions, or mock-heavy files were found.

### Quality Metrics

**Linter**: ➖ Not available  
**Type Checker**: ➖ Not configured as a verify command; pyright was not run  
**Configured Build**: ✅ Empty command, exit 0, empty output

### Canonical Verification Evidence

The exact canonical verification-evidence preimage hashed by `evidence_revision` is:

```text
change=user-accounts-auth
revision=1ef2f28710cafe4e65012c3e81c5479956b0873f
requirements=13/13
scenarios=32/32
tasks=11/11
test_command=.venv/bin/python -m pytest
test_exit_code=0
test_output_hash=sha256:74d262e0af647c3e18b7ac0944ebdd5b06b2bfab5dc6fbcfeb36f3fd8bef9ea9
focused_auth_command=.venv/bin/python -m pytest tests/test_auth.py tests/test_auth_api.py
focused_auth_exit_code=0
focused_auth_output_hash=sha256:6a079f15b5c54945b5cb2bb9338c37dbd96918eacbc850233e756eb26811046d
focused_scoping_command=.venv/bin/python -m pytest tests/test_auth_migration.py tests/test_user_isolation.py tests/test_scheduler.py
focused_scoping_exit_code=0
focused_scoping_output_hash=sha256:49e877cde4d9edf997a06af035fd99edc5a7121b374f651941f28f457427e93d
focused_spa_command=.venv/bin/python -m pytest tests/test_spa_gate.py tests/test_auth_migration.py tests/test_api.py
focused_spa_exit_code=0
focused_spa_output_hash=sha256:31f722a1ca66b1f0a22aa976821cd36f7ee79271c5c1a2e3ad9ae9bd07c87650
frontend_test_command=node --test tests/frontend/auth-form.test.mjs tests/frontend/unit-input.test.mjs tests/frontend/weight-label.test.mjs
frontend_test_exit_code=0
frontend_test_output_hash=sha256:0c685d2cb549a62c898a20328150c02b9fd818736bf61326dc0017a8c1d9d021
runtime_harness_command=temporary live uvicorn/httpx/scheduler harness + tests/smoke-ui.sh http://127.0.0.1:8810
runtime_harness_exit_code=0
runtime_harness_output_hash=sha256:a9d8ac6ef28f664aa74bf9c143b8638dfcf178ad150d122f69dcdda9c456277f
spa_401_harness_command=temporary live browser login + session revocation + protected PUT 401 harness
spa_401_harness_exit_code=0
spa_401_harness_output_hash=sha256:dc5643e3eeb3d5ce5bc38b86e79c2c7a016b99cac80352663e97d527182b9c01
build_command=
build_exit_code=0
build_output_hash=sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The preimage includes a trailing newline and hashes to `sha256:48a041209c69e8ae952b6dd8e85ec27ce4901749409dc5b9acd347f8f63f16ab`.

### Issues Found

#### CRITICAL

None.

#### WARNING

1. **`apply-progress.md` miscounts the completed tasks.** The final slice says all nine tasks are complete, but `tasks.md` contains 11 completed tasks. This does not affect implementation completeness, but the progress summary should not be used as the authoritative count.
2. **A migration docstring is stale.** `Database._migrate_legacy_schema` says it preserves legacy data under a sentinel owner, while the implementation and current specification correctly discard all legacy rows. Runtime behavior is compliant, but the misleading source comment should be corrected in a later documentation-only change.

#### SUGGESTION

1. Promote the independent browser session-revocation check into a committed regression so protected-401 gate recovery remains continuously executable without a temporary harness.

### Verdict

**PASS WITH WARNINGS**

All configured gates pass, all 13 requirements and 32 scenarios have passing runtime evidence, all 11 tasks are complete, and the implementation follows the current design. The warnings are documentation inconsistencies and do not block archive readiness.
