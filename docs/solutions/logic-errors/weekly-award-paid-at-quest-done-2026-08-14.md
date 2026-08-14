---
title: "Pay weekly awards atomically when the quest becomes done, not deferred to a later read"
date: 2026-08-14
category: logic-errors
module: rewards (weekly objectives, r2-completion S2)
problem_type: logic_error
component: database
symptoms:
  - "The 40-XP weekly award for a met objective was persisted only when GET /api/weekly happened to be read, so XP/level could be stale at the exact moment a quest was completed"
  - "Verify flagged R6 as CRITICAL: award payment deferred to a read instead of paid at the quest-done transition"
  - "The Today XP chip and level-up signal could disagree with the weekly state between completion and the next weekly read"
root_cause: logic_error
resolution_type: code_fix
severity: critical
related_components:
  - service_object
tags:
  - weekly-objectives
  - awards
  - xp
  - exactly-once
  - atomic-payment
  - quest-completion
  - derived-read
---

# Pay weekly awards atomically when the quest becomes done, not deferred to a later read

## Problem

The weekly objectives engine (r2-completion S2) paid its 40-XP award only when `GET /api/weekly` was read: `weekly_state` stamps activation on first read and pays each met goal exactly once on that read. A quest that completed a met objective therefore left the user's XP and level stale until the weekly endpoint happened to be fetched — the reward was deferred to a read, not paid at the transition that earned it.

## Symptoms

- Verify FAIL on R6 (CRITICAL): "weekly +40 award deferred to `GET /api/weekly` instead of paid when the quest becomes done".
- Between completing the tenth exercise quest and the next weekly read, `total_xp_for_user` omitted the +40: the Today chip and the level-up computation were wrong at the moment of completion.
- The read-detection path (auto-complete from log tables) had the same defect: a detected completion paid nothing until a weekly read.

## What Didn't Work

- Keeping payment in the weekly read (`weekly_state`) with the same exactly-once PK. It is exactly-once, but the payment timing is wrong — a reward granted by a transition must be paid at that transition, or every derived read between transition and payment shows stale economy state.

## Solution

Pay the award at the moment the quest transitions to done, in both mutation paths, before any level computation:

1. **Manual completion** (`routes.py::complete_quest`) — after the status write, before computing `level_after`:

```python
updated = await run_db(
    db.update_quest_status, user.id, quest_id, "done", source="manual"
)
if updated is None:
    raise HTTPException(status_code=404, detail="quest not found")
# R6: pay the 40-XP weekly award at the moment the quest completes a met
# objective — before level computation, so level_up reflects the award.
await run_db(db.reconcile_weekly_awards, user.id)
level_after = xp.level_from_xp(
    await run_db(db.total_xp_for_user, user.id)
)
```

2. **Read-detected completion** (`routes.py::_ensure_today_quests`) — only when a detection actually persists a transition (`detection_persisted`), keeping plain reads read-only:

```python
if detection_persisted:
    # R6: a read-detected completion pays the 40-XP weekly award at the
    # moment the objective becomes met — before the caller's next XP read.
    await run_db(db.reconcile_weekly_awards, user.id)
```

Exactly-once is preserved because `reconcile_weekly_awards` upserts on the natural `(user_id, week_start, goal)` primary key — re-running it is idempotent.

## Why This Works

XP is a derived sum (`total_xp_for_user` = done quests + `weekly_awards`). The award row must exist **before** any read that reports the user's economy state. Paying at the transition — inside the request that caused the transition — guarantees the very next XP/level read includes the award. The natural-PK upsert keeps the payment idempotent no matter how many times the reconcile runs, so the transition point is also the exactly-once point.

## Prevention

- **Rule: a reward granted by a transition is paid at that transition, never deferred to a later read.** Derived reads stay read-only; only the mutation that earns the reward may persist the award.
- Cover the timing with focused tests, not just the happy path: mutation timing (award present immediately after complete), non-qualifying no-pay, exactly-once on repeat, level-up includes the award, the read-detection path pays, and two-user isolation. The R6 remediation shipped six such tests (`test_weekly_tenth_quest_pays_immediately` family).
- When a read reconciles/persists state (auto-complete detection), gate the payment on `detection_persisted` so plain reads never mutate.

## Related Issues

- Verify/archive evidence: `openspec/changes/archive/2026-08-14-r2-completion/verify-report.md` (R6 FAIL → PASS after `59452ba`), `apply-progress.md` (R6 section, `met_flips` re-verify note).
- Fix commit: `59452ba fix(weekly): pay award atomically when quest becomes done` (branch `feat/r2-completion-r6-fix`, PR #64).
- Related derived-state pattern (XP sum, momentum): `openspec/changes/archive/2026-08-10-r1-quests-xp/` — derivation works for cumulative totals, but event-style rewards need a transition-time mutation.
