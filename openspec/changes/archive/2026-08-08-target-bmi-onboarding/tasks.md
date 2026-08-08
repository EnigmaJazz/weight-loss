# Tasks: BMI Target Goals and Onboarding Wizard

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,000 across 4 slices |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | BMI helpers + shared resolver + reward keys + fixture | PR 1 | `.venv/bin/python -m pytest tests/test_units.py tests/test_rewards.py -q` | N/A — pure + in-process httpx | revert units/rewards/models/constants/conftest + keys; no data impact |
| 2 | Settings/summary contract + precedence/clearing | PR 2 | `.venv/bin/python -m pytest tests/test_api.py -q` | N/A — in-process httpx | revert routes.py summary/settings edits; no data impact |
| 3 | Onboarding endpoint + flag + tests | PR 3 | `.venv/bin/python -m pytest tests/test_onboarding.py tests/test_auth_api.py -q` | N/A — in-process httpx | revert route/db method; orphan `onboarding_complete` rows harmless |
| 4 | SPA wizard + gate + smoke | PR 4 | `node --test tests/frontend/*.test.mjs && .venv/bin/python -m pytest tests/test_spa_gate.py -q` | `tests/smoke-ui.sh` vs scratch DB | revert static/* + smoke script |

## Phase 1: BMI Helpers + Shared Resolver + Reward Keys (PR 1)

- [x] 1.1 RED `tests/test_units.py`: `weight_kg_from_bmi` (22.0/175→67.4, 18.5/200→74.0, unset→None), `healthy_weight_range` (175→(56.6,76.2), unset→None), `classify_bmi` (18.5/24.9 healthy, 25.0 overweight, 18.4 underweight), `resolve_target_kg` precedence
- [x] 1.2 GREEN `units.py`: add `weight_kg_from_bmi`, `healthy_weight_range`, `classify_bmi`, `resolve_target_kg` (design §Interfaces)
- [x] 1.3 RED `tests/test_rewards.py`: `reward_state` target from target_bmi+height→67.4; weight 80 wins; null when unset
- [x] 1.4 GREEN `models.py` `AppSettings` += `target_bmi`, `onboarding_complete`; `constants.py` `DEFAULT_SETTINGS` += both; `rewards.py` `reward_state` via `resolve_target_kg`
- [x] 1.5 GREEN `database.py`: `_settings_from_conn` maps `target_bmi`; `REWARD_AFFECTING_KEYS` += `target_bmi`, `height_cm`
- [x] 1.6 GREEN `tests/conftest.py`: `onboarded_client` fixture + `complete_onboarding_via_api` helper via existing endpoints (PUT settings + POST weight) — lands BEFORE gating routes; update `tests/test_api.py` settings exact-key asserts for `target_bmi`
- [x] 1.7 RED `tests/test_api.py`: DB-level reconciliation — `update_settings({"target_bmi": ...})` recomputes checkpoints; unset revokes; user A/B isolation

## Phase 2: Settings & Summary Contract (PR 2)

- [x] 2.1 RED `tests/test_api.py`: summary exact-key asserts += `healthy_min_kg`/`healthy_max_kg`/`target_status`; route tracker-assuming tests through `onboarded_client`; new tests: BMI round-trip clears `target_weight`, weight clears `target_bmi`, out-of-range 422 no-persist, store-without-height null target, summary contract (height unset→nulls, target unset→null status), summary/rewards target_kg agree, API-level reconcile on `target_bmi`
- [x] 2.2 GREEN `routes.py`: `SettingsIn` += `target_bmi: Optional[float] = Field(default=None, gt=10, le=40)`; `put_settings` bidirectional clearing (BMI→null weight, weight→null BMI); `_summary_view` via `resolve_target_kg` + adds `healthy_min_kg`/`healthy_max_kg`/`target_status`
- [x] 2.3 DECISION (design open Q1): summary `target_bmi` vs settings `target_bmi` naming — default: keep both, no rename. Confirm with user — **recorded: keep both names, no rename (apply-progress 2026-08-08)**

## Phase 3: Onboarding Endpoint + Flag (PR 3)

- [x] 3.1 RED `tests/test_onboarding.py` (create): 401 unauthenticated; XOR-violation 422 persists nothing; unknown-key 422; height-checked-before-BMI-bounds 422; atomic happy path (settings+single today entry+rewards); idempotent re-POST single entry; mid-`_tx` weight-insert failure rolls back all
- [x] 3.2 RED `tests/test_auth_api.py`: `me()` asserts += `needs_onboarding`; new: true for bare user, false after completion, true for pre-existing (no row)
- [x] 3.3 GREEN `database.py`: factor `_apply_settings(conn,...)`/`_upsert_entry_conn(conn,...)` out of `update_settings`/`upsert_entry`; add `_today()`, `complete_onboarding(user_id, payload)` single `_tx` (settings+entry+reconcile); `_settings_from_conn` maps `onboarding_complete`
- [x] 3.4 GREEN `routes.py`: `OnboardingIn` (extra=forbid, XOR `model_validator`, height-before-bounds per design AD6); `POST /api/onboarding` → 200 `{ok: true}`; `me()` returns `needs_onboarding` (design AD4 default: settings read per call — DECISION open Q2: **default accepted, settings read per call**)
- [x] 3.5 DECISION (open Q3): `onboarding_complete` as `str(bool)` — **default kept: store "True"/"False" k/v strings, not int 0/1 (recorded in apply-progress)**

## Phase 4: SPA Wizard + Gate + Smoke (PR 4)

- [x] 4.1 RED `tests/test_spa_gate.py`: `id="onboarding-screen"` present + hidden; `app.js` `init()` branches on `needs_onboarding` (AST drift-guard style)
- [x] 4.2 GREEN `static/index.html`: `#onboarding-screen` section + wizard steps (height → weight → target weight/BMI mode → units → notifications) hidden between auth-screen and tracker
- [x] 4.3 GREEN `static/app.js`: `init()` branches on `needs_onboarding`; `showOnboarding()`; step handlers; `submitOnboarding()` posts `OnboardingIn`; target input BMI mode + healthy-range display + out-of-range flag (reused in settings + wizard)
- [x] 4.4 GREEN `tests/smoke-ui.sh`: insert wizard completion after register (existing straight-to-tracker steps break once gate lands); assert wizard visible, complete, tracker loads
- [x] 4.5 DECISION (open Q4): wizard notifications step skippable? Default: mandatory per spec; confirm per-step optionality — **recorded: mandatory (non-skippable wizard v1), no skip button (apply-progress 2026-08-08)**
