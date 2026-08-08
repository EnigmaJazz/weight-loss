# Design: BMI Target Goals and Onboarding Wizard

## Technical Approach

Persist a nullable `target_bmi` settings key; resolve the active target kg **on read only** through one pure helper consumed by both `rewards.reward_state` and `routes._summary_view`, so summary and rewards can never disagree. Add `target_bmi` and `height_cm` to `REWARD_AFFECTING_KEYS` so checkpoint reconciliation recomputes on every target- or BMI-affecting change. Gate first-time users (flag-absent `onboarding_complete`) behind a non-skippable SPA wizard that POSTs one atomic payload to a new `/api/onboarding` endpoint; `GET /api/auth/me` gains `needs_onboarding`. Maps to specs: `bmi-goal-setting` (helpers+resolver), `target-progress-rewards` (resolver+reward-affecting keys), `weight-tracking` (summary+settings contract), `user-onboarding` (endpoint+flag), `user-authentication` (`me` extension).

## Architecture Decisions

| Decision | Choice | Rejected | Why |
|---|---|---|---|
| Resolver location | `resolve_target_kg(target_weight, target_bmi, height_cm)` pure fn in `units.py`; called by `reward_state` and `_summary_view` | helper in `rewards.py`; duplicate reads | single source of truth for summary/rewards agreement (spec hard requirement); `units.py` is the pure-no-IO layer |
| Bidirectional target clearing | saving `target_bmi` clears `target_weight` AND saving `target_weight` clears `target_bmi` | one-way (BMI clears weight only, per proposal literal text) | two persisted targets silently diverge; precedence alone leaves stale `target_bmi` resurrecting on a later `target_weight: null`. Spec mandates only BMI→weight; converse is this design's decision |
| `height_cm` reward-affecting | add `height_cm` to `REWARD_AFFECTING_KEYS` next to `target_weight`, `start_weight_override`, `target_bmi` | only the three keys spec names | in BMI-mode a height change moves the resolved target → checkpoints move; spec says keys MUST *include* the three, not *only* those three; reconciliation is per-user |
| `me()` DB read | `me()` loads settings once to compute `needs_onboarding` (was stateless) | lightweight `get_onboarding_complete(user_id)` query | one extra `_tx` per `me`; `me` runs every boot, settings load is single-row k/v. Open Q if profiling objects |
| `onboarding_complete` storage | reuse settings k/v table, `str(bool)`; `_optional_bool` parses; absent row → `False` → `needs_onboarding=true` | separate column/table | reuses existing plumbing; rollback = drop keys (harmless per proposal) |
| BMI bounds in `OnboardingIn` | `target_bmi` field has `gt=0` only; `(10,40]` enforced in `model_validator(mode="after")` after height check | `Field(gt=10, le=40)` on the field | spec: "height presence checked before BMI bounds." Field bounds run before model_validator, so missing-height + out-of-range-BMI would surface BMI errors first. `SettingsIn` keeps direct `Field(gt=10, le=40)` (no height-order concern there) |

## Data Flow

```
SPA init → GET /api/auth/me ──(needs_onboarding)──► showOnboarding() | showTracker()+loadData()
POST /api/onboarding (OnboardingIn) ─► complete_onboarding(user_id, payload)
       └─ single _tx:
            _apply_settings(conn, user_id, updates + onboarding_complete=True + cleared target key=None)
            _upsert_entry_conn(conn, user_id, today, weight_kg, None)   # ON CONFLICT DO UPDATE → idempotent
            _reconcile_active_rewards(conn, user_id)
GET /api/weight ─► _summary_view ─► resolve_target_kg(...) ─► healthy_min/max_kg, target_status, *_bmi
GET /api/rewards ─► reward_state ─► resolve_target_kg(...)   # same helper → identical target_kg
PUT /api/settings ─► update_settings ─► _apply_settings + reconcile if key in REWARD_AFFECTING_KEYS
```

## File Changes

