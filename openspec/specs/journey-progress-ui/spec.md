# Journey Progress UI Specification

## Purpose

Show longitudinal quest, XP, and momentum progress on Journey.

## Requirements

### Requirement: Journey Progress Cards

Journey MUST render `#xp-card`, `#momentum-card`, `#achievements-card`, and `#quest-history-card`, with achievements immediately after momentum. The XP card MUST show level, title, total XP, progress to the next level, and recent completed quests. Momentum MUST show today's tier and successful days out of 21. Achievements MUST show all six catalogue entries, each as earned with its unlock date or locked without partial progress. History MUST show recent quest date, label, status, and awarded XP, where non-done statuses show zero awarded XP.

(Previously: Journey rendered XP, momentum, and quest history cards without an achievements card.)

#### Scenario: Render populated progress

- GIVEN XP, momentum, achievement, and recent quest data exist
- WHEN Journey renders
- THEN all four cards MUST show their values, achievements MUST follow momentum, and quest records MUST be newest first

#### Scenario: Render empty history

- GIVEN no historical quests exist and all achievements are locked
- WHEN Journey renders
- THEN history MUST show an explicit empty state and all six locked achievements MUST remain visible without hiding XP or momentum

### Requirement: Journey Data Loading

The shared `loadData` flow MUST add authenticated requests for quests, XP, momentum, and achievements, render only the current user's responses, and preserve successful Journey data when one request fails. Loading and failure states MUST be announced accessibly and scoped to the affected card.

(Previously: Journey loaded quests, XP, and momentum, with no achievements request or achievement-specific failure state.)

#### Scenario: Load all progress sources

- GIVEN an authenticated user opens Journey
- WHEN `loadData` completes
- THEN quests, `/api/xp`, `/api/momentum`, and `/api/achievements` MUST each be fetched and rendered once

#### Scenario: Partial request failure

- GIVEN the achievements request fails while other Journey requests succeed
- WHEN loading settles
- THEN XP, momentum, and quest history MUST remain visible and achievements MUST show a scoped accessible error state

### Requirement: Journey UI Regression Contract

The four cards MUST use existing tokens, support dark mode, preserve focus and mobile stacking, and neutralize new motion for `prefers-reduced-motion`. Existing Journey selectors and copy MUST remain; SPA gate and smoke suites MAY add only achievement-card selectors and data checks.

(Previously: The regression contract covered the three existing Journey cards and unspecified new card ids.)

#### Scenario: Gate and smoke coverage

- GIVEN the existing Journey surfaces and the achievements card are present
- WHEN SPA gate, smoke, dark-mode, and reduced-motion checks run
- THEN `#achievements-card` MUST be found after `#momentum-card` and every pre-existing check MUST still pass
