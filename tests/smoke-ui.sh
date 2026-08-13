#!/usr/bin/env bash
# smoke-ui.sh — Browser smoke test for the Weight Loss Tracker SPA.
#
# Drives the real browser UI via playwright-cli (installed globally, skill at
# ~/.claude/skills/playwright-cli). Verifies the full user loop:
#   gate shown unauthenticated -> register a fresh account -> tracker loads
#   -> kg entry + st/lb (unit-toggle) entry -> me/BMI -> rewards ->
#   today quests card + XP chip -> logout returns to the gate. The tracker is
#   tabbed, so Journey/World/Me assertions click their tab first.
#
# NOTE: this registers a fresh account and writes test weight entries into the
# target app's database. Point it at a scratch instance (WEIGHT_LOSS_DB tmp)
# if you don't want that.
#
# Usage:
#   tests/smoke-ui.sh [BASE_URL]        # default http://localhost:8000
#
# Exit 0 on pass, 1 on any failed assertion.
set -u

BASE_URL="${1:-http://localhost:8000}"
# Browser selection: system Chrome when present (CI runners have it),
# else the bundled Playwright Chromium (local dev machines).
# Override with SMOKE_BROWSER=chromium|chrome|firefox|webkit.
if [ -n "${SMOKE_BROWSER:-}" ]; then
  BROWSER="$SMOKE_BROWSER"
elif command -v google-chrome >/dev/null 2>&1 || [ -x /usr/bin/google-chrome ]; then
  BROWSER=chrome
else
  BROWSER=chromium
fi
TEST_WEIGHT="88.8"
TEST_DATE="$(date +%F)"
ST_DATE="$(date -d "yesterday" +%F 2>/dev/null || date -v-1d +%F)"
# Fresh unique account per run, so reruns against a persistent DB don't 409.
TEST_USER="smoke$(date +%s)"
TEST_PASSWORD="password123"
TEST_EMAIL="${TEST_USER}@example.com"
PASS=0
FAIL=0
declare -a FAILED_STEPS=()

# ---- helpers ---------------------------------------------------------------

step_ok()   { PASS=$((PASS+1)); echo "  ✔ $1"; }
step_fail() { FAIL=$((FAIL+1)); FAILED_STEPS+=("$1"); echo "  ✘ $1"; }

# assert a substring appears in the live page: args = <step name> <needle>
assert_find() {
  local name="$1"; shift
  local needle="$1"; shift
  local out
  out="$(playwright-cli find --regex "/${needle}/i" 2>&1)"
  if printf '%s' "$out" | grep -qi "$needle"; then
    step_ok "$name"
  else
    step_fail "$name"
    echo "      (find '$needle' produced: ${out:0:200})"
  fi
}

# assert an element's hidden state: args = <step name> <selector> visible|hidden
assert_visibility() {
  local name="$1"; shift
  local selector="$1"; shift
  local expect="$1"; shift
  local raw
  raw="$(playwright-cli --raw eval "!document.querySelector('$selector').hidden" 2>&1 | tr -d '"')"
  if [ "$raw" = "true" ] && [ "$expect" = "visible" ]; then
    step_ok "$name"
  elif [ "$raw" = "false" ] && [ "$expect" = "hidden" ]; then
    step_ok "$name"
  else
    step_fail "$name (expected $expect, got hidden=$raw)"
  fi
}

cleanup() {
  playwright-cli close >/dev/null 2>&1
}
trap cleanup EXIT

# ---- prerequisites ---------------------------------------------------------

command -v playwright-cli >/dev/null || { echo "error: playwright-cli not installed"; exit 1; }
curl -s -o /dev/null "$BASE_URL/" || { echo "error: app not reachable at $BASE_URL (is the service running?)"; exit 1; }

echo "== Weight Loss Tracker UI smoke test"
echo "   target: $BASE_URL  (user: $TEST_USER, entry: $TEST_DATE $TEST_WEIGHT kg)"

# ---- 1. page loads: gate first ---------------------------------------------

echo "-- page load (unauthenticated gate)"
playwright-cli open "$BASE_URL" --browser="$BROWSER" >/dev/null 2>&1 || { echo "error: could not open browser ($BROWSER)"; exit 1; }

TITLE="$(playwright-cli --raw eval 'document.title' 2>&1 | tr -d '"')"
if [ "$TITLE" = "Weight Loss Tracker" ]; then
  step_ok "page title is 'Weight Loss Tracker'"
else
  step_fail "page title is 'Weight Loss Tracker' (got '$TITLE')"
fi
# game-appearance: the fox mascot must render visibly in the header lockup
# (visual selector only — no text pin).
MASCOT_VIS="$(playwright-cli --raw eval "!!document.querySelector('.header-row .mascot') && document.querySelector('.header-row .mascot').offsetParent !== null" 2>&1 | tr -d '"')"
if [ "$MASCOT_VIS" = "true" ]; then
  step_ok "fox mascot visible in header"
