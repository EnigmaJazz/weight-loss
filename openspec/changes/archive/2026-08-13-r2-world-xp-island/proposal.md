# Proposal: R2 World v1 — XP island

## Intent

R2's goal: "XP causes a plant/tree/island/base to evolve visually" — tasks must feel rewarding without AI. Today `#tab-world` is an inert placeholder ("Your adventure map is coming soon."). Replace it with an island whose five stages evolve with total XP: a reward display, not a game economy.

## Scope

### In Scope
- `worldStage(totalXp)` in `format.js` + node drift pins.
- Inline SVG island, 5 stages, token fills, dark mode, motion gate.
- Stage-up confetti (read-diff) + progress display.
- Pin updates in `test_spa_gate.py` + `smoke-ui.sh`; tab pins kept.

### Out of Scope
Backend/schema/endpoint changes; collectibles, economies; weekly objectives, quest categories, Coach; per-domain influence (R7); momentum/achievement flora; persistent avatars; new assets.

## Capabilities

### New Capabilities
- `world-island-ui`: five-stage island on `#tab-world` — stage from total XP, celebration, progress display.

### Modified Capabilities
- `game-appearance`: Motion System extended — confetti eligibility gains stage-ups; suppression/gating unchanged.

## Approach

Frontend-only. `worldStage(totalXp)` in `format.js` bands XP on the LEVEL_TITLES thresholds; `renderWorld(xpPayload)` reuses the fetched `/api/xp` (per-user isolation inherited), toggles `data-stage`, celebrates stage-ups via read-diff with new pure `stageChanged`.

## Key Decisions

1. **Frontend-only** — no `stage` field on `/api/xp`; derivation pinned to test_xp.py vectors.
2. **Stages anchor to LEVEL_TITLES bands** (Sprout→Legend at 0/700/2700/10450/23200).
3. **Inline SVG over assets** — no stamping, no dark-mode pairs; token fills keep lockstep.
4. **"`<Title> Isle`" names; fox only at Legend**; monotonic elements (sprout→sapling→tree→lush).
5. **Stage-1 shows level progress** (0/100), not frozen "0/700"; stages 2+ XP to next band.

## Affected Areas

- `static/format.js` — `worldStage`/`stageChanged`
- `static/app.js` — `renderWorld`, read-diff confetti
- `static/index.html` — island card replaces placeholder
- `static/style.css` — token fills, `data-stage`, motion gate
- `tests/frontend/world.test.mjs` (new) — bands + eligibility pins
- `test_spa_gate.py` + `smoke-ui.sh` — placeholder → island pins

## Risks

- **High** — placeholder pins break if not updated together; pins in scope.
- **Med** — SVG art may exceed 400-line budget; simple layers, 2-PR fallback.
- **Med** — confetti over/under-fire; null-prev first render, node pins.

## Rollback Plan

Frontend-only, additive: revert the PR(s); placeholder restored from git.

## Dependencies

R1 + r2-achievements archived. Nothing external.

## Success Criteria

- [ ] Island renders per band across 0/699/700/…/23200; never regresses.
- [ ] Confetti once per stage-up; never first render; motion-gated.
- [ ] Stage-1 level progress; stages 2–5 XP-to-next-band; token fills both themes.
- [ ] Full suite green (pytest + node + smoke); pins replaced.

## Delivery Notes

Single PR (~380–450 lines); 2-PR fallback if art exceeds budget.
