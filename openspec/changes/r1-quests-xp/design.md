# Design: R1 Quests, XP & Momentum

## Technical Approach

Implement per-user SQLite state plus pure modules. Routes remain `async` with `run_db`; dataclasses stay in `models.py`. `reward_events` remains dropped. Six product slices require ten physical PRs.

## Architecture Decisions

| Decision | Choice and rationale |
|---|---|
| Determinism | Rank rotating keys by `sha256(f"{user_id}:{date}:{key}").digest()` then catalogue order; take the first N. Unlike Python `hash()`, this survives process restarts. Replacement uses the same ranking after excluding every key represented by any row that day. |
| Derivation | `quests.py`, `xp.py`, and `momentum.py` accept dataclasses/facts and perform no I/O, matching `rewards.py`; `Database` gathers/persists facts transactionally. |
| Progress | XP is `SUM(quests.xp_value WHERE done)`. `xp.py` owns `threshold_for_level`, `level_from_xp`, `level_progress`, `title_for_level`; titles are 1–4 Sprout, 5–9 Explorer, 10–19 Adventurer, 20–29 Champion, 30+ Legend. Completion returns `level_up:{from,to}|null`; R1 sends no push or animation. |
| Loading | Keep existing `Promise.all`; use `Promise.allSettled` for R1 requests so scoped failures preserve existing cards. |

## Data and API Contracts

`quests(id,user_id,date,quest_key,domain,title,description,xp_value,status CHECK(open|done|skipped|replaced),difficulty,source,completed_at,created_at)` has no date uniqueness. Source is `rules`, then `manual`/`detected`. Entry-style dataclasses omit owner IDs. `mood_entries(id,user_id,date,time,mood,note,created_at)` and `habit_entries(id,user_id,date,time,habit_type,created_at)` allow multiple daily rows. Dates are required; times normalize to null.

`QUEST_POOL` order is `exercise_10,log_meal,streak_alive,habit_checkin`, plus mandatory `mood_checkin` and weekly `log_weight`; entries are `(key,domain,title,description,xp_value,size)`. `generate_quests(user_id,date,settings)` selects mood + weight + one rotation when `date.weekday()==reminder_weekday`, otherwise mood + two. Generation excludes assigned-today keys only; replacement excludes all assigned/replaced keys and counts `status='replaced'` (cap one). `QuestDetectionFacts` maps weight row, exercise sum ≥10, meal row, or any qualifying row; S3 adds mood/habit facts.

`GET /api/quests` generates when no rows exist, reconciles open quests, and returns three current rows, `is_today_weigh_in`, `can_replace`, and newest 10 history rows. `POST /api/quests/{id}/complete|skip|replace`: foreign/missing 404; non-today 409; done completion 200 no-op; skipped/replaced completion 409; skip is idempotent only for skipped; replace requires open/current/cap/eligible key, else 409. `GET /api/xp` returns level/title/total/xp_into_next/next_level_at and 10 recent completions. `GET /api/momentum` returns tier/successful_days/window_days/is_successful_today.

`momentum.py` consumes bulk `Database.momentum_facts(user,start,end)`. Actions are done quests plus log-row counts. Assignments exclude replaced rows. Great = all done and ≥1 action; Good ≥2; Spark ≥1; no assignments = none. Window is today−20 through today.

## Delivery Slices

