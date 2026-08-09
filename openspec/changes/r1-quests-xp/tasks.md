# Tasks: R1 Quests, XP & Momentum (r1-quests-xp)

## Review Workload Forecast

```
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low
```

| Field | Value |
|---|---|
| Estimated changed lines | ~3490 total (300–390 per PR) |
| 400-line budget risk | Low — every PR ≤390, no `size:exception` |
| Chained PRs recommended | Yes — 10 stacked PRs to main |
| Suggested split | S1a→S1b→S2a→S2b, then S3a→S3b and S5a→S5b (parallel off S2b tip, merged before S4), then S4a→S4b |
| Delivery strategy | auto-chain (proceed; no user decision gate) |

### PR merge order + work-unit evidence

| # | PR title (branch) | Focused test cmd | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 1 | `feat(quests): deterministic quest domain + engine` (S1a) | `python -m pytest tests/test_quests.py -q` | in-process ASGI via pytest (real route path) | revert database.py DDL/methods + models.py + constants.py + quests.py (inert table) |
| 2 | `feat(routes): expose quest lifecycle` (S1b) | `python -m pytest tests/test_api.py -q` | in-process ASGI via pytest | revert routes.py quest endpoints; rows preserved |
| 3 | `feat(progress): derive xp levels` (S2a) | `python -m pytest tests/test_xp.py tests/test_api.py -q` | in-process ASGI via pytest | revert xp.py + constants + `/api/xp` |
| 4 | `feat(momentum): derive 21-day state` (S2b) | `python -m pytest tests/test_momentum.py tests/test_api.py -q` | in-process ASGI via pytest | revert momentum.py + `/api/momentum` |
| 5 | `feat(logging): add mood and habits` (S3a) | `python -m pytest tests/test_mood_api.py tests/test_habit_api.py tests/test_spa_gate.py -q` | served static + SPA gate | revert mood/habit tables + routes (inert rows) |
| 6 | `feat(quests): detect wellbeing actions` (S3b) | `python -m pytest tests/test_quests.py tests/test_momentum.py -q` | in-process ASGI via pytest | revert detection/momentum extension only |
| 7 | `feat(today): surface quests and xp` (S4a) | `node --test tests/frontend/xp.test.mjs && python -m pytest tests/test_spa_gate.py -q` | `bash tests/smoke-ui.sh` (served app) | revert Today markup/JS/CSS |
| 8 | `feat(journey): show progression` (S4b) | `python -m pytest tests/test_spa_gate.py -q` | `bash tests/smoke-ui.sh` | revert Journey cards markup/JS/CSS |
| 9 | `feat(onboarding): persist goals and lifestyle` (S5a) | `python -m pytest tests/test_onboarding.py -q` | in-process ASGI via pytest | revert AppSettings fields + validators; retained keys harmless |
| 10 | `feat(spa): collect and edit goals` (S5b) | `python -m pytest tests/test_index_html.py tests/test_spa_gate.py -q` | `bash tests/smoke-ui.sh` (wizard flow) | revert wizard step + form markup |

Threat matrix: all rows N/A per design; auth/ownership/404/422/409 behaviors are covered by the API tests listed per PR — no separate RED tasks.

---

## PR 1 · S1a (~360) — quest domain + engine

- [x] 1.1 `database.py`: append `CREATE TABLE IF NOT EXISTS quests(...)` (status CHECK open|done|skipped|replaced, no date uniqueness) to `SCHEMA_STATEMENTS`; add `_quest_from_row` mapper.
- [x] 1.2 `database.py`: ownership-scoped (WHERE user_id) methods — `insert_quests`, `list_quests_for_date`, `update_quest_status`, `list_assigned_keys_today`, `count_replaced_today` (status='replaced', user+date).
- [x] 1.3 `models.py`: add `Quest` + `QuestDetectionFacts` dataclasses (entry-style, omit owner ids).
- [x] 1.4 `constants.py`: add `QUEST_POOL` — order `exercise_10, log_meal, streak_alive, habit_checkin` + mandatory `mood_checkin` + weekly `log_weight`; entries `(key, domain, title, description, xp_value, size)`.
- [x] 1.5 create `quests.py` (pure, no I/O): `generate_quests(user_id, date, settings)` — weigh-in day = log_weight+mood+1 rotating, else mood+2; rotation = `sha256(f"{user_id}:{date}:{key}")` ranked, excludes assigned-today only; `reconcile`; transition rules (done idempotent, skip terminal, replace excludes assigned+replaced keys, cap 1/day); `detect` from `QuestDetectionFacts` (weight/exercise/meal; mood/habit inactive until PR 6).
- [x] 1.6 Tests `tests/test_quests.py`: `test_generation_matrix`, `test_seed_stability`, `test_replace_exclusions_and_cap`, `test_transition_matrix`, `test_detection_matrix`.
- Commit plan (work unit): `feat(quests): add deterministic quest domain` — tasks 1.1–1.6 in one commit (tests with code). Acceptance: `python -m pytest tests/test_quests.py -q` all green; `pyright` clean.

