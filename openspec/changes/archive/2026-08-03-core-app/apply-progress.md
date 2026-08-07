# Apply Progress: core-app — Slice 1 (Foundation)

**Change**: core-app
**Slice**: 1 of 3 (stacked-to-main) — branch `slice-1-foundation`, PR #1 → `main`
**Mode**: Strict TDD (active, resolved from openspec/config.yaml `strict_tdd: true`)
**Status**: 4/4 slice tasks complete (1.1, 1.2, 1.3, 1.4) + baseline commit 5.1
**Test counts**: 37 passing at start → 65 passing at end (all green)

## Completed Tasks

- [x] 1.1 Units conversions/BMI — `units.py` (kg→lb, kg→stone, BMI, display view) + `tests/test_units.py`
- [x] 1.2 Rewards redesign — checkpoint thresholds 10/25/50/75/100, active state from latest-dated weight, next checkpoint, band progress; step-based logic replaced in `rewards.py` + `tests/test_rewards.py`
- [x] 1.3 Migration/settings — `active_rewards(checkpoint_percent PK, threshold_kg, earned_at)` replaces `reward_events`; local timestamps for `created_at`/`earned_at`/`sent_at`; `RewardMilestone` removed; `height_cm` added; `milestone_step_kg` retired and rejected
- [x] 1.4 Reward reconciliation — transactional reconcile inside upsert/delete/settings-update; startup reconcile in `main.py`
- [x] 5.1 Baseline commit `chore: establish weight tracker baseline`

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | tests/test_units.py (9 tests) | Unit | existing 37-test suite | ImportError: no `WeightDisplay`/`units` (0/9 pass) | 46 passed (9 new) | kg/lb factor, stone decomposition, BMI exact, missing height, display shape | `KG_TO_LB` constant; WeightDisplay dataclass in models.py |
| 1.2 | tests/test_rewards.py (rewritten, 21 tests) | Unit | suite (46) | ImportError: no `CHECKPOINTS`/`checkpoint_thresholds`/`reward_state` | 55 passed | five thresholds, inclusive equality, regression/revocation, override vs earliest start, band progress edges (0.0/0.5/1.0) | old step functions retained (dead, 4.2 removes); `reward_state` centralizes derivation |
| 1.3+1.4 | tests/test_api.py, tests/test_weight.py (28 new/rewritten) | Integration | suite (55) | 15 failures: missing `active_rewards` table, missing `height_cm`/retired-key contract, old rewards shape | 65 passed (one test bug fixed: re-earn weight 94 → 90 so 50% threshold is actually reached) | local timestamps via `_local_now` monkeypatch; re-earn refreshes `earned_at`; historical upsert moves start; delete revokes; settings update re-derives | 1.3+1.4 landed as ONE commit — the storage migration cannot be green without the reconciliation keeping `active_rewards` consistent (app would break between the two); separate tasks, one atomic deliverable |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_units.py tests/test_rewards.py` → 30 passed; full suite `.venv/bin/python -m pytest -q` → **65 passed in 0.30s** |
| Runtime harness command/scenario and exact result | httpx ASGITransport integration: `tests/test_api.py` exercises upsert→earn, regression→revoke, re-earn→fresh `earned_at`, historical upsert→start change, delete→reconcile, settings update→reconcile, retired-key 422, local timestamps (65/65 green) |
| Rollback boundary | Revert branch `slice-1-foundation` to `main`; slice-1 files: `units.py`, `rewards.py`, `models.py`, `constants.py`, `database.py`, `main.py`, `routes.py` (minimal compat), `tests/test_units.py`, `tests/test_rewards.py`, `tests/test_api.py`, `tests/test_weight.py` |

## Deviations from Design

1. **routes.py minimally touched in slice 1** (design places full API work in 2.1): `SettingsIn` drops `milestone_step_kg` + `extra="forbid"` (spec-required retired-key rejection is a 1.3 test); `upsert_weight` drops the old reconcile call (DB now self-reconciles); `get_rewards` serializes the new checkpoint contract (old milestone data source was deleted — endpoint would 500 otherwise). Full kg/lb/st/BMI summaries, validation, and mutation-reconciliation endpoints remain for 2.1.
2. **1.3+1.4 landed as one commit** (`feat(rewards): migrate to active_rewards with transactional reconciliation`) — the migration cannot land green without reconciliation (see TDD table). Tasks remain separate for verification.
3. **`target >= start` yields no checkpoints** — thresholds are only meaningful when a loss is possible; `checkpoint_thresholds` returns `[]` (design-silent edge, regression-tested).
4. **Dead step code retained**: `milestone_levels`/`next_milestone`/`progress_to_next`/`lost_delta` in rewards.py and `_float` removal only where 1.3's rewrite orphaned it — 4.2 owns the rest (out of slice scope).
5. **Task 5.1 committed inside PR #1** — `main` had zero commits; the baseline must live somewhere, and slice 1 is the first PR.

## Issues Found

- None blocking. `.gga` pre-commit hook is not installed in `.git/hooks` (no `core.hooksPath`); commits proceeded without hook review. Flagged for the orchestrator — the hook either needs wiring or slice 2+ should install it.
- Pyright LSP diagnostics (18) are environment noise: the LSP cannot resolve the project `.venv` (fastapi/pydantic/httpx/pytest unresolved); runtime imports prove fine (65 passed). 4.1 addresses pyright config.

## Status

Slice 1 complete: 4/4 tasks. Ready for verify (orchestrator) → next_recommended: sdd-verify, then slice 2.

---

# Apply Progress: core-app — Slice 2 (Backend)

**Change**: core-app
**Slice**: 2 of 3 (stacked-to-main) — branch `slice-2-backend`, PR #2 → `main`
**Mode**: Strict TDD (active)
**Status**: 2/2 slice tasks complete (2.1, 2.2). PR #1 (slice 1) merged; PR #2 left open for review.
**Test counts**: 65 passing at start → 74 passing at end (all green; 9 new, 2 contract updates)

## Completed Tasks

- [x] 2.1 API display data — `routes.py`: `WeightIn` strict (`extra="forbid"`); `_weight_view` None-safe raw lb/stone/stone_lb/bmi per weight; entries carry `lb`/`stone`/`stone_lb`/`bmi`; summary carries `*_lb`/`*_stone`/`*_stone_lb` for all five values + `*_bmi` on real weights (baseline/current/target, not deltas); rewards active/next checkpoints carry `threshold_lb`/`threshold_stone`/`threshold_stone_lb`. Mutations already self-reconcile via the DB layer (slice 1) — verified through the API. Tests: `tests/test_api.py` (+6 new, 2 contract updates).
- [x] 2.2 Scheduler local time — `scheduler.py` passes the injected tick's own local wall time (`now.strftime("%Y-%m-%d %H:%M:%S")`) to `mark_notification_sent`; `database.py` accepts optional `sent_at` (defaults to fresh `_local_now()` for direct callers). Local HH:MM comparison + local-calendar-date day key were already correct by construction; DST repeated-hour single-send, DST skipped-time fires-on-next-tick, and tick-sourced `sent_at` pinned with regression tests. Tests: `tests/test_scheduler.py` (+3 new).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | tests/test_api.py (+6 new: entries display units, entries bmi with height, summary display units, summary None-empty, rewards threshold units, WeightIn unknown-key 422; 2 contract updates) | Integration | suite (65) | 6 failures: missing `lb`/`stone`/`stone_lb`/`bmi` keys (KeyError) + unknown weight key not rejected (201 != 422) | 73 passed (6 new + 2 updated contracts) | exact kg↔lb factor (×2.2046226218), stone decomposition, BMI 175cm, None-safe empty summary, rewards 10%/50% thresholds, unknown-key 422 | `_weight_view` + `_summary_view` helpers centralize derivation; canonical `*_kg` keys untouched so the SPA keeps its existing contract |
| 2.2 | tests/test_scheduler.py (+3 new: tick-sourced `sent_at` via `_local_now` decoy monkeypatch, DST repeated hour single-send, DST skipped time fires on next tick) | Integration | suite (73) | 1 genuine failure (stored `sent_at` = decoy, not the tick's local time) + 1 test-authoring bug fixed during RED (23:59 tick legitimately fires tip/reminder → `count == 2`, only exercise deduped); 2 DST regressions green immediately (behavior already correct by construction) | 74 passed | monkeypatched `database._local_now` decoy proves the tick's timestamp wins; repeated 01:30 wall time on same local date sends once; 02:30 skipped → fires at 03:00 same date | `mark_notification_sent` gains `sent_at: Optional[str] = None` param; scheduler passes `now.strftime` |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_api.py tests/test_scheduler.py` → **38 passed** (was 32 before slice); full suite `.venv/bin/python -m pytest -q` → **74 passed in 0.59s** |
| Runtime harness command/scenario and exact result | Real uvicorn boot (`WEIGHT_LOSS_DB=/tmp/... WEIGHT_LOSS_VAPID_KEYS=/tmp/... uvicorn main:app --port 8793`): PUT settings height=175/target=80 → POST 100kg, 95kg → GET `/api/weight` 200 (entry: `{weight_kg:95, lb:209.439, stone:14, stone_lb:13.439, bmi:31.020}`; summary baseline/current/lost/target/remaining with `_lb`/`_stone`/`_stone_lb`, `_bmi` only on baseline/current/target) → GET `/api/rewards` 200 (active 10%/25% with `threshold_lb`/`threshold_stone`/`threshold_stone_lb`/`earned_at`, next 50% with display units) → POST `/api/weight` with unknown key `units` → **422** |
| Rollback boundary | Revert branch `slice-2-backend` to `main` (PR #1 content). Slice-2 files: `routes.py` (display serialization + `WeightIn` strictness), `scheduler.py`, `database.py` (`mark_notification_sent` signature), `tests/test_api.py`, `tests/test_scheduler.py`. Frontend untouched — slice 3 renders the new fields. |

## Deviations from Design

1. **`_weight_view`/`_summary_view` helpers in routes.py** — the design places display construction in units.py (`weight_display` already exists there and is reused); routes adds thin dict serializers. No logic duplication, `units.weight_display` remains the single source of truth.
2. **BMI field policy**: entries + summary real weights (baseline/current/target) carry `bmi`; deltas (lost/remaining) carry multi-unit only — the spec requires BMI only for the current summary/history/tooltip, and BMI of a delta is meaningless. Documented in `_summary_view` docstring; pinned by tests (no `lost_bmi`/`remaining_bmi` keys).
3. **Two pre-existing rewards tests updated** (`test_rewards_checkpoints_earned_via_upserts`, `test_rewards_regression_revokes_checkpoints`): exact-equality `next_checkpoint == {"percent": …, "threshold_kg": …}` assertions extended to the new additive keys — contract extension, not relaxation (per design's "existing step/default assertions must change").
4. **`database.py` touched in 2.2** (tasks.md says "update scheduler.py ~100 lines"): the `sent_at` override parameter lives on `mark_notification_sent`; the scheduler alone cannot force its tick time into the DB layer otherwise.

## Issues Found

1. **Latent slice-1 bug — persisted VAPID load path crashes (out of slice scope, flagged):** py_vapid 1.9.4 `Vapid.from_raw` crashes with `TypeError: can only concatenate str (not "bytes") to str` on a str private key loaded from `vapid_keys.json` (`notifications._vapid_from_payload`). Fresh-generate path works, so the first boot is fine but **every subsequent boot with persisted keys crashes**. Reproduced 3× against a real server; fix verified as `Vapid.from_raw(payload["private_key"].encode("ascii"))`. Not fixed here — notifications.py is not in slice-2 scope; recommend a small follow-up (slice 3/4 or dedicated PR) with a regression test.
2. Pyright LSP diagnostics (17) remain environment noise (`.venv` unresolved; `pyrightconfig.json` is 4.1) — runtime imports prove fine (74 passed).

## Status

Slice 2 complete: 2/2 tasks (2.1, 2.2). PR #2 open for review (not merged — orchestrator/verify decides). next_recommended: sdd-apply slice 3 (frontend) after PR #2 merge, or sdd-verify first.

---

# Apply Progress: core-app — Slice 3 (Frontend + cleanup)

**Change**: core-app
**Slice**: 3 of 3 (stacked-to-main) — branch `slice-3-frontend`, PR #3 → `main`
**Mode**: Strict TDD (active)
**Status**: 4/5 slice tasks complete (3.1, 4.1, 4.2, 5.2) + EXTRA VAPID fix; **3.2 DEFERRED** (budget gate, see below). PR #1 + PR #2 merged; PR #3 left open.
**Test counts**: 74 passing at start → **76 passing at end** (all green; +2 VAPID regression tests)

## Completed Tasks

- [x] 3.1 Frontend presentation — `static/index.html`, `static/app.js`, `static/style.css` rewritten against the fixed raw-value contract (the SPA was still speaking the retired milestone-step contract; settings save 422'd on `milestone_step_kg`). Summary shows kg (lb; st lb) + BMI for baseline/current/target/lost/remaining; history rows show the same; chart tooltip (canvas hover) shows date, kg, lb, st-lb, BMI; rewards UI shows earned count, active checkpoint chips (percent + kg + lb/st + earned date), next checkpoint threshold, and a progress bar fed by `progress_to_next`; settings form swaps `milestone_step_kg` → `height_cm`; weight form defaults to the **local** date (no UTC off-by-one). Asset paths fixed to the `/static` mount. Frontend has no automated test harness — verified via `node --check` + live uvicorn smoke (documented below).
- [x] 4.1 `pyrightconfig.json` (venvPath `.venv`, pythonPlatform linux, pythonVersion 3.14) + `AGENTS.md` module map refreshed (units.py, checkpoint rewards, `active_rewards` reconciliation, `_local_now` wall-clock timestamps, `height_cm`, notifications tests). **Pyright smoke blocked by environment**: both the pip-installed wrapper and the AFT-cached node binary hang with zero output (tested sandboxed + unsandboxed, with/without `--outputjson`, 4 attempts); the 19 LSP diagnostics are all `.venv`-unresolved import noise that the config addresses. `pyright -p pyrightconfig.json` must be run in CI/normal env to complete the smoke.
- [x] 4.2 Dead-code cleanup — removed `milestone_levels`, `next_milestone`, `progress_to_next` (old step-based helpers) from `rewards.py`; verified unused across the repo (only slice-1's apply-progress note referenced them). `RewardMilestone` was already removed in slice 1.3; no dead imports found. Full suite green.
- [x] EXTRA (orchestrator-mandated) — latent VAPID reload bug fixed in `notifications._vapid_from_payload`: `Vapid.from_raw` now receives `payload["private_key"].encode("ascii")` (py_vapid 1.9.4 `b64urldecode` crashes on str with `TypeError: can only concatenate str (not "bytes") to str`). Regression tests added in `tests/test_notifications.py` (new file): round-trip key equality + second-boot load path. Real second boot verified at runtime (server logs "loaded VAPID keys from …").
- [x] 5.2 Feature commits — four conventional work units on `slice-3-frontend` (see below), no AI attribution.
- [ ] 3.2 Optional polish — **DEFERRED**: slice diff measured **575+/431− = 1,006 changed lines**, far over the 400-line gate, so the explicit condition (implement only if the budget allows) was not met. Both halves (manifest icons, local unsubscribe) deferred together per design. The disable-push wiring drafted during implementation was stripped so no half-wired deferred feature ships.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| VAPID fix | tests/test_notifications.py (new, 2 tests) | Unit | suite (74) | Both fail: `TypeError: can only concatenate str (not "bytes") to str` in py_vapid b64urldecode on second-boot load | 76 passed | `_vapid_to_payload` round-trip asserts public-key DER equality; load-path test boots the file twice; live second boot logs "loaded VAPID keys" | one-line fix + comment: encode("ascii") — orchestrator-suggested approach confirmed against py_vapid 1.9.4 source |
| 4.2 (cleanup) | no new tests (removal of unused code — no behavior to pin; grep proved zero references) | Structural | suite (74) | N/A — removing dead symbols cannot have a RED test; confirmation was static (repo-wide grep for `milestone_levels`/`next_milestone`/`progress_to_next`/`lost_delta`) | 76 passed after removal (0 regressions) | imports in tests/rewards checked; no orphaned references | commit `chore(rewards): remove dead step-based milestone helpers` (-26 lines) |
| 4.1 (tooling) | n/a (config + docs) | Tooling | suite (74) | N/A — no behavior | pyrightconfig.json created; AGENTS.md refreshed | pyright smoke attempted 4× — blocked: hangs with zero output in this env (pip wrapper + AFT node binary, sandboxed + host) | committed with explicit note; smoke must run in CI |
| 3.1 (frontend) | no harness by scope — **manual smoke is the check** (documented, per orchestrator) | Presentation | suite (76) | N/A (no frontend test runner) | `node --check static/app.js` OK; live uvicorn smoke: all `/static/*` 200; PUT settings (height+target) 200; 3 POSTs 200; GET `/api/rewards` → earned_count 1, progress_to_next 0.9187 (matches hand calc), next 25% → 82.3 kg + lb/st; GET `/api/weight` → entry 86.4 kg | 190.5 lb | 13 st 8.5 lb | BMI 28.2; summary carries target_bmi; retired-key 422 confirmed | contract keys verified field-by-field against `routes.py`; local-date helper, tooltip, progress bar eyeballed via served HTML/JS |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_notifications.py` → **2 passed**; full suite `.venv/bin/python -m pytest -q` → **76 passed in 0.30s** |
| Runtime harness command/scenario and exact result | Real uvicorn boot (`WEIGHT_LOSS_DB=/tmp/slice3.db WEIGHT_LOSS_VAPID_KEYS=/tmp/slice3_vapid.json uvicorn main:app --port 8126`): boot #2 on existing vapid_keys.json → "loaded VAPID keys" (no crash); PUT settings {height_cm:175, target_weight:70}; POST 3 weights (86.4/84.1/82.5); GET `/api/rewards` → `{earned_count: 1, progress_to_next: 0.9187, next_checkpoint: {percent: 25, threshold_kg: 82.3, threshold_lb: 181.44, threshold_stone: 12, threshold_stone_lb: 13.44}}`; GET `/api/weight` entry `{weight_kg: 86.4, lb: 190.5, stone: 13, stone_lb: 8.5, bmi: 28.2}`; all `/static/*` assets 200 |
| Rollback boundary | Revert branch `slice-3-frontend` to `main` (PR #2 content). Slice-3 files: `notifications.py` (1-line VAPID fix), `rewards.py` (dead-code removal), `pyrightconfig.json` (new), `AGENTS.md`, `static/index.html`, `static/app.js`, `static/style.css`, `tests/test_notifications.py` (new). No schema/API changes — backend contract untouched. |

## Deviations from Design

1. **3.1 was a rewrite, not presentation polish** — the design assumed the SPA already consumed the new contract; in reality it was fully on the retired milestone-step contract (`reward_total_kg`, `next_milestone_kg`, `milestones[]`, `milestone_step_kg`), so settings save 422'd on main. This is the root cause of the slice's budget overrun (1,006 vs ~300–400 estimated) and of the 3.2 deferral.
2. **3.2 deferred (budget gate)** — icons + local unsubscribe NOT implemented; both recorded deferred per design's Conditional Release Polish scenario. `disable-push` wiring stripped from the draft so nothing half-wired ships.
3. **Static asset paths corrected to `/static/...`** — my first draft used root-relative paths; main's convention (confirmed via `git show main:static/index.html`) is `/static/`-prefixed since the app mounts `StaticFiles` at `/static`.
4. **`progress_to_next` requires a target weight** — with `target_weight: null` the backend returns `0.0`/`None`; rewards UI only becomes meaningful once a target is set (documented in rewards.py docstring).
5. **Pyright smoke not completed in-env** — see Issues; config per design, execution pending a normal env.

## Issues Found

1. **Pyright hangs with zero output in this environment** — 4 attempts: pip-installed wrapper (20+ min), AFT-cached node binary (150s/45s), `--outputjson`, unsandboxed host run — all produce no output and no exit. Not a config issue (config is standard); an environment limitation. `pyright -p pyrightconfig.json` should run in CI or a normal shell.
2. **Slice budget overrun (1,006 changed lines vs 400)** — structural, not cosmetic: the SPA rewrite from the retired contract. Reported transparently (same as PR #1's 826-line note); 3.2 deferred per the explicit gate.
3. `.gga` pre-commit hook not wired in this env — per orchestrator: do not install or bypass; commits proceeded normally.

## Status

Slice 3 complete: 4/5 tasks (3.1, 4.1, 4.2, 5.2) + VAPID fix; 3.2 deferred. **76/76 tests green.** PR #3 open (not merged). next_recommended: sdd-verify (post-merge), then sdd-archive.

---

# Apply Progress: core-app — Slice 3, Executor Re-verification (pass 2)

**Change**: core-app
**Slice**: 3 of 3 — branch `slice-3-frontend` (re-verified on top of the pass-1 commits)
**Mode**: Strict TDD (active)
**Status**: Re-verification of pass-1 work complete; **2 UI bugs found and fixed**; 3.2 stays deferred. Full suite **76 passed**; slice budget re-measured at **1,078 changed lines** (641+/437−), confirming the 3.2 gate decision.
**Test counts**: 76 passing before and after this pass (frontend-only fixes, no backend change).

## What This Pass Did

The orchestrator re-launched apply for slice 3; the branch already contained pass-1 work (5 commits, pushed to origin). This pass **verified that work end-to-end instead of redoing it**, then fixed what verification found:

1. **Verified pass-1 commits** (625d61e VAPID fix, ff122d4 rewards cleanup, c5bf8ec pyright/AGENTS.md, d1041f8 UI rewrite, 0c71296 docs): conventional messages, no AI attribution, tests green.
2. **Verified API↔UI contract field-by-field** against `routes.py` serialization (`_weight_view`/`_summary_view`/rewards endpoint): entry `weight_kg/lb/stone/stone_lb/bmi`; summary `*_kg/*_lb/*_stone/*_stone_lb` + `*_bmi` only on baseline/current/target; rewards `active_checkpoints[{percent,threshold_kg,threshold_lb,threshold_stone,threshold_stone_lb,earned_at}]`, `earned_count`, `next_checkpoint|null`, `progress_to_next` — all consumed correctly by `app.js`.
3. **Confirmed pyright is blocked in this environment** — pass-1's claim reproduced with hard evidence: `timeout 180 .venv/bin/pyright -p pyrightconfig.json` → **exit 124, zero output**; direct `node .venv/.../pyright/dist/index.js` → **exit 124, zero output**. Config is standard (venvPath `.venv`, linux, 3.14, basic, excludes static); must run in CI/normal env.
4. **Fixed two UI bugs** (commits below):
   - **`setPushUi` crash**: `$("disable-push").hidden = !enabled` throws `TypeError` on null because index.html has no `disable-push` button (stripped when 3.2 deferred). Enabling push succeeded but then showed a false "Could not enable notifications" toast. Now null-guarded.
   - **Summary BMI missing when height unset**: `renderSummary` only rendered the BMI line when `*_bmi != null`, so with no height the summary showed NO BMI display, violating the weight-tracking spec scenario "each BMI display MUST be —" (history rows and chart tooltip already rendered `—`; summary now does too, for baseline/current/target — deltas still unlabeled since the API omits their bmi key).
   - **Manifest description** still said "earn milestones" (step terminology, 4.2 scope) → "earn checkpoints".
5. **Live runtime smoke** (uvicorn, tmp DB + VAPID): boot #1 generated keys, **boot #2 loaded persisted keys without crashing** (VAPID fix verified live); PUT settings height=175/target=70 → 200; POST 86.4/84.1/82.5 → 201; GET `/api/weight` entry `{weight_kg: 82.5, lb: 181.881, stone: 12, stone_lb: 13.881, bmi: 26.939}` + full summary (baseline/current/target carry `_bmi`; lost/remaining do not); GET `/api/rewards` → 10% active at 84.76 kg with `earned_at`, next 25% at 82.3 kg (181.44 lb / 12 st 13.44 lb), `progress_to_next: 0.9187` (hand-calc match); PUT settings with `milestone_step_kg` → **422**; all `/static/*` assets → 200.

## TDD Cycle Evidence (this pass)

| Fix | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|-----|-----------|-------|------------|-----|-------|-------------|----------|
| `setPushUi` null crash | n/a — no JS harness by scope (manual smoke is the check) | Presentation | suite (76) | Code-path proof: `setPushUi(true)` dereferences `$("disable-push")` → null → TypeError on enable success (traced, not executed) | `node --check static/app.js` OK; live smoke: enable→subscribe→POST subscribe 201 without error toast (guard verified by inspection of the enabled path) | enabled vs disabled toggle both null-safe (guard covers both branches) | one-line guard + explanatory comment |
| Summary BMI when height unset | n/a — no JS harness by scope | Presentation | suite (76) | Spec scenario: height absent → summary BMI display must be `—`; current code renders no BMI line at all (history/tooltip already correct) | `node --check` OK; live smoke with `height_cm: 175` returns `current_bmi: 26.939` → line renders; `bmiLabel(null)` → `—` path verified in `_weight_view` None contract | renders for baseline/current/target (key present), skips lost/remaining (key absent) — matches API key policy exactly | condition tightened `!= null` → `!== undefined` with comment |
| manifest wording | n/a (string) | Structural | suite (76) | N/A — no behavior | description updated | N/A — single string | N/A |

Frontend has no automated test runner by scope (orchestrator: "manual smoke acceptable; no E2E by scope"); TDD evidence for JS is code-path RED proof + `node --check` + live uvicorn smoke, same precedent as pass 1.

## Work Unit Evidence (this pass)

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `node --check static/app.js` → OK (exit 0); `.venv/bin/python -m pytest -q` → **76 passed in 0.33s** (unchanged — frontend-only fixes) |
| Runtime harness command/scenario and exact result | Real uvicorn boot (port 8133, tmp DB/VAPID): boot #2 "loaded VAPID keys from /tmp/slice3_verify_vapid.json" (no crash); PUT settings 200 (height_cm 175 persisted); POST 3 weights 201; GET `/api/weight` entry 82.5 kg → 181.881 lb / 12 st 13.881 lb / BMI 26.939; GET `/api/rewards` → earned_count 1, 10% active (84.76 kg, earned_at set), next 25% (82.3 kg), progress_to_next 0.9187; PUT settings `milestone_step_kg` → 422 extra_forbidden; `/static/{app.js,style.css,manifest.webmanifest,sw.js,index.html}` all 200; GET `/` 200 |
| Rollback boundary | This pass's fixes: `static/app.js` (2 edits), `static/manifest.webmanifest` (1 string). Revert commits 1e04e3c + f6150a8 (or `git revert`) to return to pass-1 state; whole slice rolls back to `main`. Backend untouched by this pass. |

## Commits Added (this pass, on slice-3-frontend)

| Hash | Message |
|------|---------|
| `1e04e3c` | `fix(ui): guard push-UI toggle and always render summary BMI` |
| `f6150a8` | `chore(static): use checkpoint wording in manifest description` |

(Pass-1 commits unchanged: `625d61e`, `ff122d4`, `c5bf8ec`, `d1041f8`, `0c71296` — 7 commits total on the branch.)

## Deviations from Design (this pass)

None — pass 1's deviations stand. This pass only fixed pass-1 UI correctness gaps against the same design/specs.

## Issues Found (this pass)

1. **NEW FLAG — schedules cannot be disabled through the API (pre-existing, slice-1/2 backend, out of slice-3 scope):** the scheduler treats `""` as disabled (`_due_today`), and slice-2 tests cover that, but the settings contract makes `""` unreachable: `_valid_time` rejects non-"HH:MM" strings (422) and `SettingsIn` accepts only `None`, which `update_settings` maps to DELETE-row → `_settings_from_conn` falls back to `DEFAULT_SETTINGS` (e.g. exercise_time "17:00"). Net effect: PUT settings with `exercise_time: null` returns `"17:00"`; no client can disable a notification type. The UI sends `null` for an empty time input (matches the API contract), so behavior is consistent — the gap is backend-only. Recommend a small follow-up (store `""` for null times or add an explicit disabled sentinel) with a regression test; NOT fixed here (routes.py/database.py are PR-1/2 territory).
2. **3.2's API-unsubscribe half is already supportable:** `POST /api/push/unsubscribe` + `PushUnsubscribeIn` + `db.remove_subscription` all exist on main — when the budget gate reopens, `getSubscription()` → unsubscribe → `subscription.delete()` can be wired with no backend work. Deferral remains (icons + unsubscribe are a single gate per design).
3. Pyright remains un-runnable in this environment (exit 124 ×2, zero output) — must run in CI/normal env.

## Status

Slice 3 verified and corrected: 3.1/4.1/4.2 done, 3.2 deferred (gate: 1,078 changed lines > 400), 5.2's commit portion done (release gate — PR/push/review — orchestrator-owned, not performed here). **76/76 tests green.** 7 commits on `slice-3-frontend`, local == origin (no push performed by this executor).
