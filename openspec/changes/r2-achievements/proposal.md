# Proposal: R2 Achievements (six behaviour families + confetti)

## Intent

Six §11 behaviour achievements make progress visible beyond XP/momentum; nothing recognises them today. R2 ships them derived-on-read with a Journey card and client celebration.

## Scope

### In Scope
- `achievements.py` pure engine: 6 earn predicates + earliest-earned date.
- `ACHIEVEMENTS` catalog (`constants.py`); dataclasses (`models.py`).
- `GET /api/achievements` (per-user isolation).
- Journey `#achievements-card` after the momentum card.
- Client confetti on new unlocks via read-diff (reuses R1 `shouldCelebrate`/`fireConfetti`).
- Tests: engine unit, API, frontend node + SPA drift pins.

### Out of Scope
Server push on unlock; partial-progress display; Today surface; World screen; catalogue changes; `reward_events` reuse.

## Capabilities

### New Capabilities
- `achievements`: catalog, six earn predicates, earliest-earned derivation, `GET /api/achievements`.

### Modified Capabilities
- `journey-progress-ui`: `#achievements-card` after the momentum card.
- `game-appearance`: confetti extended to achievement unlocks.

## Approach

Pure `achievements.py` mirroring `momentum.py`/`rewards.py`: no I/O; database.py gathers per-day facts (done quests by key/domain/date, action counts, daily exercise sums) in one read; one endpoint; SPA diffs earned keys across loads (first render suppressed). No schema change, no new tables.

## Key Decisions

1. **Any-window earn (endorse).** Earned stays earned — §7's unlock-state/date model implies a permanent event; trailing windows would flash unlocks. Consistency = 5 successful days (`momentum.is_successful`) in ANY 7-day span.
2. **Expose `unlocked_at` (ISO date) for all six.** Every predicate has a computable earliest date; null when locked. Local calendar dates, matching momentum.
3. **Comeback:** return = any day with ≥1 action (Spark-or-better, reusing `action_count`). Inactive day = assigned-quest day with zero actions (`assigned_quests > 0`, skipped counts as assigned, replaced-only days neutral — verified in `classify_day`). Predicate: ≥3 consecutive inactive days before a return day. A Spark day IS a return; requiring success would make it a consistency achievement in disguise.
4. **Personal Best: first exercise day counts.** Daily `SUM(exercise_entries.duration_min)` on D > max over strictly earlier days; empty pre-history max = 0, so the first >0-minute day earns it. Behaviour-first: free early win reinforces the behaviour; requiring a prior record feels unreachable.
5. **Moving Forward pins `quest_key == 'exercise_10'` AND `status == 'done'`, count ≥ 10.** Verified: `exercise_10` persists domain `exercise`, `streak_alive` persists `movement` — domain-pinning would wrongly count streak_alive and miss exercise_10.
6. **Explorer:** ≥5 distinct persisted `quests.domain` among done quests (pool has 6 domains — demanding but reachable late-game).
7. **Client-side read-diff confetti IN (endorse); server push deferred.** Reuses R1's proven `shouldCelebrate` pattern with first-render suppression; keeps the quest-complete hot path, schema, and scheduler untouched.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `achievements.py` | New | Pure engine |
| `constants.py`, `models.py` | Modified | Catalog + dataclasses |
| `database.py`, `routes.py` | Modified | Facts gather (one read); endpoint |
| `static/index.html`, `app.js`, `style.css` | Modified | Card + confetti read-diff |
| `tests/`, `tests/test_spa_gate.py` | Modified | Regression + drift pins |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Comeback false positive (replaced quests) | Low | Inactivity requires `assigned_quests > 0`; replaced-only days neutral (verified) |
| Confetti over/under-fire | Med | Proven read-diff + first-render suppression; node tests pin |
| History scan cost | Low | Single-user SQLite; one gather query |
| Exploration verification drift | Low | `exploration.md` (2026-08-10) verifies each claim against the live codebase; re-check facts during spec/design |
| Personal Best un-earns on entry deletion | Low | Derived-on-read accepted; deletion is rare and reversible by re-logging |

## Delivery Notes

3 chained PRs, each < 400 changed lines: S1 engine + catalog + dataclasses + unit tests (pure); S2 facts gather + endpoint + API tests; S3 SPA card + confetti + node tests + drift pins.

## Rollback Plan

Additive only. Revert slices in reverse (S3 → S2 → S1); frontend-only if celebration misbehaves. No migration, no backfill.

## Dependencies

- R1 archived (quests/momentum, exercise_entries, Journey UI). Nothing external.

## Success Criteria

- [ ] All six families earn per spec scenarios; data isolated per user.
- [ ] Confetti fires exactly once per new unlock; never on first render.
- [ ] Unlock dates correct across fresh/mid-flight/full histories.
- [ ] Full suite green (pytest + node --test); drift pins updated.
