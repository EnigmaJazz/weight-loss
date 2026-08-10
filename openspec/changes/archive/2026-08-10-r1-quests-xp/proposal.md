# Proposal: R1 Quests, XP & Momentum (Release 1 umbrella)

## Intent

Ship RELEASE 1 of `docs/strategy.md` — the smallest complete behaviour-change loop (Goal → Quest → Action → Log → Reward → Progress). Today the app tracks weight/exercise/meals/streaks but lacks daily quests, XP/momentum, mood/habits, and goals/lifestyle onboarding. 6 chained PR slices (<400 lines, green, stacked-to-main); this proposal scopes the whole release.

## Assumptions (user-confirmed)

1. **Quest pool v1** (6 keys): `log_weight` weekly-only on settings `reminder_weekday`; `mood_checkin` always; rotation from `exercise_10`/`log_meal`/`streak_alive`/`habit_checkin`. 3/day (weigh-in: log_weight+mood+1; else mood+2); rotation seeded `hash(user_id,date)`; auto-complete read-detected (never punishes honest logging); skip terminal/no-XP; replace cap 1/day excluding assigned/replaced.
2. **XP**: 20 small/40 normal at generation; derived `SUM(xp_value WHERE done)`; level n = cumulative `100+(n−1)×50`; `LEVEL_TITLES` Sprout→Legend.
3. **Momentum** (derived): Spark ≥1 action, Good ≥2, Great = all quests done (≥1 action); successful = Good/Great; trailing 21-day window incl. today; no-quest day → none.
4. **Habits v1**: `water`, `fruit_veg`, `home_cooked`, `sleep_routine` (allowlist + drift-guard test); multi-row/day.
5. **Mood**: 1–5 + optional note, multi-row/day; POST/GET/DELETE `/api/mood` + `/api/habits`.
6. **Full R1 train**: quests; XP+momentum; mood/habits; Today UI (quests card + XP chip); Journey UI (XP/momentum/quest-history); onboarding extension (primary_goal allowlist `weight_loss|general_health|fitness|wellbeing`; secondary_goals + health_domains JSON lists; activity_level allowlist `sedentary|light|moderate|active`; ALL optional; wizard step "Goals & lifestyle" between target and units).
7. Completion read-derived (no upsert-route coupling); level-up via before/after diff.
8. `reward_events` dropped every init — never reuse; XP derived sidesteps it.
9. **Slices**: S1 quests backend → S2 XP+momentum → S3 mood/habits → S4a Today → S4b Journey → S5 onboarding (∥ after S2; order S3 ∥ S5, then S4a → S4b).

## Scope

### In Scope
- **S1**: `quests` table + `quests.py` engine (generate/select/status/replace; hash rotation; entry-table auto-detect) + `/api/quests`.
- **S2**: XP (derived, level curve, titles) + `momentum.py` (tiers, 21-day) + `/api/progress`.
- **S3**: `mood_entries` + `habit_entries`; `/api/mood`, `/api/habits` CRUD; `HABIT_TYPES` allowlist.
- **S4a**: Today quests card + XP chip. **S4b**: Journey XP/momentum/quest-history cards.
- **S5**: onboarding extension — 4 optional fields + "Goals & lifestyle" step (wizard gate/smoke-pin updates).

### Out of Scope (R2+)
Achievements, level-up celebrations/push, weekly objectives, World, Coach/AI, social, quest categories/icons/rerolls, weekly summary, food database, `reward_events`, multi-day quests.

## Capabilities

### New Capabilities
- `daily-quests`: pool, generation, lifecycle, auto-complete.
- `xp-progression`: XP derivation, level curve, titles.
- `momentum`: Spark/Good/Great tiers, 21-day window.
- `mood-logging` / `habit-logging`: multi-entry CRUD + allowlist.
- `today-quests-ui`: Today quests card + XP chip.
- `journey-progress-ui`: Journey XP/momentum/quest-history cards.

### Modified Capabilities
- `user-onboarding`: optional goals/lifestyle fields + new wizard step.
- `game-appearance`: R1 surfaces consume token system; wizard step-indicator/DOM/copy pins updated.

## Approach

Pure modules (`quests.py`, `momentum.py`) mirror `rewards.py`: no I/O, dataclasses in `models.py`, tables via SCHEMA_STATEMENTS, routes via `run_db`. Completion/XP/momentum derived on read from entry tables (weight/exercise/meal; mood/habit after S3). Hash seeding keeps rotation stable. All endpoints per-user (config rule).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `database.py` | Modified | quests/mood_entries/habit_entries + methods |
| `models.py` | Modified | Quest, MoodEntry, HabitEntry, XP/Momentum state |
| `constants.py` | Modified | QUEST_POOL, XP, LEVEL_TITLES, HABIT_TYPES |
| `quests.py` / `momentum.py` | New | Pure engines |
| `routes.py` | Modified | `/api/quests`, `/api/progress`, `/api/mood`, `/api/habits` |
| `static/*` | Modified | Today/Journey UI, onboarding wizard |
| `tests/` | Modified | Engine/API/drift-guard regression tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Wizard step insertion breaks pinned DOM/copy smoke tests | Med | Update smoke-ui + pins in S5 |
| Parallel S3 ∥ S5 touch shared files | Med | Disjoint routes/tables; rebase before S4a |
| Legacy users lack `reminder_weekday`/new fields | Med | Defaults; fields optional |
| `reward_events` temptation | Low | Derived XP; dropped every init |
| Auto-detect timezone drift | Med | `_local_now()` pattern |

## Rollback Plan

Each slice reverts independently (file revert; `CREATE IF NOT EXISTS` needs no migration; derived state no backfill). Full revert = revert merged slices; data preserved.

## Dependencies

- `activity-logging` merged (exercise/meal tables are auto-detect sources); S1 auto-detect for mood/habit keys lands with S3 tables.

## Success Criteria

- [ ] All 6 slices green (pytest, node tests, pyright) at merge.
- [ ] Same day renders identical rotation; XP/momentum stable across reads.
- [ ] Strategy exit: usable daily ~2 weeks without DB/dev-tool edits.

## Open Questions

- Level-up celebration in R1 (default: quiet XP chip, no push)?
- Weekly summary in R1 (default: no)?
