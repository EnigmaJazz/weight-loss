```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:7e0bc58379535fb0a852ffe5797d7793e30df1c01321beb3c345c4fb2026077b
verdict: pass
blockers: 0
critical_findings: 0
requirements: 12/12
scenarios: 25/25
test_command: .venv/bin/python -m pytest -q
test_exit_code: 0
test_output_hash: sha256:5d3c9046c05626641cc7e17b8086f7a90f263f07b91fefbd67fbb44b0d732cb3
build_command: ""
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: core-app  
**Version**: N/A  
**Mode**: Strict TDD  
**Revision**: `b0c8ec8a66ac36fb5095053d5aff51c0e9b2c209` (`main`, matching `origin/main`)  
**Final verdict**: **PASS WITH WARNINGS**

All 12 requirements and 25 scenarios are compliant on the remediated tree. The full Python suite passes, the new frontend formatter suite passes against the production `static/format.js`, the exact required `kg (lb; st lb)` shape is proven at runtime, and a live uvicorn smoke confirms the SPA asset order and required routes. There is no configured build step; the known Pyright environment hang is recorded as a warning rather than as the build gate.

### Completeness

| Metric | Value |
|--------|-------|
| Requirements | 12/12 complete |
| Scenarios | 25/25 compliant |
| Tasks total | 12 |
| Tasks complete | 12 |
| Tasks incomplete | 0 |
| Conditional task 3.2 | Complete through its explicit deferral branch: 1,142 authored changed lines exceeded the 400-line gate, so manifest icons and local unsubscribe were both deferred |

Task 3.2 is complete because its own conditional contract requires deferral when the final forecast exceeds 400 changed lines. The current task artifact records that branch explicitly. The baseline and subsequent implementation/remediation commits use conventional commit messages without AI attribution.

### Build & Tests Execution

**Configured build**: ✅ No build step configured

```text
build_command: ""
build_exit_code: 0
build_output: <empty>
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

`openspec/config.yaml` declares `build_command: ""`; therefore no build command was executed and the build gate succeeds with the SHA-256 digest of exact empty output. Pyright is not the configured build gate or quality checker.

**Full Python tests**: ✅ 76 passed

```text
$ .venv/bin/python -m pytest -q
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 0.30s
exit: 0
sha256: 5d3c9046c05626641cc7e17b8086f7a90f263f07b91fefbd67fbb44b0d732cb3
```

**Frontend formatter regression**: ✅ 6 passed

```text
$ node --test tests/frontend/weight-label.test.mjs
✔ weightLabel renders the full multi-unit shape kg (lb; st lb) (0.793658ms)
✔ weightLabel renders kg (lb) when no stone is present (0.082166ms)
✔ weightLabel is null-safe for missing kg (0.066295ms)
✔ weightLabel renders bare kg when only kg is present (0.070894ms)
✔ fmt1 rounds to one decimal (toFixed(1)) (0.069432ms)
✔ weightLabel rounds stone-lb via fmt1 (spec example) (0.076825ms)
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 84.285438
exit: 0
sha256: e3120c46e450c40ca1fcf21bdde684d5ebc60fcdecd7b609df24c625bb62a091
```

**JavaScript syntax**: ✅ `node --check static/format.js && node --check static/app.js` exited 0.

**Coverage**: ➖ Not available. `openspec/config.yaml` declares no coverage tool and a threshold of 0.

### Runtime Sanity

**Exact production formatter shape**: ✅ Passed

```text
actual=82.5 kg (181.9 lb; 13 st 0.4 lb)
expected=82.5 kg (181.9 lb; 13 st 0.4 lb)
match=true
exit=0
sha256: 01fb2225dc315dd6638c029c4d89b9da7fb33ffedde0d29c7cb6c4e5a716b7ba
```

This proof imported the same `static/format.js` loaded by the browser. `static/app.js` consumes `globalThis.WeightFormat`, and summary, history, chart tooltip, active-checkpoint, and next-checkpoint views all call the shared `weightLabel`/`summaryLabel` helpers.

**Live uvicorn smoke with temporary SQLite and VAPID files**: ✅ Passed

```text
GET / status=200 bytes=3541
GET /static/format.js status=200 bytes=1293
GET /static/app.js status=200 bytes=14500
GET /api/weight status=200 bytes=484
GET /api/rewards status=200 bytes=88
index_format_script_position=3436
index_app_script_position=3480
format_before_app=True
format_exports_weightLabel=True
app_consumes_WeightFormat=True
exit=0
sha256: 5844b46cb53fad0ef431992a55cc333e2326f988dfaad8c8b14cb08a5cab88e4
```

