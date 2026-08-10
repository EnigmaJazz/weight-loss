# Backlog

> **Strategic plan**: `docs/strategy.md` ("Health Adventure") is the governing product plan — behaviour-first health journey, 12 vertical releases (R0–R11). Items below are reconciled against it; new work should map to a release.

## Gamification (fun-first direction)

Shipped:
- [x] **Notification message variety** — pools of (title, body) variants per type (tip ×6, reminder ×5, exercise ×6), picked at send time. Commit `c766cca`.
- [x] **Goal-setting foundation** — target as weight *or* BMI, healthy-weight range recommendation (BMI 18.5–24.9) with under/overweight flagging, first-run onboarding wizard (height, current weight, target, unit + notification preferences). PRs #27–#30, merge `7ba15ed`.
- [x] **Checkpoint celebration push** — one batched push naming the top milestone on newly-earned checkpoints (PR #36, `b14e503`).
- [x] **Gamified goals dashboard** — hero goal ring, streak tiles, milestone strip (one-line achieved dots, bigger last-achieved, text-only next). PRs #37–#40.
- [x] **Daily quests (R1)** — rotating quests across health domains (log today, move 10 min, one healthy meal) with skip/replace, deterministic SHA-256 rotation, 3/day; change `r1-quests-xp`, 10 chained PRs #43–#51. The strategy's product loop (Goal → Quest → Action → Log → Reward → Progress) is now live.
- [x] **XP/level system (R1)** — XP per completed quest, levels with titles; strategy §8.
- [x] **Momentum (R1)** — Good Day / Great Day tiers from daily completion, 21-day window; strategy §9–10.
- [x] **Mood + habits logging (R1)** — 1–5 mood with optional note; water/fruit_veg/home_cooked/sleep_routine habits; strategy §R1.
- [x] **Celebration micro-interactions** — confetti on newly-earned checkpoints (motion-gated), one-line milestone strip, checkpoint celebration push (PRs #33/#36/#40). Remaining: celebrations on quest completion/level-up/achievements ride along R2.

Backlog (priority order):
- [ ] **Streak badges / achievements (R2)** — Getting Started / Consistency / Comeback / Personal Best families; strategy §11. The next release after R1.

## Appearance (mobile-game aesthetic for adults)

Shipped:
- [x] **Duolingo-like UI rework** — bold rounded cards, adult-friendly vibrant palette, playful typography, micro-interactions. (`game-appearance`)
- [x] **Dark mode** — three-state theme preference, FOUC-safe theming. (`dark-mode`)
- [x] **Journey screen (R1)** — quest/history/XP surface beyond the Today dashboard: XP/level stat, successful-days momentum, quest-history cards.

Backlog:
- [ ] Mascot personality pass — reuse the fox from `static/icons/`; reaction states on milestones/streaks (strategy: World/Coach surfaces, later releases).
- [ ] Coach + World screens (R3+) — personalised recommendations and progression maps per strategy.
