---
date: 2026-08-13
topic: r2-completion
---

# R2 Completion: Quest Icons, Weekly Objectives, Collectibles, Celebrations

## Summary

Complete the R2 "Make it enjoyable" vertical release with four additions: per-domain inline-SVG quest icons (plus a cartoon-fox mascot rework so the icon set is coherent), Mon–Sun weekly objectives (10 quests / 3 good days, +40 XP each, awarded the moment a goal is met, forward-only from activation with a first-partial-week exemption), a cosmetic collectibles system fed by achievements, goal checkpoints, meal-day streaks and first-time weekly completions (Journey shelf + World island accent, retroactive unlock from full history), and richer celebrations (level-up banner, quest-complete delight, achievement toast, weekly/collectible toasts) — all under the existing reduced-motion gate.

---

## Problem Frame

The R2 release defined by `docs/strategy.md` ("Make it enjoyable") set an exit condition: *opening and completing tasks feels rewarding even without AI*. Most of R2 shipped — levels, achievements, momentum tiers, celebrations, the XP island. Four items remain: quest cards still carry plain text with no iconography; there is no weekly rhythm or weekly reward moment; there is nothing to collect beyond achievement rows; and celebrations are confined to confetti bursts, with level-ups and quest completions passing without ceremony. The backlog still lists R2's achievements item as open although it shipped, so the remaining gap is invisible until the strategy list is reconciled. Closing these four items completes the release's reward loop: a visible daily quest identity, a weekly goal to pace the week, a shelf of tokens to grow, and a celebration at every meaningful moment.

---

## Key Flows

- F1. Weekly objective cycle
  - **Trigger:** A calendar week (Mon) starts; the Today screen loads. The first Monday after activation starts the first counted week — the partial activation week is exempt.
  - **Actors:** A1 (the user)
  - **Steps:** The week's two objectives (10 quests, 3 good days) initialize from derived quest/momentum facts. Each day, completed quests and good-day momentum advance the bars on Today. When a goal's count reaches its target, it is met: the bar flips to met, +40 XP is awarded immediately, and a toast fires. The first time ever that goal is met (counting qualifying pre-activation weeks from history for the token only), its collectible unlocks.
  - **Outcome:** The user sees week-to-date progress on Today, met/unmet status on Journey after the week, immediate +40 XP per met goal, and at most one collectible per goal ever.
  - **Covered by:** R5, R6, R7, R8, R9

- F2. Collectible earn and display
  - **Trigger:** A collectible source event first becomes true — including events already true in history at activation, which unlock retroactively.
  - **Actors:** A1 (the user)
  - **Steps:** The source fact flips; the collectibles shelf derives the newly-unlocked token and shows it; a toast names the earn; the World island accent updates to the most recent earn.
  - **Outcome:** The token appears once, never relocks, never duplicates; both surfaces stay consistent on every load.
  - **Covered by:** R10, R11, R12, R13

- F3. Celebration moments
  - **Trigger:** A level increase, a quest completion, an achievement unlock, a weekly goal met, or a collectible first-earn is detected on a data refresh or action.
  - **Actors:** A1 (the user)
  - **Steps:** The event is detected once per transition (level diff, quest status change, achievement read-diff, weekly met flip, collectible diff). Simultaneous events queue and render sequentially in priority order: level-up banner first, then achievement toast, then weekly/collectible toast, then quest delight. Reduced-motion users get the static outcome only.
  - **Outcome:** Each moment celebrates exactly once per transition, one at a time, never on every load.
  - **Covered by:** R14, R15, R16, R17, R18

---

## Requirements

**Quest icons & mascot**
- R1. Every quest domain gets a distinct inline-SVG icon for the nine-domain set — the six stored quest domains (nutrition, movement, exercise, routine, wellbeing, weight) plus the three strategy domains without quests yet (strength, sleep, recovery) — shown on quest cards and quest history rows. The icon maps to the quest's stored domain value exactly; the mapping is explicit and pinned.
- R2. The main fox icon is rebuilt as a cartoon fox face (replacing the current geometric fox) in the same pass, so the icon set reads as one coherent style.
- R3. The icons ship as inline SVG in the existing static delivery — no new dependencies, no new image formats, no external requests.
- R4. Icons are decorative (the domain is already shown as text) and are marked aria-hidden; any new motion obeys the existing reduced-motion setting.

