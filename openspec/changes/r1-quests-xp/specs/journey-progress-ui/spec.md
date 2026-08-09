# Journey Progress UI Specification

## Purpose

Show longitudinal quest, XP, and momentum progress on Journey.

## Requirements

### Requirement: Journey Progress Cards

Journey MUST render `#xp-card`, `#momentum-card`, and `#quest-history-card`. The XP card MUST show level, title, total XP, progress to the next level, and recent completed quests. Momentum MUST show today's tier and successful days out of 21. History MUST show recent quest date, label, status, and awarded XP, where non-done statuses show zero awarded XP.

#### Scenario: Render populated progress

- GIVEN XP, momentum, and recent quest data exist
- WHEN Journey renders
- THEN all three cards MUST show the corresponding values and newest quest records first

#### Scenario: Render empty history

- GIVEN no historical quests exist
- WHEN Journey renders
- THEN the history card MUST show an explicit empty state without hiding XP or momentum

### Requirement: Journey Data Loading

The shared `loadData` flow MUST add authenticated requests for quests, XP, and momentum, render only the current user's responses, and preserve existing Journey data when one new request fails. Loading and failure states MUST be announced accessibly.

#### Scenario: Load all new sources

- GIVEN an authenticated user opens Journey
- WHEN `loadData` completes
- THEN quests, `/api/xp`, and `/api/momentum` MUST each be fetched and rendered once

#### Scenario: Partial request failure

- GIVEN the momentum request fails while other Journey requests succeed
- WHEN loading settles
- THEN XP and quest history MUST remain visible and momentum MUST show a scoped error state

### Requirement: Journey UI Regression Contract

The cards MUST use existing tokens, support dark mode, preserve focus and mobile stacking, and neutralize new motion for `prefers-reduced-motion`. Existing Journey selectors and copy MUST remain; SPA gate and smoke suites MAY add only the new card selectors and data checks.

#### Scenario: Gate and smoke coverage

- GIVEN the R1 Journey surfaces are present
- WHEN SPA gate, smoke, and reduced-motion checks run
- THEN each new id MUST be found and every pre-existing check MUST still pass
