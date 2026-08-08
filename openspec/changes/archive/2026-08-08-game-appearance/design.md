# Design: Game-Like Appearance (Duolingo-style for Adults)

## Technical Approach

Frontend-only presentation rework. Extend `static/style.css` `:root` with design tokens (no new sheet → `_CSS_HREFS` unchanged); self-host Baloo 2 woff2 under `static/fonts/`; add fox mascot + flame + confetti markup/logic in `static/index.html` + `static/app.js`; replace the inline-SVG diamond favicon with a fox glyph; swap canvas hardcoded colors/fonts for `getComputedStyle` token reads; add drift-guard tests. No API/data/copy/id changes.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Stylesheet | Extend `style.css` (add motion section) | New `game.css` sheet | One request; `_CSS_HREFS` stays a 1-tuple; a 2nd sheet MUST join the tuple (spec) — avoided. |
| Confetti | Inline `fireConfetti()` in `app.js` + pure `shouldCelebrate()` in `format.js` | New `confetti.js` module | Pure helper is the only testable unit (node:test); DOM burst is glue. No new file → `_JS_SCRIPTS` unchanged. |
| Icons | **No change** to `make_icons.py` / PNGs / `test_icons.py` | Regenerate | `make_icons.py` already renders a fox (`FOX=#eb892c`, white muzzle, nose) on `BG=#2f7d54`; accent stays out of icon art. Byte-pin stays green. |
| Palette lockstep test | New `tests/test_palette_lockstep.py` (4 locations) | Fold into `test_spa_gate.py` | Cross-file (CSS `:root` + HTML theme-color + manifest + py literal); isolates the invariant. Token/favicon/reduced-motion/asset-stamp asserts stay in `test_spa_gate.py`. |
| Canvas colors/font | `getComputedStyle(documentElement/body)` reads tokens once into `CHART_COLORS`/`CHART_FONT` | Keep hardcoded hex | Spec: charts token-consistent + readable system fallback while font loads; computed `fontFamily` keeps `system-ui` in the stack. |

## Data Flow

```
index.html ──┬─ style.css :root tokens ──┐
             ├─ fonts/baloo2-*.woff2 ────┤
             └─ fox favicon (SVG data URI)
app.js loadData(): rewards.earned_count ── shouldCelebrate(prev,cur) ── fireConfetti()
                                          (format.js pure fn, node:test)
getComputedStyle(--accent/--fox/...) ── drawChart/drawBars (no hardcoded hex)
```

## Token Architecture (`:root` additions)

```css
--radius-sm:8px; --radius-md:12px; --radius-lg:18px; --radius-pill:999px;
--shadow-1:0 1px 3px rgba(0,0,0,.05); --shadow-2:0 4px 12px rgba(0,0,0,.08); --shadow-3:0 8px 24px rgba(0,0,0,.12);
--space-1:.25rem; --space-2:.5rem; --space-3:.75rem; --space-4:1rem; --space-5:1.5rem;
--fox:#eb892c; --fox-dark:#b45c16; --gold:#f5c518; --gold-deep:#d4a017;
--font-display:'Baloo 2',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--font-body:'Baloo 2',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
/* --accent:#2f7d54 unchanged — brand anchor */
```

## Font Pipeline

- **Source/commit**: Google Fonts OFL Baloo 2 woff2 (offline fetch). Commit `static/fonts/baloo2-400.v1.woff2` (body) + `static/fonts/baloo2-600.v1.woff2` (display). Version segment `v<n>` in filename bumps on asset change.
- **@font-face**: `@font-face{font-family:'Baloo 2';font-weight:400;font-display:swap;src:url('/static/fonts/baloo2-400.v1.woff2') format('woff2')}` (+ 600). `system-ui` in `--font-*` fallback stacks.
- **Canvas**: `const CHART_FONT=`11px ${getComputedStyle(document.body).fontFamily}`` → keeps system fallback while Baloo 2 loads.

## Component Styling Plan

| Component | Change |
|---|---|
| Header | Add `<span class="mascot" aria-hidden="true">` inline-SVG fox (reuse favicon glyph) inside `.header-row` before `h1`; no id change. |
| Auth/onboarding cards + wizard indicator | Add `<ol class="wizard-indicator">` with 5 `<li data-step>` (new classes, no ids); `showWizardStep` toggles `.is-current`. |
| Summary scoreboard | `.stat-value` → `--font-display`; tile radius `--radius-md`. |
| Streak tiles | `renderStreaks` adds flame `<span class="flame">🔥</span>` + `tile.dataset.streakActive=String(s[key]>0)`; CSS pulses only `[data-streak-active="true"] .flame`. |
| Rewards/chips/track | Chips `--radius-pill` + pop-in keyframe; progress fill uses `--fox`→`--accent` gradient. |
| Buttons | `button:active{transform:scale(.97)}`; min-height 48px. |
| Forms/inputs | `min-height:48px`; `border-radius:var(--radius-sm)`; `--font-body`. |
| Tabs | Token colors; reduced-motion kills transition. |
| History rows | Token borders/radius; no copy change. |
| Charts | `CHART_COLORS={line:--accent,grid:--border,muted:--muted,tooltip:--text}` via `getComputedStyle`. |
| Toast | Keep `hidden` toggle (gate) + add `.is-visible` class-swap for opacity/transform reveal; no `@starting-style`. |
| Focus-visible | `:focus-visible{outline:3px solid var(--fox);outline-offset:2px}` on all interactive. |