| File | Action | Description |
|---|---|---|
| `units.py` | Modify | Add `weight_kg_from_bmi(bmi, height_cm)`, `healthy_weight_range(height_cm)`, `classify_bmi(bmi)`, `resolve_target_kg(target_weight, target_bmi, height_cm)` |
| `models.py` | Modify | `AppSettings += target_bmi: Optional[float]=None; onboarding_complete: bool=False` |
| `constants.py` | Modify | `DEFAULT_SETTINGS += "target_bmi": None, "onboarding_complete": False` |
| `database.py` | Modify | `_settings_from_conn` maps `target_bmi`+`onboarding_complete`; `REWARD_AFFECTING_KEYS += "target_bmi", "height_cm"`; factor `_apply_settings(conn,...)` and `_upsert_entry_conn(conn,...)` out of `update_settings`/`upsert_entry`; new `complete_onboarding(user_id, payload)` single `_tx`; `_today()` helper |
| `rewards.py` | Modify | `reward_state`: `target = resolve_target_kg(settings.target_weight, settings.target_bmi, settings.height_cm)` |
| `routes.py` | Modify | `_summary_view` uses `resolve_target_kg`; adds `healthy_min_kg`/`healthy_max_kg`/`target_status`; `SettingsIn += target_bmi: Optional[float]=Field(default=None, gt=10, le=40)`; clearing in `put_settings` (BMI→null weight, weight→null BMI); `me()` returns `needs_onboarding`; new `POST /api/onboarding` + `OnboardingIn` (extra=forbid, XOR `model_validator`, height-before-bmi bounds) |
| `static/index.html` | Modify | New `#onboarding-screen` section (hidden) between `#auth-screen` and `#tracker`; wizard step markup (height → current weight → target weight/BMI mode → units → notifications) |
| `static/app.js` | Modify | `init()` branches on `needs_onboarding` from `/api/auth/me`; `showOnboarding()`; wizard step handlers; `submitOnboarding()` building `OnboardingIn` and POSTing; target input gains BMI mode + healthy-range display + out-of-range flag (CSS class+msg) reused in settings AND wizard |
| `tests/conftest.py` | Modify | New `onboarded_client` fixture + `complete_onboarding_via_api(client, **opts)` helper (defaults height 175, weight 80, target_weight 70) |
| `tests/test_units.py` | Modify | New helper tests: `weight_kg_from_bmi` (both-set 67.4, boundary 74.0, unset→None), `healthy_weight_range` (175→(56.7,76.3), unset→None), `classify_bmi` (18.5/24.9 healthy, 25.0 overweight, 18.4 underweight), `resolve_target_kg` precedence |
| `tests/test_api.py` | Modify | Update exact-key assertions for new settings (`target_bmi`, `onboarding_complete`) and summary (`healthy_min_kg`/`healthy_max_kg`/`target_status`) keys; route most existing `auth_client` settings/summary/rewards tests through `onboarded_client` where they assume a ready tracker; new: precedence, BMI round-trip+clearing, summary contract (height-set/unset/target-unset), reconciliation on `target_bmi` change |
| `tests/test_auth_api.py` | Modify | `me()` assertions add `needs_onboarding`; new: needs_onboarding true for bare new user, false after `complete_onboarding`, true for pre-existing account (no `onboarding_complete` row) |
| `tests/test_onboarding.py` | Create | XOR violation 422; unknown-key 422; height-checked-before-bmi-bounds; 401 unauthenticated; atomic happy path; idempotent re-POST (single today entry); `complete_onboarding` partial-failure rollback (monkeypatch weight insert to raise mid-`_tx`) |
| `tests/test_spa_gate.py` | Modify | Add `id="onboarding-screen"` present + hidden; assert `init()` branches on `needs_onboarding` (drift-guard/AST pattern matching the existing gate style) |

## Interfaces / Contracts

```python
# units.py — all None-safe
def weight_kg_from_bmi(bmi, height_cm) -> Optional[float]:     # round(bmi*(h/100)**2, 1); None if either unset
def healthy_weight_range(height_cm) -> Optional[tuple[float, float]]:  # (round(18.5*(h/100)**2,1), round(24.9*(h/100)**2,1)); None if height unset
def classify_bmi(bmi: float) -> str:                            # "underweight"(<18.5) | "healthy"(18.5–24.9) | "overweight"(≥25)
def resolve_target_kg(target_weight, target_bmi, height_cm) -> Optional[float]:  # target_weight if set else weight_kg_from_bmi(...)

# routes.py
class OnboardingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    height_cm: float = Field(gt=0)                              # required, positive
    weight_kg: float = Field(gt=0)                              # required, positive (today's first entry)
    target_weight: Optional[float] = Field(default=None, gt=0)
    target_bmi: Optional[float] = Field(default=None, gt=0)     # (10,40] checked in validator (after height)
    # + weight_unit/height_unit/target_unit/weight_display, tip_time/reminder_time/reminder_weekday/exercise_time
    #   reusing the SAME field validators as SettingsIn
    @model_validator(mode="after")
    def _check(self): ...  # exactly one of (target_weight, target_bmi); 10 < target_bmi <= 40 if set
```
`GET /api/auth/me` → `{id, username, email, created_at, needs_onboarding: bool}`.
`GET /api/weight` summary adds `healthy_min_kg`, `healthy_max_kg` (null when height unset), `target_status` (null when target or height unset, else `classify_bmi(calculate_bmi(target_kg, height_cm))`).
`POST /api/onboarding` → 200 `{ok: true}` (idempotent); 401 unauth; 422 validation.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | `units.py` helpers + resolver | `tests/test_units.py` pure-fn boundary cases |
| Integration | onboarding endpoint, summary contract, settings clearing/round-trip, precedence, reconciliation, `me` flag | httpx ASGITransport via `auth_client`/`onboarded_client`; conftest stubbed push |
| E2E | SPA gate branch, wizard submission, healthy-range flag | `tests/test_spa_gate.py` delivered-HTML + AST drift-guard; `tests/smoke-ui.sh` for live flow |

## Threat Matrix

N/A — no shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. `/api/onboarding` is a standard authenticated JSON route reusing `require_user`; no untrusted command surface.

## Migration / Rollout

No schema migration needed (settings is k/v; new keys default absent). Pre-existing accounts lack `onboarding_complete` → flagged `needs_onboarding=true` once on next login (accepted product decision). Rollback: revert code; leftover `onboarding_complete`/`target_bmi` rows are harmless and ignored by the old `_settings_from_conn`.

## Open Questions

- [ ] Name overlap: existing `summary.target_bmi` (BMI-of-resolved-target-weight) vs new `settings.target_bmi` (BMI goal). Different response objects so no technical conflict, but easily confused. Rename one? Proposal uses both names verbatim — flag for confirmation.
- [ ] `me()` now performs a DB read on every call (was stateless). Acceptable, or add a lightweight `get_onboarding_complete(user_id)`?
- [ ] `onboarding_complete` stored as `str(bool)` (`"True"`/`"False"`) in the k/v settings table — confirm this matches team preference vs an int 0/1.
- [ ] Should the wizard's "notifications" step be skippable (leave defaults) while height/weight/target remain mandatory? Spec mandates non-skippable wizard v1 but does not specify per-step optionality.