# Exploration: R2 Achievements (six behaviour families)

> Verified against the live codebase on 2026-08-10. The existing `proposal.md`
> in this folder was drafted from an injected digest; this artifact verifies
> each of its claims against real code and surfaces the gaps a spec/design must
> resolve. No product code was changed.

## Current State

No achievements/badges state exists anywhere (no tables, endpoints, UI, or
catalog — grep for `achiev|badge` matches only the checkpoint *milestone strip*
and strategy/backlog prose). Strategy §11 (docs/strategy.md lines 606–640)
defines six behaviour families and forbids "eat less than 1,000 calories"-style
achievements. Strategy §7's `Achievement` model (type, requirements, progress,
unlock state, unlock date) and §6.2 (Journey surface contains achievements)
are the normative anchors. R1 shipped the data substrate:

- **quests table** — per-user rows, `quest_key`, `domain`, `status`
  (`open|done|skipped|replaced`), `xp_value`, `source` (`manual|detected`),
  `completed_at`, `date`. No per-date uniqueness (replacement adds a row).
  Completion is idempotent and terminal; `completed_at` is stamped by
  `update_quest_status` for BOTH manual and read-detected completions.
- **exercise_entries** — per-user rows, `date`, `duration_min`, multiple rows
  per day allowed (no per-date uniqueness).
- **momentum** — pure engine (`momentum.py`) with `MomentumDayFacts`
  (`assigned_quests`, `done_quests`, `log_rows` per date), `action_count`,
  `classify_day` (Spark ≥1 action, Good ≥2, Great = all done; `none` when
  `assigned_quests == 0` regardless of logs), `is_successful` (Good/Great only).
  `db.momentum_facts(user_id, start, end)` is **already parameterised by
  date range** — reusable over full history, not just the 21-day window.
- **xp** — pure `SUM(xp_value) WHERE status='done'`, no ledger.
- **Journey UI** — `#tab-journey` renders `#xp-card`, `#momentum-card`,
  `#quest-history-card`; `loadJourneyCards` fetches `/api/momentum`
  failure-scoped. Confetti read-diff: `shouldCelebrate(prev, cur)` in
  `format.js`, first render suppressed via `prevEarned === null` in `loadData`.

## Affected Areas

- `achievements.py` (new) — pure engine mirroring momentum.py/rewards.py: six
  earn predicates + earliest-earned date. No I/O.
- `constants.py`, `models.py` — `ACHIEVEMENTS` catalog; `AchievementState` /
  achievement dataclasses (per AGENTS.md hard rule 3).
- `database.py` — facts gather for the families momentum_facts cannot serve
  (Moving Forward key-count, Explorer distinct domains, Personal Best daily
  exercise sums). Per-user isolation via `user_id` filters (existing pattern).
- `routes.py` — `GET /api/achievements` (async, `Depends(require_user)`,
  `run_db` wrapper), mirroring `get_momentum`.
- `static/index.html`, `app.js`, `format.js`, `style.css` — Journey
  `#achievements-card` after `#momentum-card`; read-diff confetti on new
  unlocks; pure eligibility helper in format.js (node:test-pinnable).
- `tests/` — new `tests/test_achievements.py` (pure engine + DB layer, mirror
  test_momentum.py), API cases in `test_api.py`, frontend
  `tests/frontend/achievements.test.mjs` (mirror confetti.test.mjs), SPA drift
  pins in `tests/test_spa_gate.py`.

## Data Sources per Family (verified)

| Family | Predicate | Data source | Earliest-earned date |
|---|---|---|---|
| Getting Started | first done quest | `quests` first `status='done'` row | quest `date` (local calendar day) |
| Moving Forward | ≥10 done `quest_key='exercise_10'` | `COUNT(*) FROM quests WHERE quest_key='exercise_10' AND status='done'` | date of the 10th such quest |
| Consistency | ≥5 successful days in ANY 7-day span | `momentum_facts` over full history + `classify_day`/`is_successful` | 5th successful day of the earliest qualifying span |
| Comeback | return day after ≥3 consecutive inactive days | `momentum_facts` over full history; inactive = `assigned_quests > 0` and `action_count == 0`; return = any day with ≥1 action | the return day |
| Explorer | ≥5 distinct done `domain`s | `SELECT DISTINCT domain FROM quests WHERE status='done'` | date the 5th domain's first done quest |
| Personal Best | day whose `SUM(duration_min)` > max over strictly earlier days | `SELECT date, SUM(duration_min) FROM exercise_entries GROUP BY date` | the record-setting day (first exercise day when max=0) |

