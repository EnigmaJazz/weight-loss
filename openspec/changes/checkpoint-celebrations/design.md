# Design: Checkpoint Celebration Notifications

## Technical Approach

Fire-and-forget celebration push on checkpoint earn. Each earn-capable route captures `before = list_active_rewards`, mutates (the DB method already calls `_reconcile_active_rewards` inside its tx), captures `after`, diffs percents, and sends ONE batched push naming the top newly-earned percent. `earned_at` is the dedupe — a checkpoint in both `before` and `after` is not "newly earned". Reuses `send_to_all(notif_type="checkpoint")`; SW has no tag allowlist (`sw.js` uses `data.tag` verbatim) so zero SW/SPA/scheduler changes. No persisted celebration state.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|---|---|---|---|
| Diff input shape | ActiveCheckpoint dataclasses / dicts | `list[dict]` matching `list_active_rewards` return | Avoids 5× conversion in routes; helper reads only `checkpoint_percent`, stays I/O-free |
| Where orchestration lives | `fire_celebration` in notifications.py (db callback) / helper in routes.py | `_celebrate_if_earned` in routes.py | notifications.py imports neither `database` nor `run_db` today; leaking db in breaks the module boundary. `send_celebration(subs, percent, vapid)` stays pure (pick + send) |
| Message pool location | key inside `NOTIFICATION_MESSAGES` / standalone constant | standalone `CELEBRATION_MESSAGES` | `NOTIFICATION_TYPES` untouched; `test_notifications.py` iterates `NOTIFICATION_TYPES` (not keys()) so standalone is safe; no `/api/notify/checkpoint` |
| Top-percent selection | sort / `max()` | `max(r["checkpoint_percent"] for r in diff)` | One batched push per mutation (proposal decision 1) |
| before/after capture on theme-only settings | guard on REWARD_AFFECTING_KEYS / always capture | always capture, diff no-fires | Uniform 5-route pattern > micro-optimization; `update_settings` skips reconcile for non-reward keys so `after==before` → empty diff |

## Data Flow

```
Route ──> before=list_active_rewards(uid) ──> mutate (reconciles in-tx) ──> after=list_active_rewards(uid)
   │                                                                           │
   └─> _celebrate_if_earned(db, vapid, uid, before, after)
            ├─ diff = newly_earned_checkpoints(before, after)   # rewards.py, pure
            ├─ if diff: top = max(percents); subs = list_subscriptions(uid)
            └─ if subs: send_celebration(subs, top, vapid) ─> send_to_all(notif_type="checkpoint")
```

## Interfaces / Contracts

```python
# rewards.py — pure, I/O-free
def newly_earned_checkpoints(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """after − before by checkpoint_percent. Returns the after-dicts whose percent
    is not in before. Empty list when no new earn (idempotent / revoke-only /
    same-event revoke+re-earn of the same percent)."""
    before_pct = {r["checkpoint_percent"] for r in before}
    return [r for r in after if r["checkpoint_percent"] not in before_pct]
```

```python
# constants.py — standalone, style-matched (no emojis, second-person, exclamations)
CELEBRATION_MESSAGES: tuple[tuple[str, str], ...] = (
    ("Checkpoint unlocked!", "You just hit {percent}% of your goal. Every log got you here."),
    ("Milestone reached", "{percent}% down — that's real progress. Keep showing up."),
    ("{percent}% — nice!", "Another checkpoint in the bag. Future you is cheering."),
    ("Progress check", "You've hit {percent}% toward your target. Data wins again."),
    ("Checkpoint earned", "{percent}% of the way there. The streak's working — log the next one."),
    ("Level up!", "{percent}% reached. Small steps, big chart. Onward."),
)
```

```python
# notifications.py — mirrors pick_message; send_celebration wraps send_to_all
def pick_celebration(percent: int, rng: random.Random | None = None) -> tuple[str, str]:
    title, body = (rng or random).choice(CELEBRATION_MESSAGES)
    return title, body.replace("{percent}", str(percent))

async def send_celebration(subscriptions, percent: int, vapid) -> int:
    title, body = pick_celebration(percent)
    return await send_to_all(subscriptions, title, body, vapid, notif_type="checkpoint")
```

```python
# routes.py — private async helper (db access legal here, not in notifications.py)
async def _celebrate_if_earned(db, vapid, user_id, before, after) -> int:
    diff = newly_earned_checkpoints(before, after)
    if not diff:
        return 0
    top = max(r["checkpoint_percent"] for r in diff)
    subs = await run_db(db.list_subscriptions, user_id)
    if not subs:
        return 0
    return await notifications.send_celebration(subs, top, vapid)
```

