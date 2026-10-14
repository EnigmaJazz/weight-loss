---
title: "feat: In-app mood & habit quick check-in (R1 completion)"
type: feat
status: active
date: 2026-08-15
origin: openspec/specs/mood-logging/spec.md, openspec/specs/habit-logging/spec.md, openspec/specs/today-quests-ui/spec.md
---

# In-App Mood & Habit Quick Check-In

## Overview

Add a "Check in" card to the Today tab so `mood_checkin` and `habit_checkin` quests can be completed by actually doing the task in-app. The backend contract and the quest auto-complete detection already exist and are tested; this slice builds the missing SPA surface: a mood scale (1–5, optional note) and the four HABIT_TYPES quick-log chips, wired to `POST /api/mood` / `POST /api/habits`, after which the assigned quest flips to **Auto-completed** on the next quests read.

## Problem Frame

A real user completes `mood_checkin` today by clicking the quest row's Complete button — the strategy's "one-tap completion" entry method, which is deliberate — but the honest path (log the mood → quest auto-completes) is unreachable in-app: the SPA has no mood/habit logging UI. The strategy's product loop (Goal → Quest → Action → Log → Reward → Progress) wants the logging surface to exist; the backend and detection engine already honor it (`quests.detect()` maps mood rows → `mood_checkin`, habit rows → `habit_checkin`; `_ensure_today_quests` persists detected completions on read).

## Requirements Trace

