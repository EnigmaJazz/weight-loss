---
title: "feat: R2B per-user accent colour selection"
type: feat
status: active
date: 2026-08-14
---

# R2B — Per-User Accent Colour Selection

## Overview

Add a per-user accent colour preference (Me/settings) extending the shipped three-state theme preference. Purple is an explicit user request (MUST be an option) plus a small curated set — teal/blue/green/orange. The accent rides the existing token system (`--accent`/`--accent-dark`), defaults to the current palette so existing users see zero change, and is API-contract-identical to `theme`: `PUT /api/settings` `accent` key, 422 on invalid values, per-user isolated, NOT part of `OnboardingIn`.

## Problem Frame

A real user asked for a purple option. The app already has a full theme-preference system (`theme`: system/light/dark) with token-only theming — the accent is a one-key extension of that system, not new architecture. See strategy §RELEASE 2B (merged PR #66) for the source requirements.

## Requirements Trace

- R1. Per-user `accent` key in settings, alongside `theme`; default = current palette (`green`), nothing changes for existing users.
- R2. Purple MUST be an option; curated set: purple/teal/blue/green/orange.
- R3. Token-only theming: accent colours are CSS design tokens (`--accent`/`--accent-dark` per accent in both themes); no hex literals in components (palette lockstep test); mobile and reduced-motion unaffected.
- R4. API: `PUT /api/settings` accepts `accent`, 422 on invalid, per-user isolated, NOT in `OnboardingIn` (same rules as `theme`).
- R5. Gate and smoke pins updated: chosen accent renders across Today/Journey/World/Me in both themes.

## Scope Boundaries

- No new onboarding step (accent is a post-onboarding settings preference only).
- No per-accent favicon/manifest/meta theming — `theme-color` meta, manifest `theme_color`, and `make_icons.py` BG stay lockstep on the brand green (PWA chrome is not part of the app's accent surfaces).
- No change to the theme (light/dark/system) mechanics, quest/XP/reward engines, or notification behavior (accent-only saves push nothing, same as theme-only).

### Deferred to Separate Tasks

- Backlog reconciliation (`docs/backlog.md` R2B row) and ROUTER-LOG row: cycle-close housekeeping with delivery.

## Context & Research

### Relevant Code and Patterns

- **Theme preference as the template** (everything mirrors it): `DEFAULT_SETTINGS["theme"]` (constants.py:42), `AppSettings.theme` (models.py:160), `SettingsIn.theme` + `_valid_theme` (routes.py:456-459, 491, 518-521), `_settings_from_conn` read with default (database.py:1054), `_apply_settings` generic upsert (database.py:1064-1081).
- **Theme API tests** (tests/test_api.py:188-246): default, roundtrip, invalid 422 without mutation, null restores default, per-user isolation — the exact shape for `accent`.
- **Theme push neutrality**: `test_settings_theme_only_no_fire` (tests/test_celebrations.py:228) — accent-only must extend this guarantee (accent not in `REWARD_AFFECTING_KEYS`).
- **Onboarding exclusion**: `test_onboarding_rejects_theme_key` (tests/test_onboarding.py:125) — mirror for accent.
- **Token system**: `--accent`/`--accent-dark` in style.css :root (lines 20-21) and `[data-theme="dark"]` block (62-79); components consume `var(--accent)`/`var(--accent-dark)` exclusively (46+ usages); `refreshChartColors` (app.js:1294) re-reads `--accent` from computed style; `CONFETTI_COLORS` uses `var(--accent)` (app.js:1545) so confetti follows automatically.
- **FOUC bootstrap** (index.html:11-27): head script applies `localStorage.theme` pre-paint; accent rides the same pattern (`localStorage.accent`, only for non-default values).
- **Theme lifecycle in app.js**: `themePref` from `/api/settings` on load (app.js:702-703), `applyTheme` (1303), Appearance radio group + `saveThemePreference` (app.js:2336, 2835-2841), `setRadio` helper (2314).
- **Palette lockstep test** (tests/test_palette_lockstep.py): brand `#2f7d54` pinned across style.css :root, index.html theme-color meta, manifest, make_icons.py BG — the four PWA locations stay pinned; the accent token sets are the new lockstep surface.

### Institutional Learnings

- Scratch server conventions: `setsid -f env WEIGHT_LOSS_DB=... WEIGHT_LOSS_VAPID_KEYS=...`, scratch port (e.g. 8129), restart AFTER committing (the `?v=` stamp in `_stamped_index_html`); `pkill -f "uvicorn main:app"` to free the port.
- `node --test tests/frontend/*.test.mjs` glob (bare dir fails on Node 26); frontend tests import real `static/format.js`/`app.js` pieces via the node-test UMD pattern.
- gga STRICT-mode intermittent fail: run `gga run` then retry the commit (memory #501).
- Frontend lane precedent (r2-achievements S3, r2-world-xp-island): UI bundles run frontend-dev → frontend-apply-local with orchestrator merging results; no SDD change for this small feature (ce:work route, cached session decision).

## Key Technical Decisions

- **Accent palette lives in `constants.py`** as `ACCENT_COLORS` (purple/teal/blue/green/orange), driving route validation exactly like the `PRIMARY_GOALS` allowlist — server is the single source of truth; the SPA mirrors the literals with a drift guard (existing convention).
- **Default accent = `green`** (the current palette `#2f7d54`): zero token changes for existing users; the `[data-accent]` attribute is set ONLY for non-default accents, so default behavior is byte-identical to today.
- **Accent theming = CSS token overrides scoped by `[data-accent="..."]`**, with a `[data-theme="dark"]` variant per colour for `--accent-dark` coherence (mirrors the existing light/dark token split). All hex literals stay in style.css — the extended lockstep test forbids them elsewhere.
- **FOUC-safe bootstrap**: the head script applies a saved non-default accent pre-paint (localStorage), exactly like theme; server settings win on load via `applyAccent`.
- **API contract mirrors `theme`**: optional string in `SettingsIn`, validator against `ACCENT_COLORS`, null restores default, no `OnboardingIn` key, no celebration/push side effects.

## Implementation Units

- [ ] **Unit 1: Backend accent setting (API + persistence)**

**Goal:** `PUT /api/settings` accepts `accent`; persisted per user; validated; defaulted to `green`; excluded from onboarding.

**Requirements:** R1, R2, R4

**Dependencies:** None

**Files:**
- Modify: `constants.py` (DEFAULT_SETTINGS["accent"] = "green"; ACCENT_COLORS allowlist)
- Modify: `models.py` (`AppSettings.accent: str = "green"`)
- Modify: `routes.py` (`_valid_accent`, `SettingsIn.accent` + validator; NOT in `OnboardingIn`)
- Modify: `database.py` (`_settings_from_conn` reads accent with default)
- Test: `tests/test_api.py` (accent block mirroring the theme block at 188-246)
- Test: `tests/test_onboarding.py` (rejects accent key)
- Test: `tests/test_celebrations.py` (accent-only save fires zero pushes)

**Approach:**
- Mirror the theme implementation at every layer: allowlist constant → model field → SettingsIn validator → settings-table read with default. `_apply_settings` already handles any key generically.
- `REWARD_AFFECTING_KEYS` untouched — accent is not reward-affecting.

**Patterns to follow:**
- `theme` chain: constants.py:42 → models.py:160 → routes.py:456-459/491/518-521 → database.py:1054.
- Theme tests: tests/test_api.py:188-246; `test_settings_theme_only_no_fire` (test_celebrations.py:228); `test_onboarding_rejects_theme_key` (test_onboarding.py:125).

**Test scenarios:**
- Happy path: `accent` defaults to `"green"` for a fresh user (GET /api/settings).
- Happy path: roundtrip each valid accent (`purple`, `teal`, `blue`, `green`, `orange`) via PUT → persisted → GET returns it.
- Edge case: PUT `{"accent": null}` restores the default `"green"`.
- Error path: PUT `{"accent": "pink"}` → 422 and current settings unchanged (no mutation).
- Integration: per-user isolation — Alice sets `purple`, Bob still reads `"green"`.
- Integration: PUT `{"accent": "purple"}` fires zero push notifications (extends the theme-only neutrality test).
- Error path: POST /api/onboarding with an `accent` key → 422 (extra=forbid, same as theme).

**Verification:**
- Full pytest suite green including the new accent block; pyright clean.

- [ ] **Unit 2: Frontend accent theming + settings UI (frontend lane)**

**Goal:** Accent tokens for all five colours in both themes; FOUC-safe application; accent picker in Me/settings; accent applies across all surfaces; tests.

**Requirements:** R1, R2, R3, R5

**Dependencies:** Unit 1 (API contract)

**Files:**
- Modify: `static/style.css` (`[data-accent="..."]` token blocks + dark variants; all hex literals confined here)
- Modify: `static/index.html` (FOUC bootstrap reads `localStorage.accent`; accent picker in the Appearance card)
- Modify: `static/app.js` (`applyAccent`, accent radio render/save, chart redraw on accent change)
- Test: `tests/test_palette_lockstep.py` (extended: every accent colour defines `--accent`/`--accent-dark` in light and dark; no hex literals outside style.css's token definitions)
- Test: `tests/frontend/accent.test.mjs` (node-test on the pure helpers)
- Test: `tests/test_spa_gate.py` (gate pins: picker markup, bootstrap wiring, drift guard mirroring the PRIMARY_GOALS mirror guard)
- Test: `tests/smoke-ui.sh` (accent pick pin: select purple, assert applied across Today/Journey/World/Me in both themes)

**Approach:**
- Token-only: `[data-accent="purple"] { --accent: ...; --accent-dark: ...; }` etc.; per-colour `[data-theme="dark"]` overrides for `--accent-dark` (lightened for contrast, mirroring `#58a97e`); green defines no override (default palette).
- `applyAccent(pref)`: set `documentElement.dataset.accent` (only non-default), persist `localStorage.accent`, call `refreshChartColors()` + redraw visible charts (Journey canvases), mirroring `applyTheme`'s visibility-gated redraw.
- FOUC bootstrap sets `data-accent` pre-paint from localStorage; `loadData` overrides with server settings.
- Appearance card gains an accent radio group (5 swatch options, "green" default checked); change handler saves via the existing settings PUT path.
- Confetti follows automatically (`var(--accent)`).

**Patterns to follow:**
- applyTheme/refreshChartColors/syncThemeSystemListener lifecycle (app.js:1294-1331); setRadio + Appearance group (app.js:2314, 2336, 2835-2841); FOUC head script (index.html:11-27); `[data-theme="dark"]` token split (style.css:62-79); drift-guard convention (test_spa_gate.py:78-91 mirror guard).

**Test scenarios:**
- Happy path: each of the four non-default accents defines `--accent` and `--accent-dark` in light AND dark contexts; green has no override block (default).
- Error path: no hex color literal appears in `static/index.html`, `static/app.js`, or `static/format.js` (lockstep extension); style.css remains the only literal carrier.
- Happy path (gate pin): Appearance card ships the accent group with exactly the five values in contract order; FOUC bootstrap reads `localStorage.accent`; `applyAccent` exists.
- Edge case: stored accent value unknown → no `data-accent` attribute (falls back to green).
- Integration (smoke-ui.sh): select purple in Me → accent chips/buttons render purple on Today, Journey, World, Me; repeat in dark theme; default account shows no `data-accent`.

**Verification:**
- node frontend tests + pytest + pyright clean; smoke-ui.sh full pass on a scratch server (restart AFTER commit for the `?v=` stamp).

- [ ] **Unit 3: Delivery — commits, PR, gate**

**Goal:** Land R2B as reviewable work-unit commits on `feat/r2b-accent-colour`, pass the RDD gate, open the PR, reconcile backlog + ROUTER-LOG.

**Requirements:** R1-R5

**Dependencies:** Units 1-2

**Files:**
- Modify: `docs/backlog.md` (check the R2B row)
- Modify: `/home/james/ai-workspace/workflow_optimisation/ROUTER-LOG.md` (one row: date, task, class, gate outcome, probe flag, evidence)

**Approach:**
- Work-unit commits: (1) backend accent API + tests, (2) frontend accent theming + UI + tests, (3) gate/smoke pin updates. Conventional commits, no AI attribution.
- Receipt-driven gate per repository policy; advisory ce:review before the gate (small-feature route).

**Verification:**
- PR #67 (or next number) opened from `feat/r2b-accent-colour` against main; receipt allow; all suites green.

## System-Wide Impact

- **Interaction graph:** settings read/write chain (routes → database → AppSettings → SPA loadData/renderSettings); FOUC bootstrap; chart colors; confetti colors.
- **Error propagation:** invalid accent → 422 via SettingsIn validator (same as theme); unknown stored value → client falls back to green silently.
- **State lifecycle risks:** localStorage accent vs server settings can drift (server wins on load, same as theme); `?v=` stamp requires server restart after commit for smoke.
- **API surface parity:** `theme` is the contract twin; `OnboardingIn` explicitly unchanged (extra=forbid already rejects `accent`).
- **Integration coverage:** API tests + gate pins + smoke-ui prove cross-layer behavior; node tests cover pure helpers.
- **Unchanged invariants:** `--accent` brand `#2f7d54` in the four PWA locations (palette lockstep stays green); theme mechanics, XP/quest engines, notifications untouched; `REWARD_AFFECTING_KEYS` unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Palette lockstep test drift when accent tokens land | Extended lockstep test asserts per-accent tokens in both themes and forbids literals outside style.css |
| Accent flash on load (FOUC) | Bootstrap reads `localStorage.accent` pre-paint, mirroring theme |
| Dark-theme contrast incoherence per accent | Per-colour `[data-theme="dark"]` `--accent-dark` overrides (mirrors existing `#58a97e` treatment) |
| Change exceeds 400-line budget | Small mirror-of-theme change (~350 lines incl. tests); no chaining needed |

## Sources & References

- **Origin:** `docs/strategy.md` §RELEASE 2B (merged PR #66); `docs/backlog.md` R2B row
- Related code: `constants.py` DEFAULT_SETTINGS, `routes.py` SettingsIn/`_valid_theme`, `database.py` `_settings_from_conn`/`_apply_settings`, `models.py` AppSettings, `static/style.css` token blocks, `static/app.js` applyTheme/refreshChartColors/setRadio, `static/index.html` FOUC script, `tests/test_api.py` theme block, `tests/test_palette_lockstep.py`
- Related PRs: #66 (docs/strategy R2B step); prior theme cycle PRs (dark-mode)