else
  step_fail "fox mascot visible in header (got '$MASCOT_VIS')"
fi
assert_find "auth form visible" "Username"
assert_find "password field visible" "Password"
assert_visibility "tracker hidden on load" "#tracker" "hidden"
assert_visibility "auth screen shown on load" "#auth-screen" "visible"

# ---- 2. register a fresh account -------------------------------------------

echo "-- signup"
playwright-cli click "#auth-toggle" >/dev/null 2>&1
playwright-cli fill "#auth-username" "$TEST_USER" >/dev/null 2>&1
# registration requires an email; the field is only visible in signup mode
playwright-cli fill "#auth-email" "$TEST_EMAIL" >/dev/null 2>&1
playwright-cli fill "#auth-password" "$TEST_PASSWORD" >/dev/null 2>&1
playwright-cli click "#auth-form button[type=submit]" >/dev/null 2>&1
sleep 1

# A fresh account has no onboarding_complete row, so the SPA must land in the
# wizard (the gate test pins this branch), NOT the tracker.
assert_visibility "wizard visible after signup" "#onboarding-screen" "visible"
assert_visibility "tracker hidden while wizard shows" "#tracker" "hidden"
assert_visibility "auth screen hidden after signup" "#auth-screen" "hidden"
assert_find "wizard heading visible" "set up your tracker"

# ---- 2.5 complete the onboarding wizard -------------------------------------

echo "-- onboarding wizard"
# step 1: height (cm default) -> step 2: current weight -> step 3: target
# (weight mode default) -> step 4: goals & lifestyle (all optional, defaults
# pass through untouched) -> step 5: units (defaults) -> step 6:
# notifications (defaults) -> finish. The wizard's weight entry is today's
# first entry, so section 3's identical kg entry becomes an idempotent upsert.
playwright-cli fill "#ob-height-cm" "175" >/dev/null 2>&1
playwright-cli click "#wizard-step-height [data-action=next]" >/dev/null 2>&1
playwright-cli fill "#ob-weight-kg" "$TEST_WEIGHT" >/dev/null 2>&1
playwright-cli click "#wizard-step-weight [data-action=next]" >/dev/null 2>&1
playwright-cli fill "#ob-target-weight" "70" >/dev/null 2>&1
playwright-cli click "#wizard-step-target [data-action=next]" >/dev/null 2>&1
# The goals & lifestyle step must actually be the NEXT step (spec: between
# target and units) — assert its visibility in the real browser, then click
# through and confirm units follows.
assert_visibility "goals-lifestyle step shown after target" "#wizard-step-goals-lifestyle" "visible"
playwright-cli click "#wizard-step-goals-lifestyle [data-action=next]" >/dev/null 2>&1
assert_visibility "units step shown after goals-lifestyle" "#wizard-step-units" "visible"
playwright-cli click "#wizard-step-units [data-action=next]" >/dev/null 2>&1
playwright-cli click "#wizard-step-notifications [data-action=finish]" >/dev/null 2>&1
sleep 1

assert_visibility "tracker visible after wizard" "#tracker" "visible"
assert_visibility "wizard hidden after completion" "#onboarding-screen" "hidden"
# game-appearance: once streaks render, every tile carries a flame (visual
# selector only — no text pin).
FLAME_COUNT="$(playwright-cli --raw eval "document.querySelectorAll('.flame').length" 2>&1 | tr -d '"')"
if [ "$FLAME_COUNT" -gt 0 ] 2>/dev/null; then
  step_ok "streak tiles render flames ($FLAME_COUNT)"
else
  step_fail "streak tiles render flames (count='$FLAME_COUNT')"
fi
# goals-dashboard S2: the hero goal ring must render on the Today tab with an
# arc — a non-zero stroke-dashoffset means less than a full ring (a fresh
# account has 0% progress, dashoffset = C; the null empty state also renders
# no arc). Selector-only, no text pins.
RING_ARC="$(playwright-cli --raw eval "(() => { const p = document.querySelector('#goal-ring .goal-ring-progress'); return String(!!p && parseFloat(p.getAttribute('stroke-dashoffset')) > 0); })()" 2>&1 | tr -d '"')"
if [ "$RING_ARC" = "true" ]; then
  step_ok "goal ring renders with an arc on Today"
else
  step_fail "goal ring renders with an arc on Today (got '$RING_ARC')"
fi
assert_find "summary section visible" "Summary"
assert_find "log-weight form visible" "Log weight"
assert_find "logout button visible" "Log out"

# ---- 3. add a weight entry (kg) --------------------------------------------