## PR 2 · S1b (~390) — quest lifecycle API

- [ ] 2.1 `routes.py`: quest serializers + `GET /api/quests` — generate when absent, reconcile, return 3 current rows, `is_today_weigh_in`, `can_replace`, newest 10 history rows.
- [ ] 2.2 `routes.py`: `POST /api/quests/{id}/complete|skip|replace` — foreign/missing → 404; non-today → 409; done-complete → 200 no-op; skipped/replaced-complete → 409; skip idempotent only for skipped; replace requires open/current/cap/eligible key else 409. No write coupling from existing log routes.
- [ ] 2.3 Tests `tests/test_api.py`: `test_quest_crud_and_idempotency`, `test_quest_404_isolation`, `test_quest_wrong_day_409`, `test_quest_auto_detection`.
- Commit plan (work unit): `feat(routes): expose quest lifecycle` — tasks 2.1–2.3. Acceptance: `python -m pytest tests/test_api.py -q` green; `pyright` clean.

## PR 3 · S2a (~330) — derived XP

- [ ] 3.1 `constants.py`: `LEVEL_XP_PER_LEVEL`, `LEVEL_XP_STEP`, `LEVEL_TITLES` (1–4 Sprout, 5–9 Explorer, 10–19 Adventurer, 20–29 Champion, 30+ Legend).
- [ ] 3.2 create `xp.py` (pure): `threshold_for_level` (cumulative 100+(n−1)×50), `level_from_xp` (greatest L with threshold ≤ total, min 1), `level_progress` (xp_into_next, next_level_at), `title_for_level`.
- [ ] 3.3 `models.py`: XP state dataclass (level, title, total_xp, xp_into_next, next_level_at).
- [ ] 3.4 `database.py`: per-user XP aggregate = `SUM(xp_value) WHERE status='done'` (no `reward_events`).
- [ ] 3.5 `routes.py`: `GET /api/xp`; level-up detection in quest complete via before/after level diff (`level_up:{from,to}|null`, quiet on repeat).
- [ ] 3.6 Tests: `tests/test_xp.py` (`test_threshold_vectors` 99/100/250, `test_progress_vectors`, `test_title_bands` 4/5/29/30); `tests/test_api.py` (`test_xp_api_boundaries`, `test_level_up_diff`).
- Commit plan (work unit): `feat(progress): derive xp levels` — tasks 3.1–3.6. Acceptance: `python -m pytest tests/test_xp.py tests/test_api.py -q` green; `pyright` clean.

## PR 4 · S2b (~280) — momentum

- [ ] 4.1 create `momentum.py` (pure): `classify_day` — all done & ≥1 action = Great, ≥2 = Good, ≥1 = Spark, no assignments = none (Great precedence; replaced rows not current; skipped blocks Great).
- [ ] 4.2 `database.py`: `momentum_facts(user, start, end)` — done quests + weight/exercise/meal rows per date; window = today−20 … today (21 days).
- [ ] 4.3 `routes.py`: `GET /api/momentum` → `today_tier`, `successful_days` (Good/Great), `window_days` (21).
- [ ] 4.4 Tests: `tests/test_momentum.py` (`test_tier_matrix`, `test_inclusive_21_days`, `test_day_22_excluded`, `test_no_quests_none`); `tests/test_api.py` `test_momentum_api_isolation`.
- Commit plan (work unit): `feat(momentum): derive 21-day state` — tasks 4.1–4.4. Acceptance: `python -m pytest tests/test_momentum.py tests/test_api.py -q` green; `pyright` clean.