## Verified Proposal Claims

1. **Moving Forward pins `quest_key == 'exercise_10'`** — CORRECT and
   important: in `QUEST_POOL`, `exercise_10` has domain `exercise` and
   `streak_alive` has domain `movement`. Domain-pinning would count
   `streak_alive` (wrong) and miss `exercise_10`. Pin the key, not the domain.
2. **Comeback inactivity semantics** — CORRECT per `classify_day`:
   `assigned_quests == 0` (all rows replaced) → `none` regardless of logs, so
   replaced-only days are neutral; skipped counts as assigned (`status !=
   'replaced'` in `momentum_facts`); inactive requires assigned quests with
   zero actions. A Spark day IS a return.
3. **Explorer pool has 6 domains** — CORRECT: exercise, nutrition, movement,
   routine, wellbeing, weight.
4. **`momentum_facts` reuse** — CONFIRMED: it takes `(start, end)` so the full
   history (Consistency, Comeback) needs no new query. Only Moving Forward,
   Explorer, and Personal Best need new gather queries (one combined query or
   three small ones — design decision).

## Gaps and Risks

- **WARNING — Personal Best is not monotonic**: `exercise_entries` can be
  edited/deleted (`PUT`/`DELETE /api/exercise/{id}` exist). Deleting the
  record-setting entry un-earns the achievement under derived-on-read — unlike
  the five quest-based families (quests are terminal, done stays done). Spec
  must decide: accept un-earn on data deletion (honest derivation, simplest),
  or persist unlock events (adds the `reward_events`-adjacent table risk).
- **WARNING — earliest-earned date semantics**: use `quest.date` (local
  calendar day, matches momentum) NOT `completed_at` (wall-clock read time —
  for detected completions it is the read moment, not the entry day). Spec
  must pin this; the proposal says "ISO date" but does not pin the column.
- **GAP — "one gather query" claim**: momentum_facts covers 2 of 6 families;
  the other 3 need new queries. Not one query — at most one combined gather.
- **GAP — Consistency span definition**: "five of seven days" must be pinned
  to a rolling ANY-7-day span with ≥5 successful (proposal endorses this).
  It is monotonic (facts only accumulate), so it cannot un-earn.
- **RISK — confetti read-diff**: checkpoint diff uses a scalar earned count;
  achievements need a key-set diff (or a count — but a count can regress if
  Personal Best un-earns). First-render suppression pattern (`prev === null`)
  is proven and reusable.
- **RISK — history scan cost**: full-history momentum_facts + group-bys per
  request. Fine for single-user SQLite (R1 precedent), but the endpoint runs
  on every Journey load — keep the gather to one DB call.

## Approaches

1. **Derived-on-read (endorsed by existing proposal)** — pure engine +
  gather query + endpoint; no new tables, no schema change, no migration.
   - Pros: matches momentum/xp/rewards precedent exactly; zero persistence
     risk (avoids `reward_events`-style tables entirely); trivially unit
     testable.
   - Cons: Personal Best can un-earn on entry deletion (see risk above);
     earliest-earned recomputed each read.
   - Effort: Medium.
2. **Persisted unlocks** — new `achievements_earned` table (NOT
   `reward_events`), write on earn, read for state.
   - Pros: unlock is permanent; pushes naturally surfaceable; matches §7
     "unlock state/date" model.
   - Cons: schema change + write path on the quest-complete hot path;
     backfill for existing users; more surface to test; conflicts with the
     project's strong derived-not-persisted precedent.
   - Effort: High.

## Recommendation

Derived-on-read (Approach 1), consistent with the codebase's established
pattern — but the spec must explicitly accept the Personal Best un-earn edge
case (data deletion is rare, honest, and reversible by re-logging) and pin the
earliest-earned date to `quest.date`. Add a monotonic-key-set read-diff helper
in format.js for confetti (count-diff is unsafe only if Personal Best regresses;
a key-set diff is robust either way).

## Ready for Proposal

Yes — the existing `proposal.md` is substantially correct after verification.
The orchestrator should tell the user: decisions to confirm at spec time are
(1) Personal Best un-earn on entry deletion — accept or persist, (2) earliest-
earned date = quest local date, (3) Moving Forward pins quest_key not domain,
(4) no Today surface (Journey only), per the proposal's out-of-scope list.
