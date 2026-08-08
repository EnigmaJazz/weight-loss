# Apply Progress — target-bmi-onboarding (Phases 1–4 / PRs 1–4)

- Updated: 2026-08-08 (Phase 4 batch merged into the Phase 1+2+3 artifact)
- Mode: Strict TDD (pytest, `.venv/bin/python -m pytest`; node:test for frontend)
- Delivery: auto-chain, stacked-to-main, slices 1–4 (`feat/target-bmi-onboarding-s1` … `-s4`)
- Batch 1: tasks 1.1–1.7 ONLY (Phase 1). Batch 2: tasks 2.1–2.3 ONLY (Phase 2). Batch 3: tasks 3.1–3.5 ONLY (Phase 3). Batch 4: tasks 4.1–4.5 ONLY (Phase 4). All phases complete — ready for verify.

---

## Phase 4 (PR 4) — Completed Tasks (batch 4)

| Task | Status | Evidence |
|------|--------|----------|
| 4.1 RED `tests/test_spa_gate.py` onboarding wizard + needs_onboarding branch | [x] | 2 failed RED confirmed (onboarding-screen absent; needs_onboarding branch absent); 2 new tests |
| 4.2 GREEN `static/index.html` wizard markup + `#goal-range-hint` | [x] | gate test 1 green; 7/7 gate suite |
| 4.3 GREEN `static/app.js` gate/step/submit + healthy-range flag; `format.js` helpers + node:test | [x] | gate 7/7; frontend 88/88 (14 new); full suite 349 passed; pyright 0 errors |
| 4.4 GREEN `tests/smoke-ui.sh` wizard completion | [x] | Browser smoke 29 passed / 0 failed (real chromium against scratch server) |
| 4.5 DECISION (open Q4) | [x] | **Notifications step MANDATORY (non-skippable) in wizard v1 — no skip button** (recorded below) |

### Decision 4.5 — recorded (design open Q4: per-step optionality)

The spec mandates a non-skippable wizard v1 and does not specify per-step
optionality. DEFAULT accepted: **the notifications step is mandatory — no skip
button ships.** Height/weight/target stay mandatory; the step's time fields are
individually optional (blank = disabled, the same sentinel the Settings
reminders form uses), so "mandatory step" means the user must pass through it,
not fill every field. Revisit per-step skippability in a v2 only if users ask.

## Phase 4 — TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 | `tests/test_spa_gate.py` | Delivery/static (httpx) | ✅ 5/5 gate; 74 frontend | ✅ Written — 2 failed (onboarding-screen missing; needs_onboarding branch missing) | ✅ Passed after 4.2+4.3 — 7/7 | ✅ 2 scenarios (HTML shape/order; app.js branch + payload keys) | ✅ regex drift-guard style reused; none needed |
| 4.2 | `static/index.html` (via gate test) | Delivery | ✅ 5/5 gate | N/A (GREEN task) | ✅ gate 1 green | ✅ 5 steps + target mode + schedule fields asserted | ➖ None needed (static markup) |
| 4.3 | `tests/frontend/bmi-target.test.mjs` + `tests/test_spa_gate.py` | Unit (node:test) + Delivery | ✅ 74 frontend; 5/5 gate | ✅ Written — 14 node:test failures (helpers undefined); 2 gate failures | ✅ 88/88 frontend; 7/7 gate; 349 full suite | ✅ 14 cases across weightKgFromBmi/bmiFromKg/healthyRange/classifyBmi/targetRangeHint (spec values pinned: 22/175→67.4, 18.5/200→74.0, 175→(56.7,76.3)) | ✅ shared `targetRangeHint` extracted — wizard and settings reuse one helper; JS mirrors units.py arithmetic |
| 4.4 | `tests/smoke-ui.sh` | E2E (real browser) | ✅ 349 full suite | N/A (GREEN task — script was red against the new gate by construction) | ✅ 29 passed / 0 failed | ✅ wizard visible → complete → tracker loads; pre-wizard tracker-hidden asserted | ✅ 5 existing post-signup assertions replaced with wizard-aware ones; count grew 24→29 |
| 4.5 | N/A (decision) | — | — | — | — | — | — |

