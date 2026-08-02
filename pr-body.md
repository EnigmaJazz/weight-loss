# feat(rewards): checkpoint-based rewards foundation (slice 1 of 3)

Implements SDD change **core-app**, slice 1 — the foundation for unit conversions,
checkpoint-based rewards, and the new reward storage schema. Built with strict TDD
(RED → GREEN per work unit, 65/65 tests green).

## Chain Context

| Field | Value |
|-------|-------|
| Chain | core-app (stacked to main) |
| Tracker PR | Not needed |
| Position | 1 of 3 |
| Base | `main` |
| Depends on | None |
| Follow-up | PR #2 — API + scheduler (slice 2) |
| Review budget | 826 slice lines (672+/154−; see note) / 400 |
| Starts at | empty `main` (scaffold baseline commit included, ~2700 lines) |
| Ends with | units helpers + checkpoint rewards persisted transactionally |

> **Budget note**: 826 changed lines excludes the scaffold baseline commit
> (`chore: establish weight tracker baseline`, unavoidable as PR #1 from an empty
> `main`). The slice itself is ~270 production lines + ~400 test lines + ~66 doc
> lines. The user-approved chain places work unit 1 as PR #1 (tasks.md suggested
> split). If a tighter review unit is wanted, slice 2 can be split further.

### Chain Overview

```text
main
 └── 📍 #1 This PR — foundation (units, rewards, schema/settings)
      └── #2 API + scheduler (kg/lb/st/BMI summaries, local scheduler)
           └── #3 SPA, Pyright, cleanup (frontend + tooling)
```

### Scope

- **Includes**: `units.py` (kg→lb, kg→stone, BMI, display view); checkpoint rewards
  redesign (`rewards.py` — thresholds 10/25/50/75/100, active/revoked, next
  checkpoint, band progress); storage migration `reward_events` → `active_rewards`;
  local wall-clock timestamps; `height_cm` setting; retired `milestone_step_kg`
  rejected; transactional reward reconciliation on startup/upsert/delete/settings.
- **Excludes**: API endpoint expansion (2.1), scheduler local-time (2.2), SPA
  (3.1/3.2), Pyright/AGENTS (4.1), dead-code cleanup (4.2).

### Autonomy

- [x] CI is expected to pass for this PR branch (65/65 tests green)
- [x] This PR has one deliverable scope (foundation)
- [x] This PR can be rolled back without unrelated changes (revert to `main`)
- [x] Tests, docs, or manual verification cover this unit (unit + ASGI integration)

## Verification plan

- Focused: `.venv/bin/python -m pytest tests/test_units.py tests/test_rewards.py` → 30 passed
- Full: `.venv/bin/python -m pytest -q` → **65 passed in 0.30s** (was 37 at baseline)
- Runtime: httpx `ASGITransport` integration covers upsert→earn, regression→revoke,
  re-earn with fresh local `earned_at`, historical-upsert start change, delete
  reconcile, settings-update reconcile, retired-key 422, local timestamps.
- Slice 2 will run `sdd-verify` against the full spec set.
