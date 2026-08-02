# Proposal: Core App

## Intent

Harden the single-user tracker for its first release: reversible target-based rewards, clear weight/BMI displays, local-date consistency, and an initial commit.

## Scope

### In Scope
- Keep kg as canonical storage and v1 input. Render weights as `kg (lb; st lb)`; show BMI in summaries, history, and chart tooltips when height exists.
- Add `height_cm` settings; BMI = `current_kg / (height_cm / 100)^2`, otherwise `—`.
- Replace kg-step rewards with 10%, 25%, 50%, 75%, and 100% checkpoints from start (override or earliest entry) to target: `start - checkpoint × (start - target)`.
- A checkpoint is active only when latest-dated weight is at/below its threshold. Reconcile on upsert/delete; remove it above threshold and re-earn it below. Retire kg-step settings.
- Use local time for timestamps, scheduler, and daily dedupe; remove `RewardMilestone`; configure Pyright; create the initial conventional commit.
- Include manifest icons and local unsubscribe only if the full forecast is ≤400 changed lines; otherwise defer them.

### Out of Scope
- Streaks, export, trends/EMA, auth, multi-user support, full device management, unit-aware input, E2E, and revoked-reward history.

## Capabilities

### New Capabilities
- `weight-tracking`: kg-canonical tracking with multi-unit and BMI presentation.
- `target-progress-rewards`: target-progress checkpoints with active-state revocation.
- `local-time-notifications`: local-time persistence and scheduled-notification day semantics.

### Modified Capabilities
- None — `openspec/specs/` is currently empty.

## Approach

Keep conversion/reward logic pure in `rewards.py`; persist settings and active rewards in `database.py`; serialize in `routes.py`; render in the SPA. Add unit, regression, deletion, local-time, and API tests.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `rewards.py`, `database.py`, `models.py` | Modified | Rewards, settings, cleanup |
| `routes.py`, `static/`, `tests/` | Modified | Display/API and regression coverage |
| `scheduler.py`, `pyrightconfig.json` | Modified/New | Local time and type-checking |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Reward semantics surprise users | Med | Visible active state; regression tests |
| Local-time change affects rows | Low | Back up SQLite first |
| Polish exceeds budget | Med | Defer it first |

## Rollback Plan

Revert the initial commit and restore the pre-change SQLite backup if needed.

## Dependencies

- No new runtime dependencies.

## Success Criteria

- [ ] All checkpoints and revocation/re-earn paths pass tests.
- [ ] API/UI uses kg, lb, st, and correct configured-height BMI.
- [ ] Local-date behavior, pytest, and Pyright pass; the repository has an initial conventional commit.