## PR 5 · S3a (~390) — mood & habit CRUD

- [ ] 5.1 `database.py`: `mood_entries` + `habit_entries` DDL (multi-row/day), `_mood_from_row`/`_habit_from_row`, CRUD methods (list newest-first, insert, delete ownership-scoped).
- [ ] 5.2 `models.py`: `MoodEntry`, `HabitEntry` dataclasses.
- [ ] 5.3 `constants.py`: `HABIT_TYPES` = exactly `water, fruit_veg, home_cooked, sleep_routine`.
- [ ] 5.4 `routes.py`: `MoodIn` (mood 1–5, note ≤500 chars), `HabitIn` (`habit_type` allowlist); `POST/GET/DELETE /api/mood`, `/api/habits` — 422 validation, 404 on foreign/missing, newest-first.
- [ ] 5.5 `static/app.js`: `HABIT_TYPES` mirror of the constant.
- [ ] 5.6 Tests: `tests/test_mood_api.py` + `tests/test_habit_api.py` (`test_create_list_delete`, `test_multiple_daily`, `test_validation`, `test_404_isolation`, `test_401`); drift guard `test_spa_gate.py::test_habit_types_literal_matches_server_constant`.
- Commit plan (work unit): `feat(logging): add mood and habits` — tasks 5.1–5.6. Acceptance: `python -m pytest tests/test_mood_api.py tests/test_habit_api.py tests/test_spa_gate.py -q` green; `pyright` clean.

## PR 6 · S3b (~320) — wellbeing detection

- [ ] 6.1 `quests.py`: extend `QuestDetectionFacts` + `detect` — mood row → `mood_checkin` done/source `detected`; habit row → `habit_checkin`; `streak_alive` any qualifying row; `exercise_10` sum ≥10 stays.
- [ ] 6.2 `database.py`: detection-facts query now includes mood/habit rows; keep routes free of quest writes.
- [ ] 6.3 `momentum.py`: actions now include mood/habit row counts.
- [ ] 6.4 Tests: extend `test_quests.py::test_detection_matrix` (mood/habit keys) and momentum tier test with mood/habit rows.
- Commit plan (work unit): `feat(quests): detect wellbeing actions` — tasks 6.1–6.4. Acceptance: `python -m pytest tests/test_quests.py tests/test_momentum.py -q` green; `pyright` clean.

## PR 7 · S4a (~380) — Today quests card + XP chip

- [ ] 7.1 `static/index.html`: `#quests-card` (3 rows: label, domain, XP, status; open rows offer Complete/Skip/Replace; terminal rows no invalid controls) + `#xp-summary-chip` (title, level, total, progress) on Today.
- [ ] 7.2 `static/app.js`: `loadData` adds quests + xp via `Promise.allSettled`; `renderQuests`; `mutateQuest` (disable while pending, error feedback, never remove card, replace-cap 409 leaves assignment); `renderXpChip`.
- [ ] 7.3 `static/format.js`: pure mirrors `thresholdForLevel`, `levelFromXp`, `xpIntoNext`.
- [ ] 7.4 `static/style.css`: token-only (no hex literals), dark-mode, 48px targets, focus visible, `prefers-reduced-motion` neutralized.
- [ ] 7.5 Tests: `tests/frontend/xp.test.mjs` (99/100/250 vs backend); `test_spa_gate.py::test_today_quest_surface`; `tests/smoke-ui.sh` quest selectors/actions.
- Commit plan (work unit): `feat(today): surface quests and xp` — tasks 7.1–7.5. Acceptance: `node --test tests/frontend/xp.test.mjs && python -m pytest tests/test_spa_gate.py -q && bash tests/smoke-ui.sh` green; `pyright` clean.

## PR 8 · S4b (~350) — Journey XP/momentum/quest-history cards

- [ ] 8.1 `static/index.html`: `#xp-card` (level, title, total, progress, recent completions), `#momentum-card` (today tier, successful/21), `#quest-history-card` (date, label, status, awarded XP; non-done = 0; explicit empty state).
- [ ] 8.2 `static/app.js`: `renderJourneyXp`, `renderMomentum`, `renderQuestHistory`; `loadData` scoped failure preserves other cards; accessible loading/error announcements.
- [ ] 8.3 `static/style.css`: Journey card styling (existing tokens, mobile stacking).
- [ ] 8.4 Tests: `test_spa_gate.py::test_journey_progress_surfaces`; Journey smoke; `test_index_html_journey_panel_absorbs_charts_and_history` must stay unchanged.
- Commit plan (work unit): `feat(journey): show progression` — tasks 8.1–8.4. Acceptance: `python -m pytest tests/test_spa_gate.py -q && bash tests/smoke-ui.sh` green.

