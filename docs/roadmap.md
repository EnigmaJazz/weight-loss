# Roadmap & Consolidated TODO

Snapshot: 2026-10-14. Governing product plan: `docs/strategy.md` (releases R0–R11, §838–1397).
This file consolidates `docs/backlog.md`, `docs/plans/*`, `docs/brainstorms/*` and repo state into one ordered list. Update it when an item ships.

## Where we are

| Release | Scope | Status |
|---|---|---|
| R0 | Skeleton, accounts, core logging | Shipped |
| R1 | Quests, XP, momentum, mood/habits, onboarding, Journey | Shipped (PRs #43–#51, quick check-in #68) |
| R2 | Achievements, World island, weekly objectives, collectibles, celebration queue | Shipped (r2-completion S1–S6, #64) |
| R2B | Per-user accent colour | Shipped (#67) |
| R2A | Island theme polish (fox redraw, progressive plants) | **In progress** — `feat/r2a-island-polish`, 3 commits ahead of `main` |
| R3 | Rules-based personalisation (scoring, rerolls, easy/challenge, planned rest, recovery quests) | Not started |
| R4–R11 | Health integrations, NL logging/AI, AI coach, world expansion, analytics, nutrition, social, maintenance | Not started |

## Now — close R2A

- [x] Unit 1: fox redrawn in reference style at every island stage, icons regenerated (`f262943`)
- [x] Unit 2: 16 progressive collectible plants, earned/locked states (`703cf0f`)
- [x] Follow-up: unified island artwork across surfaces (`554679f`)
- [ ] Unit 3a: mapping-consistency gate pin in `tests/test_spa_gate.py` — plant keys ⊆ `COLLECTIBLE_CATALOG`, one plant per key, monotonic stage growth (not yet present on the branch)
- [ ] Unit 3b: smoke pins in `tests/smoke-ui.sh` — fox at stage, progressive spot set, earned/locked flip (verify what the existing +46 lines already cover)
- [ ] Run full gate: `pytest -q`, `node --test tests/frontend/*.test.mjs`, smoke on a scratch server
- [ ] Update `docs/strategy.md` §R2A (§971–986): drop "reference images to be provided", record progressive spots + fox-at-every-stage decisions
- [ ] Flip R2A to done in `docs/backlog.md`
- [ ] Open PR `feat/r2a-island-polish` → `main`

## Next — housekeeping (small, do alongside or right after R2A)

- [ ] Commit the untracked planning docs: `docs/plans/`, `docs/brainstorms/`, `docs/refs/`, plus `CLAUDE.md` and the `AGENTS.md` module-map refresh
- [ ] Decide what to do with `artifacts/` (screenshots): commit, gitignore, or delete
- [ ] Reconcile `docs/backlog.md`: "Streak badges / achievements (R2)" is still open but shipped (openspec archive `2026-08-11-r2-achievements`)
- [ ] Mark shipped plans `status: completed`: r2-completion, r2b-accent-colour, inapp-quicklog (all still say `active` with unchecked units)
- [ ] Fix `origin/HEAD` → `main` (currently points at `slice-1-foundation`): `git remote set-head origin main`
- [ ] Prune remote branches already merged into `origin/main` (~30: auth/slice-*, feat/r1-*, feat/r2-*, feat/inapp-quicklog, feat/r2b-accent-colour, …)
- [ ] Review the ~21 unmerged remote branches (mostly 2026-08-07 activity/weight work, likely squash-merged) before deleting

## Small follow-ups (deferred from shipped plans)

- [ ] Quest-row "Check in" affordance that scrolls/focuses the quick check-in card (inapp-quicklog plan)
- [ ] Mood/habit history list in the UI — GET endpoints already exist (inapp-quicklog plan)
- [ ] Per-accent favicon / manifest / theme-color (excluded from R2B)

## Later — R3 rules-based personalisation (next release)

Scope per `docs/strategy.md` §1018. Needs a brainstorm → plan before code.

- [ ] Brainstorm R3 requirements (`docs/brainstorms/`)
- [ ] Quest scoring: relevance × preference × difficulty × novelty
- [ ] Quest rerolls
- [ ] Easy / challenge mode
- [ ] Planned rest days
- [ ] Recovery quests after missed days
- [ ] Adaptation rules (difficulty follows completion history)
- [ ] Coach screen surface (backlog "Coach + World screens (R3+)")

## Continuous / unscheduled

- [ ] Asset polish (R2A+): PWA icons, plant artwork, fox pose variants, favicon/metadata — does not gate any release
- [ ] Mascot personality pass: fox reaction states on milestones/streaks (World/Coach surfaces)

## Future releases (not yet planned)

R4 health integrations & auto-complete · R5 natural-language logging & AI summaries · R6 AI quest generation, coach, adaptive difficulty · R7 world expansion · R8 analytics & experiments · R9 nutrition expansion · R10 social · R11 maintenance & graduation. See `docs/strategy.md` §1068–1397 and the development order at §1399.