- R1. Today tab ships a `#checkin-card` with a mood quick check-in (five mood values 1–5, optional note ≤ 500 chars) and a habit quick-log (exactly `HABIT_TYPES`: water, fruit_veg, home_cooked, sleep_routine).
- R2. Logging posts to the existing `POST /api/mood` and `POST /api/habits` (today's date, validated server-side: 422 on invalid, per-user isolated); the card shows accessible success/error feedback without removing existing content.
- R3. After a successful log, quests + XP refresh so an assigned `mood_checkin`/`habit_checkin` flips to Auto-completed (source "detected") and pays XP, feeding momentum the same way any logged action does.
- R4. Token-only styling (both themes, mobile, reduced-motion unaffected — static controls, no animation); `HABIT_TYPES` mirror drift-guarded against the server constant; existing gate pins keep passing.
- R5. The Complete button stays on quest rows (strategy "one-tap completion" is a first-class entry method) — this feature adds the honest logging path, it does not remove the one-tap path.

## Scope Boundaries

- No backend changes: `/api/mood`, `/api/habits`, detection, XP, momentum are untouched (already shipped + tested).
- No onboarding changes, no notifications, no AI.
- No delete/edit UI for past entries (list surfaces exist server-side; not part of this slice).
- No per-quest inline controls inside the quest card — the check-in card is the logging surface (row affordances are deferred polish).

### Deferred to Separate Tasks

- Quest-row "Check in" affordance (scroll/focus hint from a `mood_checkin` row to the card): polish, not required for the honest path.
- Mood/habit history list in the UI (GET endpoints exist; the Today card is quick-log only).

## Context & Research

### Relevant Code and Patterns

- **Backend contract (done, tested)**: `POST /api/mood` (mood 1–5, optional note ≤500, date defaults to today per memory #514) and `POST /api/habits` (habit_type allowlisted) in routes.py:1169-1245; `MoodEntry`/`HabitEntry` models; `insert_mood_entry`/`insert_habit_entry` (database.py:635-711); per-user isolation tested in test_mood_api.py + test_habit_api.py.
- **Detection (done, tested)**: `quests.detect()` (quests.py:193-213) maps `has_mood` → mood_checkin, `has_habit` → habit_checkin; `_ensure_today_quests` (routes.py:1287-1330) reconciles and persists detected completions on GET /api/quests, paying the weekly award when a met objective flips (R6).
- **Quest card / XP chip**: `#quests-card` + `#quests-list` (index.html:291-295), `renderQuests` + `buildQuestActions` (app.js:2165-2226), `loadQuestsAndXp` sequencing (memory #522 — quests fetch before xp fetch), `renderXpChip` (app.js:2228+).
- **Existing logging card patterns to mirror**: the weight/exercise/meal logging cards on Today/Journey — form + submit + error/success hint pattern, `fetchJson` helper, `hint error` role=alert pattern.
- **Drift-guard convention**: `HABIT_TYPES` literal in app.js (line 14-15) pinned by test_spa_gate.py's mirror guard; the check-in card's four chips must join that pin.
- **Frontend lane precedent**: r2b-accent-colour (frontend-dev → frontend-apply-local, orchestrator merges evidence); smoke scratch-server conventions (setsid env uvicorn, restart after commit for the `?v=` stamp).

### Institutional Learnings

- `node --test tests/frontend/*.test.mjs` glob (bare dir fails on Node 26).
- gga STRICT-mode flake: retry the identical commit (memory #501).
- Smoke helper conventions: `assert_find`, `assert_visibility`, `step_ok`/`step_fail`, synchronous XHR for API truth (the rotation-aware XP pins pattern from eceb42a).
- Reduced-motion gate: static controls need no animation; keep existing `prefers-reduced-motion` CSS intact.

## Key Technical Decisions

- **One new `#checkin-card` on Today** (between quests-card and weekly-card) with two sections: Mood check-in (five buttons + optional note input + submit) and Habit quick-log (four chips). One card, one surface, honest-logging path for both quest keys.
- **POST then refresh**: after a successful log, call the existing quests+XP refresh path (`loadQuestsAndXp`), so the quest flips to Auto-completed and XP/momentum update — reuses the shipped detection flow, zero backend changes.
- **Client mirror of HABIT_TYPES drives the chips** (rendered from the pinned app.js literal), so the drift guard covers both the literal and the UI.
- **Mood values are 1–5 buttons** with accessible labels (aria-pressed or radio semantics); note input has maxlength=500 matching the server contract.
- **Complete button unchanged** — one-tap completion stays per strategy; the check-in card is additive.

## Implementation Units

- [ ] **Unit 1: Check-in card markup, tokens, and logging logic (frontend lane)**

**Goal:** Today tab ships the mood + habit check-in card; logging works end-to-end and flips assigned quests to Auto-completed.

**Requirements:** R1, R2, R3, R4, R5

**Dependencies:** None (backend already live)

**Files:**
- Modify: `static/index.html` (`#checkin-card` between quests-card and weekly-card: mood section with five 1–5 buttons + optional note + submit; habit section with four HABIT_TYPES chips; hint/error elements)
- Modify: `static/style.css` (token-only card styles: `.checkin-*` classes, mood buttons, habit chips, active/disabled states, dark-mode compatible via existing tokens)
- Modify: `static/app.js` (render check-in card state; mood/habit submit handlers calling `fetchJson` POST; success → clear controls + `loadQuestsAndXp()` refresh; failure → accessible error hint; disable controls while pending — mirror the quest-action mutation pattern)
- Modify: `tests/test_spa_gate.py` (gate pins: `#checkin-card` markup ships; the four chip values match `HABIT_TYPES` exactly; mood buttons are 1–5 in order; success-path wiring exists — e.g. fetchJson POST to /api/mood and /api/habits)
- Test: `tests/frontend/checkin.test.mjs` (node:test on pure helpers if any are extracted to format.js — e.g. a mood-label/validate helper; at minimum pin the chip catalogue mirror)

**Approach:**
- Render the habit chips from the existing `HABIT_TYPES` literal in app.js (single source in the SPA), not hardcoded HTML — the drift guard then covers the UI.
- Mood buttons: five labeled buttons (1–5) in a row; selecting one marks it active; optional note input; Submit posts `{"mood": N, "note": "..."}`.
- Habit chips: one tap posts `{"habit_type": "..."}` immediately (quick-log semantics), disabled while pending.
- After any successful POST: clear the section, call the existing quests+XP refresh (sequenced per memory #522), show a transient success hint; on failure show the error hint and keep the user's selection.

**Patterns to follow:**
- Weight/exercise logging card form + hint pattern; `buildQuestActions` pending-disable pattern (app.js:2228+); `fetchJson`; the `hint error` role=alert convention; the HABIT_TYPES mirror pin (test_spa_gate).

**Test scenarios:**
- Happy path (gate): `#checkin-card` ships on Today with mood section (five buttons 1–5 in order) and habit section (exactly four chips matching `HABIT_TYPES`).
- Happy path (node): chip catalogue mirror equals `HABIT_TYPES`; any extracted mood helper validates 1–5.
- Error path (gate or node): invalid mood value rejected client-side before POST (no request for 0/6/empty).
- Integration: a successful mood POST followed by the quests refresh causes an assigned `mood_checkin` quest to render Auto-completed (smoke covers the real chain; unit-level if a pure helper is extracted).

**Verification:**
- node tests green (glob); pytest gate file green; pyright clean on changed python; full suite still green.

- [ ] **Unit 2: Smoke pins + full verification + delivery**

**Goal:** The honest-logging loop is proven in a real browser (log mood → quest Auto-completes; log habit → same), and the change ships through ce:review + the RDD gate.

**Requirements:** R1–R5

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/smoke-ui.sh` (check-in pins: today's rotation is deterministic — compute the assigned keys from the API and assert: when `mood_checkin` is assigned, logging a mood flips its row to Auto-completed and the chip total rises by that quest's XP; same for `habit_checkin`; do NOT hardcode which quests are assigned — reuse the rotation-aware pattern from eceb42a)
- Modify: `docs/backlog.md` (mark the R1 mood/habits row or add a completion note) — optional if the row already reads done
- Modify: `/home/james/ai-workspace/workflow_optimisation/ROUTER-LOG.md` (one row: date, task, class, gate outcome, probe flag, evidence)

**Approach:**
- Smoke asserts the real chain: from the quests API read, find the assigned mood/habit quest; click the corresponding check-in control; assert the row flips to Auto-completed (source label) and XP chip consistency (rotation-aware derivation from GET /api/xp, never hardcoded).
- Run ce:review advisory (small feature route), then the RDD gate (`gentle-ai review status` with base-ref origin/main — the gate is live again).
- Work-unit commits: (1) check-in card + tests, (2) smoke pins + housekeeping. Conventional commits, no AI attribution.

**Verification:**
- Full smoke pass (123+ new pins) on a scratch server, restarted AFTER commits (`?v=` stamp).
- ce:review findings resolved; RDD receipt issued; PR opened with `type:feature` label (via `gh api` — the `gh pr edit --add-label` GraphQL workaround, memory #648).

## System-Wide Impact

- **Interaction graph:** check-in POST → `/api/mood`/`/api/habits` → next `GET /api/quests` read-detection persists completion → XP chip + weekly award (R6) + momentum derive on their next reads.
- **Error propagation:** server 422/4xx → error hint in the card, user's selection preserved; network failure → same hint, no state loss.
- **State lifecycle risks:** none persisted client-side; the card is stateless between loads (entries live server-side).
- **API surface parity:** no API changes; the SPA finally consumes two shipped endpoints.
- **Unchanged invariants:** quest card Complete/Skip/Replace untouched; detection rules, XP curve, momentum, HABIT_TYPES, and all existing gates unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Quest rotation varies per day — smoke must not hardcode which quests are assigned | Rotation-aware pins derived from GET /api/quests (eceb42a pattern); skip the check-in assertion gracefully when neither quest is assigned (non-weigh-in days always assign mood_checkin, so at least one is present) |
| Double-tap duplicate mood/habit rows | Pending-disable on controls while the POST is in flight (mirror quest actions) |
| Drift between chip labels and HABIT_TYPES | Chips rendered from the pinned app.js literal; gate asserts exact set equality |
| 400-line budget | Small frontend slice (~300 lines incl. tests); no chaining needed |

## Sources & References

- **Origin specs:** `openspec/specs/mood-logging/spec.md`, `openspec/specs/habit-logging/spec.md`, `openspec/specs/today-quests-ui/spec.md` (all archived from r1-quests-xp)
- Related code: `routes.py` (/api/mood, /api/habits, `_ensure_today_quests`), `quests.py` (`detect`), `static/index.html` (Today tab), `static/app.js` (loadQuestsAndXp, buildQuestActions), `tests/test_mood_api.py`, `tests/test_habit_api.py`, `tests/test_spa_gate.py`, `tests/smoke-ui.sh`
- Related PRs: #43–#51 (R1), #67 (r2b-accent-colour — the routing/lane precedent)
