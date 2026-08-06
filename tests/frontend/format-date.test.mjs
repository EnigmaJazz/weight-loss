/* Frontend date/unit-display helper tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses. Pins two display contracts:
 *   - formatDate: the API's ISO "YYYY-MM-DD" -> "DD/MM/YY" for every
 *     user-facing date (history rows, chart axis, chart tooltip, rewards).
 *   - unitPref: per-user weight/height unit preferences fall back to the
 *     project defaults (kg / cm) when missing or empty.
 *   - chronological: the chart's left->right time axis — the API returns
 *     newest-first, the chart must plot oldest->newest. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { formatDate, unitPref, chronological } = format;

/* ---- formatDate --------------------------------------------------------- */

test("formatDate renders DD/MM/YY from an ISO date", () => {
  assert.equal(formatDate("2026-08-05"), "05/08/26");
});

test("formatDate zero-pads day and month", () => {
  assert.equal(formatDate("2026-01-09"), "09/01/26");
  assert.equal(formatDate("2026-11-03"), "03/11/26");
});

test("formatDate two-digit year boundary (2099 -> 99)", () => {
  assert.equal(formatDate("2099-12-31"), "31/12/99");
});

test("formatDate is null-safe (missing date renders empty)", () => {
  assert.equal(formatDate(null), "");
  assert.equal(formatDate(undefined), "");
});

test("formatDate tolerates a full timestamp (trailing time is ignored)", () => {
  assert.equal(formatDate("2026-08-05T10:30:00"), "05/08/26");
});

test("formatDate passes through non-ISO input unchanged (no crash)", () => {
  assert.equal(formatDate("not-a-date"), "not-a-date");
});

/* ---- unitPref ----------------------------------------------------------- */

test("unitPref falls back to kg when the weight preference is missing or empty", () => {
  assert.equal(unitPref(undefined, "kg"), "kg");
  assert.equal(unitPref(null, "kg"), "kg");
  assert.equal(unitPref("", "kg"), "kg");
});

test("unitPref falls back to cm when the height preference is missing or empty", () => {
  assert.equal(unitPref(undefined, "cm"), "cm");
  assert.equal(unitPref(null, "cm"), "cm");
  assert.equal(unitPref("", "cm"), "cm");
});

test("unitPref honors a stored preference", () => {
  assert.equal(unitPref("st-lb", "kg"), "st-lb");
  assert.equal(unitPref("ft-in", "cm"), "ft-in");
  assert.equal(unitPref("kg", "st-lb"), "kg");
});

/* ---- chronological ------------------------------------------------------ */

test("chronological reverses the newest-first API array for the chart axis", () => {
  const newestFirst = [
    { date: "2026-08-05" },
    { date: "2026-08-01" },
    { date: "2026-07-28" },
  ];
  assert.deepEqual(
    chronological(newestFirst).map((e) => e.date),
    ["2026-07-28", "2026-08-01", "2026-08-05"]
  );
});

test("chronological never mutates its input (returns a copy)", () => {
  const input = [
    { date: "2026-08-05" },
    { date: "2026-08-01" },
  ];
  const out = chronological(input);
  assert.notEqual(out, input);
  assert.deepEqual(
    input.map((e) => e.date),
    ["2026-08-05", "2026-08-01"]
  );
});

test("chronological is a no-op for a single entry", () => {
  assert.deepEqual(
    chronological([{ date: "2026-08-05" }]).map((e) => e.date),
    ["2026-08-05"]
  );
});

test("chronological of an empty list stays empty", () => {
  assert.deepEqual(chronological([]), []);
});