echo "-- weight entry"
playwright-cli fill "#entry-date" "$TEST_DATE" >/dev/null 2>&1
playwright-cli fill "#entry-weight" "$TEST_WEIGHT" >/dev/null 2>&1
playwright-cli click "#entry-form button[type=submit]" >/dev/null 2>&1
sleep 1

# The weight history list lives on the Journey tab (the longitudinal view);
# switch to it before asserting, then back to Today for the summary assertion.
playwright-cli click "[data-tab=journey]" >/dev/null 2>&1
assert_find "journey shows the new weight entry" "$TEST_WEIGHT"
playwright-cli click "[data-tab=today]" >/dev/null 2>&1
assert_find "summary shows a current value (not —)" "Current"

# ---- 4. unit-input toggle (st + lb) still works after login ----------------

echo "-- unit-input toggle (st + lb)"
playwright-cli click 'input[name="weight-unit"][value="st-lb"]' >/dev/null 2>&1
playwright-cli fill "#entry-date" "$ST_DATE" >/dev/null 2>&1
playwright-cli fill "#entry-stone" "12" >/dev/null 2>&1
playwright-cli fill "#entry-lb" "4" >/dev/null 2>&1
playwright-cli click "#entry-form button[type=submit]" >/dev/null 2>&1
sleep 1

playwright-cli click "[data-tab=journey]" >/dev/null 2>&1
# The st+lb entry (12 st 4 lb = 172 lb) renders as total pounds in the
# default weight-display mode (lb); "12 st" no longer appears anywhere.
assert_find "journey shows the st+lb entry" "172.0 lb"

# ---- 5. settings + BMI -----------------------------------------------------

echo "-- me (settings)"
# The Goal & body form lives on the Me tab (the old Settings panel); switch to
# it before filling.
playwright-cli click "[data-tab=me]" >/dev/null 2>&1
playwright-cli fill "#height-cm" "175" >/dev/null 2>&1
playwright-cli fill "#target-weight" "70" >/dev/null 2>&1
playwright-cli click "#goal-form button[type=submit]" >/dev/null 2>&1
sleep 1

# Saving settings reloads data and lands back on the Today tab, where the
# summary card renders the BMI.
assert_find "BMI renders after height saved" "BMI 2"

# ---- 5.1 goals & lifestyle settings card (S5b) ----------------------------
# The wizard completed with all four goals/lifestyle fields untouched, so the
# Me card must prefill the empty state; then a select save round-trips through
# PUT /api/settings and back into the re-rendered card (loadData re-renders
# settings, and any reload lands on Today — the values are read from the DOM
# regardless of the active tab).
echo "-- goals & lifestyle settings card"
playwright-cli click "[data-tab=me]" >/dev/null 2>&1
GOAL_EMPTY="$(playwright-cli --raw eval "document.querySelector('#primary-goal').value" 2>&1 | tr -d '"')"
if [ "$GOAL_EMPTY" = "" ]; then
  step_ok "goals card prefills empty primary goal after wizard"
else
  step_fail "goals card prefills empty primary goal after wizard (got '$GOAL_EMPTY')"
fi
playwright-cli --raw eval "document.querySelector('#primary-goal').value = 'weight_loss'" >/dev/null 2>&1
playwright-cli --raw eval "document.querySelector('#activity-level').value = 'moderate'" >/dev/null 2>&1
playwright-cli click "#goals-lifestyle-settings-form button[type=submit]" >/dev/null 2>&1
sleep 1
GOAL_AFTER="$(playwright-cli --raw eval "document.querySelector('#primary-goal').value" 2>&1 | tr -d '"')"
LEVEL_AFTER="$(playwright-cli --raw eval "document.querySelector('#activity-level').value" 2>&1 | tr -d '"')"
if [ "$GOAL_AFTER" = "weight_loss" ] && [ "$LEVEL_AFTER" = "moderate" ]; then
  step_ok "goals card save round-trips primary_goal + activity_level"
else
  step_fail "goals card save round-trips primary_goal + activity_level (goal='$GOAL_AFTER', level='$LEVEL_AFTER')"
fi

# ---- 5.15 today quests card + XP chip (r1-quests-xp S4a) ------------------
# The quests card and XP chip render on the Today tab after login. The
# wizard's weight entry auto-completes any assigned streak_alive quest with
# source 'detected' (so done rows must read Auto-completed), and the chip
# shows the derived Level-1 XP state (a fresh account is always below 100 XP:
# at most log_weight 20 + streak_alive 20). Mutation order is chosen so every
# step only needs the one open row that is always guaranteed (mood_checkin is
# assigned daily and never auto-completes without a mood entry): surface,
# replace -> replace-cap 409 -> complete.
echo "-- today quests + XP chip"
playwright-cli click "[data-tab=today]" >/dev/null 2>&1
sleep 1

