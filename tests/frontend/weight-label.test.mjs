/* Frontend formatter regression tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the display contract:
 * kg always primary, with ONE imperial form chosen by displayUnit ("lb" total
 * pounds by default, or "st-lb" stones + pounds). */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { fmt1, weightLabel, summaryLabel, weightImperial } = format;

test("weightLabel defaults to lb mode: kg (total lb)", () => {
  assert.equal(weightLabel(82.5, 181.9, 13, 0.4), "82.5 kg (181.9 lb)");
});

test("weightLabel explicit lb mode: kg (total lb)", () => {
  assert.equal(weightLabel(82.5, 181.9, 13, 0.4, "lb"), "82.5 kg (181.9 lb)");
});

test("weightLabel st-lb mode: kg (st lb)", () => {
  assert.equal(weightLabel(82.5, 181.9, 13, 0.4, "st-lb"), "82.5 kg (13 st 0.4 lb)");
});

test("weightLabel st-lb mode omits the breakdown under one stone", () => {
  // Under one stone the pounds already show the value; "0 st 1.1 lb" would
  // duplicate it, so it falls back to total lb.
  assert.equal(weightLabel(0.5, 1.1, 0, 1.1, "st-lb"), "0.5 kg (1.1 lb)");
  assert.equal(weightLabel(1.5, 3.3, 0, 3.3, "st-lb"), "1.5 kg (3.3 lb)");
});

test("weightLabel st-lb mode falls back to lb when stone is missing", () => {
  assert.equal(weightLabel(82.5, 181.9, null, null, "st-lb"), "82.5 kg (181.9 lb)");
});

test("weightLabel is null-safe for missing kg in every mode", () => {
  assert.equal(weightLabel(null, null, null, null), "—");
  assert.equal(weightLabel(null, null, null, null, "lb"), "—");
  assert.equal(weightLabel(null, null, null, null, "st-lb"), "—");
  assert.equal(weightLabel(undefined, undefined, undefined, undefined), "—");
});

test("weightLabel renders bare kg when only kg is present", () => {
  assert.equal(weightLabel(82.5, null, null, null), "82.5 kg");
  assert.equal(weightLabel(82.5, null, null, null, "st-lb"), "82.5 kg");
});

test("fmt1 rounds to one decimal (toFixed(1))", () => {
  assert.equal(fmt1(181.881), "181.9");
  assert.equal(fmt1(13.881), "13.9");
  assert.equal(fmt1(26.939), "26.9");
});

test("weightLabel rounds stone-lb via fmt1 in st-lb mode", () => {
  assert.equal(weightLabel(70, 154.3, 11, 0.3, "st-lb"), "70.0 kg (11 st 0.3 lb)");
});

test("summaryLabel passes the display mode through", () => {
  const o = { current_kg: 82.5, current_lb: 181.9, current_stone: 13, current_stone_lb: 0.4 };
  assert.equal(summaryLabel(o, "current"), "82.5 kg (181.9 lb)");
  assert.equal(summaryLabel(o, "current", "lb"), "82.5 kg (181.9 lb)");
  assert.equal(summaryLabel(o, "current", "st-lb"), "82.5 kg (13 st 0.4 lb)");
});

test("weightImperial lb mode: total pounds", () => {
  assert.equal(weightImperial(181.9, 13, 0.4, "lb"), "181.9 lb");
  assert.equal(weightImperial(181.9, 13, 0.4), "181.9 lb");
});

test("weightImperial st-lb mode: whole stones + pounds", () => {
  assert.equal(weightImperial(181.9, 13, 0.4, "st-lb"), "13 st 0.4 lb");
});

test("weightImperial st-lb mode falls back to total lb under one stone", () => {
  assert.equal(weightImperial(1.1, 0, 1.1, "st-lb"), "1.1 lb");
  assert.equal(weightImperial(3.3, 0, 3.3, "st-lb"), "3.3 lb");
});

test("weightImperial is empty for null lb in every mode", () => {
  assert.equal(weightImperial(null, null, null), "");
  assert.equal(weightImperial(null, null, null, "lb"), "");
  assert.equal(weightImperial(null, null, null, "st-lb"), "");
});
