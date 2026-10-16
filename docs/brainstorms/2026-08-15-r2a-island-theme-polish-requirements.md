---
date: 2026-08-15
topic: r2a-island-theme-polish
---

# R2A Island Theme Polish — Fox Mascot Redraw + Earnable Island Plants

## Summary

Refresh the World island into one coherent living scene: redraw the fox mascot in the maintainer-provided reference style at every island stage, and give all 16 collectible catalogue entries a unique island plant that appears on the island when earned (silhouette when locked). Presentation-only: the collectible catalogue, API, engine, economy, and XP are untouched.

## Problem Frame

The World island currently reads as generic: the fox is a simple geometric placeholder that only appears at the top stage, and collectibles exist only as CSS medallions on the Journey shelf — nothing earned ever appears on the island itself. The maintainer's reference set (fox identity system + 20-item plant catalogue, both in a warm-brown-outlined, flat-illustrated style) defines a coherent visual language the island does not yet use. R2A's exit condition is that the World reads as one living island where the mascot and every earned collectible are recognisable parts of the same scene. R2A also guards presentation-only: no gameplay value changes (R10).

## Actors

- **App user** — earns collectibles through achievements/checkpoints/streaks; views the World island on the World tab in both themes, mobile and desktop.
- **Maintainer** — supplied the reference images (`1786819113186.png` fox set, `1786819118886.png` plant set) as the style source of truth.

## Key Flows

1. **Island viewing** — user opens the World tab; the island renders its current stage with the fox in the reference style at that stage. Earned plants appear on the island; unearned plants show as reserved silhouettes.
2. **Earning a collectible** — an achievement/checkpoint/streak flips a catalogue entry to earned; the island re-renders showing that entry's plant in full colour in its reserved spot, and the Journey shelf medallion updates as today.
3. **Theme switching** — the island (fox + plants) uses design tokens so light and dark themes both stay coherent; reduced-motion users see static rendering only.

## Requirements

- **R-R2A-1 — Fox mascot redraw (reference style)**: the island fox is redrawn per the maintainer reference set: warm-brown outlines (approx. `#78371F` family), orange fur, cream muzzle/cheeks, oversized ears, expressive eyes with highlights, flat fills with restrained shading. All fox colours flow through design tokens (existing `--fox` family + a new outline token); no hex literals in components.
- **R-R2A-2 — Fox at every stage**: every island stage (scene descriptors `sprout`/`sapling`/`tree`/`lush`/`thriving`, displayed as Sprout/Explorer/Adventurer/Champion/Legend Isle) shows the fox in the reference style, sized and posed appropriately for the stage's scene (the current fox only exists at the top stage).
- **R-R2A-3 — 16 unique plants, full coverage**: all 16 collectible catalogue entries (`COLLECTIBLE_CATALOG` in `constants.py`: 6 achievements + 5 checkpoints + 3 meal streaks + 2 weekly) map to a unique island plant rendered on/in the island scene.
- **R-R2A-4 — Earned vs locked rendering**: an earned plant renders in full colour in its reserved island spot; a locked plant renders as a faint silhouette in its reserved spot (per strategy: "locked tokens stay silhouettes"); a spot only exists at stages whose progressive set includes it, so locked silhouettes are always for earnable-in-reach collectibles. Reserved spots are consistent across themes; the silhouette mechanism is a dedicated token (e.g. `--island-plant-locked`) whose value is distinct from the island ground token in BOTH light and dark themes so locked spots stay visible on every background.
- **R-R2A-5 — Presentation-only**: the collectible catalogue, `/api/collectibles` contract, `collectibles.py` engine, XP, economy, and progression rules are unchanged (R10 guard). The Journey shelf's existing medallion rendering is unchanged.
- **R-R2A-6 — Token-only theming**: all new artwork uses design tokens; the palette lockstep test (or its equivalent gate) still passes; both themes and mobile widths render coherently; reduced-motion users see static rendering with no animation.
- **R-R2A-7 — Gate and smoke pins**: the SPA gate pins and the smoke UI test are updated so the fox redraw and island plants are pinned: fox present at every stage, earned-plant rendering, locked-silhouette rendering, token-only CSS, both themes. NOTE: `tests/test_spa_gate.py::test_index_html_world_panel_ships_xp_island` currently pins `fox_in == {"1": False ... "5": True}` (fox ONLY at stage 5) — R-R2A-2 deliberately inverts this to fox present in all five stage groups; the pin is a rewrite target, not an addition. New plant/fox tokens must be declared in BOTH `:root` and the `[data-theme=dark]` block (the existing island-token gate asserts dark-block parity).
- **R-R2A-9 — Icon regeneration (strategy-mandated)**: `static/icons/*.png` (PWA icons) are regenerated via `make_icons.py` in the reference style in the same change (icons stay token-only, per strategy RELEASE 2A Implement); the PWA icon matches the new fox art.
- **R-R2A-8 — Plant mapping sensible**: each catalogue entry gets a plant that matches its meaning, following the reference set's botanical specificity (succulents, berries, flowers, trees). The concrete per-entry mapping table (e.g. Personal Best → a flowering milestone plant; 10% checkpoint → a seedling; 7-day meal streak → a small bush) is produced in the design phase from this requirement + the reference set; a gate pin asserts the chosen mapping is applied consistently.