QUEST_ROWS="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row').length" 2>&1 | tr -d '"')"
if [ "$QUEST_ROWS" = "3" ]; then
  step_ok "quests card renders exactly 3 rows ($QUEST_ROWS)"
else
  step_fail "quests card renders exactly 3 rows (count='$QUEST_ROWS')"
fi

OPEN_ROWS="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row[data-status=\"open\"]').length" 2>&1 | tr -d '"')"
if [ "$OPEN_ROWS" -ge 1 ] 2>/dev/null; then
  step_ok "at least one open quest row renders ($OPEN_ROWS)"
else
  step_fail "at least one open quest row renders (count='$OPEN_ROWS')"
fi

# Every open row offers exactly Complete/Skip/Replace; terminal rows none.
OPEN_ACTIONS="$(playwright-cli --raw eval "(() => { let ok = true; for (const row of document.querySelectorAll('#quests-card .quest-row[data-status=\"open\"]')) { const a = [...row.querySelectorAll('.quest-action')].map(b => b.dataset.action).sort().join(','); if (a !== 'complete,replace,skip') ok = false; } return String(ok); })()" 2>&1 | tr -d '"')"
if [ "$OPEN_ACTIONS" = "true" ]; then
  step_ok "open quest rows offer Complete/Skip/Replace"
else
  step_fail "open quest rows offer Complete/Skip/Replace (got '$OPEN_ACTIONS')"
fi

TERMINAL_ACTIONS="$(playwright-cli --raw eval "(() => { let n = 0; for (const row of document.querySelectorAll('#quests-card .quest-row[data-status=\"done\"], #quests-card .quest-row[data-status=\"skipped\"]')) n += row.querySelectorAll('.quest-action').length; return String(n); })()" 2>&1 | tr -d '"')"
if [ "$TERMINAL_ACTIONS" = "0" ]; then
  step_ok "terminal quest rows expose no action controls"
else
  step_fail "terminal quest rows expose no action controls (count='$TERMINAL_ACTIONS')"
fi

# Detected completion must display as auto-completed (vacuous when no done
# row exists that day: every() over an empty list is true).
AUTO_COMPLETED="$(playwright-cli --raw eval "(() => { const rows = [...document.querySelectorAll('#quests-card .quest-row[data-status=\"done\"]')]; return String(rows.every(r => r.querySelector('.quest-status')?.textContent === 'Auto-completed')); })()" 2>&1 | tr -d '"')"
if [ "$AUTO_COMPLETED" = "true" ]; then
  step_ok "detected-done rows read as Auto-completed"
else
  step_fail "detected-done rows read as Auto-completed (got '$AUTO_COMPLETED')"
fi

# XP chip: title, level, total, and progress toward the next level.
CHIP_LEVEL="$(playwright-cli --raw eval "document.querySelector('.xp-chip-level')?.textContent" 2>&1 | tr -d '"')"
if [ "$CHIP_LEVEL" = "Level 1" ]; then
  step_ok "XP chip shows Level 1"
else
  step_fail "XP chip shows Level 1 (got '$CHIP_LEVEL')"
fi
CHIP_TITLE="$(playwright-cli --raw eval "document.querySelector('.xp-chip-title')?.textContent" 2>&1 | tr -d '"')"
if [ "$CHIP_TITLE" = "Sprout" ]; then
  step_ok "XP chip shows Sprout title"
else
  step_fail "XP chip shows Sprout title (got '$CHIP_TITLE')"
fi
CHIP_TOTAL="$(playwright-cli --raw eval "document.querySelector('.xp-chip-total')?.textContent" 2>&1 | tr -d '"')"
if printf '%s' "$CHIP_TOTAL" | grep -Eq '^[0-9]+ XP$'; then
  step_ok "XP chip shows a total ($CHIP_TOTAL)"
else
  step_fail "XP chip shows a total (got '$CHIP_TOTAL')"
fi
CHIP_PROGRESS="$(playwright-cli --raw eval "document.querySelector('.xp-chip-progress .progress-label')?.textContent" 2>&1 | tr -d '"')"
if printf '%s' "$CHIP_PROGRESS" | grep -Eq 'XP to level 2$'; then
  step_ok "XP chip shows progress to level 2 ($CHIP_PROGRESS)"
else
  step_fail "XP chip shows progress to level 2 (got '$CHIP_PROGRESS')"
fi

