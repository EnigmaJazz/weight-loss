# Design: R2 World v1 — XP Island

## Technical Approach

Implement both specs in the vanilla SPA. `static/format.js` derives five World stages from `/api/xp`; `static/app.js` renders the inline SVG, progress, and successful-read stage diff. Backend derivation, per-user isolation, tab order, and confetti stay unchanged.

## Architecture Decisions

| Option | Tradeoff | Decision and rationale |
|---|---|---|
| Client derivation vs. API `stage` | Client math needs drift pins; API expansion duplicates `total_xp`. | Add pure `worldStage(totalXp)` to `format.js`, following existing XP mirrors and frontend-only scope. |
| Inline SVG vs. assets | Inline markup costs lines; assets need cache registration and theme variants. | Use one SVG with five `data-stage`-selected groups; semantic fills need no asset pipeline. |
| New effect vs. existing confetti | A new effect duplicates motion handling. | Add pure `stageChanged(previous, current)` and reuse `fireConfetti()`, matching existing read diffs. |
| Persisted vs. derived state | Persistence introduces migrations and reconciliation. | Keep World derived; lower reads render but never celebrate. |

## Data Flow and Module Boundaries

    quests table → Database.total_xp_for_user → GET /api/xp
                                               ↓ successful response
    worldStage → renderWorld → data-stage/SVG/progress → stageChanged → fireConfetti

`database.py` keeps gathering per-user done-quest XP; all Python modules remain unchanged and backend state stays on `app.state`. The SPA keeps transient `prevWorldStage = null` beside existing read-diff state, updating it only after successful render.

## Data Model and Migration

No schema/dataclass changes. `XpState` stays derived. Never create `reward_events`, which schema initialization drops; future persistence needs an additive, user-owned table in another change. No migration or flag is required; rollback is a frontend revert.

## API Contract

No endpoint is added or modified.

- `GET /api/xp`, no body or query parameters; authenticated session cookie required.
- `200`: `{level: int, title: string, total_xp: int, xp_into_next: int, next_level_at: int, recent_completions: [{id: int, quest_key: string, title: string, xp_value: int, completed_at: string|null}]}`.
- `401`: missing, expired, or invalid session; other failures retain existing handling.

Stages start at `0/700/2700/10450/23200`. Stage 1 shows `xp_into_next / (next_level_at - thresholdForLevel(level))`; stages 2–4 normalize progress between stage thresholds; stage 5 shows “Island fully evolved” and a complete bar. Failed reads show scoped error, do not update history, and cannot celebrate.

## SPA and CSS

Replace the placeholder with `#world-card`, `#world-island`, five monotonic groups, `#world-stage-name`, and accessible progress. The fox exists only at Legend. Call `renderWorld` in the fulfilled `/api/xp` branch of `loadQuestsAndXp()`, covering startup and quest refresh. First success initializes history; only increases fire once.

Add derived semantic tokens, token-only SVG classes, one-stage selectors, responsive sizing, and optional motion. The existing reduced-motion block disables island motion without hiding the stage. No asset is added: startup already precomputes `index.html` and git-`?v=` stamps existing JS/CSS; deployment restarts refresh it.

## File Changes

| File | Action | Description |
|---|---|---|
| `static/format.js` | Modify | Add/export stage derivation and diff helpers. |
| `static/index.html` | Modify | Replace placeholder with inline island/progress markup. |
| `static/app.js` | Modify | Render successful XP reads and stage-up confetti. |
| `static/style.css` | Modify | Theme, stages, responsive layout, motion gate. |
| `tests/frontend/world.test.mjs` | Create | Pure boundary and eligibility regressions. |
| `tests/test_spa_gate.py` | Modify | Replace placeholder pins with delivered-artifact pins. |
| `tests/smoke-ui.sh` | Modify | Exercise the World tab in-browser. |

## Testing Strategy

Strict RED-GREEN-REFACTOR applies. `tests/frontend/world.test.mjs` pins every boundary and `stageChanged` suppression/fire cases. `tests/test_spa_gate.py::test_index_html_world_panel_ships_xp_island` pins one SVG, five groups, Legend-only fox, tokens, renderer, tabs, and motion CSS. Existing ASGITransport cases `tests/test_api.py::{test_xp_api_boundaries,test_xp_api_isolation,test_xp_requires_auth}` re-prove the API. Smoke asserts card/progress, one visible stage, absent placeholder, and both themes. Gates: pytest, `node --test tests/frontend/*.test.mjs`, pyright, then scratch-server smoke.

## Chained PR Slices (each <400 changed lines)

1. **Pure contract:** `format.js` + `world.test.mjs`; verify focused Node tests and full Node suite. Shippable unused exports; rollback these two files.
2. **Static island:** `index.html` + bounded SVG/CSS + SPA gate replacement; verify `test_spa_gate.py` and reduced-motion/theme pins. Shippable loading/error-capable surface; rollback markup/styles/gates.
3. **Live behavior:** `app.js` wiring, final CSS adjustments, SPA wiring pins, and smoke updates; verify all gates and browser smoke. Rollback preserves Slice 2’s static surface.

## Threat Matrix

N/A — this change adds no routing, shell, subprocess, VCS/PR automation, executable classification, or process-integration boundary; it only consumes an unchanged route.

## Risks and Open Questions

- SVG size may breach a slice budget: keep paths compact and enforce the per-slice diff before commit.
- CSS selectors could expose multiple stages: structural gate plus browser count assertion requires exactly one visible group.
- Confetti could over-fire: update prior state only after successful rendering and pin every suppressed transition.

Open questions: None.
