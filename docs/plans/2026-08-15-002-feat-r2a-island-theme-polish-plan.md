---
title: "feat: R2A island theme polish — fox redraw + progressive island plants"
type: feat
status: active
date: 2026-08-15
origin: docs/brainstorms/2026-08-15-r2a-island-theme-polish-requirements.md
---

# R2A — Island Theme Polish: Fox Mascot Redraw + Progressive Earnable Island Plants

## Overview

Refresh the World island into one coherent living scene: redraw the fox mascot in the maintainer's reference style at every island stage, and give all 16 collectible catalogue entries a unique island plant rendered on/in the island when earned — with plant spots appearing PROGRESSIVELY as the island grows (stage 1 shows early-game spots, stage 5 shows all 16). Locked spots render as silhouettes. PWA icons regenerate via `make_icons.py` in the reference style. Presentation-only: catalogue, API, engine, XP, and economy untouched.

## Problem Frame

The World island reads as generic: the fox is a simple geometric placeholder that only appears at the top stage, and collectibles exist only as CSS medallions on the Journey shelf — nothing earned appears on the island. The maintainer's reference set (fox identity system + 20-item plant set, warm-brown-outlined flat illustration) defines a coherent visual language the island does not use. R2A's exit condition: the World reads as one living island where the mascot and every earned collectible are recognisable parts of the same scene — presentation-only (R10 guard). See origin requirements (R-R2A-1..9) for the full contract.

## Requirements Trace

- R-R2A-1. Fox mascot redraw in reference style (warm-brown outlines, orange fur, cream muzzle, expressive eyes, token-only).
- R-R2A-2. Fox at every island stage (scene descriptors `sprout`/`sapling`/`tree`/`lush`/`thriving`; displayed Sprout/Explorer/Adventurer/Champion/Legend Isle), sized/posed per stage.
- R-R2A-3. 16 unique plants, full catalogue coverage, PROGRESSIVE spots: stage 1 shows early-game spots; stage 5 shows all 16.
- R-R2A-4. Earned = full colour in spot; locked = silhouette via `--island-plant-locked` token, visible in both themes.
- R-R2A-5. Presentation-only (no catalogue/API/engine/XP/economy change).
- R-R2A-6. Token-only theming, both themes + mobile + reduced-motion static.
- R-R2A-7. Gate + smoke pins updated (fox at every stage, earned/locked rendering, token-only CSS, both themes; gate-pin inversion documented).
- R-R2A-8. Sensible plant mapping (concrete table produced in design phase; gate pin asserts consistency).
- R-R2A-9. `static/icons/*.png` regenerated via `make_icons.py` in reference style (token-only).

## Scope Boundaries

- No collectible engine/catalogue/API change; no XP/economy/progression impact (R10).
- No change to the Journey shelf medallion rendering. `#world-latest-earn` IS REMOVED and subsumed by the plant layer (its latest-earn role is covered by the earned spots).
- No new image generation beyond the maintainer's reference set (6 fox variants → 5 stages; 20-plant set → 16 entries, 4 surplus unused).
- No mascot personality reactions (smiling/streak states) — later release.
- No plant-reveal animation — static rendering; reduced-motion unaffected.

### Deferred to Separate Tasks

- Backlog reconciliation (`docs/backlog.md` R2A row unblock + done) and ROUTER-LOG row: cycle-close housekeeping with delivery.
- Strategy doc note: record the progressive-spots and fox-every-stage decisions in `docs/strategy.md` §RELEASE 2A.

## Context & Research

### Relevant Code and Patterns

