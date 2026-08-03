# Archive Report: core-app

**Change**: core-app
**Archived**: 2026-08-03
**Archived to**: `openspec/changes/archive/2026-08-03-core-app/`
**Final revision**: `11581a2` (main, matching `origin/main`)
**Verdict at close**: PASS WITH WARNINGS — admitted verify-report (`verify-report.md`), 0 blockers, 0 CRITICAL findings

## Final State

The change is fully implemented, verified, and closed. The final admitted `verify-report.md`
(recorded at `11581a2`) reports **12/12 requirements compliant, 25/25 scenarios compliant,
12/12 tasks complete, verdict PASS WITH WARNINGS** with `critical_findings: 0` and
`blockers: 0`.

Final automated test evidence at close (per the admitted verify-report):

| Suite | Command | Result |
|-------|---------|--------|
| Python (pytest) | `.venv/bin/python -m pytest -q` | 76 passed, exit 0 |
| Frontend formatter (node:test) | `node --test tests/frontend/weight-label.test.mjs` | 6 passed, exit 0 |
| JS syntax | `node --check static/format.js && node --check static/app.js` | exit 0 |
| Build gate | `build_command: ""` (config-declared) | exit 0, empty output hash |

Task 3.2 (conditional polish) is complete **through its explicit deferral branch**: the final
authored forecast (1,142 changed lines) exceeded the 400-line gate, so manifest icons and the
local-unsubscribe UI action were deferred together per the Conditional Release Polish
requirement. The persisted `tasks.md` records this branch explicitly and shows 12/12 `[x]`
with zero unchecked implementation tasks.

### Final-State Authority Notes

- The first verify run found a UI formatting defect; it was remediated in commit `b0c8ec8`
  (weight label rendered as `kg (lb; st lb)` via the shared formatter extracted to
  `static/format.js`, with six node:test regressions in `tests/frontend/weight-label.test.mjs`).
  The final admitted verify-report is the terminal record and supersedes the earlier snapshot.
- The earlier pyright environment hang is **not** a build gate: `openspec/config.yaml`
  declares `build_command: ""` and no type checker under `testing.quality`. The final
  verify-report records `build_command: ""` / `build_exit_code: 0`.
- Commit `11581a2` records the final `tasks.md` + `verify-report.md`; all three slice PRs
  merged to `main`; `HEAD == origin/main == 11581a2`.

## Spec Sync

`openspec/specs/` held no main specs before this archive (only `.gitkeep`), so every delta
spec under `openspec/changes/core-app/specs/` is a **full spec**, not a delta. Each was copied
verbatim to `openspec/specs/{domain}/spec.md` — all ADDED, none MODIFIED/REMOVED/RENAMED.

| Domain | Action | Details |
|--------|--------|---------|
| weight-tracking | Created | 4 requirements, 8 scenarios copied to `openspec/specs/weight-tracking/spec.md` |
| target-progress-rewards | Created | 4 requirements, 8 scenarios copied to `openspec/specs/target-progress-rewards/spec.md` |
| local-time-notifications | Created | 4 requirements, 9 scenarios copied to `openspec/specs/local-time-notifications/spec.md` |

**Destructive-delta assessment** (`rules.archive`: "Warn before merging destructive deltas"):
no destructive merge occurred — no requirements were REMOVED or RENAMED, and no existing main
spec was modified. The warning rule is assessed and does not trigger.

## Archive Contents

- `proposal.md` ✅
- `exploration.md` ✅ (optional exploration artifact, preserved)
- `specs/` ✅ (3 domain delta/full specs: weight-tracking, target-progress-rewards, local-time-notifications)
- `design.md` ✅
- `tasks.md` ✅ (12/12 tasks complete; 3.2 complete via deferral branch; 0 unchecked)
- `apply-progress.md` ✅ (slices 1–3, incl. slice-3 re-verification pass)
- `verify-report.md` ✅ (admitted PASS WITH WARNINGS, 0 CRITICAL)
- `archive-report.md` ✅ (this record)

## Gates

| Gate | Result | Evidence |
|------|--------|----------|
| Native Review Receipt | ✅ Allow | Orchestrator launch prompt asserts review receipt present; admitted verify-report (`verdict: pass`, `blockers: 0`, `critical_findings: 0`) recorded at `11581a2`. No engram review topics exist in this openspec-mode backend. |
| Task Completion | ✅ Pass | `tasks.md`: 12/12 `[x]`, 0 unchecked implementation tasks; 3.2 completed via its own conditional deferral branch |
| CRITICAL findings | ✅ None | `verify-report.md`: `critical_findings: 0`, `blockers: 0` |

No exceptional archive-time reconciliation was performed — no stale checkboxes required repair.

## Warnings Carried Forward (non-blocking)

1. **Pyright unavailable as independent evidence in this environment** — the process hangs
   with zero output (documented across apply-progress and verify-report). Not the configured
   build gate (`build_command: ""`); must be run in CI / a normal shell.
2. **Empty disabled schedule not naturally persistable via the current API/UI path** — the
   scheduler semantics are correct and tested (`""` = disabled), but the settings path maps a
   null time back to the default. Access-path usability gap, recorded as a WARNING in the
   admitted verify-report; out of scope for this change.
3. **Latent VAPID reload bug was fixed in-scope** (slice 3, commit `625d61e`): py_vapid 1.9.4
   `Vapid.from_raw` crashes on str keys; fixed with `encode("ascii")` and two regression tests
   in `tests/test_notifications.py`. Not an open issue at close.

## Source of Truth Updated

The following main specs now reflect the delivered behavior:

- `openspec/specs/weight-tracking/spec.md`
- `openspec/specs/target-progress-rewards/spec.md`
- `openspec/specs/local-time-notifications/spec.md`

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived. Ready for the next change.