RED-to-GREEN trace: 2 gate failures + 14 node:test failures → 7/7 gate, 88/88
frontend, 349 backend, pyright 0 errors, browser smoke 29/29.

## Phase 4 — Work Unit Evidence

| Unit | Focused test command + exact result | Runtime harness | Rollback boundary |
|------|-------------------------------------|-----------------|-------------------|
| 4. SPA wizard gate RED→GREEN | `node --test tests/frontend/*.test.mjs` → 88 pass; `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → 7 passed; full `.venv/bin/python -m pytest -q` → 349 passed; `.venv/bin/pyright` → 0 errors | `tests/smoke-ui.sh http://localhost:8001` against a scratch server (`WEIGHT_LOSS_DB=/tmp/wl-smoke.db WEIGHT_LOSS_VAPID_KEYS=/tmp/wl-vapid.json .venv/bin/uvicorn main:app --port 8001`) → 29 passed / 0 failed (real bundled chromium-1232) | revert static/app.js + static/index.html + static/style.css + static/format.js + tests/test_spa_gate.py + tests/frontend/bmi-target.test.mjs + tests/smoke-ui.sh (commit 0d13eed); openspec/ artifacts are untracked planning files; no DB impact (wizard writes only via the Phase-3 endpoint, which old code ignores) |

## Phase 4 — Deviations / Risks

1. **PR-4 size above the 400-line guard**: 762 insertions in one commit. This is
   the forecast's final slice (4 of 4) and the SPA wizard is one deliverable
   that cannot split into autonomous green units — the gate tests pin both
   index.html and app.js, and the smoke-flow update must land with the gate or
   the script is broken. Reviewer may want to review the commit by section.
2. **`novalidate` on the onboarding form**: added so the browser's native
   constraint validation never blocks Enter-to-advance on a hidden step's
   required input (steps hide via `[hidden]`, and a hidden required control can
   still block a submit with a cryptic error). JS validation is the gate; the
   required attributes stay for a11y.
3. **Wizard target_unit radio appears in steps 3 AND 4** (same `name`, one
   form): they form a single radio group, so both views always agree and
   `checkedRadio("ob-target-unit")` reads one preference — satisfies the task's
   step-4 spec (units: weight_display + target_unit) while keeping the step-3
   input unit usable.
4. **submitAuth also branches** (beyond init): a fresh register/login lands in
   the wizard too — required by the spec's pre-existing-accounts scenario and
   confirmed by the smoke flow (wizard visible after signup).
5. **JS rounding vs Python round()**: `weightKgFromBmi` uses `Math.round(x*10)/10`
   (half-up) where Python uses banker's rounding. All spec-pinned values
   (67.4, 74.0, 56.7, 76.3) agree; a half-to-even-only .5 boundary could diverge
   in the wizard hint. Display hint only — the API remains authoritative;
   noted for review.
6. **Logout hidden during the wizard**: the wizard is non-skippable by design;
   the logout button follows the tracker pattern (hidden while the wizard
   shows). A user can still close the tab / log out after completion.
7. **openspec/ untracked** (consistent with slices 1–3): the planning artifacts
   (tasks.md checkboxes, apply-progress merge) live outside git; PR 4's diff is
   pure code.

---

## Phase 1 (PR 1) — Completed Tasks (batch 1)

| Task | Status | Evidence |
|------|--------|----------|
| 1.1 RED `tests/test_units.py` BMI helpers + resolver | [x] | ImportError RED confirmed; 10 new tests |
| 1.2 GREEN `units.py` helpers + resolver | [x] | 19 passed in test_units |
| 1.3 RED `tests/test_rewards.py` resolver via reward_state | [x] | 1 failed RED confirmed (target not BMI-derived yet) |
| 1.4 GREEN `models.py`/`constants.py` fields + `rewards.py` resolver | [x] | 24 passed test_rewards; 52 passed test_api |
| 1.5 GREEN `database.py` mapping + reward keys | [x] | 127 passed targeted safety net |
| 1.6 GREEN `tests/conftest.py` fixture/helper + exact-key asserts | [x] | 53 passed test_api (fixture contract test added) |
| 1.7 RED `tests/test_api.py` DB-level reconciliation | [x] | 3 new tests pass immediately — behavior landed in units 3–4 (see note) |