| Slice / physical PRs | Exact surface, tests, commit, rollback, gates |
|---|---|
| S1a (≈360) → S1b (≈390) | `database.py` DDL/row mapper/query+transaction methods; `models.py:Quest,QuestDetectionFacts`; `constants.py:QUEST_POOL`; create `quests.py`; `routes.py` quest serializers/routes. Tests `test_quests.py`, quest cases in `test_api.py`. Commits `feat(quests): add deterministic quest domain` then `feat(routes): expose quest lifecycle`. Revert leaves/removes inert table code; pytest/pyright, no SPA gate. |
| S2a (≈330) → S2b (≈280) | `constants.py:LEVEL_XP_PER_LEVEL,LEVEL_XP_STEP,LEVEL_TITLES`; create `xp.py`,`momentum.py`; `models.py` fact/state dataclasses; `database.py` aggregate methods; `routes.py` XP/momentum and before/after complete diff. Tests `test_xp.py`,`test_momentum.py`, API cases. Commits `feat(progress): derive xp levels` then `feat(momentum): derive 21-day state`. Revert is calculation/API-only; pytest/pyright. |
| S3a (≈390) → S3b (≈320) | DDL/dataclasses/row mappers/CRUD; `constants.py:HABIT_TYPES`; `routes.py:MoodIn,HabitIn`, POST/GET/DELETE `/api/mood`,`/api/habits`; extend detection/momentum; `static/app.js:HABIT_TYPES`. Tests `test_mood_api.py`,`test_habit_api.py`, drift gate. Commits `feat(logging): add mood and habits` then `feat(quests): detect wellbeing actions`. Revert leaves inert rows; pytest/pyright/SPA gate. |
| S4a (≈380) | `index.html:#quests-card,#xp-summary-chip`; `app.js:loadData,renderQuests,mutateQuest,renderXpChip`; `format.js` XP mirrors; token-only `style.css`. Tests `frontend/xp.test.mjs`, new Today SPA gates, smoke quest selectors/actions. Commit `feat(today): surface quests and xp`; UI-only revert; pytest/node/smoke/pyright. |
| S4b (≈350) | `index.html:#xp-card,#momentum-card,#quest-history-card`; `app.js:loadData,renderJourneyXp,renderMomentum,renderQuestHistory`; `style.css`. New Journey gates/smoke; existing `test_index_html_journey_panel_absorbs_charts_and_history` stays unchanged. Commit `feat(journey): show progression`; UI-only revert; all gates. |
| S5a (≈300) → S5b (≈390) | Backend: settings defaults/AppSettings, `_optional_json_list`, JSON serialization in `_apply_settings`, validators in `SettingsIn`/`OnboardingIn`, atomic completion. UI: `WIZARD_STEPS`, `#wizard-step-goals-lifestyle`, six dots, payload, `#goals-lifestyle-form`, render/save handlers. Tests onboarding/settings then gates/smoke. Commits `feat(onboarding): persist goals and lifestyle` then `feat(spa): collect and edit goals`. Revert safely ignores retained keys; pytest/node/smoke/pyright. |

Merge S1a→S1b→S2a→S2b; branch S3 and S5 there, rebase/merge both before S4a→S4b.

## Test Inventory

New: `test_quests.py::{test_generation_matrix,test_seed_stability,test_replace_exclusions_and_cap,test_transition_matrix,test_detection_matrix}`; `test_api.py::{test_quest_crud_and_idempotency,test_quest_404_isolation,test_quest_wrong_day_409,test_quest_auto_detection,test_xp_api_boundaries,test_level_up_diff,test_momentum_api_isolation}`; `test_xp.py::{test_threshold_vectors,test_progress_vectors,test_title_bands}`; `test_momentum.py::{test_tier_matrix,test_inclusive_21_days,test_day_22_excluded,test_no_quests_none}`; mood/habit files each `{test_create_list_delete,test_multiple_daily,test_validation,test_404_isolation,test_401}`; SPA gates `{test_habit_types_literal_matches_server_constant,test_today_quest_surface,test_journey_progress_surfaces}`; node `xp.test.mjs` vectors 99/100/250; smoke adds quest/chip/Journey checks.

Existing changed only in S5: `test_index_html_ships_onboarding_wizard_between_auth_and_tracker` (six steps), `test_index_html_ships_mascot_and_wizard_indicator` (six dots), `tests/smoke-ui.sh` (goals step). Onboarding XOR/extra/atomic/idempotent/rollback tests remain green.

## Threat Matrix

HTTP routes change, but all matrix rows are N/A: documentation-like paths, Git selection, commit, push, and PR commands are never executed. Authentication, ownership-scoped SQL, 404 concealment, validation 422, and lifecycle 409 tests cover APIs.

## Migration / Rollout

Tables use additive `CREATE IF NOT EXISTS` statements inside `init_schema`’s existing `_tx`; no backfill or destructive migration. Settings are additive key/value rows. Rollback preserves data. Each physical PR is independently green and shippable.

## Open Questions / Conflicts

- **Blocking before tasks:** launch says 10/20 XP, while proposal and daily-quests spec require 20/40; design follows normative 20/40 pending confirmation.
- Launch says mood note ≤200 and `habit_key`; specs require ≤500 and `habit_type`; design follows specs.
- Launch names `#wizard-step-goals`; onboarding spec requires `#wizard-step-goals-lifestyle`; design follows the spec.
- Six PRs cannot credibly satisfy the 400-line guard; the ten physical boundaries above preserve the six product slices.
