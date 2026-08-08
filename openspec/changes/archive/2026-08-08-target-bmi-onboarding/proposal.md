# Proposal: BMI Target Goals and Onboarding Wizard

## Intent

Goal-setting and onboarding foundation for a fun-first, gamified app. Today users set only a target weight; new users get no guided setup, so height, target, and schedules are often missing and BMI stays unused. This change lets users target a BMI (with implied weight and total loss shown), get a healthy-range recommendation with classification, and walks first-time users through a wizard collecting height, current weight, target, and unit/notification preferences.

## Assumptions (recorded product decisions)

- `target_weight` wins over `target_bmi` when both set; BMI-mode edits set `target_bmi` and clear `target_weight`.
- Settings endpoint MAY store `target_bmi` without height (resolved target is null; UI prompts "set height to enable BMI target"); onboarding REQUIRES height.
- Flag-absent `onboarding_complete` marks every pre-existing account as needing the wizard once on next login (accepted: forces height/target for new features).
- Wizard is NOT skippable in v1 — bounded 4–5 step flow after email-only registration.
- Classification buckets: underweight <18.5, healthy 18.5–24.9, overweight ≥25. No obese bucket in v1.
- `target_unit` validator stays `kg|st-lb`; BMI is a separate SPA input mode, no new target unit.

## Scope

### In Scope
- `target_bmi` settings key (AppSettings, DEFAULT_SETTINGS, SettingsIn `extra="forbid"`); derived `target_kg` computed on read only, never persisted; key added to `REWARD_AFFECTING_KEYS`.
- Pure helpers in units.py: `weight_kg_from_bmi`, `healthy_weight_range`, `classify_bmi`.
- `GET /api/weight` summary gains `healthy_min_kg`/`healthy_max_kg`/`target_status`.
- `POST /api/onboarding` + `onboarding_complete` flag; `GET /api/auth/me` gains `needs_onboarding`.
- `database.complete_onboarding`: settings upsert + first weight entry + reward reconciliation in one idempotent transaction.
- SPA `#onboarding-screen` wizard reusing existing payload shapes; `app.js` branches on `needs_onboarding`.
- Tests: onboarding fixture/helper for `auth_client`; regressions for helpers, summary contract, precedence, onboarding endpoint.

### Out of Scope
- Obese bucket, skippable wizard, target-edit UX beyond BMI mode, milestone UI redesign, email collection changes.

## Capabilities

### New Capabilities
- `bmi-goal-setting`: BMI target mode — precedence, healthy range, classification, shared target-resolution helper.
- `user-onboarding`: `needs_onboarding` gating + atomic `POST /api/onboarding` flow.

### Modified Capabilities
- `target-progress-rewards`: thresholds/progress resolve target through the shared helper; `target_bmi` is a reward-affecting key.
- `weight-tracking`: summary contract extension; settings contract gains `target_bmi`, `onboarding_complete`, unit prefs.
- `user-authentication`: `GET /api/auth/me` returns `needs_onboarding`.

## Approach

Persist `target_bmi`; resolve `target_kg` on read via one pure helper shared by rewards.py and `_summary_view` so summary and rewards can never disagree. Add the key to `REWARD_AFFECTING_KEYS` so checkpoint reconciliation recomputes on target-mode changes. Gate the SPA on `needs_onboarding`; wizard posts one atomic payload to `/api/onboarding`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `units.py` | New | BMI helpers + resolution helper |
| `database.py` | Modified | `target_bmi` key, `complete_onboarding`, `REWARD_AFFECTING_KEYS` |
| `rewards.py` / `routes.py` | Modified | Shared target resolution; summary contract |
| `models.py` / `constants.py` | Modified | AppSettings, defaults, onboarding flag |
| `static/*` | Modified | Onboarding screen, wizard steps, BMI input mode |
| `tests/` | Modified | Onboarding fixture + new regressions |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Reconciliation breaks if `target_bmi` missing from `REWARD_AFFECTING_KEYS` | High | Add key; regression test |
| Summary/rewards target divergence | Med | Single shared helper + contract tests |
| Forced wizard upsets existing users | Med | Accepted decision; one-time, idempotent |
| Wizard partial writes | Med | Single transaction; idempotent re-run |

## Rollback Plan

Revert `target_bmi`/onboarding code and the SPA gate. Settings are key-value: drop the new keys, no destructive migration; leftover `onboarding_complete` flags are harmless. Existing entries, schedules, and rewards untouched.

## Dependencies

None external. Reuses existing settings plumbing and notification-schedule preferences.

## Success Criteria

- [ ] All existing tests + new regressions pass (pytest)
- [ ] Summary and rewards resolve identical targets for every settings combination
- [ ] Unauthenticated/invalid onboarding requests rejected 401/422
- [ ] Wizard completes atomically; re-POST is idempotent
- [ ] Pre-existing accounts see the wizard once on next login
