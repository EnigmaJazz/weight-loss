#!/usr/bin/env bash
# smoke-ui.sh — Browser smoke test for the Weight Loss Tracker SPA.
#
# Drives the real browser UI via playwright-cli (installed globally, skill at
# ~/.claude/skills/playwright-cli). Verifies the full user loop:
#   page loads -> weight entry added -> history/summary update -> settings
#   saved -> BMI appears -> rewards render.
#
# NOTE: this writes one test weight entry into the target app's database.
# Point it at a scratch instance (WEIGHT_LOSS_DB tmp) if you don't want that.
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

cleanup() {
  playwright-cli close >/dev/null 2>&1
}
trap cleanup EXIT

# ---- prerequisites ---------------------------------------------------------

command -v playwright-cli >/dev/null || { echo "error: playwright-cli not installed"; exit 1; }
curl -s -o /dev/null "$BASE_URL/" || { echo "error: app not reachable at $BASE_URL (is the service running?)"; exit 1; }

echo "== Weight Loss Tracker UI smoke test"
echo "   target: $BASE_URL  (test entry: $TEST_DATE $TEST_WEIGHT kg)"

# ---- 1. page loads ---------------------------------------------------------

echo "-- page load"
playwright-cli open "$BASE_URL" --browser="$BROWSER" >/dev/null 2>&1 || { echo "error: could not open browser ($BROWSER)"; exit 1; }

TITLE="$(playwright-cli --raw eval 'document.title' 2>&1 | tr -d '"')"
if [ "$TITLE" = "Weight Loss Tracker" ]; then
  step_ok "page title is 'Weight Loss Tracker'"
else
  step_fail "page title is 'Weight Loss Tracker' (got '$TITLE')"
fi
assert_find "summary section visible" "Summary"
assert_find "log-weight form visible" "Log weight"

# ---- 2. add a weight entry -------------------------------------------------

echo "-- weight entry"
playwright-cli fill "#entry-date" "$TEST_DATE" >/dev/null 2>&1
playwright-cli fill "#entry-weight" "$TEST_WEIGHT" >/dev/null 2>&1
playwright-cli click "#entry-form button[type=submit]" >/dev/null 2>&1
sleep 1

assert_find "history shows the new entry" "$TEST_WEIGHT"
assert_find "summary shows a current value (not —)" "Current"

# ---- 3. settings + BMI -----------------------------------------------------

echo "-- settings"
playwright-cli fill "#height-cm" "175" >/dev/null 2>&1
playwright-cli fill "#target-weight" "70" >/dev/null 2>&1
playwright-cli click "#settings-form button[type=submit]" >/dev/null 2>&1
sleep 1

assert_find "BMI renders after height saved" "BMI 2"

# ---- 4. rewards + screenshot ----------------------------------------------

echo "-- rewards / capture"
assert_find "checkpoints section visible" "Checkpoints"
playwright-cli screenshot --filename="smoke-ui.png" >/dev/null 2>&1
[ -f smoke-ui.png ] && step_ok "screenshot saved (smoke-ui.png)" || step_fail "screenshot saved"

# ---- 5. summary ------------------------------------------------------------

echo ""
echo "== Result: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  printf '   failed steps: %s\n' "${FAILED_STEPS[*]}"
  exit 1
fi
echo "   UI smoke test PASSED"