# ---- 5.16 quest actions: replace -> 409 -> complete (r1-quests-xp S4a) -----
# Replace an open quest (one replacement per day): the replaced row disappears
# and a fresh open row takes its place (still 3 current rows). A second
# Replace must 409: accessible error feedback appears and the assignment is
# unchanged. Then Complete must refresh the row to done (open count drops by
# one) and raise the chip total by the quest's XP.
echo "-- quest actions"
REPLACED_IDS="$(playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('#quests-card .quest-row')].map(r => r.dataset.questId).sort())" 2>&1 | tr -d '"')"
playwright-cli --raw eval "document.querySelector('#quests-card .quest-row[data-status=\"open\"] [data-action=\"replace\"]').click()" >/dev/null 2>&1
sleep 1
ROWS_AFTER_REPLACE="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row').length" 2>&1 | tr -d '"')"
AFTER_IDS="$(playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('#quests-card .quest-row')].map(r => r.dataset.questId).sort())" 2>&1 | tr -d '"')"
if [ "$ROWS_AFTER_REPLACE" = "3" ] && [ "$AFTER_IDS" != "$REPLACED_IDS" ]; then
  step_ok "replace swaps in a fresh quest (still 3 rows)"
else
  step_fail "replace swaps in a fresh quest (rows='$ROWS_AFTER_REPLACE', ids changed=$([ "$AFTER_IDS" != "$REPLACED_IDS" ] && echo yes || echo no))"
fi
ERROR_HIDDEN_AFTER_REPLACE="$(playwright-cli --raw eval "document.querySelector('#quests-error').hidden" 2>&1 | tr -d '"')"
if [ "$ERROR_HIDDEN_AFTER_REPLACE" = "true" ]; then
  step_ok "successful replace leaves the error region hidden"
else
  step_fail "successful replace leaves the error region hidden (hidden='$ERROR_HIDDEN_AFTER_REPLACE')"
fi

PRE_409_IDS="$(playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('#quests-card .quest-row')].map(r => r.dataset.questId).sort())" 2>&1 | tr -d '"')"
playwright-cli --raw eval "document.querySelector('#quests-card .quest-row[data-status=\"open\"] [data-action=\"replace\"]').click()" >/dev/null 2>&1
sleep 1
ERROR_VISIBLE="$(playwright-cli --raw eval "!document.querySelector('#quests-error').hidden" 2>&1 | tr -d '"')"
POST_409_IDS="$(playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('#quests-card .quest-row')].map(r => r.dataset.questId).sort())" 2>&1 | tr -d '"')"
ROWS_AFTER_409="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row').length" 2>&1 | tr -d '"')"
if [ "$ERROR_VISIBLE" = "true" ] && [ "$POST_409_IDS" = "$PRE_409_IDS" ] && [ "$ROWS_AFTER_409" = "3" ]; then
  step_ok "replacement cap 409 shows error and keeps the assignment"
else
  step_fail "replacement cap 409 shows error and keeps the assignment (error='$ERROR_VISIBLE', rows='$ROWS_AFTER_409', ids same=$([ "$POST_409_IDS" = "$PRE_409_IDS" ] && echo yes || echo no))"
fi

OPEN_BEFORE_COMPLETE="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row[data-status=\"open\"]').length" 2>&1 | tr -d '"')"
ROW_XP="$(playwright-cli --raw eval "Number(document.querySelector('#quests-card .quest-row[data-status=\"open\"] .quest-xp').textContent.replace(/[^0-9]/g, ''))" 2>&1 | tr -d '"')"
CHIP_BEFORE="$(playwright-cli --raw eval "Number(document.querySelector('.xp-chip-total').textContent.replace(/[^0-9]/g, ''))" 2>&1 | tr -d '"')"
playwright-cli --raw eval "document.querySelector('#quests-card .quest-row[data-status=\"open\"] [data-action=\"complete\"]').click()" >/dev/null 2>&1
sleep 1
OPEN_AFTER_COMPLETE="$(playwright-cli --raw eval "document.querySelectorAll('#quests-card .quest-row[data-status=\"open\"]').length" 2>&1 | tr -d '"')"
CHIP_AFTER="$(playwright-cli --raw eval "Number(document.querySelector('.xp-chip-total').textContent.replace(/[^0-9]/g, ''))" 2>&1 | tr -d '"')"
EXPECTED_CHIP=$((CHIP_BEFORE + ROW_XP))
if [ "$OPEN_AFTER_COMPLETE" = "$((OPEN_BEFORE_COMPLETE - 1))" ] && [ "$CHIP_AFTER" = "$EXPECTED_CHIP" ]; then
  step_ok "complete refreshes the row to done and adds XP to the chip ($CHIP_AFTER)"
else
  step_fail "complete refreshes the row to done and adds XP to the chip (open $OPEN_BEFORE_COMPLETE -> $OPEN_AFTER_COMPLETE, chip $CHIP_BEFORE + $ROW_XP = $EXPECTED_CHIP, got $CHIP_AFTER)"
fi

# ---- 5.17 journey progress cards: XP / momentum / quest history (S4b) ----

