#!/usr/bin/env bash
# smoke-ui.sh — Browser smoke test for the Weight Loss Tracker SPA.
#
# Drives the real browser UI via playwright-cli (installed globally, skill at
# ~/.claude/skills/playwright-cli). Verifies the full user loop:
#   gate shown unauthenticated -> register a fresh account -> tracker loads
#   -> kg entry + st/lb (unit-toggle) entry -> settings/BMI -> rewards ->
#   logout returns to the gate. The tracker is tabbed, so History/Settings/
#   Progress assertions click their tab first.
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

assert_visibility "tracker visible after signup" "#tracker" "visible"
assert_visibility "auth screen hidden after signup" "#auth-screen" "hidden"
assert_find "summary section visible" "Summary"
assert_find "log-weight form visible" "Log weight"
assert_find "logout button visible" "Log out"

# ---- 3. add a weight entry (kg) --------------------------------------------

echo "-- weight entry"
playwright-cli fill "#entry-date" "$TEST_DATE" >/dev/null 2>&1
playwright-cli fill "#entry-weight" "$TEST_WEIGHT" >/dev/null 2>&1
playwright-cli click "#entry-form button[type=submit]" >/dev/null 2>&1
sleep 1

# The weight history list lives on the History tab; switch to it before
# asserting, then back to Today for the summary assertion.
playwright-cli click "[data-tab=history]" >/dev/null 2>&1
assert_find "history shows the new entry" "$TEST_WEIGHT"
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

playwright-cli click "[data-tab=history]" >/dev/null 2>&1
# The st+lb entry (12 st 4 lb = 172 lb) renders as total pounds in the
# default weight-display mode (lb); "12 st" no longer appears anywhere.
assert_find "history shows the st+lb entry" "172.0 lb"

# ---- 5. settings + BMI -----------------------------------------------------

echo "-- settings"
# The Goal & body form lives on the Settings tab; switch to it before filling.
playwright-cli click "[data-tab=settings]" >/dev/null 2>&1
playwright-cli fill "#height-cm" "175" >/dev/null 2>&1
playwright-cli fill "#target-weight" "70" >/dev/null 2>&1
playwright-cli click "#goal-form button[type=submit]" >/dev/null 2>&1
sleep 1

# Saving settings reloads data and lands back on the Today tab, where the
# summary card renders the BMI.
assert_find "BMI renders after height saved" "BMI 2"

# ---- 5.25 weight-display radio toggle (auto-save, no Save button) -----------

echo "-- weight-display radio toggle"
# The display preference is a radio group that saves itself on change — no
# "Save settings" click. Toggling to st-lb must re-render the History list
# immediately (and persist via the debounced settings PUT).
playwright-cli click "[data-tab=settings]" >/dev/null 2>&1
playwright-cli click 'input[name="weight-display"][value="st-lb"]' >/dev/null 2>&1
sleep 1
playwright-cli click "[data-tab=history]" >/dev/null 2>&1
# The 12 st 4 lb entry (172 lb) renders as stones+pounds once st-lb is chosen;
# "12 st" only appears in this mode, so this proves the toggle took effect
# without any Save click.
assert_find "st-lb display after radio toggle (no Save)" "12 st 4"

# ---- 5.5 progress tab: charts draw on visibility ---------------------------

echo "-- progress tab (charts)"
playwright-cli click "[data-tab=progress]" >/dev/null 2>&1
assert_visibility "progress panel visible" "#tab-progress" "visible"
assert_visibility "today panel hidden on progress tab" "#tab-today" "hidden"

# The canvases have zero width while their panel is hidden; a non-zero
# clientWidth proves each chart was redrawn when Progress became visible.
CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart').clientWidth" 2>&1 | tr -d '"')"
if [ "$CHART_W" = "true" ]; then
  step_ok "weight chart draws on progress tab"
else
  step_fail "weight chart draws on progress tab (clientWidth=$CHART_W)"
fi

EXERCISE_CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart-exercise').clientWidth" 2>&1 | tr -d '"')"
if [ "$EXERCISE_CHART_W" = "true" ]; then
  step_ok "exercise chart draws on progress tab"
else
  step_fail "exercise chart draws on progress tab (clientWidth=$EXERCISE_CHART_W)"
fi

MEALS_CHART_W="$(playwright-cli --raw eval "!!document.querySelector('#chart-meals').clientWidth" 2>&1 | tr -d '"')"
if [ "$MEALS_CHART_W" = "true" ]; then
  step_ok "meals chart draws on progress tab"
else
  step_fail "meals chart draws on progress tab (clientWidth=$MEALS_CHART_W)"
fi

# ---- 6. rewards + screenshot -----------------------------------------------

echo "-- rewards / capture"
# Checkpoints live on the Today tab; switch back before asserting.
playwright-cli click "[data-tab=today]" >/dev/null 2>&1
assert_find "checkpoints section visible" "Checkpoints"
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