Note on 1.7 "RED": the orchestrator's work-unit order lands the resolver + reward-affecting
keys (units 3–4) BEFORE the reconciliation tests (unit 5). The tests were written for this
batch and describe the spec'd behavior, but passed on first run because the production
behavior was already implemented by earlier units in the same phase. Documented as
cross-unit regression coverage, not a fresh RED→GREEN.

## Phase 2 (PR 2) — Completed Tasks (batch 2)

| Task | Status | Evidence |
|------|--------|----------|
| 2.1 RED `tests/test_api.py` summary/settings contract tests | [x] | 9 failed RED confirmed (KeyError healthy keys, 422 target_bmi, summary/rewards target_kg mismatch); 12 tracker-assuming tests routed through `onboarded_client` |
| 2.2 GREEN `routes.py` SettingsIn + clearing + `_summary_view` | [x] | 9 RED → GREEN; test_api 66/66; full suite 335 passed; pyright 0 errors |
| 2.3 DECISION (design open Q1) | [x] | **Keep both `target_bmi` names, no rename** (recorded below) |

### Decision 2.3 — recorded (design open Q1: name overlap)

`summary.target_bmi` (BMI of the resolved target weight, pre-existing key) and
`settings.target_bmi` (the BMI goal, new persisted key) are DIFFERENT response
objects — no technical conflict. DEFAULT accepted: **keep both names, no rename.**
No existing API key was renamed. The SPA distinguishes them by context (settings
form field vs summary stat). Revisit only if a shared client helper needs one
name for both.

## Phase 3 (PR 3) — Completed Tasks (batch 3)

| Task | Status | Evidence |
|------|--------|----------|
| 3.1 RED `tests/test_onboarding.py` (create) | [x] | 9 failed RED confirmed (404 — endpoint missing); 9 tests written first |
| 3.2 RED `tests/test_auth_api.py` `needs_onboarding` | [x] | 5 failed RED confirmed (KeyError needs_onboarding + 404); 3 new tests + 2 modified asserts |
| 3.3 GREEN `database.py` refactor + `complete_onboarding` | [x] | Refactor gate: full suite 333 passed (335 − 2 deliberately modified tests) with zero behavior change; onboarding_complete mapped via `_optional_bool` |
| 3.4 GREEN `routes.py` `OnboardingIn` + endpoint + `me()` flag | [x] | 31/31 focused passed; test_api 66/66; full suite 347 passed; pyright 0 errors |
| 3.5 DECISION (open Q3) | [x] | **Keep `str(bool)` storage** (recorded below) |

### Decision 3.5 — recorded (design open Q3: storage representation)

`onboarding_complete` is persisted in the settings k/v table as `str(bool)`
(`"True"`/`"False"`), DEFAULT accepted. Not switched to int 0/1. The k/v
store is string-only (`update_settings`/`_apply_settings` `str(value)`), so
`str(bool)` needs no new coercion path; `_optional_bool` parses
absent/empty → False, case-insensitive "true" → True. Rollback remains
drop-the-keys. (Design open Q2 — `me()` DB read — also accepted as default:
settings read per call, no lightweight `get_onboarding_complete` added.)

