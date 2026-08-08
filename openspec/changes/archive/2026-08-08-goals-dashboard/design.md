# Design: Goals Dashboard

## Technical Approach

Frontend-only re-skin of the Today tab (additions to pinned contracts). New pure helpers in `format.js` (`goalProgress`, `checkpointThresholds`, `kgToImperial`) mirror `rewards.py`/`units.py` exactly; new renderers wire a hero goal ring into `#summary-card`, a 5-card milestone track into `#rewards-content`, and upgrade streak tiles in place. No backend, no new tab, no new asset tuple entry (format.js/style.css already stamped).

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Ring render host | New `renderGoalRing(summary)` called in `loadData` after `renderSummary` | Inline into `renderSummary` | Keeps the stats-grid renderer focused; reads same `chartData.weightSummary`. |
| Ring placement | Hero block inside `#summary-card`, after `<h2>Summary</h2>`, before `#summary-stats` (kept) | Replace stats grid | `#summary-stats` is pinned — must remain present. Ring sits above it. |
| Milestone drop | Remove `.rewards-next` line + `.checkpoint-list` chips; keep `.rewards-count` + `.progress-track` band | Keep rewards-next | Next threshold is now the highlighted card; subsumes the line. Neither is pinned. |
| Pending-card threshold label | Derive ALL five cards' label from `threshold_kg` via new `kgToImperial(kg)` → `weightLabel(kg, lb, stone, stoneLb, displayUnit)`; ignore API `threshold_lb/stone/stone_lb` for the track | Per-card API lb (earned) vs bare kg (pending) | Guarantees uniform 1dp display; mirrors `units.kg_to_stone`'s 14-lb carry so earned/pending never diverge. |
| kg→lb mirror | New `kgToImperial(kg)` returning `{lb, stone, stoneLb}` (raw, `weightLabel` rounds) | Inline constant in app.js | Matches the project's "conversions live in format.js" convention; node:test guardable. |
| 100% gold | `.milestone-card.is-100.is-earned { background: linear-gradient(var(--gold), var(--gold-deep)); }`, text stays `var(--text)`/`var(--accent-dark)` | gold text | Spec bars gold from any text color property. |

## Data Flow

```
/api/rewards ─▶ renderRewards ─▶ milestone-grid (5 cards from active_checkpoints ∪ {next}, thresholds ✓)
/api/weight.summary ─▶ renderGoalRing ─▶ SVG stroke-dashoffset = C·(1−pct); overlay pct + remaining_*
format.js goalProgress/checkpointThresholds ← mirror rewards.py (4dp) ; kgToImperial ← mirror units.py
```

## File Changes

| File | Action | Description |
|---|---|---|
| `static/index.html` | Modify | Insert `<div class="goal-ring" id="goal-ring" aria-hidden="true"></div>` inside `#summary-card` after its h2, before `#summary-stats`. h2 strings + form placement untouched. |
| `static/format.js` | Modify | Add `goalProgress(b,c,t)`, `checkpointThresholds(b,t)`, `kgToImperial(kg)`; register all three in the `api` object. |
| `static/app.js` | Modify | Add `renderGoalRing(summary)` (called in `loadData` after `renderSummary`); rewrite `renderRewards` to emit `.milestone-grid` (5 `.milestone-card`) + keep `.rewards-count` + `.progress-track` band; upgrade `renderStreaks` flame. |
| `static/style.css` | Modify | Add `.goal-ring`/`#goalGrad`/`.milestone-grid`/`.milestone-card` state classes + streak flame sizing; rail `stroke-dashoffset` transition into the reduced-motion block. |
| `tests/frontend/goals.test.mjs` | Create | node:test for `goalProgress`/`checkpointThresholds` (drift pin `100,80→[98,95,90,85,80]`) + `kgToImperial`. |
| `tests/test_spa_gate.py` | Modify | Add: ring SVG + `.milestone-grid` present in `index.html`; helpers present in `format.js`; empty-state copy present. |
| `tests/smoke-ui.sh` | Modify | Add (additions-only): ring visible, `.milestone-card` count == 5, `.flame` count unchanged. No pinned-string edits. |

