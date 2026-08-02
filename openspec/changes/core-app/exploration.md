# Exploration: core-app

## Current State

A working single-user weight-loss tracker scaffold (FastAPI 0.141 + stdlib sqlite3 + vanilla JS SPA, no build step, no auth). **37 tests passing** (`pytest -q` run verified, 0.20s). Git repo exists but **nothing is committed yet** — all files untracked.

### Architecture (module-per-concern)

| Module | LOC | Role |
|---|---|---|
| `main.py` | 68 | `create_app` factory, lifespan (scheduler start/stop), `init_app_state`, static mount |
| `routes.py` | 291 | 12 `/api/*` endpoints, pydantic validation, serialization |
| `database.py` | 288 | `Database` class (one connection + RLock, manual `BEGIN`/`COMMIT`), `run_db` thread helper |
| `rewards.py` | 67 | Pure milestone math (baseline/current/lost, milestone levels, progress) — no I/O |
| `notifications.py` | 99 | VAPID load/generate/persist, `send_push`, `send_to_all` (asyncio.gather) |
| `scheduler.py` | 59 | asyncio loop (60 s tick), daily due-check, dedupe via `notifications_sent` |
| `constants.py` | 71 | Logger factory, defaults, notification messages (3 types) |
| `models.py` | 47 | Dataclasses: `WeightEntry`, `PushSubscription`, `RewardMilestone` (**unused**), `AppSettings` |
| `static/` | ~671 | `index.html` (102), `app.js` (350), `sw.js` (43), `style.css` (176), `manifest.webmanifest` |
| `tests/` | 472 | conftest harness + 37 tests (8 weight, 12 rewards, 13 api, 3 scheduler, 1 impl detail) |

### Data model (5 tables)

`weight_entries` (date UNIQUE, upsert semantics), `push_subscriptions` (endpoint UNIQUE), `reward_events` (milestone_kg UNIQUE, earned_at), `notifications_sent` (PK date+type, scheduler dedupe), `settings` (key/value, defaults in `constants.DEFAULT_SETTINGS`).

### API surface (12 endpoints)

- Weight: `GET /api/weight` (entries + summary), `POST /api/weight` (201 create / 200 update), `DELETE /api/weight/{id}` (404 if missing)
- Rewards: `GET /api/rewards` (milestones, earned_count, reward_total_kg, next_milestone_kg, progress_to_next)
- Settings: `GET/PUT /api/settings` (target, milestone step, start override, 3 schedule times)
- Push: `GET /api/push/vapid-public-key`, `POST /api/push/subscribe`, `POST /api/push/unsubscribe`, `POST /api/push/test`
- Manual: `POST /api/notify/{tip|reminder|exercise}` (404 on unknown type)
- `GET /` → index.html

### Test harness (`tests/conftest.py`)

tmp_path DB + tmp VAPID keys, `start_scheduler=False`, autouse `stub_push` monkeypatch on `notifications.send_to_all` — **no real web push ever sent in tests**; payloads recorded for assertions. Async fixtures use `@pytest_asyncio.fixture`, async tests use `@pytest.mark.asyncio` (strict mode).

## Feature Coverage (the 4 user requirements)

| Requirement | Present? | Evidence |
|---|---|---|
| **Push notifications: weight-loss tips + reminders** | ✅ Full | `tip` (09:00) + `reminder` (20:00) notification types; VAPID key gen/persist (`vapid_keys.json`); subscribe/unsubscribe/test endpoints; `sw.js` push + notificationclick handlers; scheduler fires per type once per day with `notifications_sent` dedupe (tested) |
| **Exercise encouragement** | ✅ Full | `exercise` (17:00) type, scheduled + manual trigger, dedicated message; time configurable/disable-able via `""` |
| **Weight logging system** | ✅ Full | Upsert-by-date CRUD, date/weight validation (422s), newest-first history, summary (baseline/current/lost/target/remaining), canvas line chart, delete with 404, settings (target, start-weight override) |
| **Reward system for lost weight** | ✅ Present | Milestones every `milestone_step_kg` (default 1.0), `rewards.reconcile_milestones` on upsert, rewards API + UI (total, next, progress bar, earned list with ✓), `start_weight_override` for baseline |

## Gaps, Rough Edges, and Design Decisions Worth Revisiting