## Phase 3 — TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/test_onboarding.py` | Integration (httpx ASGITransport) | ✅ 335 full | ✅ Written — 9 failed (404 endpoint missing) | ✅ Passed after 3.3+3.4 | ✅ 10 cases (401; XOR ×2; unknown key; height-before-bounds ×2 variants; bounds over/under/40-boundary; atomic; idempotent re-POST; mid-tx rollback) | ✅ helper `_payload` extracted; type hints added for review gate |
| 3.2 | `tests/test_auth_api.py` | Integration | ✅ 335 full | ✅ Written — 5 failed (KeyError needs_onboarding; 404 on /api/onboarding) | ✅ Passed after 3.4 | ✅ 4 cases (bare user, after completion, pre-existing account, +2 existing round-trips updated) | ✅ helper type hints fixed for review gate (pre-existing `_session_token`/`_register`) |
| 3.3 | `database.py` (via suite) | Integration/DB | ✅ 335 full | N/A (GREEN task) | ✅ Refactor gate 333 passed (only the 2 deliberately modified tests fail); final 347 | ✅ `_optional_bool` parser + `_today()` | ✅ `_apply_settings`/`_upsert_entry_conn` factored out of `update_settings`/`upsert_entry` — no behavior change |
| 3.4 | `routes.py` (via `tests/test_onboarding.py` + `test_auth_api.py`) | Integration | ✅ 335 full | N/A (GREEN task) | ✅ 31/31 focused; 347 full | ✅ unit validators extracted to module fns and reused by both `SettingsIn` and `OnboardingIn` | ✅ `me()` gains db dep + `needs_onboarding` (AD4 default) |
| 3.5 | N/A (decision) | — | — | — | — | — | — |

RED-to-GREEN trace: 14 failing (9 onboarding + 5 auth) → 31 passing in the
focused files. Two mid-cycle test fixes were required (see Deviations 3–4):
httpx cookie-domain behavior for the pre-existing-account test, and
Starlette 1.3.1's always-re-raise ServerErrorMiddleware for the rollback
observability test (transport `raise_app_exceptions=False`).

## Phase 3 — Work Unit Evidence

| Unit | Focused test command + exact result | Runtime harness | Rollback boundary |
|------|-------------------------------------|-----------------|-------------------|
| 3. onboarding endpoint RED→GREEN | `pytest tests/test_onboarding.py tests/test_auth_api.py -q` → RED 14 failed → GREEN 31 passed; `pytest tests/test_api.py -q` → 66 passed; full suite → 347 passed | N/A — in-process httpx ASGITransport IS the integration path (no live server; scheduler disabled, push stubbed); the rollback test drives a real 500 through the transport (`raise_app_exceptions=False`) | revert routes.py (OnboardingIn, POST /api/onboarding, me() flag) + database.py (complete_onboarding, helpers, `_optional_bool`, `_today`) + test files; orphan `onboarding_complete`/`target_bmi` settings rows harmless (ignored by old `_settings_from_conn`) |

## Phase 3 — Deviations / Risks

1. **AD2 clearing inside `complete_onboarding`**: on top of the task's "nothing
   to clear beyond what's given", the other target key is explicitly nulled
   (mirrors `put_settings`). For a fresh user this is a no-op; it guards the
   corner where a re-POST switches target mode (weight→BMI) and would
   otherwise leave two persisted targets (target_weight precedence would win).
   Not pinned by a test in this slice — noted for review.
2. **OnboardingIn validation order (AD6) confirmed working as designed**: with
   `target_bmi` carrying field-level `gt=0` only, a missing/zero height + out-
   of-bounds BMI target surfaces ONLY the height error (model validator never
   runs after field errors). Tests assert loc `["body", "height_cm"]` present
   and no `target_bmi` in any error message. The (10, 40] bounds surface as a
   `["body"]`-level ValueError naming target_bmi.
3. **httpx cookie-domain gotcha (found in RED)**: `client.cookies.set(name,
   token, domain="test", path="/")` is silently NOT sent by httpx to
   `http://test`; omitting the domain sends it. The pre-existing
   `test_expired_session_is_rejected` uses `domain="test"` and passes only
   because it expects 401 — a latent vacuous-assertion issue outside this
   slice's scope (not fixed; flagged for review).
4. **Starlette 1.3.1 ServerErrorMiddleware always re-raises** after sending a
   500 ("allows test clients to optionally raise the error"). The rollback
   test therefore builds its own transport with `raise_app_exceptions=False`
   so the real 500 response is observable; the default fixture transport
   would surface the injected RuntimeError instead. This is a test-harness
   detail only — production behavior is unchanged (500 + full rollback).
