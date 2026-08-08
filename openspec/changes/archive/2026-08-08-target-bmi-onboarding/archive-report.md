# Archive Report: target-bmi-onboarding

**Change**: target-bmi-onboarding
**Archived**: 2026-08-08
**Mode**: Strict TDD
**Final verdict**: PASS — 14/14 requirements, 41/41 scenarios, 349 pytest + 88 node:test + pyright 0 errors, live browser smoke 29/29, CI green on all 4 merged PRs, service restarted on merged main

## Summary

Closed the BMI target goals and onboarding wizard change end-to-end. Users can now set a BMI target (with shared target resolution, healthy-weight-range recommendation, and 3-bucket classification), and first-time users are gated behind a one-time wizard (`POST /api/onboarding`) that atomically collects height, first weight, target, and preferences, exposed to the SPA via `needs_onboarding` on `/api/auth/me`.

Key implementation facts (final state, per orchestrator final-state handoff and merged main at `7ba15ed`):

- All four slice PRs merged to main in order: #27 (rewards/BMI helpers), #28 (routes settings + summary), #29 (onboarding endpoint + flag), #30 (SPA wizard). Merge commit `7ba15ed` = PR #30's merge; `origin/main == local main`.
- `units.py`: `weight_kg_from_bmi`, `healthy_weight_range`, `classify_bmi`, `resolve_target_kg` (shared resolver; `target_weight` wins on both-set).
- `models.py`/`constants.py`: `AppSettings += target_bmi`, `onboarding_complete`; `DEFAULT_SETTINGS` updated.
- `rewards.py`/`database.py`: `reward_state` resolves target via shared helper; `REWARD_AFFECTING_KEYS += target_bmi, height_cm`; per-user reconciliation; `complete_onboarding` single-transaction (settings + entry + reconcile); `_optional_bool` maps `str(bool)`.
- `routes.py`: `SettingsIn.target_bmi` bounds (10, 40] with `extra="forbid"`, bidirectional clearing, `_summary_view += healthy_min_kg/healthy_max_kg/target_status`, `OnboardingIn` (XOR validator, height-checked-before-BMI-bounds), `POST /api/onboarding`, `me()` returns `needs_onboarding`.
- `static/`: SPA wizard (`#onboarding-screen`) between auth gate and tracker; `init()` branches on `needs_onboarding`; wizard non-skippable in v1; existing accounts see the wizard once.
- Service (`weight-loss.service`) restarted and serving merged main at stamp `7ba15ed`.

Spec correction applied pre-merge: healthy weight range for 175 cm is `(56.7, 76.3)` — `bmi-goal-setting` and `weight-tracking` scenario numbers were updated to the formula-consistent values (`round(18.5 × 1.75², 1)` = 56.7; `round(24.9 × 1.75², 1)` = 76.3). Code, tests, SPA, and the live API all agree with the corrected spec values.

Decisions recorded (see `apply-progress.md` and `tasks.md`): shared target resolver in `units.py`; keep both `target_bmi` names (summary vs settings); `target_weight` wins on both-set; bidirectional target clearing; existing accounts flagged once (wizard once); wizard non-skippable v1; `onboarding_complete` stored as `str(bool)` ("True"/"False"), parsed by `_optional_bool`; three classification buckets (underweight <18.5, healthy 18.5–24.9, overweight ≥25).

## Evidence

- Native review gate: `reviewGate` structurally absent in the archive handoff → no receipt exists for this candidate; archive proceeds under ordinary repository policy. No CRITICAL issues in the verification report.
- Full configured suite: `.venv/bin/python -m pytest` → 349 passed, exit 0 (per `verify-report.md` §test_exit_code 0; re-verified on local main per final-state handoff).
- Frontend Node suite: 88 passed (`node --test`), per `verify-report.md`.
- Build: `.venv/bin/pyright` → 0 errors, 0 warnings, 0 informations (verify-report build section).
- Browser smoke: 29/29 steps passed (run during slice 4 against a scratch server; recorded in `verify-report.md` E2E row).
- CI: browser-smoke + test checks passed for every PR at merge time on fresh merge refs (update-branch) (orchestrator final-state handoff).
- Live runtime spot-check (in-process ASGITransport, scratch DB): register → needs_onboarding true → onboarding (h=175, w=80, target_bmi=22) → needs_onboarding false → summary healthy 56.7/76.3, target_status healthy → target_bmi=16 flips target_status to underweight, target_kg 49.0 matches rewards target_kg; bidirectional clearing confirmed. All steps match spec-pinned values.