## PR 9 · S5a (~300) — onboarding backend (goals/lifestyle)

- [ ] 9.1 `models.py`: `AppSettings` adds `primary_goal`, `secondary_goals`, `health_domains`, `activity_level` (defaults `null`, `[]`, `[]`, `null`).
- [ ] 9.2 `database.py`: settings defaults + `_optional_json_list` helper + JSON list serialization in `_apply_settings` (round-trip preserves order).
- [ ] 9.3 `routes.py`: `SettingsIn`/`OnboardingIn` validators — primary_goal `weight_loss|general_health|fitness|wellbeing`, activity_level `sedentary|light|moderate|active`, `extra="forbid"`, height checked before BMI bounds; `complete_onboarding` atomically upserts all settings incl. goals/lifestyle, inserts today's weight (single), reconciles rewards.
- [ ] 9.4 Tests: `tests/test_onboarding.py` — allowlist 422 preserves settings, JSON list round-trip per user, idempotent re-POST keeps single weight, partial-failure rollback; existing XOR/extra/atomic tests stay green.
- Commit plan (work unit): `feat(onboarding): persist goals and lifestyle` — tasks 9.1–9.4. Acceptance: `python -m pytest tests/test_onboarding.py -q` green; `pyright` clean.

## PR 10 · S5b (~390) — wizard step + Me card UI

- [ ] 10.1 `static/app.js`: `WIZARD_STEPS` → six steps (height, weight, target, goals-lifestyle, units, notifications); `#wizard-step-goals-lifestyle` between target and units; six step dots; wizard payload includes 4 optional fields; branch on `needs_onboarding` before tracker load.
- [ ] 10.2 `static/index.html`: `#goals-lifestyle-form` — primary_goal select, secondary_goals + health_domains lists, activity_level select (ALL optional).
- [ ] 10.3 `static/app.js`: render/save handlers for the step + Me tab goals/lifestyle settings card.
- [ ] 10.4 Tests: update `test_index_html_ships_onboarding_wizard_between_auth_and_tracker` (six steps), `test_index_html_ships_mascot_and_wizard_indicator` (six dots), `tests/smoke-ui.sh` goals step.
- Commit plan (work unit): `feat(spa): collect and edit goals` — tasks 10.1–10.4. Acceptance: `python -m pytest tests/test_index_html.py tests/test_spa_gate.py -q && bash tests/smoke-ui.sh` green.

## Final · Verify Checklist (per spec coverage)

- [ ] V.1 `daily-quests` — `python -m pytest tests/test_quests.py tests/test_api.py -q` (generation/seed/replace/transition/detection; 404 isolation; 409 wrong day).
- [ ] V.2 `xp-progression` — `python -m pytest tests/test_xp.py tests/test_api.py -q` (99/100/250; titles 4/5/29/30; level-up diff quiet on repeat).
- [ ] V.3 `momentum` — `python -m pytest tests/test_momentum.py tests/test_api.py -q` (tiers, 21-day inclusive, day 22 excluded, isolation).
- [ ] V.4 `mood-logging` + `habit-logging` — `python -m pytest tests/test_mood_api.py tests/test_habit_api.py -q` + drift guard (four-value pin across backend/UI/detection).
- [ ] V.5 `today-quests-ui` + `journey-progress-ui` + `game-appearance` — `node --test tests/frontend/ && python -m pytest tests/test_spa_gate.py -q && bash tests/smoke-ui.sh` (selectors, reduced motion, existing pins unchanged).
- [ ] V.6 `user-onboarding` — `python -m pytest tests/test_onboarding.py tests/test_index_html.py tests/test_spa_gate.py -q` (allowlists, XOR, atomic, wizard gates).
- [ ] V.7 Full gate — `python -m pytest -q && node --test tests/frontend/ && pyright && bash tests/smoke-ui.sh`; all green on the final merged main.