The served `index.html` loads `/static/format.js` before deferred `/static/app.js`.

### Per-Spec Verdicts

| Spec | Requirements | Scenarios | Verdict | Notes |
|------|--------------|-----------|---------|-------|
| `weight-tracking` | 4/4 | 8/8 | ✅ PASS | Canonical mutations, derived units, configured/absent BMI, settings validation, and the exact production UI label shape all have passing runtime coverage. |
| `target-progress-rewards` | 4/4 | 8/8 | ✅ PASS | Five thresholds, override/earliest start, inclusive earning, revocation, mutation reconciliation, and fresh re-earning timestamps pass. |
| `local-time-notifications` | 4/4 | 9/9 | ✅ PASS WITH WARNING | Local persisted times, due/disabled checks, zero-subscription consumption, DST/day dedupe, and the over-budget deferral branch are compliant; API/UI persistence of an empty disabled schedule remains awkward. |

### Spec Compliance Matrix

| Requirement | Scenario | Runtime evidence | Result |
|-------------|----------|------------------|--------|
| WT-1 Canonical Weight Mutations | Create and update one date | `tests/test_weight.py::test_update_on_duplicate_date` | ✅ COMPLIANT |
| WT-1 Canonical Weight Mutations | Delete an entry | `tests/test_weight.py::test_delete_entry` | ✅ COMPLIANT |
| WT-2 Multi-Unit Presentation | Derive alternate units | `tests/test_units.py::test_kg_to_lb_uses_spec_factor`, `test_kg_to_stone_decomposes_into_whole_and_remaining_lb`, and `tests/frontend/weight-label.test.mjs` exact-shape cases | ✅ COMPLIANT |
| WT-2 Multi-Unit Presentation | Update canonical kg | `test_update_on_duplicate_date`, `test_weight_entries_include_display_units`, and shared production formatter use in all views | ✅ COMPLIANT |
| WT-3 BMI Presentation | Height is configured | `test_bmi_with_configured_height`, `test_weight_entries_bmi_with_height`, `test_weight_summary_has_display_units` | ✅ COMPLIANT |
| WT-3 BMI Presentation | Height is absent | `test_bmi_without_height_is_none`, `test_weight_entries_include_display_units`; SPA `bmiLabel(null)` renders `—` | ✅ COMPLIANT |
| WT-4 Settings Contract | Save height | `test_settings_save_height`, `test_weight_entries_bmi_with_height` | ✅ COMPLIANT |
| WT-4 Settings Contract | Submit retired setting | `test_settings_retired_key_rejected` | ✅ COMPLIANT |
| TR-1 Checkpoint Thresholds | Use earliest entry | `test_thresholds_use_earliest_entry_without_override`, `test_baseline_uses_oldest_date` | ✅ COMPLIANT |
| TR-1 Checkpoint Thresholds | Use configured override | `test_thresholds_use_configured_override`, `test_start_weight_override_wins` | ✅ COMPLIANT |
| TR-2 Active Reward State | Earn checkpoints inclusively | `test_active_checkpoints_inclusive_equality`, `test_rewards_checkpoints_earned_via_upserts` | ✅ COMPLIANT |
| TR-2 Active Reward State | Revoke after regression | `test_rewards_regression_revokes_checkpoints` | ✅ COMPLIANT |
| TR-3 Mutation Reconciliation | Upsert changes latest progress | `test_rewards_checkpoints_earned_via_upserts`, `test_rewards_regression_revokes_checkpoints` | ✅ COMPLIANT |
| TR-3 Mutation Reconciliation | Historical upsert changes start | `test_rewards_historical_upsert_changes_start` | ✅ COMPLIANT |
| TR-3 Mutation Reconciliation | Delete changes governing entries | `test_rewards_delete_reconciles`, `test_startup_reconciles_active_rewards` | ✅ COMPLIANT |
| TR-4 Re-Earning | Re-earn after renewed progress | `test_rewards_reenroll_refreshes_earned_at` | ✅ COMPLIANT |
| LT-1 Local Persisted Time | Persist local event times | `test_weight_created_at_uses_local_time`, `test_notification_sent_at_uses_local_time`, `test_scheduler_persists_sent_at_from_tick` | ✅ COMPLIANT |
| LT-1 Local Persisted Time | Re-earned reward timestamp | `test_rewards_reenroll_refreshes_earned_at` | ✅ COMPLIANT |
| LT-2 Local Scheduler Semantics | Scheduled type becomes due | `test_due_checks_fire_once_then_dedupe`, `test_due_checks_respects_scheduled_times` | ✅ COMPLIANT |
| LT-2 Local Scheduler Semantics | Schedule is disabled | `test_due_checks_respects_scheduled_times` | ✅ COMPLIANT |
| LT-3 Calendar-Day Deduplication | Repeated DST hour | `test_dst_repeated_hour_sends_once` | ✅ COMPLIANT |
| LT-3 Calendar-Day Deduplication | Skipped DST time | `test_dst_skipped_time_fires_on_next_tick` | ✅ COMPLIANT |
| LT-3 Calendar-Day Deduplication | Next local day | `test_due_checks_fire_once_then_dedupe` | ✅ COMPLIANT |
| LT-4 Conditional Release Polish | Forecast meets gate | Conditional policy branch preserved by `design.md` and `tasks.md`; not activated by this over-budget change | ✅ COMPLIANT |
| LT-4 Conditional Release Polish | Forecast exceeds gate | `tasks.md` and `apply-progress.md`: final forecast exceeded 400 lines and both polish items were deferred | ✅ COMPLIANT |