# The three progression cards render on the Journey tab: #xp-card (level,
# title, total, progress), #momentum-card (today tier + successful/21), and
# #quest-history-card (date, label, status, awarded XP; non-done = 0; explicit
# empty state). The smoke account has completed one quest on the Today tab,
# so XP > 0 and the history card shows its empty state (no past-day rows).
echo "-- journey progress cards"
playwright-cli click "[data-tab=journey]" >/dev/null 2>&1
assert_visibility "journey panel visible for progress cards" "#tab-journey" "visible"

XP_CARD_TITLE="$(playwright-cli --raw eval "document.querySelector('#xp-card .journey-xp-title')?.textContent.trim()" 2>&1 | tr -d '"')"
if [ -n "$XP_CARD_TITLE" ]; then
  step_ok "xp card renders the level title ($XP_CARD_TITLE)"
else
  step_fail "xp card renders the level title (got '$XP_CARD_TITLE')"
fi

XP_CARD_LEVEL="$(playwright-cli --raw eval "document.querySelector('#xp-card .journey-xp-level')?.textContent.trim()" 2>&1 | tr -d '"')"
case "$XP_CARD_LEVEL" in
  "Level "*) step_ok "xp card shows level and total ($XP_CARD_LEVEL)" ;;
  *) step_fail "xp card shows level and total (got '$XP_CARD_LEVEL')" ;;
esac

MOMENTUM_TIER="$(playwright-cli --raw eval "document.querySelector('#momentum-card .momentum-tier')?.textContent.trim()" 2>&1 | tr -d '"')"
if [ -n "$MOMENTUM_TIER" ]; then
  step_ok "momentum card renders today's tier ($MOMENTUM_TIER)"
else
  step_fail "momentum card renders today's tier (got '$MOMENTUM_TIER')"
fi

MOMENTUM_COUNT="$(playwright-cli --raw eval "document.querySelector('#momentum-card .momentum-count')?.textContent.trim()" 2>&1 | tr -d '"')"
case "$MOMENTUM_COUNT" in
  *"in the last 21"*) step_ok "momentum card shows successful days out of 21 ($MOMENTUM_COUNT)" ;;
  *) step_fail "momentum card shows successful days out of 21 (got '$MOMENTUM_COUNT')" ;;
esac

# Quest history: the smoke account has completed a quest today but has no
# past-day rows, so the explicit empty state must render (XP/momentum above
# stay visible — the empty state never hides the other cards).
HISTORY_ROWS="$(playwright-cli --raw eval "document.querySelectorAll('#quest-history-card .quest-history-row').length" 2>&1 | tr -d '"')"
HISTORY_EMPTY="$(playwright-cli --raw eval "document.querySelector('#quest-history-card .hint')?.textContent.trim()" 2>&1 | tr -d '"')"
if [ "$HISTORY_ROWS" = "0" ] && [ -n "$HISTORY_EMPTY" ]; then
  step_ok "quest history renders the explicit empty state ($HISTORY_EMPTY)"
else
  step_fail "quest history renders the explicit empty state (rows='$HISTORY_ROWS', empty='$HISTORY_EMPTY')"
fi

# Achievements card (r2-achievements S3): renders all six catalogue rows
# (earned with an unlock date or locked with no partial progress) and sits
# immediately after momentum. The smoke account has exactly one earned
# achievement at this point — Getting Started from the streak_alive quest the
# wizard weight entry auto-completed — so five stay locked.
ACH_CARD_ORDER="$(playwright-cli --raw eval "(() => { const sections = [...document.querySelectorAll('#tab-journey section')]; const idx = ['momentum-card','achievements-card','quest-history-card'].map(id => sections.findIndex(s => s.id === id)); return String(idx[0] !== -1 && idx[0] < idx[1] && idx[1] < idx[2]); })()" 2>&1 | tr -d '"')"
if [ "$ACH_CARD_ORDER" = "true" ]; then
  step_ok "achievements card renders after momentum, before quest history"
else
  step_fail "achievements card renders after momentum, before quest history (got '$ACH_CARD_ORDER')"
fi

ACH_ROWS="$(playwright-cli --raw eval "document.querySelectorAll('#achievements-card .achievement-row').length" 2>&1 | tr -d '"')"
if [ "$ACH_ROWS" = "6" ]; then
  step_ok "achievements card renders all six catalogue rows ($ACH_ROWS)"
else
  step_fail "achievements card renders all six catalogue rows (count='$ACH_ROWS')"
fi

ACH_EARNED="$(playwright-cli --raw eval "document.querySelectorAll('#achievements-card .achievement-row[data-state=\"earned\"]').length" 2>&1 | tr -d '"')"
if [ "$ACH_EARNED" = "1" ]; then
  step_ok "achievements card shows exactly one earned row ($ACH_EARNED)"
else
  step_fail "achievements card shows exactly one earned row (count='$ACH_EARNED')"
fi

