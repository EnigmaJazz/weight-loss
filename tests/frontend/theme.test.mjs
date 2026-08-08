/* Frontend theme-resolution tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning resolveTheme
 * (design §JS Theming Lifecycle, spec 'Pure resolveTheme Helper'): an
 * explicit light/dark preference always wins; "system" follows systemPref;
 * an unavailable/null systemPref resolves to light (the no-JS default). */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { resolveTheme } = format;

test("resolveTheme resolves the full truth table", () => {
  // (pref, systemPref) -> expected
  const table = [
    ["system", "dark", "dark"],
    ["system", "light", "light"],
    ["light", "dark", "light"],
    ["light", "light", "light"],
    ["dark", "dark", "dark"],
    ["dark", "light", "dark"],
    ["system", null, "light"],
  ];
  for (const [pref, systemPref, expected] of table) {
    assert.equal(resolveTheme(pref, systemPref), expected, `resolveTheme(${pref}, ${systemPref})`);
  }
});

test("resolveTheme treats an invalid preference as system (OS-following)", () => {
  // An unknown pref (e.g. a legacy or corrupt value) must never win: it
  // falls through to system resolution, exactly like "system".
  assert.equal(resolveTheme("auto", "dark"), "dark");
  assert.equal(resolveTheme("purple", "light"), "light");
  assert.equal(resolveTheme("", "dark"), "dark");
});

test("resolveTheme treats an unavailable systemPref as light", () => {
  // matchMedia can be unavailable/throw in old or embedded browsers; the
  // fallback must be light, never a crash.
  assert.equal(resolveTheme("system", undefined), "light");
  assert.equal(resolveTheme("system", ""), "light");
});