## AA Contrast Pairs (computed)

| Pair | Ratio | Use |
|---|---|---|
| `--text` #1f2933 / `--card` #fff | ~14:1 | body ✓ |
| #fff / `--accent` #2f7d54 | 4.6:1 | buttons ✓ normal |
| `--accent-dark` #266442 / #fff | 6.5:1 | text ✓ |
| `--fox-dark` #b45c16 / #fff | 5.8:1 | orange text ✓ normal |
| #fff / `--fox` #eb892c | 2.8:1 | large bold/UI only (≥3:1) |
| `--gold` #f5c518 | — | **non-text accent only** (confetti/badge fill); never body text |

## Confetti

`shouldCelebrate(previousEarned, currentEarned) -> "fire" | "suppress"` in `format.js` (pure, UMD, node:test). Fires only when `currentEarned > previousEarned` AND `previousEarned != null` (first render → suppress). `loadData()` keeps module `let prevEarned=null`; after render sets `prevEarned=earned_count`. `fireConfetti()` in `app.js` creates N `.confetti-piece` spans, CSS falls them, removes on `animationend`. Gate: JS `matchMedia('(prefers-reduced-motion: reduce)')` skips + CSS `@media (prefers-reduced-motion: reduce){.confetti-piece{display:none}}`.

## Favicon

Replace index.html line-8 data URI: drop diamond path `M32 8l14 22-14 8-14-8z`; add fox glyph drawn from `make_icons.py` geometry (ears + head + muzzle triangles) in the 64×64 SVG. `theme-color` stays `#2f7d54`.

## Icons

`make_icons.py` unchanged — `BG=#2f7d54` already lockstep, fox art already present, no accent enters icon art. `test_icons.py` untouched (byte-pin stays green). **Spec assumption "regenerate together" is moot** — no regeneration needed.

## File Changes

| File | Action | Description |
|---|---|---|
| `static/style.css` | Modify | `:root` tokens, @font-face, motion, components, reduced-motion block, focus-visible |
| `static/index.html` | Modify | fox favicon, mascot span, wizard indicator `<ol>`, font preconnect/link (none — self-hosted) |
| `static/app.js` | Modify | `renderStreaks` flame+data-attr, `loadData` confetti diff + `prevEarned`, `fireConfetti()`, `CHART_COLORS`/`CHART_FONT` in drawChart/drawBars, toast class-swap, wizard indicator sync in `showWizardStep` |
| `static/format.js` | Modify | add `shouldCelebrate()` to `api` export |
| `static/fonts/baloo2-400.v1.woff2` | Create | OFL woff2 |
| `static/fonts/baloo2-600.v1.woff2` | Create | OFL woff2 |
| `static/manifest.webmanifest` | Modify | `theme_color` stays #2f7d54 (asserted); no icon path change |
| `main.py` | Modify | **No tuple change** (extend style.css; no new JS) — but assert in test |
| `tests/test_spa_gate.py` | Modify | +token presence, +fox favicon (no diamond), +reduced-motion block, +asset stamps, +no @starting-style |
| `tests/test_palette_lockstep.py` | Create | 4-location #2f7d54 lockstep |
| `tests/frontend/confetti.test.mjs` | Create | node:test for `shouldCelebrate` (fire/suppress/first-render) |
| `tests/smoke-ui.sh` | Modify | +visual selectors for `.mascot`, `.flame` (no text-pin change) |

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit | `shouldCelebrate` | node:test `tests/frontend/confetti.test.mjs` |
| Unit | palette 4-location lockstep | `tests/test_palette_lockstep.py` (CSS/HTML/manifest/py parse) |
| Integration | tokens/favicon/reduced-motion/stamps delivered | `tests/test_spa_gate.py` new asserts on served HTML/CSS |
| E2E | mascot + flame elements render | `tests/smoke-ui.sh` selector-only additions |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration. **Rollback boundary**: pure static assets (`style.css`, `index.html`, `app.js`, `format.js`, `fonts/`) + `main.py` tuples (unchanged) → `git revert` those files restores corporate UI; remove `fonts/` dir restores system-ui fallback. Icons atomic pair (`make_icons.py` + PNGs) is **not touched** — no rollback needed there.

## Open Questions

- [ ] **Baloo 2 body readability**: spec pins Baloo 2 for both `--font-display` AND `--font-body`; Baloo 2 is a heavy rounded display face — body text at 0.9rem may read dense. Confirm `--font-body` should be Baloo 2 400 (not a lighter Nunito) before apply. (Spec is explicit → defaulting to Baloo 2 400; flag for owner.)
- [ ] **Gold AA usage**: `--gold` #f5c518 fails AA as text on every light surface. Design restricts it to non-text accents (confetti, badge fills with dark text). Confirm no gold body-text use is intended.
- [ ] **Wizard indicator copy**: adding `<ol class="wizard-indicator">` introduces no visible text (dots only) — confirm dots-only (no "Step 1/5" text) to keep smoke text pins intact.