**Weekly objectives**
- R5. Each Mon–Sun calendar week has two objectives: complete 10 quests (done status) and earn 3 good days. A good day uses the existing momentum definition: Good Day = at least two actions that day; Great Day = all assigned quests done plus at least one action. A one-action Spark day does not count.
- R6. Meeting the quests objective awards +40 XP and meeting the good-days objective awards +40 XP (max +80 XP per week), awarded the moment the goal is met (mid-week possible). XP is recorded in a persisted award source — it is not derivable from quest rows.
- R7. Weekly objective state is forward-only from feature activation: weeks before activation never award XP. The partial activation week is exempt — the first counted week is the first full Monday after activation. The activation date is persisted; the weekly cycle derives from it.
- R8. The Today screen shows live week-to-date progress for both objectives; the Journey screen shows the current/latest week's met status and history.
- R9. The first-ever completion of each weekly objective unlocks its collectible — counting qualifying pre-activation weeks from history for the token only (no XP for those weeks); later weeks pay XP only.

**Collectibles**
- R10. Collectibles are cosmetic tokens with no gameplay effect.
- R11. Collectible earning sources: each achievement family on first earn (six families); each goal checkpoint on first crossing (10/25/50/75/100% of goal); each meal-day streak milestone (7/30/100 consecutive meal-log days — the only day-based streak counter); and each weekly objective on first meet (two tokens).
- R12. The Journey screen shows a collectibles shelf card, always rendered: earned tokens show artwork and unlock dates; locked tokens show silhouettes. The World island shows the most recent earn as an accent.
- R13. A collectible unlocks exactly when its source event first becomes true — including events already true at activation, which unlock retroactively from full history — appears once, and never relocks or duplicates. Unlock state is monotonic: checkpoint and streak sources are revocable in their live state, so the unlock predicate derives from earliest crossing over history or a persisted first-earn record (mechanism chosen at planning), never from the live revocable state.

**Celebrations**
- R14. A level increase shows a level-up banner naming the new level and title (multi-level jumps show the landing level), exactly once per transition. The banner auto-dismisses (~3s), dismisses on tap, and overlays without blocking interaction.
- R15. Completing a quest shows a brief completion delight (checkmark pop) on the quest card, exactly once per completion.
- R16. An achievement unlock shows a toast alongside the existing confetti, exactly once per unlock.
- R17. All celebration motion obeys the existing reduced-motion setting; reduced-motion users see the static outcome only.
- R18. Meeting a weekly objective shows a toast with the +40 XP award; a first-time collectible earn shows a toast naming the token. Both fire exactly once per event and follow the F3 priority queue.

---

## Acceptance Examples

- AE1. **Covers R5, R6.** Given a user in calendar week W completes 10 quests by Friday, when the 10th quest completes, the quests objective flips to met and their XP total increases by +40 immediately.
- AE2. **Covers R7.** Given the feature activates on a Wednesday, when the following Monday arrives, the first counted week starts — the partial activation week awards and counts nothing.
- AE3. **Covers R9, R13.** Given a user's good-days objective is met for the first time in week W (including a qualifying pre-activation week), when the collectibles shelf loads, the weekly days token is unlocked with that week's date; meeting it again in later weeks adds no duplicate token.
- AE4. **Covers R11, R13.** Given a user's meal-log streak reaches 30 consecutive days, when the shelf loads, the 30-day streak token unlocks once and stays unlocked even if the streak later breaks.
- AE5. **Covers R13.** Given a user crossed the 50% checkpoint before activation, when the feature launches, the checkpoint token is already unlocked.
- AE6. **Covers R14.** Given a quest completion pushes the user's XP across a level threshold, when the data refresh returns, the level-up banner shows once — reloading the page does not repeat it.
- AE7. **Covers R15, R17.** Given a user with reduced motion completes a quest, when the card updates, the checkmark state appears without animation.
- AE8. **Covers R1.** Given a quest card renders a quest with stored domain "movement", the card shows the movement icon.

---

## Success Criteria

- Human outcome: a user opening the app sees an icon-identified quest, a weekly goal with progress and an immediate reward moment, a growing shelf of collectibles, and a celebration at level-up, completion, weekly and achievement moments — satisfying R2's exit condition ("opening and completing tasks feels rewarding even without AI").
- Handoff: a planner can produce the SDD change without inventing product behavior; the four backlog items are closed and the strategy's R2 list is fully shipped.

---

## Scope Boundaries

- Mascot personality/reaction states — the fox rework in this release is visual only; the personality pass stays in its later release.
- No gameplay effect or economy for collectibles (strategy: "avoid complex game economies yet").
- No new notification types for weekly goals or collectibles; notification behavior is unchanged.
- No AI features (RELEASE 5+).
- No World expansion beyond the collectible accent (World/progression expansion is RELEASE 7).

