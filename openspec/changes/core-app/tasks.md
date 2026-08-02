# Tasks: Core App

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900–1,200 total; per task below |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 foundation; PR 2 backend; PR 3 frontend/tooling |
| Delivery strategy | ask-on-risk (resolved: chained PRs, stacked-to-main) |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes — resolved: chained PRs, stacked-to-main
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Units, rewards, schema/settings (~300–400 lines) | PR 1 | `.venv/bin/python -m pytest tests/test_units.py tests/test_rewards.py` | SQLite tmp-path fixture | `units.py`, `rewards.py`, models/database changes |
| 2 | API and scheduler (~250–350 lines) | PR 2 | `.venv/bin/python -m pytest tests/test_api.py tests/test_scheduler.py` | `httpx.ASGITransport` | `routes.py`, `main.py`, `scheduler.py` |
| 3 | SPA, Pyright, docs (~300–400 lines) | PR 3 | `.venv/bin/python -m pytest && pyright -p pyrightconfig.json` | Browser manual smoke; no E2E by scope | `static/`, `pyrightconfig.json`, `AGENTS.md` |

## Phase 1: Foundation — units, rewards, persistence

- [x] 1.1 Add RED tests in `tests/test_units.py` for kg/lb, stone decomposition, BMI, and missing height; create `units.py` pure display helpers (~100 lines).
- [x] 1.2 Replace step-based RED cases in `tests/test_rewards.py` with five thresholds, equality, regression, re-earn, override/earliest start, and band progress; redesign `rewards.py` (~160 lines).
- [x] 1.3 Add RED migration/settings tests in `tests/test_api.py`/`tests/test_weight.py` for local timestamps, `active_rewards`, `height_cm`, and retired-key rejection; update `models.py`, `constants.py`, and `database.py` (~220 lines).
- [x] 1.4 Reconcile active rewards transactionally after startup, weight upsert/delete, and reward-affecting settings updates; wire startup reconciliation in `main.py` and prove earliest/latest-entry changes (~100 lines).

## Phase 2: Backend — API and scheduler

- [ ] 2.1 Add RED API scenarios for kg/lb/st/BMI summaries, history payloads, active checkpoint serialization, validation, and mutation reconciliation; update `routes.py` (~180 lines).
- [ ] 2.2 Add RED scheduler cases for local `sent_at`, due/disabled schedules, zero-subscription consumption, local-day rollover, and DST repeat/skip; update `scheduler.py` (~100 lines).

## Phase 3: Frontend — presentation and optional polish

- [ ] 3.1 Update `static/index.html`, `static/app.js`, and `static/style.css` for shared kg/lb/st formatting, height/BMI, history/chart tooltips, checkpoint progress, and local date construction; browser-smoke each view (~280 lines).
- [ ] 3.2 **Optional only if final authored forecast ≤400 lines:** add 192/512 icons and `getSubscription()` → API unsubscribe → `subscription.delete()` in `static/manifest.webmanifest`, `static/icons/`, and `static/app.js`; otherwise record both deferred (~60 lines).

## Phase 4: Tooling and cleanup

- [ ] 4.1 Create `pyrightconfig.json`; update `AGENTS.md` module map/rules to remove `RewardMilestone` and step terminology; run `pyright -p pyrightconfig.json` (~40 lines).
- [ ] 4.2 Remove obsolete `RewardMilestone`, milestone-step APIs/tests/UI, and dead imports; run the full `.venv/bin/python -m pytest` suite (0–30 lines).

## Phase 5: Commit and release gate

- [x] 5.1 Before implementation, commit the scaffold plus OpenSpec/tooling baseline as `chore: establish weight tracker baseline`, excluding DB, VAPID keys, and `.venv` (~0 lines).
- [ ] 5.2 After tests, Pyright, backup/rollback checks, and forecast gate pass, commit work units conventionally without AI attribution (~0 lines).