**Compliance summary**: 25/25 scenarios compliant.

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Canonical Weight Mutations | ✅ Implemented | SQLite upsert uniqueness and delete behavior reconcile dependent active rewards. |
| Multi-Unit Presentation | ✅ Implemented | `units.py` uses the specified factor/decomposition; `static/format.js` emits exactly `kg (lb; st lb)` and is shared by all weight views. |
| BMI Presentation | ✅ Implemented | Calculations use unrounded kg/height; SPA rounds only for display and renders `—` when absent. |
| Settings Contract | ✅ Implemented | Positive nullable `height_cm` is supported; unknown and retired keys are rejected. |
| Checkpoint Thresholds | ✅ Implemented | `(10, 25, 50, 75, 100)` and override/earliest-start behavior match the spec. |
| Active Reward State | ✅ Implemented | Latest-dated weight and inclusive thresholds determine only currently active checkpoints. |
| Mutation Reconciliation | ✅ Implemented | Startup, upsert, delete, and reward-affecting settings reconcile transactionally. |
| Re-Earning | ✅ Implemented | Revoked rows are deleted; reinserted rows receive a fresh local timestamp. |
| Local Persisted Time | ✅ Implemented | `_local_now` and scheduler tick-derived `sent_at` use host-local wall time. |
| Local Scheduler Semantics | ✅ Implemented | Local `HH:MM` checks and empty-string disable behavior are runtime tested. |
| Calendar-Day Deduplication | ✅ Implemented | Keys are `(local date, type)` and are consumed for every scheduled attempt, including zero subscriptions. |
| Conditional Release Polish | ✅ Implemented | The selected over-400 branch deferred both optional items together. |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Kg-only canonical storage | ✅ Yes | Alternate units and BMI are derived; no alternate-unit persistence is used. |
| Pure `units.py` and `rewards.py` logic | ✅ Yes | Formulas and state derivation remain free of I/O. |
| `active_rewards` replaces event history | ✅ Yes | Active rows use checkpoint percentage as the primary key; revoked history is removed. |
| Async request boundary | ✅ Yes | Route database calls use `await run_db(...)`; blocking work is kept off the event loop. |
| Reconcile after mutations and startup | ✅ Yes | Reconciliation runs transactionally after relevant mutations and at startup. |
| Host-local naive timestamps/day keys | ✅ Yes | `_local_now`, scheduler `datetime.now()`, and tick-derived `sent_at` match the design. |
| Routes serialize; SPA rounds/renders | ✅ Yes | API supplies raw values; the shared production formatter handles one-decimal presentation. |
| Conditional polish gate | ✅ Yes | Apply measured over budget and deferred both icons and local unsubscribe. |
| Pyright configuration | ⚠️ Unverified in this environment | Configuration exists, but Pyright's known zero-output hang prevents an independent result; it is not the configured build gate. |

