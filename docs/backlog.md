# Backlog

Working list of future improvements, ordered by the product direction. Check items off when shipped.

## Gamification (fun-first direction)

Shipped:
- [x] **Notification message variety** — pools of (title, body) variants per type (tip ×6, reminder ×5, exercise ×6), picked at send time. Commit `c766cca`.
- [x] **Goal-setting foundation** — target as weight *or* BMI, healthy-weight range recommendation (BMI 18.5–24.9) with under/overweight flagging, first-run onboarding wizard (height, current weight, target, unit + notification preferences). PRs #27–#30, merge `7ba15ed`.

Backlog (in priority order):
- [ ] **Checkpoint celebration notifications** — fun push when a reward checkpoint (10/25/50/75/100 %) is earned, reusing the message-pool pattern.
- [ ] **Gamified goals dashboard** — game-like progress visualization: progress rings, streak flames, milestone cards (streaks engine already exists from activity-logging).
- [ ] **Streak-based badges/achievements** — e.g. 1/4/8-week weight-log streaks, exercise streaks, meal streaks.
- [ ] **XP/level system** — logging, exercise, and meals award XP; levels with titles.
- [ ] **Daily quests** — small rotating challenges (log today, move 10 minutes, one healthy meal) with completion rewards.
- [ ] **Celebration micro-interactions** — confetti/milestone animations (ties into the appearance rework below).

## Appearance (mobile-game aesthetic for adults)

Shipped:
- [x] **Duolingo-like UI rework** — bold rounded cards, adult-friendly vibrant palette, playful typography, micro-interactions. (change: `game-appearance`)

Backlog:
- [ ] Mascot personality pass — reuse the fox from `static/icons/`; reaction states on milestones/streaks.
- [ ] Dark mode.