- **Island SVG** (`static/index.html` `#world-island`): 240×150 viewBox, five `g.island-stage` groups keyed `data-stage`/`data-stage-name`, stage swap via `#world-island[data-current-stage]` CSS (`display:none`), existing `.island-fox` placeholder ONLY in stage 5.
- **Stage render** (`static/app.js` `renderWorld`/`worldStage`/`WORLD_STAGE_NAMES`): `renderWorld(xp)` sets `data-current-stage`, aria-label, stage name, progress; the fox redraw + plant layer hook here.
- **Token family** (`static/style.css`): `--fox`/`--fox-dark`/`--island-fox-face`/`--island-fox-eye` + island tokens (`--island-foliage`, `--island-ground`, etc.) — NOTE: the dark block currently declares `--fox`, `--island-fox-face`, `--island-fox-eye` but NOT `--fox-dark` (inheritance covers it today); Unit 1 must add `--fox-dark` to the dark block explicitly when extending the fox tokens; `test_index_html_world_panel_ships_xp_island` pins `_ISLAND_TOKENS` parity in both blocks and hex-free `.island-*` rules.
- **Collectible catalogue** (`constants.py` `COLLECTIBLE_CATALOG`): 16 entries (6 achievements `getting_started`…`personal_best`, 5 checkpoints, 3 meal streaks, 2 weekly); `collectibles.py` derives states; `/api/collectibles` returns `{key, title, earned, unlocked_at}` in catalogue order.
- **Shelf + island wiring** (`static/app.js` `renderCollectibles` → `renderCollectibleShelf` + `renderWorldLatestEarn`): the Journey shelf rows (CSS medallions) stay; `renderWorldLatestEarn` (the `#world-latest-earn` medallion) is REPLACED by the plant layer.
- **Palette lockstep** (`tests/test_palette_lockstep.py`): brand hex pinned across style.css :root, index.html meta, manifest, `make_icons.py` BG — new plant/fox tokens are the new lockstep surface; `make_icons.py` must stay token-derived.
- **Gate pin to invert** (`tests/test_spa_gate.py::test_index_html_world_panel_ships_xp_island`): `fox_in == {"1": False, "2": False, "3": False, "4": False, "5": True}` → fox present in ALL five groups; `_ISLAND_TOKENS` extended in both `:root` and dark.
- **Reduced motion** (`static/style.css` `@media (prefers-reduced-motion: reduce)`): universal neutralizer kills animations; new artwork adds none.
- **Smoke world section** (`tests/smoke-ui.sh` §2.75): fresh-account island pins in both themes (stage name, progress, visible stage group, chip==API); extended for fox-at-stage, plant spots, earned/locked rendering.

### Institutional Learnings

- `docs/solutions/workflow-issues/hybrid-routing-missing-tdd-evidence-2026-08-13.md`: UI bundles ride the frontend lane (frontend-dev → frontend-apply) inside an SDD change; orchestrator merges results. This feature is frontend-lane work.
- Prior plan model: `docs/plans/2026-08-14-002-feat-r2b-accent-colour-plan.md` (token-system extension pattern, gate+smoke pin discipline).

### External References

- Maintainer reference images (checked into repo): `docs/refs/r2a/fox-reference-set.png` (6 fox variants), `docs/refs/r2a/plant-reference-set.png` (20-item plant set).

## Key Technical Decisions

