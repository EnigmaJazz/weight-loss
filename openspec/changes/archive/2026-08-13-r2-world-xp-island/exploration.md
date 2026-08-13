# Exploration: R2 World v1 — XP island

> Verified against the live codebase on 2026-08-12 (post r2-achievements
> archive). This is a READ/THINK artifact: no product code was changed, no
> backend or SPA file was touched. It decides the minimal v1 World surface per
> strategy §R2 ("first simple persistent World") and §6.3 ("one simple object
> that evolves with XP").

## Intent Framing

R2's World goal is: **"XP causes a plant/tree/island/base to evolve visually."**
The exit condition is "opening and completing tasks feels rewarding even
without AI" — the World is a reward *display*, not a game economy. Today
`#tab-world` ships a static fox placeholder card (copy: "Your adventure map is
coming soon."), rendered by no JS at all. The change replaces that placeholder
with an island whose evolution stage is derived from the user's total XP, with
zero or minimal backend change.

## Current State (verified)

### Backend — everything a stage needs already exists

- **XP is derived-on-read**: `xp.py` (pure, no I/O) computes `level_from_xp`,
  `level_progress`, `threshold_for_level`, `title_for_level` from
  `SUM(quests.xp_value) WHERE status='done'` (no ledger; `reward_events` is
  dropped on every init and must never be used).
- **Level curve** (constants.py + xp.py): `T(L) = 25*(L-1)*(L+2)` cumulative;
  level 1 starts at 0 XP; verified thresholds: L5=700, L10=2700, L20=10450,
  L30=23200.
- **Title bands** (constants.py `LEVEL_TITLES`): Sprout (1–4), Explorer (5–9),
  Adventurer (10–19), Champion (20–29), Legend (30+). These five bands are the
  natural anchors for five island evolution stages — they are the product's
  existing progression narrative, pinned by `tests/test_xp.py`.
- **`GET /api/xp`** (routes.py:1434) returns `level`, `title`, `total_xp`,
  `xp_into_next`, `next_level_at`, plus `recent_completions` (newest 10 done
  quests). Authenticated, per-user isolated, async + `run_db`. **This payload
  alone is sufficient to drive a stage** — no new endpoint needed.
- **Derived-state precedent**: momentum.py, streaks.py, achievements.py are all
  pure engines + `GET /api/*` endpoints; no schema changes since R1.

### Frontend — the World tab is inert today

- `index.html:400-406`: `<div class="tab-panel" id="tab-world" hidden>` →
  `<section class="card world-placeholder">` with the fox-mascot SVG glyph,
  `<h2>World</h2>`, `<p class="hint">Your adventure map is coming soon.</p>`.
- `app.js`: `switchTab()` only toggles `hidden`; **no World renderer exists**.
  `loadData()` fetches `/api/xp` once via `loadQuestsAndXp()` and feeds
  `renderXpChip` + `loadJourneyCards`. The same `xpPayload` would feed a World
  render — no extra fetch.
- `format.js` (UMD, loaded before app.js) already mirrors the level curve:
  `thresholdForLevel`, `levelFromXp`, `xpIntoNext` (node-tested, pinned to
  xp.py vectors). A stage banding helper fits naturally here.
- **Celebration precedent** (r2-achievements): `newAchievementKeys` /
  `shouldCelebrate` read-diff + `fireConfetti()`, first render suppressed via
  `prevAchievementKeys === null`, all gated by `prefers-reduced-motion`.
- **Design system** (game-appearance + dark-mode specs, verified in
  `static/style.css`): Baloo 2 display font; tokens `--accent #2f7d54`,
  `--fox #eb892c`, `--gold #f5c518`, `--radius-*`, `--space-*`, `--shadow-*`;
  dark mode via `[data-theme="dark"]` redefining semantic tokens; tokens-only
  CSS (no hardcoded palette hex — `tests/test_palette_lockstep.py`);
  reduced-motion block neutralizes all new motion.
- **Test gates that pin the placeholder** (verified):
  - `tests/test_spa_gate.py:708` `test_index_html_world_panel_ships_fox_placeholder`
    asserts `"Your adventure map is coming soon."`, `class="mascot" aria-hidden="true"`,
    and `fill="#eb892c"` inside the `#tab-world` slice.
  - `tests/test_spa_gate.py:667` pins the four tab buttons and panel order
    (`today < journey < world < me`) — must stay.
  - `tests/smoke-ui.sh:518-522` clicks `[data-tab=world]` and asserts the
    placeholder copy.
- **Asset stamping**: `main.py` `_stamped_index_html()` injects `?v=<git>`
  into `_JS_SCRIPTS`/`_CSS_HREFS`; scratch servers must be restarted after
  commits for browsers to fetch new bundles. **No new static asset is required**
  if the island is inline SVG (recommended).

## Affected Areas

| Area | Impact | Why |
|------|--------|-----|
| `static/index.html` | Replace | `#tab-world` placeholder → island card with stage groups |
| `static/app.js` | Modify | `renderWorld(xpPayload)`; stage read-diff celebration |
| `static/format.js` | Modify | Pure `worldStage(totalXp)` / stage-band helper + api export |
| `static/style.css` | Modify | Island SVG token styling, stage transition, reduced-motion gate |
| `tests/frontend/world.test.mjs` | New | node:test pins for stage bands + celebration eligibility |
| `tests/test_spa_gate.py` | Modify | Replace placeholder pins with island pins; keep tab pins |
| `tests/smoke-ui.sh` | Modify | World tab assert → island selector (no placeholder copy) |
| `tests/test_xp.py` | None | Bands derive from existing pinned thresholds |

## Approaches

### 1. World-state model

**A. Derived-on-read from XP (recommended).** No new table, no schema change,
no migration. Stage = banded total XP; a pure helper in `format.js` mirrors the
same math. Matches the momentum/achievements/xp precedent exactly; trivially
unit-testable; zero persistence risk (never touches `reward_events`).

- Pros: no DB risk, no migration, no backfill; XP is monotonic (done quests
  never un-done), so the stage can never regress — unlike Personal Best, no
  un-earn edge case; single source of truth (quests table).
- Cons: none material for v1. (A future R7 richer World with territories
  per-domain would need its own table — correctly deferred.)

**B. Persisted world-state table** (e.g., `world_state`). Write on XP change.

- Pros: allows non-derived extras later (placements, toggles).
- Cons: schema + write path + migration + backfill; contradicts the codebase's
  strong derived-on-read precedent; YAGNI for v1.
- Effort: High. **Rejected for v1.**

### 2. Visual driver

**A. Total XP only (recommended).** Stage = `worldStage(totalXp)` banded on the
five title-band anchors (Sprout 0–699 / Explorer 700–2699 / Adventurer
2700–10449 / Champion 10450–23199 / Legend 23200+). Progress-to-next-stage =
`totalXp - thresholdForLevel(nextBandMinLevel)` — all existing math.

- Pros: exactly the strategy's "XP causes ... to evolve"; monotonic; reuses
  pinned thresholds; minimal.
- Cons: momentum/achievements don't influence the island in v1 (they already
  have their own reward surfaces on Today/Journey).

**B. Composite (XP + momentum + achievements).** E.g., stage from XP, flora
from momentum, landmarks from achievements.

- Pros: richer; makes the World feel alive.
- Cons: more derivations, more tests, more surface for a v1 that must stay a
  focused slice; each extra input adds read-diff complexity. Deferred to R7.

**C. Level alone.** Stage = title band from `xp.title`.

- Pros: simplest possible; the API already returns the title.
- Cons: coarse progress feedback (no partial bar within a stage without extra
  math); tying stage to a *string* couples UI to copy. Banding on XP with
  level-threshold anchors is barely more code and gives real progress.

**Recommendation: A (total XP), banded on the title-band level thresholds,
implemented as a pure `worldStage(totalXp)` in format.js** returning
`{ index, name, minLevel, minXp }` (and the same for the next stage), so the
SPA renders stage visuals + a "x / y XP to next stage" progress bar from one
helper.

### 3. API surface

**A. No backend change (recommended).** `GET /api/xp` already returns `level`,
`total_xp`, `xp_into_next`, `next_level_at`; the stage banding is pure
client-side math on thresholds `format.js` already mirrors (pinned to xp.py).
`loadData()` already holds the payload — `renderWorld(r1.xp)` reuses it.

- Pros: zero backend files touched; no new pytest API tests; no route/auth
  surface; smallest blast radius.
- Cons: stage banding exists only in JS (mitigated by node:test drift pins
  against the same vectors test_xp.py pins).

**B. Extend `GET /api/xp` with a `stage` field.** Server-computed stage +
next-stage progress.

- Pros: backend authority; SPA dumb-renders.
- Cons: backend change + tests for a value that is pure derivation of an
  already-served number; adds a drift surface where none is needed.

**Recommendation: A.** If spec-time review prefers server authority, B is a
small additive option — but v1 should stay frontend-only.

### 4. Visual evolution design

**A. Inline SVG island, 5 stage layers (recommended).** One
`<svg>` in `#tab-world` containing five stage layers; `renderWorld` shows the
layer for the current stage (e.g., `data-stage="n"` + CSS toggling, or
`.stage-${n}` display). Stages track the titles: Sprout → bare islet with a
sprout; Explorer → grass + sapling; Adventurer → tree + path; Champion → lush
trees + flowers; Legend → thriving island with the fox mascot companion. Fills
use `var(--accent)/var(--fox)/var(--gold)` via classes so both themes resolve
correctly (tokens-only rule; `test_palette_lockstep.py` guards hex drift).

- Pros: no new static assets → no `_CSS_HREFS`/`_JS_SCRIPTS` stamping or
  restart concerns; token-driven theming works in light AND dark out of the
  box (dark-mode redefines the semantic tokens); matches the existing
  mascot/ring inline-SVG precedent; reduced-motion gate via existing media
  block; node:test-pinnable stage math.
- Cons: hand-authored SVG art is the main effort; keep each layer simple.

**B. Image assets (PNG/SVG files).**

- Pros: richer art possible.
- Cons: asset pipeline registration + `?v=` stamping + restart discipline +
  dark-mode variants (two asset sets) + `test_icons.py`-style byte pins; the
  game-appearance spec's asset pipeline burden for v1.
- Effort: High. **Rejected for v1.**

**Celebration:** reuse the achievements read-diff pattern with a NEW
stage-eligible helper (`stageChanged(prevStage, curStage)` returning "fire"/"suppress",
first render suppressed, reduced-motion gated) — or generalize the existing
key-set diff. Do NOT invent a new confetti path.

### 5. UI surface

Replace the placeholder card's interior with:

- `#world-card` (the card section; keeps the `World` h2 pin), containing the
  island SVG, a stage title line (e.g., "Sprout Isle"), and a progress line
  "x / y XP to Explorer isle" built from the stage helper (or, for a brand-new
  user at stage 1, the existing level progress so the bar never looks frozen at
  0/700).
- Update `test_spa_gate.py:708` to pin island presence (island element id,
  `data-stage`, token-based fills, no `coming soon` copy) and keep the tab-set
  and panel-order pins (line 667) untouched.
- Update `tests/smoke-ui.sh:518-522` to assert a world selector instead of the
  placeholder copy.

## Scope Boundaries

### In Scope (v1)

- Frontend-only World island on `#tab-world`; stage derived from total XP.
- `worldStage` pure helper in format.js + node:test drift pins.
- Island SVG (inline) with 5 stages, token fills, both themes, reduced-motion
  gate, one stage-up celebration reusing confetti.
- SPA gate + smoke pin updates for the replaced placeholder.

### Out of Scope (explicitly deferred)

- **Any backend change** (no new/changed endpoint, DB table, or migration).
- Collectibles, currencies/resources, upgrades, unlocks, economies.
- Weekly objectives; quest categories; Coach integration.
- Per-domain world influence (strategy §R7: movement explores, nutrition grows
  the garden, etc.).
- Momentum/achievement-driven flora (each has its own reward surface).
- Persistent avatar system; multiple islands/bases; placement/toggling.
- New static assets and their stamping pipeline.

## Risks / Unknowns

1. **Test pin updates are mandatory in the same change.** The placeholder copy
   and `class="mascot"` + `fill="#eb892c"` assertions in `test_spa_gate.py:708`
   and `smoke-ui.sh:522` will fail the moment the placeholder is replaced —
   updating them IS part of the change, not a follow-up. Verify the full gate
   suite (`pytest`, `node --test tests/frontend/*.test.mjs`, `smoke-ui.sh`) on
   the final merged branch.
2. **0-XP / brand-new user.** A fresh user is Sprout (stage 1) with 0 XP and
   700 XP to the next stage; a progress bar reading "0 / 700 XP" feels frozen.
   Mitigation: for stage 1, show the existing level progress (0/100 to level 2)
   plus the stage label, so the World still moves after the first quest.
   Stage-up confetti must NOT fire on first render (read-diff with null-prev).
3. **Dark mode rendering.** The island SVG must resolve fills from tokens under
   `[data-theme="dark"]` (semantic tokens are redefined there; `--accent` stays
   `#2f7d54`). Token-only fills avoid hex drift; visually verify both themes via
   smoke screenshot.
4. **Cache stamping discipline.** No new static asset means no new stamping —
   but any in-scope temptation to add a CSS/JS file must instead be rejected or
   properly registered in `main.py` tuples and scratch servers restarted after
   commits (documented R1 gotcha).
5. **Unknown — stage naming.** Stage names ("Sprout Isle" vs "Island of
   Sprouts", fox companion only at Legend vs earlier) are product copy choices
   for the proposal/spec to pin; copy must follow the game-appearance no-em-dash
   / minimal-copy conventions.
6. **Low** — stage boundaries derive from existing pinned thresholds, but the
   *banding itself* is new JS; node:test pins must cover the five boundaries
   (0/699/700/2699/2700/.../23200) and mirror the test_xp.py vectors.

## Ready for Proposal

Yes. The orchestrator should tell the user: v1 is frontend-only (no backend,
no schema, no new endpoint), stage = total XP banded on the five title-band
anchors via a pure format.js helper, inline-SVG island with five stages +
confetti stage-up reusing the achievements read-diff, and the placeholder test
pins get updated in the same change. Decisions to confirm at proposal/spec
time: (1) stage names + fox-companion placement, (2) stage-1 progress bar shows
level progress (recommended) vs raw stage progress, (3) whether `GET /api/xp`
gains a `stage` field (recommended: no), (4) the exact 5-stage visual
progression.
