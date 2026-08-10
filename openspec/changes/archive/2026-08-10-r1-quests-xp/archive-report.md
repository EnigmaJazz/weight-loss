# Archive Report — r1-quests-xp (Release 1: Quests, XP, Momentum, Mood/Habits, Journey UI, Onboarding Extension)

**Status**: COMPLETE
**Archived**: 2026-08-10
**Branch**: `main` — closed at commit `99a011b` (`docs(openspec): verify r1-quests-xp pass after remediation`)

## Executive Summary

Release 1 of `docs/strategy.md` shipped — the smallest complete behaviour-change loop (Goal → Quest → Action → Log → Reward → Progress):

- **Daily quests**: `quests` table + pure `quests.py` engine; 3 quests/day (weigh-in day: log_weight + mood + 1, else mood + 2); deterministic SHA-256 rotation seeded `(user_id, date, key)`; read-detected auto-completion (never punishes honest logging); skip terminal/no-XP; replace cap 1/day; ownership-scoped API with 404/409 isolation.
- **XP + levels**: derived `SUM(xp_value WHERE done)`; cumulative level curve `100+(n−1)×50`; `LEVEL_TITLES` Sprout→Explorer→Adventurer→Champion→Legend; level-up diff via before/after; no ledger (sidesteps the dropped `reward_events` table).
- **Momentum**: pure 21-day derivation; Spark ≥1 action, Good ≥2, Great = all done; successful = Good/Great; trailing window incl. today.
- **Mood + habits**: multi-row/day CRUD; mood 1–5 + ≤500-char note; `HABIT_TYPES` allowlist exactly `water|fruit_veg|home_cooked|sleep_routine` with literal drift-guard pin.
- **Today UI**: `#quests-card` (open rows offer Complete/Skip/Replace; terminal rows no invalid controls) + `#xp-summary-chip` (title/level/total/progress); failure-scoped `Promise.allSettled` loading with quests→XP sequencing.
- **Journey UI**: `#xp-card` (level/title/total/progress/recent completions), `#momentum-card` (today tier + successful/21), `#quest-history-card` (date/label/status/awarded XP; non-done = 0; explicit empty state); payload reuse from S4a plus scoped momentum fetch.
- **Onboarding extension**: optional `primary_goal`/`secondary_goals`/`health_domains`/`activity_level` (allowlists + JSON-list round-trip), atomic `complete_onboarding`, six-step wizard with `#wizard-step-goals-lifestyle` between target and units, Me-tab goals/lifestyle settings card.

## Delivery

- 10 stacked PRs (S1a→S1b→S2a→S2b→S3a→S3b→S4a→S4b, S5a→S5b), all ≤400 lines except S4a (610, maintainer-accepted exception recorded in the runtime ledger), all green at merge.
- Verify checklist V.1–V.7 executed on final merged main.

## Verification Evidence (final, per verify-report @ 99a011b)

| Gate | Command | Result |
|---|---|---|
| Full pytest | `.venv/bin/python -m pytest -q` | **550 passed** |
| Frontend | `node --test tests/frontend/*.test.mjs` | **119 passed, 0 failed** |
| Type check | `.venv/bin/pyright` | **0 errors, 0 warnings** |
| Browser smoke | `bash tests/smoke-ui.sh` | **62 passed, 0 failed** |
| Spec compliance | all 30 requirements compliant | **30/30** |
| Scenarios | all 57 with passing evidence | **57/57** |
| Native validate | `gentle-ai sdd-verify-validate --requirements 30 --scenarios 57` | **valid: pass** |

### Remediation history (verify FAIL → PASS)

The first verify report (f41a5b6) recorded 4 CRITICALs. All remediated on main:

1. **MoodEntry/HabitEntry owner contract** — resolved by spec amendment: entry specs now pin the entry-style convention (owner id is a table column + API ownership filter, never a dataclass field, mirroring WeightEntry/ExerciseEntry/MealEntry). Regression pins added (dataclass MUST NOT carry `user_id`; persisted table MUST).
2. **Habit drift guard** — `HABIT_TYPES` pinned to the literal four-value tuple with a non-empty ghost-loop guard.
3. **Ghost loops** — non-empty assertions added before all four flagged iteration sites.
4. SPA-gate classList WARNING retained (browser smoke provides behavioral proof).

Remediation commits: `03ca82e` (spec amendments + drift guard + ghost-loop guards), `a2df636` (entry-style pins), `99a011b` (verify report refresh to pass).

## Delivery Note (receipt-driven review)

The native bounded review transaction for this change is **wedged by a provider runtime-interception defect**: the OpenCode provider plugin injected a different lineage's candidate context (rewards-portrait, 14 paths) into the fresh review binding (entry-style pins, 2 paths); both created lineages (`review-49573eff66924b2b`, `review-62f43dfcaeed9fe3`) are frozen with immutable lens-context records. The reviewer correctly refused to fabricate an inspection. Per the maintainer's explicit decision, the defect was **not** reported to the Gentle AI repository, and receipt-driven review was disabled for this clone (`gentle-ai review mode disable --scope clone`). Delivery proceeds under ordinary repository policy: the `.gga` pre-commit hook passed on every commit, the full test suite (550 pytest + 119 node + 62 smoke) is green on the closed revision, and pyright is clean.

## Carry-Forward Notes

- **S4a over-budget**: 610 changed lines vs 400 forecast — accepted by maintainer (runtime ledger reset recorded). Future slice forecasts should budget Today UI more conservatively.
- **Sub-agent transport instability**: six consecutive delegated-apply/verify/archive launches died in transport (`sdd_task_result_malformed`, provider socket errors) during this cycle; work was completed inline with orchestrator-verified evidence. Worth investigating the OpenCode sub-agent bridge before the next SDD cycle.
- **`tests/test_index_html.py` does not exist** in this repo; the onboarding wizard pins live in `tests/test_spa_gate.py` (per S5b).
- **`node --test tests/frontend/` (bare dir) fails on Node v26.3.0**; use `node --test tests/frontend/*.test.mjs`.
- **Scratch smoke servers**: use a distinct port + `setsid -f env WEIGHT_LOSS_DB=... WEIGHT_LOSS_VAPID_KEYS=...`; clean up with `pkill -f "uvicorn main:app --port <port>"`.

## Artifact Inventory

- Proposal, design, tasks (53/53), apply-progress, verify-report — all in this archive folder.
- Nine capability specs synced to `openspec/specs/`: daily-quests, xp-progression, momentum, mood-logging, habit-logging, today-quests-ui, journey-progress-ui (new), user-onboarding + game-appearance (delta-merged into existing catalog specs).
- Task completion gate: all 53 tasks `[x]` in the archived tasks.md.
