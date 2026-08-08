# Theme Preference Specification

## Purpose

Define a three-state per-user theme preference (`system` | `light` | `dark`) that drives a FOUC-safe, JS-as-source-of-truth theming lifecycle across pre-auth and authenticated screens.

## Requirements

### Requirement: Three-State Theme Preference

The settings API MUST accept a per-user `theme` key with value `"system"` (default), `"light"`, or `"dark"`. `SettingsIn` MUST reject any other value with 422. `GET /api/settings` round-trips the stored value; a missing row MUST default to `"system"`. The `theme` key MUST be per-user isolated and MUST NOT appear in `OnboardingIn`.

#### Scenario: Round-trip the three states

- GIVEN an authenticated user with default settings
- WHEN `PUT /api/settings` saves `{"theme": "dark"}`, then `{"theme": "light"}`, then `{"theme": "system"}`
- THEN each `GET /api/settings` MUST return the exact value just saved, and the default for no row MUST be `"system"`

#### Scenario: Reject invalid theme

- GIVEN an authenticated user with valid settings
- WHEN `PUT /api/settings` supplies `{"theme": "auto"}`
- THEN the API MUST respond 422 and current settings MUST remain unchanged

#### Scenario: Onboarding untouched

- GIVEN the onboarding payload schema
- WHEN `POST /api/onboard` is sent
- THEN `theme` MUST NOT be an accepted key and onboarding_completion MUST be unaffected by any theme value

#### Scenario: Per-user isolation

- GIVEN users A and B each register fresh
- WHEN A sets `theme: "dark"` and B sets `theme: "system"`
- THEN GET for A MUST return `dark`, GET for B MUST return `system`, and neither MUST observe the other's value

### Requirement: Pure resolveTheme Helper

`static/format.js` MUST expose a pure `resolveTheme(pref, systemPref)` returning `"light"` or `"dark"`. `pref="light"` → `"light"`; `pref="dark"` → `"dark"`; `pref="system"` → `systemPref` (`"dark"` if `matchMedia` is dark, else `"light"`), defaulting to `"light"` when systemPref is unavailable. It MUST be covered by `node:test`.

#### Scenario: Resolves the truth table

- GIVEN `resolveTheme` and a `pref` plus `systemPref`
- WHEN called with each of `("system","dark")`, `("system","light")`, `("light","dark")`, `("light","light")`, `("dark","dark")`, `("dark","light")`, `("system", null)`
- THEN it MUST return `dark`, `light`, `light`, `light`, `dark`, `dark`, `light` respectively

### Requirement: FOUC-Safe Pre-Auth Theming

An inline `<head>` script MUST set `document.documentElement.dataset.theme` from localStorage before first paint, with `matchMedia("(prefers-color-scheme: dark)")` as fallback; light is the no-JS default. Post-login the server `theme` setting MUST win via `loadData()`. A manual toggle MUST write-through to localStorage so auth screens match the user's last choice. CSS MUST NOT contain an `@media (prefers-color-scheme)` theme block.

#### Scenario: Pre-auth no flash

- GIVEN no authenticated session and an unstyled load
- WHEN the inline head script runs before paint
- THEN `data-theme` MUST be set before the body paints, honoring localStorage or the system preference, with no visible flash

#### Scenario: Server wins post-login

- GIVEN localStorage holds `dark` but the server setting is `light`
- WHEN the user is authenticated and `loadData()` runs
- THEN the resolved theme MUST follow the server setting (`light`)

### Requirement: Theme UX Surfaces

A header toggle visible pre-auth (beside `#logout-btn`) and a three-state System/Light/Dark radio in a new Settings "Appearance" card MUST both drive the same `theme` setting. In `"system"` mode a `matchMedia` change listener MUST flip `data-theme` live without reload. The wizard MUST NOT gain a theme step.

#### Scenario: Toggle updates DOM and persists

- GIVEN an authenticated user on any tab
- WHEN the header toggle or the Settings radio changes the theme
- THEN `data-theme` MUST update immediately, the new value MUST be persisted via `PUT /api/settings`, and localStorage MUST be written

#### Scenario: Live system-follow

- GIVEN `theme` is `"system"`
- WHEN the OS color scheme flips
- THEN `data-theme` MUST update to match without a page reload