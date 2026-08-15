/* Frontend check-in (mood + habit quick-log) tests — node:test (stdlib).
 *
 * Imports the REAL static/format.js the SPA uses. The SPA catalogue lives in
 * static/app.js (the HABIT_TYPES literal, pinned to constants.HABIT_TYPES by
 * the test_spa_gate drift guard), so this file parses that literal out of the
 * served app.js text and pins the format.js HABIT_LABELS mirror against it —
 * app.js stays the catalogue location, format.js stays importable by Node.
 *
 * The pure helpers under test are the client-side mood guard (validateMood)
 * and the chip-label lookup (habitLabel): invalid mood values (0, 6, empty,
 * non-integers) must be rejected before any POST reaches /api/mood.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import format from "../../static/format.js";

const { HABIT_LABELS, habitLabel, validateMood } = format;

const appJs = readFileSync(new URL("../../static/app.js", import.meta.url), "utf8");
const literal = /HABIT_TYPES\s*=\s*(\[[^\]]*\])/.exec(appJs);
assert.ok(literal, "app.js must embed the HABIT_TYPES literal");
const appHabitTypes = JSON.parse(literal[1]);

function jsFnBody(source, name) {
  /* Brace-delimited body of the named top-level function in app.js, so scoped
   * assertions never bleed into a later function. Strings/comments opaque. */
  const m = new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\([^)]*\\)`).exec(source);
  assert.ok(m, `app.js must define ${name}()`);
  const braceAt = source.indexOf("{", m.index + m[0].length);
  assert.ok(braceAt !== -1, `${name}() must have a body`);
  let depth = 0;
  let quote = null;
  let i = braceAt;
  while (i < source.length) {
    const c = source[i];
    const nxt = source[i + 1] ?? "";
    if (quote !== null) {
      if (c === "\\") {
        i += 2;
        continue;
      }
      if (c === quote) quote = null;
    } else if (c === "'" || c === '"' || c === "`") {
      quote = c;
    } else if (c === "/" && nxt === "/") {
      const nl = source.indexOf("\n", i);
      if (nl === -1) break;
      i = nl;
    } else if (c === "/" && nxt === "*") {
      const end = source.indexOf("*/", i + 2);
      if (end === -1) break;
      i = end + 2;
      continue;
    } else if (c === "{") {
      depth += 1;
    } else if (c === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(braceAt, i + 1);
    }
    i += 1;
  }
  assert.fail(`unbalanced braces in ${name}()`);
}

const CATALOGUE = ["water", "fruit_veg", "home_cooked", "sleep_routine"];

test("format.js habit label mirror equals the app.js HABIT_TYPES catalogue", () => {
  assert.deepEqual(appHabitTypes, CATALOGUE);
  assert.deepEqual(Object.keys(HABIT_LABELS), CATALOGUE);
});

test("habitLabel returns a human label for every catalogue value", () => {
  for (const type of CATALOGUE) {
    const label = habitLabel(type);
    assert.equal(typeof label, "string");
    assert.ok(label.length > 0, `${type} must have a non-empty label`);
    assert.notEqual(label, type, `${type} label should be human-readable, not the raw value`);
  }
});

test("habitLabel fails loudly on unknown habit types", () => {
  assert.throws(() => habitLabel("sugar_rush"), /Unknown habit type/);
});

test("validateMood accepts exactly the integers 1 through 5", () => {
  for (const mood of [1, 2, 3, 4, 5]) {
    assert.equal(validateMood(mood), true, `${mood} must be valid`);
  }
  // Numeric strings from the data attribute are accepted too.
  assert.equal(validateMood("3"), true);
});

test("validateMood rejects 0, 6, empty, and non-integers (no POST for invalid moods)", () => {
  for (const mood of [0, 6, -1, 7, "", "0", "6", 3.5, "abc", null, undefined]) {
    assert.equal(validateMood(mood), false, `${String(mood)} must be rejected`);
  }
});

/* ---- check-in success hint contract (quicklog fixes) -------------------- */

test("success messages use period punctuation, never an em dash", () => {
  // The hint claims only the log itself (the refresh outcome is surfaced in
  // the quest/XP regions); it must never overclaim a completed refresh.
  assert.ok(
    appJs.includes('"Mood logged."'),
    "mood success copy must be 'Mood logged.'"
  );
  assert.ok(
    appJs.includes('"Habit logged."'),
    "habit success copy must be 'Habit logged.'"
  );
  assert.ok(!appJs.includes("Mood logged. Quests refreshed."), "mood hint must not overclaim the refresh");
  assert.ok(!appJs.includes("Habit logged. Quests refreshed."), "habit hint must not overclaim the refresh");
  assert.ok(!appJs.includes("Mood logged \u2014"), "no em dash in mood success copy");
  assert.ok(!appJs.includes("Habit logged \u2014"), "no em dash in habit success copy");
});

test("success hints use element-scoped timers, never a shared _t", () => {
  const fn = jsFnBody(appJs, "showCheckinSuccess");
  // Regression pin: the pre-fix implementation cached ONE timeout on the
  // function itself, so a second success within 3s cleared the first hint's
  // hide timer and the first message could stay visible forever.
  assert.ok(!fn.includes("_t"), "showCheckinSuccess must not use a shared _t timer");
  assert.ok(/get\(id\)/.test(fn), "timer lookup must be keyed by the target element id");
  assert.ok(/set\(id, setTimeout/.test(fn), "each element must own its own hide timer");
});

test("a new request hides the stale success hint before posting", () => {
  const mood = jsFnBody(appJs, "submitMood");
  assert.ok(
    mood.indexOf('hideCheckinSuccess("mood-success")') < mood.indexOf('fetchJson("/api/mood"'),
    "submitMood must hide the previous success before a new mood POST"
  );
  const habit = jsFnBody(appJs, "logHabit");
  assert.ok(
    habit.indexOf('hideCheckinSuccess("habit-success")') < habit.indexOf('fetchJson("/api/habits"'),
    "logHabit must hide the previous success before a new habit POST"
  );
});
