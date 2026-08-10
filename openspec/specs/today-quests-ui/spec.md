# Today Quests UI Specification

## Purpose

Make today's quests and progression immediately actionable on the Today tab.

## Requirements

### Requirement: Today Quest Card

The Today tab MUST render `#quests-card` with exactly the authenticated user's three current quests. Each row MUST show quest label, domain, XP, and status. Open rows MUST offer Complete, Skip, and Replace controls; terminal rows MUST not offer invalid actions. Detected completion MUST display as auto-completed.

#### Scenario: Render and complete a quest

- GIVEN the quest API returns three quests including one open quest
- WHEN Today renders and Complete is activated
- THEN all three MUST appear and the completed row MUST refresh to done

#### Scenario: Render detected and terminal states

- GIVEN quests are detected-done, skipped, and replaced
- WHEN the card renders
- THEN detected-done MUST say auto-completed and terminal rows MUST expose no completion control

### Requirement: Replace and Error Feedback

Quest controls MUST call their matching mutation endpoints, disable duplicate submission while pending, and announce success or failure without removing the existing card. A rejected second replacement MUST leave the rendered assignment unchanged.

#### Scenario: Replacement cap error

- GIVEN one replacement has already succeeded today
- WHEN Replace is attempted again
- THEN accessible error feedback MUST appear and the three current quests MUST remain unchanged

### Requirement: XP Summary Chip and Mirrors

The existing Today summary MUST include an XP/level chip showing title, level, total XP, and progress to `next_level_at`. `static/format.js` MUST expose pure mirrors for level threshold, level-from-XP, and XP-into-next; `node:test` drift pins MUST cover totals 99, 100, and 250 against backend results.

#### Scenario: Boundary mirror

- GIVEN totals 99, 100, and 250
- WHEN backend and `format.js` progression values are compared
- THEN both MUST return levels 1, 2, and 3 with identical next-level progress

#### Scenario: Chip renders

- GIVEN `/api/xp` returns a valid progression payload
- WHEN Today loads
- THEN the summary chip MUST show its level, title, total, and next-level progress

### Requirement: Styling and Regression Gates

The new card and chip MUST use existing design tokens, remain dark-mode compatible, preserve 48px targets and focus visibility, and gate transitions under `prefers-reduced-motion`. Existing DOM/copy pins MUST remain; SPA gate and smoke tests MAY add only selectors and interactions required for these surfaces.

#### Scenario: Reduced motion and gates

- GIVEN reduced motion is requested
- WHEN the new surfaces render and smoke/gate suites run
- THEN their animation MUST be neutralized and all old plus added checks MUST pass
