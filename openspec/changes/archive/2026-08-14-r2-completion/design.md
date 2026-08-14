# Design: R2 Completion

## Technical Approach

Deliver six stacked-to-main slices, each at most 400 changed lines and developed RED/GREEN under `strict_tdd`. `weekly.py` and `collectibles.py` are pure engines; dataclasses live in `models.py`; `database.py` owns transactions; async routes use `await run_db(...)`. UI slices use the frontend lane and extend the UMD `static/format.js` seam before DOM wiring.

Module delta: `routes.py` → `Database` → pure engines; `main.py` starts reconciliation; `static/app.js` consumes the APIs and `format.js` helpers.

## Architecture Decisions

| Option | Tradeoff | Decision and rationale |
|---|---|---|
| Derived weekly XP vs persisted awards | Derivation cannot represent XP outside quest rows | Persist one award per `(user, week, goal)` and include it in the canonical XP SUM; the PK makes payment idempotent. |
| Settings key vs activation table | A settings key is user-editable | Use a dedicated activation row, keeping feature lifecycle state outside `/api/settings`. |
| Unlock ledger vs earliest crossing | A ledger adds migration/reconcile complexity | Derive collectibles from retained history, matching `achievements.states()` and enabling retroactive tokens. |
| JS object vs pair array | Object literals need a bespoke drift parser | Export an array of pairs so `ast.literal_eval` can pin domains exactly. |

## Data Flow

```text
owned rows ─→ one DB snapshot ─→ weekly/collectible engines ─→ API
                    │                     │
                    └─ award diff/insert ─┴─→ canonical XP SUM
API/read diffs ─→ priority queue ─→ banner/toast/delight, sequentially
```

## Per-Slice File Changes

| Slice | Files and boundaries | RED test surface |
|---|---|---|
| 1 Icons/fox | Modify `static/format.js`, `static/app.js`, `static/index.html`, `static/icons/make_icons.py`, PNGs; `QUEST_DOMAIN_ICONS` plus fail-loud `iconForDomain`, consumed by both quest renderers with `aria-hidden`. Preserve `--fox`; regenerate assets atomically. | Create `tests/frontend/icons.test.mjs`; extend `tests/test_spa_gate.py`, `tests/test_icons.py`, `tests/smoke-ui.sh` for drift, pixel pins, and visibility. |
| 2 Weekly backend | Create `weekly.py`, `tests/test_weekly.py`; modify `models.py`, `database.py`, `routes.py`, `main.py`, `xp.py`, `tests/test_xp.py`, `tests/test_api.py`, `tests/test_user_isolation.py`. Pure boundaries: `week_start`, `goal_state`, `is_counted_week`; DB boundaries: `weekly_snapshot`, `_reconcile_weekly_awards`. | ISO rollover, exact 10/3 thresholds, Spark exclusion, partial-week exemption, startup/read idempotency, XP +40/+80, ownership. |
| 3 Weekly UI | Modify `static/index.html`, `static/app.js`, `static/style.css`, gate/smoke tests. Today renders current progress; Journey renders newest-first bounded history and failure-scoped errors. | Container-first gate RED, API rendering, both themes, reduced-motion screenshot/smoke. |
| 4 Collectibles backend | Create `collectibles.py`, `tests/test_collectibles.py`; modify `streaks.py`, `models.py`, `constants.py`, `database.py`, `routes.py`, API/isolation tests. `CollectibleFacts` is gathered in one `_tx`; new forward meal-day walk records the first date each run reaches 7/30/100. | Earliest family/checkpoint/streak/week crossing, broken runs, regression after live-state reversal, empty and foreign histories, catalogue order. |
| 5 Collectibles UI | Modify `static/index.html`, `static/app.js`, `static/style.css`, gate/smoke tests. Always render shelf; latest `unlocked_at` drives the World accent. | Locked silhouettes, dates, scoped failure, deterministic latest accent, both themes. |
| 6 Celebrations | Create `tests/frontend/celebrations.test.mjs`; modify `static/format.js`, `static/app.js`, `static/index.html`, `static/style.css`, gate/smoke tests. Capture `mutateQuest` response; queue priority is level, achievement, weekly/collectible, quest. Banner is non-blocking, tap-dismissable, ~3s. | Pure ordering/diff/suppression tests; no overlap or replay; reduced-motion returns before animation while normal state still renders. |

## Interfaces / Contracts

```sql
CREATE TABLE weekly_activation(user_id INTEGER PRIMARY KEY, activated_at TEXT NOT NULL);
CREATE TABLE weekly_awards(user_id INTEGER NOT NULL, week_start TEXT NOT NULL,
 goal TEXT NOT NULL CHECK(goal IN ('quests','good_days')),
 xp_awarded INTEGER NOT NULL CHECK(xp_awarded=40), awarded_at TEXT NOT NULL,
 PRIMARY KEY(user_id, week_start, goal));
```

`GET /api/weekly` returns `{activation, current:{week_start,exempt,goals:[{goal,current,target,met,awarded}]}, history:[...], met_flips:[goal]}`; history is capped at 12 weeks. First read stamps activation; only full weeks beginning afterward receive XP. `GET /api/collectibles` returns `{collectibles:[{key,title,earned,unlocked_at}]}` in catalogue order. Both require `require_user`; weekly mutation and signal are produced in one transaction.

## Testing Strategy

Pytest covers engines; SQLite/API tests use the tmp DB, `pair`, and ASGITransport; Node tests import real `format.js`; gate tests pin shipped source; frontend screenshots and `tests/smoke-ui.sh` prove cross-layer behavior. Every slice records truthful RED/GREEN evidence.

## Threat Matrix

HTTP routes change, so the matrix was reviewed; no command/process boundary exists.

| Boundary | Applicability | Design response / RED tests |
|---|---|---|
| Documentation-like paths | N/A — no executable classification | None |
| Git repository selection | N/A — no Git invocation | None |
| Commit state | N/A — no commit automation | None |
| Push state | N/A — no push automation | None |
| PR commands | N/A — no PR composition | None |

## Migration / Rollout and Rollback

`CREATE TABLE IF NOT EXISTS` is additive; startup reconciles only users with activation rows. Roll out by independent slices. Revert any slice independently; full rollback restores quests-only XP, while orphaned additive rows remain inert. Fox generator, PNGs, and pins roll back together.

## Risks

Risks are double payment (PK plus transactional diff), mutable-history evidence (earliest retained crossing is authoritative), fox drift (atomic generation), accepted replay after storage clearing, and UI growth (hard slice budget).

## Open Questions

None.