## Route Wiring (per route — `request: Request` inserted after path/body params, before Depends, matching `notify_manual`)

| Route | Signature change | Sequence | Return (unchanged) |
|---|---|---|---|
| `complete_onboarding` (750) | `+request` after `payload` | before → `db.complete_onboarding` → after → celebrate | `{"ok": True}` |
| `upsert_weight` (782) | `+request` after `payload` | before → `upsert_entry` → after → celebrate | `JSONResponse(entry_dict)` |
| `edit_weight` (799) | `+request` after `entry_id,payload` | before → try `update_entry` (409/404 raise BEFORE celebrate) → after → celebrate | `_entry_dict` |
| `delete_weight` (827) | `+request` after `entry_id` | before → `delete_entry` (404 raises before celebrate) → after → celebrate | `{"deleted": True}` |
| `put_settings` (1050) | `+request` after `payload` | before → `update_settings` → after → celebrate (theme-only: no reconcile → empty diff → no fire) | `asdict(settings)` |

`before` is read before the mutate; `after` after. On `edit_weight` 409 (`DuplicateDateError` raised inside `update_entry` before reconcile) and 404, the route `raise`s before reaching celebrate → no fire. `delete_entry` reconciles even when `deleted=False`, but `after==before` and the route 404-raises first → no fire.

## File Changes

| File | Action | Description |
|---|---|---|
| `rewards.py` | Modify | +`newly_earned_checkpoints` (add `Any` to typing import); stays pure |
| `constants.py` | Modify | +`CELEBRATION_MESSAGES` standalone tuple |
| `notifications.py` | Modify | +`pick_celebration`, `send_celebration`; import `CELEBRATION_MESSAGES` |
| `routes.py` | Modify | +`_celebrate_if_earned`; `+request: Request` + before/after/celebrate in 5 routes; import `newly_earned_checkpoints` |
| `tests/test_celebrations.py` | Create | integration earn/no-fire/isolation scenarios via `stub_push` |
| `tests/test_rewards.py` | Modify | +diff helper pure units |
| `tests/test_notifications.py` | Modify | +`pick_celebration` determinism/interpolation units |

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit (test_rewards.py) | `newly_earned_checkpoints`: single earn {25}, idempotent [], revoke-only [], same-event revoke+re-earn [], batched {10,25,50}, empty | Direct calls on dict lists |
| Unit (test_notifications.py) | `pick_celebration` seeded determinism (same seed+percent → identical); `{percent}` interpolation (25→"25%", no "{percent}"); pool shape (≥3, all have {percent}) | Seeded `random.Random` |
| Integration (test_celebrations.py) | upsert single earn→1 push names 10; upsert batched {10,25,50}→1 push names 50; idempotent re-POST→0; revoke-only→0; re-earn refire (recover to 94kg→names 25); edit earn→1; edit 409→0; delete baseline-shift earn (del earliest 80, baseline→100, current 90→names 50); delete revoke-only→0; settings target earn→1; settings theme-only→0; onboarding first-entry earn→1 names top; zero-subscriptions→0 + no dedupe row; per-user isolation (pair: alice earns+subs, bob subs→only alice endpoint) | `stub_push` asserts `notif_type=="checkpoint"`, body in `CELEBRATION_MESSAGES`, top percent; threshold math baseline 100/target 80: 10%=98,25%=95,50%=90 |

**Existing-test audit**: `stub_push` is referenced only in push-only contexts — `test_api.py` push_test/manual_notify (use `auth_client`: no weight entries → no checkpoint possible), `test_user_isolation.py` push_test/manual_notify, `test_scheduler.py` disabled-schedule (tip_time, non-reward; `run_due_checks` no earn). None earn checkpoints while asserting push count → **no existing test breaks**. Earn tests (test_api rewards, test_onboarding, test_weight, test_rewards) never reference `stub_push`. Apply MUST run the full suite and re-audit; any test that (subscribes AND earns AND asserts `stub_push`) must expect the checkpoint push.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Earn detection is pure set-difference; delivery reuses the existing `send_to_all` network boundary already guarded by per-push try/except.

## Migration / Rollout

No migration. Rollback = revert the 5 route fire calls + `_celebrate_if_earned` + the 3 new helpers + `CELEBRATION_MESSAGES`. Fire-and-forget with no persisted state — reverting code stops future sends; already-sent pushes are inert.

## Open Questions

- [ ] None blocking. (Confirm at apply: `send_celebration` calling module-global `send_to_all` is captured by `conftest.stub_push`'s `monkeypatch.setattr(notifications_module, "send_to_all", ...)` — it is, since both resolve the same module global.)