5. **Review-gate type hints**: the `.gga` pre-commit hook (strict mode)
   requires annotated helper signatures; pre-existing `_session_token`/
   `_register` in test_auth_api.py were annotated (rule-2 compliance fix).
   One hook run aborted on the provider's verbose output pushing the STATUS
   line past the parser's 30-line window (review verdict was PASSED); retry
   with cached review succeeded. No `--no-verify` was used.

## Phase 2 — TDD Cycle Evidence (batch 2, preserved)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/test_api.py` | Integration (httpx ASGITransport) | ✅ 325 full | ✅ Written — 9 failed (KeyError healthy_min_kg/max_kg/target_status; PUT target_bmi 422; summary/rewards target_kg disagree; clearing not applied) | ✅ Passed after 2.2 | ✅ 10 cases (round-trip ×2 directions, bounds 5 & 45, no-height, contract nulls ×2, agree, reconcile, derived-keys guard) | ✅ 1 weak assert fixed (setup PUT status now asserted) |
| 2.2 | `routes.py` (via `tests/test_api.py`) | Integration | ✅ 325 full | N/A (GREEN task) | ✅ 66/66 test_api; 335 full | ✅ 10 cases | ✅ clearing order flipped so target_weight wins on both-set payload (matches resolver precedence) |
| 2.3 | N/A (decision) | — | — | — | — | — | — |

RED-to-GREEN trace: 9 failing → 66 passing in `tests/test_api.py` (2.1 wrote all
tests first; 2.2 implemented `SettingsIn.target_bmi`, AD2 clearing in
`put_settings`, `_summary_view` via `resolve_target_kg` + healthy/status keys, and
added `target_kg` to the `/api/rewards` response — the last was required by the
spec scenario "summary target_kg and rewards target_kg MUST be identical", which
needs an API-visible rewards target_kg).

## Work Unit Evidence

| Unit | Focused test command + exact result | Runtime harness | Rollback boundary |
|------|-------------------------------------|-----------------|-------------------|
| 2. settings/summary contract RED→GREEN | `pytest tests/test_api.py -q` → RED 9 failed → GREEN 66 passed | N/A — in-process httpx ASGITransport IS the integration path (no live server; scheduler disabled, push stubbed by conftest) | revert routes.py edits (imports, SettingsIn field, put_settings clearing, _summary_view keys, rewards target_kg) + test_api.py additions; no data impact (settings k/v rows only) |

## Phase 1 — TDD Cycle Evidence (batch 1, preserved)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/test_units.py` | Unit | ✅ 12/12 | ✅ Written (ImportError) | ✅ Passed | ✅ 10 cases | ➖ None needed (pure fns) |
| 1.2 | `tests/test_units.py` | Unit | N/A (new code) | N/A (GREEN task) | ✅ 19/19 | ✅ 10 cases | ➖ None needed |
| 1.3 | `tests/test_rewards.py` | Unit | ✅ 21/21 | ✅ Written (1 failed) | ✅ Passed | ✅ 3 cases | ➖ None needed |
| 1.4 | `tests/test_rewards.py` + suite | Unit | ✅ 318 full | N/A (GREEN task) | ✅ 24/24 + 318 full | ✅ 3 cases | ➖ None needed |
| 1.5 | `tests/test_api.py` et al | Integration/DB | ✅ 318 full | N/A (GREEN structural) | ✅ 127 targeted | ➖ Single (plumbing) | ➖ None needed |
| 1.6 | `tests/test_api.py` | Integration | ✅ 52 | N/A (infrastructure) | ✅ 53/53 | ✅ fixture contract test | ➖ None needed |
| 1.7 | `tests/test_api.py` | Integration/DB | ✅ 53 | ✅ Written (pass on run — see note) | ✅ 56/56 | ✅ 3 scenarios | ➖ None needed |

## Phase 1 — Work Unit Evidence (batch 1, preserved)

