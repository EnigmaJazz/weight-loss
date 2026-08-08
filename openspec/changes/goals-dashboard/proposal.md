# Proposal: Goals Dashboard

## Intent

Re-skin the Today tab into a Duolingo-style goals home screen: hero goal-progress ring, upgraded streak tiles, full 5-card milestone track. Motivation surfaces exist but read as disconnected widgets; the dashboard unifies them into one glanceable progression story. Frontend-only for v1.

## Assumptions (user-confirmed)

- Re-skin Today tab (NO new tab); pinned ids/strings preserved (`#summary-card`/`#streaks-card`/`#rewards-card`, "Summary"/"Streaks"/"Checkpoints", "Log weight").
- Hero ring = overall goal %; checkpoint band stays in-card; 5-card track thresholds mirrored from `rewards.py`.
- Best streak DEFERRED to v2 (needs streaks.py + API key).
- Ring: inline SVG stroke-dashoffset, tokens-only CSS, existing reduced-motion gate.
- Edge states: fresh nulls / baseline ≤ target → empty ring + copy; overshoot clamped 100%; recently-earned highlight date-granular (UTC `earned_at`).

## Scope

### In Scope
- Hero ring: inline SVG ~120–160px, round caps, fox→accent gradient.
- Streak tiles upgraded in place (keep `.flame` + `dataset.streakActive`).
- 5-card track: earned/pending/next, 100% gold fill-only (gold never text), per-card emoji.
- `format.js` pure helpers + node:test drift guards (`tests/frontend/*.test.mjs`).
- Recently-earned date-granular highlight.

### Out of Scope
- Backend/API changes. Best-streak (v2). Mascot reactions (separate backlog). Confetti (exists).

## Capabilities

### New Capabilities
None — dashboard lives under the existing game-appearance domain.

### Modified Capabilities
- `game-appearance`: ADDED requirements (hero ring, milestone track, format.js helpers + drift guards); MODIFIED "Motivation Surfaces" (Today tab becomes dashboard; pinned visible-copy/DOM-id contracts unchanged).

## Approach

- Re-skin Today in place: summary grid → hero ring; checkpoint band → 5-card track; streak tiles upgraded in place.
- `format.js`: `goalProgress(baseline, current, target)` → 0..1|null (clamped, null-safe); `checkpointThresholds(baseline, target)` mirroring `rewards.py`; milestone-state mapping.
- Ring: SVG stroke-dasharray/dashoffset; `var(--border)` track, `var(--accent)`/fox gradient; reduced-motion gate neutralizes transition.

## Affected Areas

| Area | Impact |
|------|--------|
| `static/index.html` | Modified |
| `static/app.js` | Modified |
| `static/style.css` | Modified |
| `static/format.js` | Modified |
| `tests/frontend/` | Modified |
| `tests/smoke-ui.sh` | Modified |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Pinned smoke contracts drift | Med | Additions only; pins untouched |
| Client threshold mirror drifts | Med | node:test guard vs `rewards.py` |
| Contrast/gradient regression | Low | Tokens-only; AA checks |

## Rollback Plan

Frontend-only: revert the commit. Pinned ids/strings unchanged, so smoke gates stay valid. No data migration.

## Dependencies

- Existing game-appearance tokens + `active_checkpoints` API data.

## Success Criteria

- [ ] `smoke-ui.sh` passes with new selectors; pinned strings/ids unchanged.
- [ ] node:test drift guards match `rewards.py` thresholds (5 cards).
- [ ] Ring correct for fresh/partial/overshoot (clamped, null-safe); cards show earned/pending/next + gold fill; highlight date-granular.

## Open Questions

- Ring size and per-milestone emoji set → design phase, non-blocking.
