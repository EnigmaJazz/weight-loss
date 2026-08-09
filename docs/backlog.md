# Backlog

> **Strategic plan**: `docs/strategy.md` ("Health Adventure") is the governing product plan — behaviour-first health journey, 12 vertical releases (R0–R11). Items below are reconciled against it; new work should map to a release.

## Gamification (fun-first direction)

Shipped:
- [x] **Notification message variety** — pools of (title, body) variants per type (tip ×6, reminder ×5, exercise ×6), picked at send time. Commit `c766cca`.
- [x] **Goal-setting foundation** — target as weight *or* BMI, healthy-weight range recommendation (BMI 18.5–24.9) with under/overweight flagging, first-run onboarding wizard (height, current weight, target, unit + notification preferences). PRs #27–#30, merge `7ba15ed`.
- [x] **Checkpoint celebration push** — one batched push naming the top milestone on newly-earned checkpoints (PR #36, `b14e503`).
- [x] **Gamified goals dashboard** — hero goal ring, streak tiles, milestone strip (one-line achieved dots, bigger last-achieved, text-only next). PRs #37–#40.

Backlog (priority order):
- [ ] **Daily quests (R1)** — small rotating challenges across health domains (log today, move 10 min, one healthy meal) with skip/replace; strategy §R1. The biggest single step toward the strategy's product loop (Goal → Quest → Action → Log → Reward → Progress).
- [ ] **XP/level system (R1/R2)** — XP for completions, levels with titles; strategy §8 + §R1.
- [ ] **Momentum (R1)** — Good Day / Great Day tiers from daily completion; strategy §9–10.
- [ ] **Streak badges / achievements (R2)** — Getting Started / Consistency / Comeback / Personal Best families; strategy §11.
- [ ] **Mood + habits logging (R1)** — extend basic logging beyond weight/activity; strategy §R1.
- [ ] **Celebration micro-interactions** — confetti/milestone animations (mostly shipped; ties into the appearance rework).

## Appearance (mobile-game aesthetic for adults)

Shipped:
- [x] **Duolingo-like UI rework** — bold rounded cards, adult-friendly vibrant palette, playful typography, micro-interactions. (`game-appearance`)
- [x] **Dark mode** — three-state theme preference, FOUC-safe theming. (`dark-mode`)

Backlog:
- [ ] Mascot personality pass — reuse the fox from `static/icons/`; reaction states on milestones/streaks (strategy: World/Coach surfaces, later releases).
- [ ] Journey screen (R1) — quest/history/XP surface beyond the current Today dashboard.
- [ ] Coach + World screens (R3+) — personalised recommendations and progression maps per strategy.