| Unit | Focused test command + exact result | Runtime harness | Rollback boundary |
|------|-------------------------------------|-----------------|-------------------|
| 1. BMI helpers RED→GREEN | `pytest tests/test_units.py -q` → 19 passed | N/A — pure functions, no runtime boundary | revert units.py + test_units.py additions |
| 2. models/constants fields | full suite → 318 passed | N/A — dataclass/defaults, no runtime boundary | revert models.py + constants.py field additions |
| 3. rewards resolver RED→GREEN | `pytest tests/test_rewards.py -q` → 24 passed; `pytest tests/test_api.py -q` → 52 passed | N/A — pure + in-process httpx | revert rewards.py resolver wiring + test_rewards.py |
| 4. database keys | `pytest tests/test_api.py tests/test_rewards.py tests/test_user_isolation.py tests/test_weight.py -q` → 127 passed | N/A — in-process httpx | revert database.py mapping + keys; no data impact |
| 5. conftest fixture + exact-key | `pytest tests/test_api.py -q` → 53 passed | N/A — in-process httpx | revert conftest.py + test_api.py additions |
| 6. reconciliation regressions | `pytest tests/test_api.py -q` → 56 passed | N/A — in-process httpx | revert test_api.py additions; no data impact |

## Deviations / Risks

1. **Spec-data inconsistency (flagged, Phase 1):** `bmi-goal-setting` spec scenario
   says `healthy_weight_range(175)` MUST return `(56.6, 76.2)`, but its own formula
   `round(18.5×(h÷100)², 1)` / `round(24.9×(h÷100)², 1)` yields `(56.7, 76.3)`.
   Implemented the normative formula (MUST) and pinned tests to `(56.7, 76.3)`.
   The spec scenario was corrected to `(56.7, 76.3)` per this run's launch notes —
   formula wins; tests and summary asserts use 56.7/76.3.
2. **`/api/rewards` gains `target_kg`** (Phase 2): not listed in tasks/design File
   Changes, but REQUIRED by the weight-tracking spec scenario "summary target_kg and
   rewards target_kg MUST be identical" — the rewards response previously had no
   API-visible target_kg. Additive key; no consumer breaks.
3. **Two Phase-2 tests are not fresh REDs** (documented honestly):
   `test_settings_target_bmi_out_of_range_rejected_no_persist` passes both before
   (extra="forbid" 422) and after (gt/le 422) — a contract regression, RED-by-
   mechanism-change; `test_settings_does_not_expose_summary_derived_keys` is a
   guard test (true both ways). The remaining 9 were genuine RED failures.
4. **Fixture-routing notes (Phase 2):** 12 tracker-assuming tests moved to
   `onboarded_client`; `test_settings_update_reconciles_rewards` now clears the
   fixture's seeded target first; `test_weight_entries_include_display_units`
   clears the seeded height (upsert over the fixture's 08-01 row returns 200, not
   201); `test_weight_created_at_uses_local_time` moved to a fresh date because
   `upsert_entry`'s ON CONFLICT does not refresh `created_at`. `test_rewards_empty`
   stays on `auth_client` (deliberately tests the bare-user empty state).
5. **AD2 both-set corner:** when one PUT supplies both targets, `target_weight`
   wins (matches resolver precedence) — no test pins this; noted for review.
6. **`onboarding_complete` field** added to models/constants (default False) but NOT
   mapped in `_settings_from_conn` and no `_optional_bool` helper — per Phase-1
   scope (flag lands Phase 3, task 3.3). GET /api/settings exposes it as False via
   asdict.
7. **Base branch decision (this run):** `git log main..feat/target-bmi-onboarding-s1`
   shows 6 commits NOT in main, so slice 2 was created FROM s1
   (`git checkout -b feat/target-bmi-onboarding-s2` on s1's tip 05fbccb). When s2's
   PR opens, its diff includes s1's commits until s1 merges (stacked-to-main: PR 2
   targets the previous PR's branch until it merges into main).
8. No routes.py changes beyond Phase-2 scope; Phase 3 (`/api/onboarding`, `me()`
   needs_onboarding) intentionally NOT implemented.