1. **Rewards are cumulative and never revoked.** `reconcile_milestones` only inserts; weight gain or entry deletion never un-earns a milestone. Probably deliberate, but MUST be a stated decision in the spec (with regression tests locking it in) — today it is only implicit.
2. **`RewardMilestone` dataclass is dead code.** Defined in `models.py`, never used — routes build raw dicts. Delete or wire in.
3. **Timezone inconsistency.** DB timestamps (`created_at`, `earned_at`, `sent_at`) use SQLite `datetime('now')` = UTC; the scheduler and dedupe keys use local `datetime.now()`. On a non-UTC host the daily-dedupe date and displayed timestamps diverge from user expectation. Standardize (local time is the right call for a single-user localhost app).
4. **No type-checker/linter configured.** Pyright reports 12 import errors — all false positives from not pointing at `.venv` (no pyrightconfig / python.analysis env). Tests pass; the noise blocks a clean type-check gate. Add config or accept.
5. **Frontend (350 LOC app.js) is entirely untested; no E2E layer.** Chart, push-enable flow, form validation all uncovered. `testing-capabilities.md` confirms e2e = ❌.
6. **No subscription management UI.** Unsubscribe endpoint exists but the frontend only enables push and sends a test to *all* devices; no device list, no per-device disable.
7. **`manifest.webmanifest` has no `icons`** — degraded PWA installability.
8. **Scheduler marks a type "sent" even with zero subscriptions** (fires once per day per type regardless) — tested behavior, fine, but document it.
9. **Manual/test notifications bypass `notifications_sent`** — a manual tip at 09:05 does not suppress the scheduled 09:00 tip. Fine, but undocumented.
10. **No upper bound on `weight_kg`** (only `gt=0`; 500 kg passes) and `remaining_kg` can go negative past target.
11. **`_due_today` uses string compare `"HH:MM"`** — safe only because `_valid_time` zero-pads; a hand-written DB value like `"9:00"` would misbehave.
12. **Everything is untracked in git** — first commit is part of this change's scope.

## Affected Areas

- `routes.py` — reward serialization (dead `RewardMilestone`), weight validation bounds, `remaining_kg` semantics
- `database.py` — timestamp columns (UTC → local), any reconcile/revocation logic
- `models.py` — remove or use `RewardMilestone`
- `scheduler.py` — timezone source for due-check/dedupe
- `constants.py` — defaults if revocation/streak/export knobs added
- `static/app.js` + `static/index.html` — subscription UI, manifest icons, any new fields
- `static/manifest.webmanifest` — add icons
- `tests/` — new regression tests (no-revocation, timezone, validation bounds)
- `pyrightconfig.json` (new) — point at `.venv` to silence false import errors

## Approaches

1. **Baseline hardening (recommended)** — first commit + documented behavior decisions + small real fixes.
   - Pros: small diff, reviewable; turns the implicit "cumulative rewards" decision into an explicit spec requirement with tests; fixes timezone drift; removes dead code; silences Pyright noise; git history starts clean
   - Cons: no new user-facing features; some items (timezone, dead code) are low glamour
   - Effort: **Low–Medium**

2. **Core + feature additions** — everything in (1) plus real features (streak tracking, trend line/EMA, weight export, per-device subscription management, manifest icons + install polish).
   - Pros: delivers user value beyond the scaffold; subscription UI closes a real gap
   - Cons: bigger diff, risks blowing the 400-line review budget; needs chained PRs or a bigger budget
   - Effort: **High**

3. **Contract-only (no code)** — write the spec/design documenting current behavior, no changes.
   - Pros: zero risk, fast
   - Cons: leaves known rough edges (timezone, dead code, untested frontend) in place; weak "core-app" deliverable
   - Effort: **Low**

## Recommendation

**Approach 1 (baseline hardening), plus manifest icons and a subscription-list/disable UI only if the budget allows.** Rationale: the scaffold already delivers all four required features and is well tested on the backend; the highest-value work for a "core-app" change is (a) making the implicit reward semantics an explicit, tested contract, (b) fixing the timezone inconsistency, (c) removing dead code and Pyright noise, and (d) landing the first commit. Defer streak/export/trend features to a follow-up change — that keeps this one within the 400-line review budget.

Suggested spec requirements to capture: cumulative rewards never revoked (explicit), local-time scheduling, weight bounds (0 < w ≤ 500), subscription management scope, and the zero-subscription "fires once per day" dedupe rule.

## Risks

- **Reward-revocation decision is product-level**: if the user actually wants milestones to un-earn on weight gain, the data model needs an "epoch/streak" concept — flag for confirmation before spec.
- **Timezone change touches persisted data**: existing rows carry UTC `earned_at`/`created_at`; a migration or accepted inconsistency is needed (single-user, low impact).
- **No browser/E2E layer**: frontend regressions would go undetected; recommend at minimum a manual smoke checklist in verify, or a Playwright smoke test as a stretch task.
- **Pyright import noise is config, not code**: don't "fix" by editing imports.

## Ready for Proposal

**Yes.** The orchestrator should tell the user: the app fully covers all 4 requested features; the proposal should be scoped as "core-app baseline hardening" (Approach 1) with one product question to confirm — should earned rewards ever be revoked on weight gain, or stay cumulative? (Recommend: cumulative, documented.) Optionally confirm whether subscription-management UI and PWA icons are in scope.
