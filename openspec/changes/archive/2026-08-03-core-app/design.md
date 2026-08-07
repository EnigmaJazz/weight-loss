# Design: Core App

## Technical Approach

Preserve kg-only storage and the async FastAPI/`run_db` boundary. Add pure conversions, derive active checkpoints, and use Python's host-local clock for timestamps and day keys. Routes serialize views; the SPA rounds and renders them.

## Architecture Decisions

| Option | Tradeoff | Decision and rationale |
|---|---|---|
| Reuse `reward_events` | Cannot model fixed percentages or revocation | Replace it with `active_rewards(checkpoint_percent PRIMARY KEY, threshold_kg, earned_at)`. It preserves timestamps only while active; deletion makes re-earning timestamp anew. |
| Put units in rewards/routes | Mixes concerns or duplicates formulas | Create pure `units.py`; one backend representation and frontend formatter make rounding explicit. |
| Configurable timezone | Adds settings and timezone rules outside scope | Use host-local `datetime.now()` and naive ISO wall times, matching localhost-first deployment. |
| Reconcile in reads | Mutates GET requests | Reconcile after startup, weight upsert/delete, and reward-affecting settings updates. |

## Data Flow

    POST/DELETE weight or PUT settings -> SQLite mutation
      -> reward_state(entries, settings; latest=max(date)) -> reconcile_active_rewards
      -> GET APIs -> units-derived views -> SPA formatter/chart tooltip

Every 60 seconds the scheduler supplies `datetime.now()`. `run_due_checks` compares local `HH:MM`, keys `(now.date().isoformat(), type)`, sends, then records the attempt even with zero subscriptions. Repeated DST hours dedupe; skipped times fire on the next tick.

## File Changes

| File | Action | Description |
|---|---|---|
| `units.py` | Create | Pure conversions, BMI, and display-view construction. |
| `models.py` | Modify | Remove confirmed-unused `RewardMilestone` and milestone step; add `height_cm` and typed display/checkpoint state. |
| `rewards.py` | Modify | Implement thresholds, active state, next checkpoint, and band progress. |
| `database.py` | Modify | Migrate storage; write local timestamps; reconcile active rewards transactionally. |
| `main.py` | Modify | Reconcile derived rewards once after schema initialization. |
| `routes.py` | Modify | Forbid unknown settings, expose display data, reconcile mutations, and serialize rewards. |
| `constants.py` | Modify | Remove milestone-step default; add `height_cm: None`. |
| `scheduler.py` | Modify | Retain injected `now` checks; ensure persisted `sent_at` comes from that local tick. |
| `static/index.html`, `static/app.js`, `static/style.css` | Modify | Add height/BMI, shared unit rendering, checkpoints, tooltip, and local date construction. |
| `static/manifest.webmanifest`, `static/icons/*` | Conditional | Add 192/512 icons only when the apply forecast is <=400 changed lines. |
| `pyrightconfig.json`, `AGENTS.md` | Create/Modify | Configure `.venv`, update module docs. Smoke: `pyright -p pyrightconfig.json`. |
| `tests/test_rewards.py`, `tests/test_api.py`, `tests/test_weight.py`, `tests/test_scheduler.py` | Modify | Replace obsolete contracts and add required regressions. |

## Interfaces / Contracts

```python
CHECKPOINTS: tuple[int, ...] = (10, 25, 50, 75, 100)
def checkpoint_thresholds(start: float, target: float) -> list[tuple[int, float]]: ...
def active_checkpoints(start: Optional[float], target: Optional[float], current: Optional[float]) -> list[tuple[int, float]]: ...
def reward_state(entries: Sequence[WeightEntry], settings: AppSettings) -> RewardState: ...
def progress_to_next_checkpoint(start: Optional[float], target: Optional[float], current: Optional[float]) -> float: ...
def kg_to_lb(weight_kg: float) -> float: ...
def kg_to_stone(weight_kg: float) -> tuple[int, float]: ...
def calculate_bmi(weight_kg: float, height_cm: Optional[float]) -> Optional[float]: ...
```

`GET /api/weight` keeps canonical `*_kg` and adds raw `lb`, `stone`, `stone_lb`, and `bmi` objects for entries and summary values. Settings includes `height_cm`; PUT rejects `milestone_step_kg`. Rewards returns `active_checkpoints[{percent,threshold_kg,earned_at}]`, `earned_count`, `next_checkpoint|null`, and `progress_to_next`. The SPA rounds to one decimal.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Five thresholds, equality, active/revoked state, band progress, lb/stone/BMI | Replace obsolete step-based cases in `test_rewards.py`; add `test_units.py`. |
| Integration | Mutation/settings reconciliation, revocation/re-earning, APIs, validation, local timestamps | Extend ASGI tests and inspect temp SQLite. Existing step/default assertions must change. |
| Scheduler | Local day, disabled types, zero-subscription dedupe, DST repeat/skip | Extend injected-naive-datetime tests; assert `sent_at`. |
| UI | Summary/history/tooltip and conditional polish | Manual browser smoke; E2E remains out of scope. |

## Threat Matrix

| Boundary | Applicability | Reason |
|---|---|---|
| Documentation-like paths | N/A | No executable-file classification. |
| Git repository selection | N/A | No Git automation; apply uses the confirmed project root. |
| Commit state | N/A | Initial commit is an operator work unit, not application/process logic. |
| Push state | N/A | No Git push is designed. |
| PR commands | N/A | No PR automation is designed. |

## Migration / Rollout

Back up SQLite first. `init_schema` drops `reward_events`, creates `active_rewards`, deletes stored `milestone_step_kg`, and preserves old timestamps because UTC-to-local conversion is ambiguous; new timestamps are local. Startup derives active rows. First commit the verified 37-test scaffold, OpenSpec artifacts, and tooling files (excluding DB, VAPID, `.venv`) as `chore: establish weight tracker baseline`; then implement tested work units.

Polish gate: during task forecasting, include both manifest icons and current-browser unsubscribe (`getSubscription()`, API unsubscribe, then `subscription.delete()`) only at <=400 changed lines; otherwise defer both.

## Open Questions

None blocking; the apply forecast resolves the polish gate.
