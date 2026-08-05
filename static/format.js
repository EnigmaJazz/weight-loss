/* Weight Loss Tracker — pure display formatters shared by the SPA and tests.
 * Classic-script UMD: assigns `WeightFormat` on globalThis for the browser and
 * `module.exports` for node:test. static/index.html loads this BEFORE app.js. */
"use strict";
(function (global) {
  function fmt1(v) {
    return v == null ? "—" : Number(v).toFixed(1);
  }

  /** "82.5 kg (181.9 lb; 13 st 0.4 lb)" from flat keys; null-safe. */
  function weightLabel(kg, lb, stone, stoneLb) {
    if (kg == null) return "—";
    const parts = [];
    parts.push(`${fmt1(kg)} kg`);
    if (lb != null) parts.push(`${fmt1(lb)} lb`);
    if (stone != null && stoneLb != null) {
      parts.push(`${Math.round(stone)} st ${fmt1(stoneLb)} lb`);
    }
    return parts.length > 1 ? `${parts[0]} (${parts.slice(1).join("; ")})` : parts[0];
  }

  /** Summary rows use prefixed keys: prefix_kg, prefix_lb, prefix_stone, prefix_stone_lb. */
  function summaryLabel(o, prefix) {
    return weightLabel(o[`${prefix}_kg`], o[`${prefix}_lb`], o[`${prefix}_stone`], o[`${prefix}_stone_lb`]);
  }

  /** stone + lb -> kg. The exact international pound (1 lb = 0.45359237 kg),
   * inverse of units.py's KG_TO_LB = 2.2046226218. Null-safe, rounding-free
   * (raw value; display rounding is the SPA's job). */
  function stoneLbToKg(stone, lb) {
    if (stone == null || lb == null) return null;
    return (stone * 14 + lb) * 0.45359237;
  }

  /** ft + in -> cm (1 in = 2.54 cm exactly). Null-safe, rounding-free. */
  function ftInToCm(ft, inches) {
    if (ft == null || inches == null) return null;
    return (ft * 12 + inches) * 2.54;
  }

  const api = { fmt1, weightLabel, summaryLabel, stoneLbToKg, ftInToCm };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.WeightFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