Recorded apply deviations are coherent and non-blocking: thin route serializers reuse `units.weight_display`; BMI is omitted for meaningless delta values; tasks 1.3/1.4 landed atomically; the SPA required a larger rewrite; the VAPID reload fix has passing regressions; and task 3.2 followed the explicit deferral branch.

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD evidence reported | ✅ | `apply-progress.md` contains RED/GREEN/triangulation/safety-net tables for all implementation slices. |
| All behavior tasks have tests | ✅ | 7/7 behavior tasks have current automated regression coverage; task 3.1's formatter now has six tests against the production helper. |
| RED confirmed (tests exist) | ✅ | All referenced Python files exist, and `tests/frontend/weight-label.test.mjs` exists for the remediated UI contract. |
| GREEN confirmed | ✅ | 76/76 pytest tests and 6/6 node tests pass on the current revision. |
| Triangulation adequate | ✅ | Backend behaviors cover boundary and mutation variants; the frontend helper covers full, partial, null, bare-kg, and rounding variants. |
| Safety net for modified files | ✅ | Apply records the Python safety nets; the remediation adds production-helper regression coverage while the complete pytest suite remains green. |

**TDD Compliance**: 6/6 checks passed on the current remediated tree.

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 38 | 4 | pytest (`test_units.py`, `test_rewards.py`, `test_notifications.py`) + node:test (`weight-label.test.mjs`) |
| Integration | 44 | 3 | pytest + httpx ASGITransport / temporary SQLite (`test_weight.py`, `test_api.py`, `test_scheduler.py`) |
| E2E / browser | 0 | 0 | Not installed; E2E is out of scope |
| **Total** | **82** | **7** | |

### Changed File Coverage

Coverage analysis skipped — no coverage tool is configured.

### Assertion Quality

**Assertion quality**: ✅ All reviewed assertions call production behavior and verify meaningful values. No tautologies, assertion-free production paths, ghost loops, smoke-only assertions, or mock-heavy files were found in the seven test files.

### Quality Metrics

**Linter**: ➖ Not available  
**Type Checker**: ⚠️ Not configured as a verify quality command; the known project-venv Pyright process hangs with zero output in this environment  
**JavaScript syntax**: ✅ `static/format.js` and `static/app.js` passed `node --check`

### Canonical Verification Evidence

The exact canonical verification-evidence preimage hashed by `evidence_revision` is:

```text
change=core-app
revision=b0c8ec8a66ac36fb5095053d5aff51c0e9b2c209
requirements=12/12
scenarios=25/25
tasks=12/12
test_command=.venv/bin/python -m pytest -q
test_exit_code=0
test_output_hash=sha256:5d3c9046c05626641cc7e17b8086f7a90f263f07b91fefbd67fbb44b0d732cb3
frontend_test_command=node --test tests/frontend/weight-label.test.mjs
frontend_test_exit_code=0
frontend_test_output_hash=sha256:e3120c46e450c40ca1fcf21bdde684d5ebc60fcdecd7b609df24c625bb62a091
shape_proof_hash=sha256:01fb2225dc315dd6638c029c4d89b9da7fb33ffedde0d29c7cb6c4e5a716b7ba
runtime_smoke_hash=sha256:5844b46cb53fad0ef431992a55cc333e2326f988dfaad8c8b14cb08a5cab88e4
build_command=
build_exit_code=0
build_output_hash=sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The preimage includes a trailing newline and hashes to `sha256:7e0bc58379535fb0a852ffe5797d7793e30df1c01321beb3c345c4fb2026077b`.

### Issues Found

#### CRITICAL

None.

#### WARNING

1. **Pyright remains unavailable as independent evidence in this environment.** The prior runs consistently timed out with zero output. This does not fail the configured build gate because `openspec/config.yaml` explicitly declares `build_command: ""` and no type checker under `testing.quality`.
2. **An empty disabled schedule is not naturally persistable through the current API/UI path.** The scheduler correctly treats `""` as disabled and the covering scheduler test passes, but the UI sends null for an empty time and settings fallback restores the default. This is an access-path usability gap, not a failure of the tested scheduler semantics.

#### SUGGESTION

None.

### Verdict

**PASS WITH WARNINGS**

The two prior CRITICAL findings are remediated: the production formatter emits the exact required label and six automated frontend tests pass against that same helper. All configured runtime gates pass, all 12 requirements and 25 scenarios are compliant, and the change is ready for archive.