ACH_LOCKED="$(playwright-cli --raw eval "document.querySelectorAll('#achievements-card .achievement-row[data-state=\"locked\"]').length" 2>&1 | tr -d '"')"
if [ "$ACH_LOCKED" = "5" ]; then
  step_ok "achievements card shows five locked rows ($ACH_LOCKED)"
else
  step_fail "achievements card shows five locked rows (count='$ACH_LOCKED')"
fi

ACH_EARNED_STATE="$(playwright-cli --raw eval "document.querySelector('#achievements-card .achievement-row[data-state=\"earned\"] .achievement-state')?.textContent.trim()" 2>&1 | tr -d '"')"
case "$ACH_EARNED_STATE" in
  "Unlocked "*) step_ok "earned row shows an unlock date ($ACH_EARNED_STATE)" ;;
  *) step_fail "earned row shows an unlock date (got '$ACH_EARNED_STATE')" ;;
esac

ACH_PROGRESS="$(playwright-cli --raw eval "document.querySelectorAll('#achievements-card .achievement-progress').length" 2>&1 | tr -d '"')"
if [ "$ACH_PROGRESS" = "0" ]; then
  step_ok "achievements card shows no partial progress"
else
  step_fail "achievements card shows no partial progress (count='$ACH_PROGRESS')"
fi

# ---- 5.25 weight-display radio toggle (auto-save, no Save button) -----------

echo "-- weight-display radio toggle"
# The display preference is a radio group that saves itself on change — no
# "Save settings" click. Toggling to st-lb must re-render the Journey history
# list immediately (and persist via the debounced settings PUT).
playwright-cli click "[data-tab=me]" >/dev/null 2>&1
playwright-cli click 'input[name="weight-display"][value="st-lb"]' >/dev/null 2>&1
sleep 1
playwright-cli click "[data-tab=journey]" >/dev/null 2>&1
# The 12 st 4 lb entry (172 lb) renders as stones+pounds once st-lb is chosen;
# "12 st" only appears in this mode, so this proves the toggle took effect
# without any Save click.
assert_find "st-lb display after radio toggle (no Save)" "12 st 4"

# ---- 5.5 journey tab: charts draw on visibility ---------------------------

echo "-- journey tab (charts)"
playwright-cli click "[data-tab=journey]" >/dev/null 2>&1
assert_visibility "journey panel visible" "#tab-journey" "visible"
assert_visibility "today panel hidden on journey tab" "#tab-today" "hidden"

# The canvases have zero width while their panel is hidden; a non-zero
# clientWidth proves each chart was redrawn when Journey became visible.
CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart').clientWidth" 2>&1 | tr -d '"')"
if [ "$CHART_W" = "true" ]; then
  step_ok "weight chart draws on journey tab"
else
  step_fail "weight chart draws on journey tab (clientWidth=$CHART_W)"
fi

EXERCISE_CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart-exercise').clientWidth" 2>&1 | tr -d '"')"
if [ "$EXERCISE_CHART_W" = "true" ]; then
  step_ok "exercise chart draws on journey tab"
else
  step_fail "exercise chart draws on journey tab (clientWidth=$EXERCISE_CHART_W)"
fi

MEALS_CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart-meals').clientWidth" 2>&1 | tr -d '"')"
if [ "$MEALS_CHART_W" = "true" ]; then
  step_ok "meals chart draws on journey tab"
else
  step_fail "meals chart draws on journey tab (clientWidth=$MEALS_CHART_W)"
fi

# ---- 5.6 world tab: XP island visible, placeholder gone ---------------------

echo "-- world tab (island)"
playwright-cli click "[data-tab=world]" >/dev/null 2>&1
# Static island (Slice 2): the inline SVG renders visibly and the old
# coming-soon placeholder copy is gone. Live stage labels/progress are
# Slice 3's pins, not asserted here.
# NB: SVG elements expose no offsetWidth/clientWidth (HTMLElement-only), so
# measure via getBoundingClientRect.
ISLAND_VIS="$(playwright-cli --raw eval "!!document.querySelector('#world-island') && document.querySelector('#world-island').getBoundingClientRect().width > 0" 2>&1 | tr -d '"')"
if [ "$ISLAND_VIS" = "true" ]; then
  step_ok "world island svg visible"
else
  step_fail "world island svg visible (got '$ISLAND_VIS')"
fi
PLACEHOLDER_GONE="$(playwright-cli --raw eval "!document.body.textContent.includes('Your adventure map is coming soon.')" 2>&1 | tr -d '"')"
if [ "$PLACEHOLDER_GONE" = "true" ]; then
  step_ok "world placeholder copy absent"
else
  step_fail "world placeholder copy absent (got '$PLACEHOLDER_GONE')"
fi

# ---- 5.75 theme toggle + Appearance radio (selector-only, no text pins) ----