---

## Key Decisions

- **XP is forward-only from activation** (confirmed): retroactive weekly XP would dump an instant XP chunk and distort the level curve.
- **First partial week is exempt** (confirmed): objectives start the first full Monday after activation, so a mid-week launch never produces an impossible unmet week.
- **Collectibles unlock retroactively from full history at activation** (confirmed): already-earned checkpoints, achievement families, and streak milestones show unlocked immediately — consistent with how the achievements engine already derives from history.
- **Weekly XP is awarded when the goal is met** (confirmed): immediate reward feedback; the level-up banner may fire mid-week.
- **Streak milestones use meal-log days only, 7/30/100** (confirmed): the only day-based streak counter in the engine; weigh-in/exercise streaks count weeks and are excluded.
- **Weekly collectibles unlock once, XP-only afterwards** (confirmed): repeatable weekly tokens would clutter the shelf.
- **Calendar week Mon–Sun** (confirmed): predictable weekly reset over a rolling window.
- **Targets 10 quests / 3 good days, +40 XP each** (confirmed): below the strategy's illustrative 50–100 XP weekly range, deliberately calibrated so the existing level curve stays stable (+80 XP/week max). The two goals are complementary levers — quest volume and cross-day consistency — and the targets are tunable after launch.
- **Collectibles are cosmetic-only**: rewards the eye, not the economy, per the strategy's R2 constraint.
- **Icons cover six stored quest domains plus strength, sleep, and recovery**: a coherent set now, no icon gap when those quests arrive. Domain values are pinned by the quest pool and the mapping is explicit (no aliasing).
- **Both surfaces for weekly UI** (confirmed): progress on Today, status/history on Journey.

---

## Dependencies / Assumptions

- Good-day momentum and achievement facts derive from existing quest/log rows. Weekly XP awards, the activation date, and per-goal first-earn records are **persisted** (small award/unlock records) — the derived-state pattern covers progress display, not the XP award itself.
- Existing confetti and reduced-motion infrastructure is reused and extended, not replaced.
- The quest pool's stored domains today are: weight, wellbeing, exercise, nutrition, movement, routine (constants.py QUEST_POOL, pinned by tests/test_quests.py). The strategy's initial domains add: strength, sleep, recovery.
- The current fox appears in the World island (stage-5 group) and in generated icon assets; planning inventories every fox occurrence, including the shared `--fox` CSS variables used by confetti and progress fills, before the rework.
- Week boundaries use host-local dates; the app is single-user local today, so this is safe but implicit.
- Celebration dedupe uses the existing client-side read-diff pattern (level diff, achievement read-diff); clearing browser storage can re-celebrate past transitions, matching current achievement/stage-up behavior.

---

## Outstanding Questions

### Resolve Before Planning

- None — all product decisions were resolved in dialogue.

### Deferred to Planning

- [Affects R2][Technical] Exact SVG shapes, sizes, and stroke treatment for the nine icons and the fox face.
- [Affects R1, R13][Technical] Storage/derivation mechanics: the weekly XP award source, activation-date record, and monotone first-earn predicate (persisted unlock rows vs earliest-crossing derivation over full history).
- [Affects R14][Technical] Where the level-up last-seen marker lives (client-side per the existing diff pattern is the default).

---

## Sources / Research

- `docs/strategy.md` — RELEASE 2 (lines 939–967): item list and exit condition; RELEASE 3+ context for scope boundaries; core health domains (lines 159–175).
- `docs/backlog.md` — stale R2 achievements row (shipped 2026-08-11) and the later-release items kept out of scope.
- `constants.py` — QUEST_POOL (verified domain values: exercise, nutrition, movement, routine, wellbeing, weight).
- `openspec/changes/archive/2026-08-10-r1-quests-xp/` — quest pool, XP economy, momentum definitions.
- `openspec/changes/archive/2026-08-11-r2-achievements/` — achievement engine and unlock semantics reused as a collectible source.
- `openspec/changes/archive/2026-08-13-r2-world-xp-island/` — World island surfaces (stage groups, fox placement, confetti/stage-up wiring) extended by the collectible accent.
- `streaks.py` — streak counters (weight weeks / exercise weeks / meal days) used by the meal-day milestone decision.
- Existing celebration assets: `constants.py` `CELEBRATION_MESSAGES`, confetti + motion gate in `static/` (verified present).
