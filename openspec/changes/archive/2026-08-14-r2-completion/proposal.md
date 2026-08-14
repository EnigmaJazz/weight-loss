# Proposal: R2 Completion — Quest Icons, Weekly Objectives, Collectibles, Celebrations

## Intent

Completes R2's "Make it enjoyable" loop: no quest icons, weekly rhythm, or reward moment; nothing collectible beyond achievement rows, celebrations stop at confetti.

## Scope

### In Scope
1. Nine-domain inline-SVG quest icons (six stored + strength/sleep/recovery) + cartoon-fox rework: favicon, mascot, island stage-5, PWA icons — atomic with byte-pins.
2. Weekly objectives 10 quests / 3 good days, +40 XP each when met: `weekly_awards` summed into `total_xp_for_user`, per-user activation stamp, first-partial-week exemption; Today + Journey surfaces.
3. Cosmetic collectibles: achievement families, goal checkpoints, meal-day streaks 7/30/100, weekly first-meets — earliest-crossing (monotone, retroactive, no unlock ledger); Journey shelf + World accent.
4. Sequential celebration queue: level-up banner, quest delight, achievement toast, weekly/collectible toasts — priority, once per transition, reduced-motion gated.

### Out of Scope
Mascot personality; collectible economy; new notifications; AI; World beyond the accent.

## Capabilities

### New
- quest-icons (R1–R4): catalogue, domain map, fox rework, decorative delivery
- weekly-objectives (R5–R9): engine, awards, activation, Today/Journey surfaces
- collectibles (R10–R13): four sources, earliest-crossing, shelf + World accent
- celebration-queue (R14–R18): banner, delight, toasts, queue, motion gate

### Modified
- xp-progression (MODIFIED "Derived XP"): total = done quests + `weekly_awards`; ledger ban narrowed to the award table only (gap C)
- world-island-ui (MODIFIED "Frontend-Only Regression Contract"): permit collectible accent (gap D)

## Approach

Weekly: pure `weekly.py` over week-bounded `momentum_facts`; diff-reconcile award rows once per (week, goal) + startup reconcile; stamp row, not settings; SUM extension = only XP contract change. Collectibles: earliest-crossing over history; NEW forward walk for meal-day milestones (A); reusing achievements/checkpoint engines; `/api/achievements` shape. Icons: `QUEST_DOMAIN_ICONS` pair-array on format.js UMD for the ast.literal_eval drift guard (B). Celebrations: client-side queue, read-diff detectors, `level_up` captured in mutateQuest + load-time diff.

**Slices:** icons/fox, weekly backend/UI, collectibles backend/UI, celebrations — ≤400 lines each, stacked-to-main, strict_tdd.

**Files:** database.py; weekly.py†/collectibles.py† (new); streaks.py; routes.py; static/*; tests/*; smoke-ui.sh.

## Risks

- XP contract breaks pins (Low): SUM-only; docstring + tests + delta same unit
- Fox rework breaks byte/palette pins (Med): atomic regeneration; palette unchanged
- Line-hungry UI slices (Med): ≤400-line slices
- Double-pay / token relock (Low): PK upsert + reconcile; monotone derivation
- Deltas C/D missing → archive conflict (Low): committed here; sdd-spec emits them

## Rollback Plan

Revert the offending slice — stacked commits are independent; additive schema inert. Full rollback: revert all slices; `total_xp_for_user` returns to quests-only; orphan award rows have no consumer.

## Dependencies

None external. Reuses rewards/achievements/momentum/streaks engines, conftest, frontend lane.

## Success Criteria

- [ ] Six slices stacked-to-main, ≤400 lines each, all gates green
- [ ] AE1–AE8: +40 on met, exemption week, retroactive unlocks
- [ ] Delta specs C/D merge cleanly at archive
