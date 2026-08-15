# Backlog

> **Strategic plan**: `docs/strategy.md` ("Health Adventure") is the governing product plan — behaviour-first health journey, 12 vertical releases (R0–R11). Items below are reconciled against it; new work should map to a release.

## Gamification (fun-first direction)

Shipped:
- [x] **Notification message variety** — pools of (title, body) variants per type (tip ×6, reminder ×5, exercise ×6), picked at send time. Commit `c766cca`.
- [x] **Goal-setting foundation** — target as weight *or* BMI, healthy-weight range recommendation (BMI 18.5–24.9) with under/overweight flagging, first-run onboarding wizard (height, current weight, target, unit + notification preferences). PRs #27–#30, merge `7ba15ed`.
- [x] **Checkpoint celebration push** — one batched push naming the top milestone on newly-earned checkpoints (PR #36, `b14e503`).
- [x] **Gamified goals dashboard** — hero goal ring, streak tiles, milestone strip (one-line achieved dots, bigger last-achieved, text-only next). PRs #37–#40.
- [x] **Celebration micro-interactions** — confetti burst on newly-earned checkpoints with motion-gate, achieved-milestone strip. PRs #36, #40.
- [x] **Daily quests (R1)** — rotating challenges across health domains (log today, move 10 min, one healthy meal) with skip/replace, deterministic daily rotation, auto-complete from honest logging. PRs #43–#51.
- [x] **XP/level system (R1)** — XP for quest completions, levels with titles (Sprout → Legend); strategy §8 + §R1. PRs #43–#51.
- [x] **Momentum (R1)** — Spark / Good Day / Great Day tiers from daily completion, 21-day window; strategy §9–10. PRs #43–#51.
- [x] **Mood + habits logging (R1)** — mood check-ins (1–5 + note) and habit logging (water, fruit/veg, home-cooked, sleep routine) beyond weight/activity. PRs #43–#51.
- [x] **Onboarding extension (R1)** — six-step wizard with goals & lifestyle step: primary goal, secondary goals, health domains, activity level. PRs #43–#51.

Backlog (priority order):
- [ ] **Streak badges / achievements (R2)** — Getting Started / Moving Forward / Consistency / Comeback / Explorer / Personal Best families; strategy §11.

## Appearance (mobile-game aesthetic for adults)

Shipped:
- [x] **Duolingo-like UI rework** — bold rounded cards, adult-friendly vibrant palette, playful typography, micro-interactions. (`game-appearance`)
- [x] **Dark mode** — three-state theme preference, FOUC-safe theming. (`dark-mode`)
- [x] **Journey screen (R1)** — quest history, XP/level, successful-day momentum and XP stats beyond the Today dashboard. PRs #43–#51.

Backlog:
- [ ] **Island theme polish (R2A)** — fresh pass on the mascot icon (cartoon fox) and collectibles as unique island plants matching the World scene; presentation-only (collectible catalogue/API/engine unchanged, R10); strategy §RELEASE 2A. **Blocked on maintainer reference images.**
- [x] **Accent colour selection (R2B)** — per-user accent colour (purple explicitly requested by a user, plus a small curated set: teal/blue/green/orange), token-only, extends the three-state theme preference; strategy §RELEASE 2B. **Done — PR #67.**
- [ ] Mascot personality pass — reuse the fox from `static/icons/`; reaction states on milestones/streaks (strategy: World/Coach surfaces, later releases).
- [ ] Coach + World screens (R3+) — personalised recommendations and progression maps per strategy.