## Acceptance Examples

- **AE-1 (covers R-R2A-2, R-R2A-7)**: A user at stage 1 (Sprout Isle) sees the reference-style fox in the sprout scene; at stage 5 (thriving) the fox is larger/more detailed. A gate pin asserts the fox markup exists in every stage group.
- **AE-2 (covers R-R2A-3, R-R2A-4)**: A fresh account with zero earned collectibles sees the stage-1 progressive spot set (early-game collectibles only) as silhouettes on the island — not all 16. After earning an early-game collectible (e.g. Getting Started), its plant renders in full colour while the other stage-1 spots stay silhouettes. At stage 5, all 16 spots exist: earned plants full colour, unearned silhouettes. The Journey shelf medallion also shows earned.
- **AE-3 (covers R-R2A-6)**: Switching from light to dark theme keeps the island plants and fox recognisable (token fills change, silhouettes stay visible against the new background). With `prefers-reduced-motion`, the island renders statically with no animation.
- **AE-4 (covers R-R2A-5)**: `GET /api/collectibles` returns the identical contract before and after this change; the collectible shelf row count and ordering are unchanged.

## Success Criteria

- The World island reads as one coherent living scene: the fox and every earned collectible are recognisable parts of the same island (strategy §RELEASE 2A exit condition).
- All 16 catalogue entries have unique, recognisable island plants; locked entries show as silhouettes.
- No gameplay value changed: catalogue, API contract, engine, XP, and progression identical (R10 guard).
- Full suite green: pytest, node frontend tests, pyright, and the smoke UI test (both themes, mobile widths, reduced-motion) with the new pins.

## Scope Boundaries

- **Deferred for later**: mascot personality reactions (smiling/streak states) — later-release surface (World/Coach); any collectible engine or catalogue change (R10); Coach + World screens (R3).
- **Out of scope**: XP/economy/progression changes; the Journey shelf medallion design (unchanged by R2A); reference-image editing or new image generation (the provided set is the source).

## Key Decisions

- **Full coverage**: all 16 catalogue entries get unique plants (not a first batch) — user decision.
- **Island-first**: plants render on the island; the Journey shelf keeps current medallions — user decision.
- **Full fox redraw per stage**: the fox is redrawn in the reference style at every island stage, not palette-only and not top-stage-only — user decision.
- **Style source**: the maintainer's two reference images define the art language (warm-brown outlines, orange/cream palette, flat-with-soft-shading).
- **Plant layout architecture (progressive, user decision 2026-08-15)**: reserved plant spots are PROGRESSIVE per stage — each island stage shows the spot set for the collectibles in reach at that stage (early-game entries at stage 1, all 16 at stage 5), not a static 16-spot layer. Spots live in a stage-scoped plant layer that renders only the current stage's spot set (the island already swaps visible stages via `display:none`); the visible spot set is derived from the current stage, so no spot ever needs to be duplicated across stage groups. The existing `#world-latest-earn` medallion is replaced by the plant layer (its "latest earn" role is subsumed — earned plants are always visible).

## Sources / Research

- `docs/strategy.md` §RELEASE 2A (objective, implement, exit condition).
- Maintainer reference images (checked into repo at `docs/refs/r2a/`): `fox-reference-set.png` (6 fox variants), `plant-reference-set.png` (20-item plant set). Style source of truth for R-R2A-1/2/8/9.
- `static/index.html` `#world-island` SVG — current 5-stage island with the stage-5-only fox placeholder.
- `static/style.css` — `--fox`/`--fox-dark`/`--island-fox-*` token family; island token set.
- `constants.py` `COLLECTIBLE_CATALOG` — the 16-entry catalogue (achievements + checkpoints + meal streaks + weekly).
- `static/app.js` `renderCollectibles` / `renderWorldLatestEarn` — current shelf + island "latest earn" wiring.
- `docs/backlog.md` — R2A entry (previously blocked on maintainer reference images; now unblocked).