## Interfaces / Contracts

```js
// format.js — mirror rewards.checkpoint_thresholds & units.kg_to_stone (4dp/14-lb carry)
goalProgress(b, c, t)               // → 0..1 clamped, or null if any null OR b<=t
checkpointThresholds(b, t)          // → [{percent, kg}] for 10/25/50/75/100, kg=round(b − p/100·(b−t), 4); [] if null or t>=b
kgToImperial(kg)                   // → {lb: kg*2.2046226218, stone, stoneLb} with 14-lb carry; null if kg==null
```

Ring SVG: `viewBox="0 0 140 140"`, circle r=60, `C=2π·60≈376.991`; `stroke-dasharray=C`; JS sets `stroke-dashoffset = C·(1−pct)` (pct=null → `=C`, no arc). Track `stroke: var(--border)`; progress `stroke: url(#goalGrad)` (linearGradient `var(--fox)`→`var(--accent)`). Center overlay (absolutely positioned over the svg): `${Math.round(pct*100)}%` + remaining copy from `summary.remaining_kg/remaining_lb/...` via `weightImperial`; empty state → `—` + `Set a target weight to start tracking.`.

Milestone card (data-percent, classes `milestone-card` + state):
```
.milestone-card.is-earned | .is-pending | .is-next | .is-recently-earned | .is-100
  <span class="milestone-emoji">    // 🚶🏃🔥🏆🎯 for 10/25/50/75/100
  <span class="milestone-pct">NN%
  <span class="milestone-threshold"> // weightLabel from kg (uniform kgToImperial path)
  <span class="milestone-when">     // earned YYYY-MM-DD | "pending"
```
State: `earned` = percent ∈ active_checkpoints set; `next` = percent == next_checkpoint.percent (or first pending when null); `recently-earned` = earned_at(YYYY‑MM‑DD) == max earned_at among active. `.is-100.is-earned` gold fill-only.

Streak tile upgrade: `<span class="flame">🔥` font-size → `1.7rem`; keep `dataset.streakActive` + `.flame`; value size up to `1.3rem`.

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit (node:test) | `goalProgress`/`checkpointThresholds`/`kgToImperial` incl. 0/100/overshoot/nulls/`b≤t` + drift pin `100,80→[98,95,90,85,80]` | `tests/frontend/goals.test.mjs` imports real `format.js` |
| Integration (pytest) | served `index.html` ships ring SVG + `.milestone-grid`; `format.js` ships the 3 helpers; empty-state copy | `test_spa_gate.py` additions (string/regex on served bytes) |
| E2E (smoke-ui.sh) | ring has non-zero arc, exactly 5 milestone cards, flame count unchanged | playwright-cli eval additions; no pinned-string edits |

### Audit — which existing assertions could break
- `smoke-ui.sh`: no step asserts `.checkpoint-list` or chip markup (only `Checkpoints` text + `.flame` count). **Safe.**
- `test_spa_gate.py`: no pinned `checkpoint-list`/`progress-track`/`rewards-next`; pins `.flame`, `dataset.streakActive`, `fallback` token values, reduced-motion block. New tokens are additive — `_TOKEN_NAMES` unchanged. The universal `@media *{transition-duration:0.01ms}` already neutralizes the ring transition; adding an explicit `.goal-ring-progress{transition:none}` inside the block stays compatible with `test_style_css_ships_reduced_motion_block_without_starting_style` (`@starting-style` still absent). **Safe.**
- `renderRewards` is coupled to confetti only via `r.earned_count` (consumed in `loadData`, untouched). Removing the chip loop does not affect earned_count/confetti. **Safe.**

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration. Rollback = revert the commit (pinned ids/strings/selectors unchanged, so smoke+gate remain valid).

## Open Questions

- [ ] Per-milestone emoji set final (proposed 🚶🏃🔥🏆🎯) — non-blocking, proposal deferred to design.
- [ ] Keep `.rewards-next` line for redundancy? (Design drops it; reversible if reviewer prefers.)