- **Progressive spot model (user decision)**: each stage shows the spot set for collectibles in reach at that stage; stage 5 = all 16. Spot sets are declared per stage (stage → list of catalogue keys) and rendered only for the current stage — no spot duplication across stage groups.
- **Inline SVG for plants**: plants are inline SVG groups in `static/index.html` (the island is already inline SVG; no asset files, consistent with the SPA's no-build setup). A plant is one `<g>` with token-driven fills + dark-brown outline stroke from a token.
- **Single fox definition, per-stage reference**: the reference-style fox is defined ONCE as an SVG `<defs>` symbol and referenced in each stage group via `<use class="island-fox">` with per-stage `transform` (translate/scale). The gate pin detects a `.island-fox` reference element inside EACH of the five stage groups (presence of the reference, not duplicated geometry). Poses vary by transform/scale only — no second fox geometry — so the pin and the design stay in lockstep.
- **Plant layer placement**: a `g.island-plants` inside the `#world-island` SVG (sibling of the stage groups), whose visible spot set is derived from `data-current-stage` at render time; earned/locked styling via `data-earned` attribute + CSS tokens.
- **Stage-1 fox**: small/background fox (tending the sprout) so the progressive early spots stay legible; frontend lane verifies against the reference set via screenshots.
- **Mapping table in design phase**: the per-entry plant assignment (16 entries → plants) and per-stage spot sets are produced during design from R-R2A-8 + the reference set; a gate pin asserts the mapping is applied consistently (plant keys match catalogue keys).

## Implementation Units

- [ ] **Unit 1: Fox mascot redraw (reference style, all stages) + icon regeneration**

**Goal:** Replace the stage-5-only geometric fox with the reference-style fox present in every stage group; regenerate PWA icons via `make_icons.py` in the same style.

**Requirements:** R-R2A-1, R-R2A-2, R-R2A-9

**Dependencies:** None

**Files:**
- Modify: `static/index.html` (fox markup in all 5 stage groups)
- Modify: `static/style.css` (fox token family + outline token in `:root` and `[data-theme="dark"]`)
- Modify: `static/icons/make_icons.py` (icon art in reference style; hex constants mirrored from the fox token family, brand BG lockstep-pinned)
- Modify: `static/icons/icon-192.png`, `static/icons/icon-512.png` (regenerated outputs)
- Modify: `tests/test_spa_gate.py` (fox-in-every-stage assertion — the deliberate pin inversion)
- Test: `tests/test_spa_gate.py` (gate), `tests/test_palette_lockstep.py` (token/hex surface), `tests/test_icons.py` (icon geometry probes — update `_CARTOON_FOX_PROBES`/`_FOX` if the redraw shifts the face/hue)

**Approach:**
- Define the fox once as an SVG `<defs>` symbol (reference style: warm-brown outline token, orange fur, cream muzzle, expressive eyes with gleam) and reference it in each stage group via `<use class="island-fox">` with per-stage `transform` (sprout = small/background; top stages = larger scale).
- Fox fills stay on the existing `--fox` family + new `--fox-outline` token; both `:root` and dark blocks declare them (dark-block parity is gate-pinned).
- Invert the gate assertion `fox_in` to fox present in all five stage groups; extend `_ISLAND_TOKENS` with the new tokens in both theme blocks.
- `make_icons.py`: draw the reference-style fox face with token colours (brand BG unchanged per palette lockstep), regenerate `icon-192.png`/`icon-512.png`.

**Patterns to follow:** `static/index.html` `.island-fox` group structure; `static/style.css` island token block + `--fox` family; `make_icons.py` per-pixel renderer with hex constants mirrored from the fox token family (brand BG remains the lockstep-pinned value).

**Test scenarios:**
- Happy path: gate test asserts `fox_in == {"1": True, "2": True, "3": True, "4": True, "5": True}` (a `.island-fox` reference element present in every stage group).
- Happy path: new fox outline token declared in `:root` AND `[data-theme="dark"]` (dark-block parity assertion).
- Happy path: no hex literals introduced in `.island-*` rules (existing hex-free scan passes with the new fox markup).
- Integration: `make_icons.py` regenerates icons that still satisfy the palette lockstep test (brand BG pinned; fox hue matches the `--fox` token family) and the `test_icons.py` geometry probes are updated in the same change (atomic regeneration).

**Verification:** gate tests green (fox in all stages, token parity, hex-free); icons regenerated and lockstep-clean; both themes render the fox recognisably (frontend lane screenshot check vs `docs/refs/r2a/fox-reference-set.png`).

---

- [ ] **Unit 2: Progressive island plant layer (16 plants, earned/locked)**

**Goal:** Add the `g.island-plants` layer with 16 unique plant artworks; progressive per-stage spot sets; earned = full colour, locked = silhouette via `--island-plant-locked`.

**Requirements:** R-R2A-3, R-R2A-4, R-R2A-5, R-R2A-6, R-R2A-8

**Dependencies:** Unit 1 (fox token family established; gate structure known)

**Files:**
- Modify: `static/index.html` (`g.island-plants` layer + 16 plant `<g>` definitions + per-stage spot sets)
- Modify: `static/style.css` (`--island-plant-*` token families in `:root` + dark; earned/locked styling; `--island-plant-locked` silhouette)
- Modify: `static/app.js` (`renderWorld` renders the visible spot set for the current stage; `renderCollectibles` wiring feeds earned keys into the island plant layer; `renderWorldLatestEarn` removed/replaced)
- Modify: `tests/test_spa_gate.py` (plant layer markup, spot sets, earned/locked data attributes, token-only CSS)
- Test: `tests/test_spa_gate.py`, `tests/smoke-ui.sh`

**Approach:**
- 16 plant artworks as inline SVG groups keyed by catalogue key (`data-plant-key`), token-driven fills + dark-brown outline stroke.
- Per-stage spot sets declared in app.js (stage → ordered list of catalogue keys): stage 1 = early-game entries (e.g. `getting_started`, `moving_forward`, `checkpoint_10`, `meal_7`, `weekly_quests`), stage 5 = all 16; intermediate stages add entries in reach.
- `renderWorld(xp)` sets the plant layer's visible spots from the current stage; `data-earned` per spot reads the existing `prevCollectibleKeys` module cache (maintained by `renderCollectibles`), so the island's first paint on refresh (renderWorld runs before renderCollectibles in `loadData`) uses the last-known earned set — no flash-to-locked. Fresh page load starts empty/all-locked until the first collectibles read.
- CSS: `.island-plant[data-earned="true"]` full colour; `[data-earned="false"]` silhouette via `--island-plant-locked` (distinct from island ground token in both themes).
- Remove `#world-latest-earn` medallion + `renderWorldLatestEarn` (subsumed); keep `renderCollectibleShelf` unchanged (Journey shelf untouched). REWRITE smoke §5.19's `#world-latest-earn` assertions (they query the removed element) against the plant layer's earned spots — owned by Unit 2, coordinated with Unit 3's smoke section.
- The concrete 16-entry plant mapping table + per-stage spot sets land in the design phase (this unit's approach); the catalogue-consistency pin (spot keys ⊆ catalogue, one plant per key, monotonic stage growth) is owned by Unit 3, not this unit.

**Patterns to follow:** island SVG group structure + token fills (`static/index.html`, `static/style.css`); `renderWorld` stage-swap mechanics (`static/app.js`); collectibles payload shape (`/api/collectibles`).

**Test scenarios:**
- Happy path: plant layer contains exactly 16 plant groups, each `data-plant-key` matching a `COLLECTIBLE_CATALOG` key (gate pin, one-to-one).
- Happy path: fresh account (stage 1) renders ONLY the stage-1 spot set as silhouettes (e.g. 5 spots, all `data-earned="false"`), NOT all 16 (progressive model pin).
- Happy path: earning an early-game collectible flips its spot to `data-earned="true"` and full colour; other stage-1 spots stay silhouettes.
- Edge case: stage 5 account renders all 16 spots; earned full colour, unearned silhouettes (full coverage at top stage).
- Edge case: stage transition re-renders the spot set (stage 2 adds the stage-2 entries; no stale spots from stage 1-only entries that remain earned — earned state persists by key).
- Error path: `/api/collectibles` failure leaves the plant layer unchanged and surfaces the existing scoped error slot (no blank island regression).
- Integration: earning a collectible on the Journey side (achievement/checkpoint/streak) reflects on the island after the standard refresh path (quests/XP/collectibles reload).
- Token-only: `.island-plant-*` rules carry no hex literals (existing hex-free scan covers the new surface).

**Verification:** gate tests green (16 plants, progressive spot sets, earned/locked states, token-only) and the existing smoke sections still pass (incl. rewritten 5.19); mobile width + reduced-motion render statically; frontend lane screenshot check vs `docs/refs/r2a/plant-reference-set.png`. The new smoke pins land in Unit 3.

---

- [ ] **Unit 3: Smoke pins + mapping consistency gate**

**Goal:** Extend the smoke UI test with the R2A island pins (fox at stage, progressive spots, earned/locked) and add the mapping-consistency gate pin.

**Requirements:** R-R2A-7, R-R2A-8

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `tests/smoke-ui.sh` (world island section extension)
- Modify: `tests/test_spa_gate.py` (mapping consistency pin)

**Approach:**
- Smoke §2.75 extension: assert the stage-1 fresh-account island shows the fox and the stage-1 silhouette set (count + keys); complete an early quest (existing section) then assert its plant spot flips to full colour; switch themes and re-assert both.
- The gate mapping pin: every `data-plant-key` in the island is in `COLLECTIBLE_CATALOG`; every catalogue key has exactly one plant; spot sets are strictly growing (stage n+1 ⊇ stage n).
- Rotation-aware guard: the smoke's world section already derives XP from the server; the plant pins must not depend on the day's quest rotation (only on the stage the fixture account is at — pin via the server-derived stage, not hardcoded totals).

**Patterns to follow:** `tests/smoke-ui.sh` §2.75 server-derived pins + `playwright-cli` eval patterns; `tests/test_spa_gate.py` `_ISLAND_TOKENS`/`fox_in` assertion style.

**Test scenarios:**
- Happy path: fresh account, light theme — fox present at stage 1, stage-1 silhouette set rendered (exact keys); earned states derived from `GET /api/collectibles` (server truth), never a hardcoded count (rotation-independent).
- Happy path: after completing an early quest, its plant spot shows earned state in the DOM (data-earned + computed fill differs from locked).
- Happy path: dark theme — same assertions pass (silhouette visible against dark ground token).
- Edge case: stage-5 fixture shows all 16 spots; earned/locked split correct. Mechanism: route-mock `GET /api/xp` (total_xp ≥ 23200) and `GET /api/collectibles` (16 entries with a chosen earned split) via the existing playwright route pattern, then reload — no account-leveling helper exists in the smoke.
- Integration: gate pin asserts progressive growth (spot sets monotonic) and one-to-one catalogue mapping.

**Verification:** full smoke green in both themes with the new pins; gate suite green; no rotation-date dependence in the new pins.

## System-Wide Impact

- **Interaction graph:** `renderWorld` (stage swap + spot set render) and `renderCollectibles` (earned keys → island layer) are the changed entry points; `renderWorldLatestEarn` removed — verify no other caller references `#world-latest-earn`.
- **Error propagation:** `/api/collectibles` failure already surfaces in the shelf's scoped error slot; the island layer must render without collectibles data (all spots default locked) rather than failing.
- **State lifecycle risks:** earned state is derived on read (no persistence change); stage re-renders must preserve earned spots by key (no flash-to-locked on refresh).
- **API surface parity:** `/api/collectibles`, `collectibles.py`, `COLLECTIBLE_CATALOG` unchanged (R10 guard) — verified by existing tests.
- **Integration coverage:** cross-layer earn→island reflection needs the smoke/JS-level check (unit tests cannot prove DOM re-render).
- **Unchanged invariants:** Journey shelf medallions, quest/XP/reward engines, notifications, theme mechanics, and the collectible API contract are untouched.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| 16 plant SVGs inflate `index.html` (mobile first-paint) | Plants use simple shared shapes (3–6 major shapes each, per reference); keep total added markup bounded; smoke asserts island renders at mobile width |
| Dark-theme silhouette invisibility | Dedicated `--island-plant-locked` token distinct from the island ground token in BOTH theme blocks, gate-pinned |
| Gate-pin inversion breaks existing tests if missed | Documented in Unit 1 as the deliberate rewrite of `fox_in`; run the full gate suite |
| Progressive spot sets drift from catalogue | Mapping-consistency pin: spot keys ⊆ catalogue, one plant per key, monotonic stage growth |
| Style drift from reference set across 18 artworks | Frontend lane visual verification against `docs/refs/r2a/` (screenshot loop) before freeze |
| Fox at stage 1 crowding the sprout scene | Stage-1 fox small/background; frontend lane verifies legibility at mobile width |

## Documentation / Operational Notes

- `docs/backlog.md`: flip R2A from blocked to done at delivery.
- `docs/strategy.md` §RELEASE 2A: record the progressive-spots + fox-every-stage user decisions.
- ROUTER-LOG row at cycle close.

## Sources & References

- **Origin document:** `docs/brainstorms/2026-08-15-r2a-island-theme-polish-requirements.md`
- Reference images: `docs/refs/r2a/fox-reference-set.png`, `docs/refs/r2a/plant-reference-set.png`
- Strategy: `docs/strategy.md` §RELEASE 2A
- Related code: `static/index.html` `#world-island`, `static/app.js` `renderWorld`/`renderCollectibles`, `static/style.css` island/fox token blocks, `constants.py` `COLLECTIBLE_CATALOG`, `tests/test_spa_gate.py` `test_index_html_world_panel_ships_xp_island`, `tests/smoke-ui.sh` §2.75
- Prior plan model: `docs/plans/2026-08-14-002-feat-r2b-accent-colour-plan.md`