## Delta Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| bmi-goal-setting | Created | New full main spec `openspec/specs/bmi-goal-setting/spec.md` (mechanical copy, diff-verified) — 4 requirements / 9 scenarios: Shared Target Resolution, BMI Classification, Healthy Weight Range, target_bmi Settings Bounds. |
| target-progress-rewards | Updated | MODIFIED `Checkpoint Thresholds` (shared `weight_kg_from_bmi` target with `target_weight` precedence; adds Resolve target from BMI + Weight precedence scenarios); ADDED `Reward-Affecting Settings Keys` (3 scenarios). All other requirements preserved. |
| user-authentication | Updated | MODIFIED `Authentication API` (`/api/auth/me` returns `needs_onboarding`; adds me-reports-onboarding scenarios). All other requirements preserved. |
| user-onboarding | Created | New full spec `openspec/specs/user-onboarding/spec.md` (mechanical copy, diff-verified) — 5 requirements / 13 scenarios: needs_onboarding Flag, Onboarding Request Contract, Atomic Idempotent Completion, Onboarding Authorization, Wizard SPA Gate. |
| weight-tracking | Updated | MODIFIED `Settings Contract` (now covers `target_bmi` + `onboarding_complete` + unit/schedule prefs; adds Persist target_bmi scenario); ADDED `Weight Summary Contract` (4 scenarios: healthy range, null semantics, target_status, summary/rewards agreement). All other requirements preserved. |

ADDED requirements appended before each spec's `## Acceptance Criteria`; MODIFIED requirement blocks replaced in full with the delta's complete updated text (unchanged scenarios preserved). No REMOVED or RENAMED sections, no destructive delta — the `config.yaml` archive rule "Warn before merging destructive deltas" did not trigger. Merges were model-authored writes per the sync step, then verified structurally (requirement headings, scenario preservation) and by git diff.

## Task Completion

- `tasks.md` (persisted artifact, source of truth for completion): **20/20 tasks checked**, zero unchecked implementation tasks.
- `verify-report.md` states "Tasks total 17 / complete 17" at verification time; `tasks.md` records 20 checked tasks (the discrepancy is the count of the 3 DECISION tasks vs implementation tasks). The archived `tasks.md` is authoritative for completion visibility and shows no stale unchecked boxes; verify-report's count was a snapshot-time enumeration difference, not a missing task — recorded here for audit transparency.

## Rollback

- Code rollback: revert the four merged PRs (or `git revert 7ba15ed` chain); `design.md` documents the safe ordering (helpers → routes → endpoint → SPA) and that orphan `onboarding_complete`/`target_bmi` settings rows are harmless if the endpoint is removed.
- Spec rollback: `openspec/specs/{bmi-goal-setting,user-onboarding}` are new files — delete to revert; the three updated main specs can be reverted from commit history before this archive.
- Data: no destructive migration in this change; existing rows untouched. `onboarding_complete` "True" rows simply re-flag as needing completion if the feature is rolled back (SPA falls back to existing flow).

## Follow-ups (non-blocking)

1. Non-blocking SUGGESTION (verify-report): PR #4 exceeded the 400-line guard (762 insertions — the SPA wizard is one atomic deliverable); reviewer to review by section.
2. Non-blocking SUGGESTION (verify-report): JS `Math.round` (half-up) vs Python `round()` (banker's) may diverge at a .5 boundary in the wizard display hint only — display-only; all spec-pinned values agree; the API remains authoritative.

## Traceability

- Observation IDs read: none — OpenSpec artifact store (filesystem) mode; the archive report is the ledger. Files read at archive time: `proposal.md`, all 5 delta `specs/`, `design.md`, `tasks.md` (full, 20/20 checked), `apply-progress.md`, `verify-report.md` (PASS, 0 CRITICAL/0 WARNING), and the three existing main specs merged (`target-progress-rewards`, `weight-tracking`, `user-authentication`). Previous-archive pattern read: `2026-08-05-user-accounts-auth/archive-report.md`.
- Storage: `openspec/changes/archive/2026-08-08-target-bmi-onboarding/` (all artifacts, `mv` with recursive `diff -r` readback — empty, byte-identical). No Engram artifacts for this change.
- Regression smoke for safe merge: light source rerun of `.venv/bin/python -m pytest` on local main — per final-state handoff, 349 pass.