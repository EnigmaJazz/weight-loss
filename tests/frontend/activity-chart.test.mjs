/* Frontend activity aggregation tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the weekly
 * exercise-minutes and daily-calories aggregation that feed the Progress-tab
 * charts. Both helpers are pure: deterministic, no Date.now(), never mutate. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { exerciseMinutesPerWeek, caloriesPerDay } = format;

// Fixed calendar facts (2026): 2026-08-03 is a Monday, 2026-08-09 is the
// Sunday of that same ISO week, and 2026-08-10 is the following Monday.
const MONDAY = "2026-08-03";
const SUNDAY = "2026-08-09";
const NEXT_MONDAY = "2026-08-10";

test("exerciseMinutesPerWeek: empty input -> []", () => {
  assert.deepEqual(exerciseMinutesPerWeek([]), []);
});

test("exerciseMinutesPerWeek: single entry -> one week bucket", () => {
  const out = exerciseMinutesPerWeek([{ date: MONDAY, duration_min: 30 }]);
  assert.deepEqual(out, [{ weekStart: MONDAY, minutes: 30 }]);
});

test("exerciseMinutesPerWeek: entries across one Monday..Sunday sum into one bucket", () => {
  const out = exerciseMinutesPerWeek([
    { date: MONDAY, duration_min: 20 },
    { date: SUNDAY, duration_min: 30 },
  ]);
  assert.deepEqual(out, [{ weekStart: MONDAY, minutes: 50 }]);
});

test("exerciseMinutesPerWeek: a Sunday and the following Monday are different ISO weeks", () => {
  const out = exerciseMinutesPerWeek([
    { date: SUNDAY, duration_min: 10 },
    { date: NEXT_MONDAY, duration_min: 10 },
  ]);
  assert.deepEqual(out, [
    { weekStart: MONDAY, minutes: 10 },
    { weekStart: NEXT_MONDAY, minutes: 10 },
  ]);
});

test("exerciseMinutesPerWeek: same-date entries with different times group together", () => {
  const out = exerciseMinutesPerWeek([
    { date: MONDAY, time: "09:00", duration_min: 30 },
    { date: MONDAY, time: "18:30", duration_min: 25 },
  ]);
  assert.deepEqual(out, [{ weekStart: MONDAY, minutes: 55 }]);
});

test("exerciseMinutesPerWeek: out-of-order input returns oldest -> newest", () => {
  const out = exerciseMinutesPerWeek([
    { date: NEXT_MONDAY, duration_min: 40 },
    { date: MONDAY, duration_min: 10 },
    { date: SUNDAY, duration_min: 20 },
  ]);
  assert.deepEqual(out, [
    { weekStart: MONDAY, minutes: 30 },
    { weekStart: NEXT_MONDAY, minutes: 40 },
  ]);
});

test("exerciseMinutesPerWeek: does not mutate the input array or entries", () => {
  const input = [
    { date: MONDAY, duration_min: 30 },
    { date: NEXT_MONDAY, duration_min: 20 },
  ];
  const snapshot = JSON.parse(JSON.stringify(input));
  exerciseMinutesPerWeek(input);
  assert.deepEqual(input, snapshot);
});

test("caloriesPerDay: empty input -> []", () => {
  assert.deepEqual(caloriesPerDay([]), []);
});

test("caloriesPerDay: single meal -> one day bucket", () => {
  const out = caloriesPerDay([{ date: MONDAY, calories: 650 }]);
  assert.deepEqual(out, [{ date: MONDAY, calories: 650 }]);
});

test("caloriesPerDay: same-day meals sum into one bucket", () => {
  const out = caloriesPerDay([
    { date: MONDAY, calories: 650 },
    { date: MONDAY, calories: 400 },
  ]);
  assert.deepEqual(out, [{ date: MONDAY, calories: 1050 }]);
});

test("caloriesPerDay: multiple days sorted oldest -> newest regardless of input order", () => {
  const out = caloriesPerDay([
    { date: NEXT_MONDAY, calories: 800 },
    { date: MONDAY, calories: 1050 },
  ]);
  assert.deepEqual(out, [
    { date: MONDAY, calories: 1050 },
    { date: NEXT_MONDAY, calories: 800 },
  ]);
});

test("caloriesPerDay: does not mutate the input array or entries", () => {
  const input = [{ date: MONDAY, calories: 650 }];
  const snapshot = JSON.parse(JSON.stringify(input));
  caloriesPerDay(input);
  assert.deepEqual(input, snapshot);
});