echo "-- theme toggle"
# The header toggle is always visible (design D3). The theme pref defaults to
# "system", which in the headless browser resolves to light — so first pin the
# pref to Light via the Settings Appearance radio (deterministic), then the
# toggle cycle system->light->dark->system gives exactly: dark, then back to
# the system-resolved theme. All assertions are selector-only.
playwright-cli click "[data-tab=me]" >/dev/null 2>&1
playwright-cli click 'input[name="appearance"][value="light"]' >/dev/null 2>&1
sleep 1
RADIO_THEME="$(playwright-cli --raw eval 'document.documentElement.dataset.theme' 2>&1 | tr -d '"')"
if [ "$RADIO_THEME" = "light" ]; then
  step_ok "Appearance radio (light) applies data-theme=light"
else
  step_fail "Appearance radio (light) applies data-theme=light (got '$RADIO_THEME')"
fi
playwright-cli click "#theme-toggle" >/dev/null 2>&1
sleep 1
TOGGLE_THEME="$(playwright-cli --raw eval 'document.documentElement.dataset.theme' 2>&1 | tr -d '"')"
if [ "$TOGGLE_THEME" = "dark" ]; then
  step_ok "theme toggle flips data-theme to dark"
else
  step_fail "theme toggle flips data-theme to dark (got '$TOGGLE_THEME')"
fi
# Second click: dark -> system, which must resolve to the OS scheme the
# browser reports (live system-follow without reload, design D5).
playwright-cli click "#theme-toggle" >/dev/null 2>&1
sleep 1
SYSTEM_RESOLVED="$(playwright-cli --raw eval "matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'" 2>&1 | tr -d '"')"
TOGGLE_BACK="$(playwright-cli --raw eval 'document.documentElement.dataset.theme' 2>&1 | tr -d '"')"
if [ "$TOGGLE_BACK" = "$SYSTEM_RESOLVED" ]; then
  step_ok "theme toggle returns to system-resolved theme ($SYSTEM_RESOLVED)"
else
  step_fail "theme toggle returns to system-resolved theme (got '$TOGGLE_BACK', system '$SYSTEM_RESOLVED')"
fi

# ---- 6. rewards + screenshot -----------------------------------------------

echo "-- rewards / capture"
# Checkpoints live on the Today tab; switch back before asserting.
playwright-cli click "[data-tab=today]" >/dev/null 2>&1
assert_find "checkpoints section visible" "Checkpoints"
# milestone strip (UI refinement): achieved milestones render as one-line dots;
# pending ones are hidden; the next milestone is text-only. At this point the
# smoke account (wizard 88.8 kg + 12 st 4 lb yesterday) has 0 earned checkpoints
# (current 88.8 > baseline 78.0), so the EMPTY state shows only the .milestone-next
# line — no dots, no strip container. Text pin: prefix match, never the exact
# parenthetical (display-unit dependent).
MILESTONE_DOTS="$(playwright-cli --raw eval "document.querySelectorAll('.milestone-dot').length" 2>&1 | tr -d '"')"
if [ "$MILESTONE_DOTS" = "0" ]; then
  step_ok "milestone strip empty state: no earned dots ($MILESTONE_DOTS)"
else
  step_fail "milestone strip empty state: no earned dots (count='$MILESTONE_DOTS')"
fi
MILESTONE_STRIP_PRESENT="$(playwright-cli --raw eval "!!document.querySelector('#milestone-strip')" 2>&1 | tr -d '"')"
if [ "$MILESTONE_STRIP_PRESENT" = "false" ]; then
  step_ok "milestone strip container absent in empty state"
else
  step_fail "milestone strip container absent in empty state (got '$MILESTONE_STRIP_PRESENT')"
fi
MILESTONE_NEXT="$(playwright-cli --raw eval "document.querySelector('.milestone-next')?.textContent.trim()" 2>&1 | tr -d '"')"
case "$MILESTONE_NEXT" in
  "Next: 10%"*) step_ok "milestone-next names the next checkpoint ($MILESTONE_NEXT)" ;;
  *) step_fail "milestone-next names the next checkpoint (got '$MILESTONE_NEXT')" ;;
esac
playwright-cli screenshot --filename="smoke-ui.png" >/dev/null 2>&1
[ -f smoke-ui.png ] && step_ok "screenshot saved (smoke-ui.png)" || step_fail "screenshot saved"

# ---- 7. logout returns to the gate -----------------------------------------

echo "-- logout"
playwright-cli click "#logout-btn" >/dev/null 2>&1
sleep 1

assert_visibility "tracker hidden after logout" "#tracker" "hidden"
assert_visibility "auth screen shown after logout" "#auth-screen" "visible"
assert_find "auth screen shows login again" "Log in"

echo ""
echo "== Result: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  printf '   failed steps: %s\n' "${FAILED_STEPS[*]}"
  exit 1
fi
echo "   UI smoke test PASSED"
