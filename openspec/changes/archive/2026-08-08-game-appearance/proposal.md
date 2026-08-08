# Proposal: Game-Like Appearance (Duolingo-style for Adults)

## Intent

SPA reads as corporate flat UI: muted palette, system-ui font, one transition, no press feedback, no focus styles. Target: a mobile game aimed at adults — playful, warm, motivating. Pure presentation change: no API, data, copy, or auth changes.

## Scope

### In Scope
- Palette: keep #2f7d54 green; add fox orange #eb892c + celebration gold; all 4 locations in lockstep (style.css, index.html theme-color/favicon, manifest, make_icons.py BG).
- Typography: self-hosted OFL rounded font (Baloo 2 or Nunito), @font-face filename-versioned, system-ui fallback. No CDN.
- Mascot: static fox in header + celebration moment; no animated reactions.
- Confetti on newly-earned checkpoint (client-side diff, suppressed on first render).
- Motion: press physics, card hover, chip pop-in, flame pulse — all gated by prefers-reduced-motion.
- A11y: :focus-visible, AA contrast, ~48px thumb-reach buttons.
- Favicon: inline SVG fox replaces diamond glyph.

### Out of Scope
- Dark mode; animated mascot reactions (separate backlog items).
- Copy renames, DOM id / hidden-contract changes (smoke + test_spa_gate pin them).
- Data-surface redesign beyond consistency (history, forms, charts, tabs).
- @starting-style / modern-only reveal transitions.

## Capabilities

### New Capabilities
- `game-appearance`: visual design system (palette, typography, mascot, motion, focus/contrast, mobile sizing) → `openspec/specs/game-appearance/spec.md`.

### Modified Capabilities
None — all 6 existing domain specs untouched; confetti is presentation over existing checkpoint data.

## Approach

- Tokens first: extend style.css `:root` palette; units.py untouched.
- Font: commit woff2 once; @font-face + versioned filename; system-ui fallback.
- JS class-swaps over @starting-style: `[hidden]{display:none!important}` blocks CSS-only reveals; broad browser floor.
- Confetti: small diff in loadData, suppress first render; new JS minimal (smoke is app.js's gate).
- New css/js assets MUST join main.py `_CSS_HREFS`/`_JS_SCRIPTS` tuples.
- Icons: regenerate make_icons.py output + commit PNGs together (test_icons.py byte-pinned).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| static/style.css | Modified | palette, type, motion, focus, sizing |
| static/index.html | Modified | theme-color, favicon, fonts |
| static/app.js | Modified | confetti, class-swaps |
| static/manifest.webmanifest | Modified | theme color |
| make_icons.py + icons | Modified | BG/palette lockstep |
| static/fonts/ | New | woff2 + @font-face |
| main.py | Modified | asset cache-stamp tuples |
| tests (spa_gate, smoke-ui) | Untouched | must keep passing |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| test_icons.py byte-pin breaks | Med | regenerate + commit together |
| smoke text pins break | Low | zero copy/rename changes |
| Font offline/perf failure | Low | woff2 subset, system-ui fallback |
| Motion triggers vestibular issues | Med | global reduced-motion gate |
| Palette lockstep drift (4 spots) | Med | tokens as source; verify step checks |

## Rollback Plan

git revert of static/ + main.py; palette/favicon in history; removing fonts restores fallback. No DB/API touched.

## Dependencies

OFL-licensed font committed to the repo (no runtime network).

## Success Criteria

- [ ] Full pytest + node:test + smoke-ui.sh green
- [ ] test_icons.py green (or icons regenerated together)
- [ ] Every new animation gated by prefers-reduced-motion
- [ ] AA contrast + :focus-visible on all interactive elements
- [ ] Confetti only on newly-earned checkpoints, never first render
- [ ] Palette consistent across style.css / index.html / manifest / icons
