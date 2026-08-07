/* Weight Loss Tracker — pure display formatters shared by the SPA and tests.
 * Classic-script UMD: assigns `WeightFormat` on globalThis for the browser and
 * `module.exports` for node:test. static/index.html loads this BEFORE app.js. */
"use strict";
(function (global) {
  function fmt1(v) {
    return v == null ? "—" : Number(v).toFixed(1);
  }

  /** "82.5 kg (181.9 lb)" or "82.5 kg (13 st 0.4 lb)" from flat keys;
   * null-safe. displayUnit picks which imperial form follows kg: "lb" (total
   * pounds, the default) or "st-lb" (stones + pounds). In st-lb mode the
   * breakdown only appears when there is at least one whole stone — "0 st
   * 1.1 lb" would duplicate the lb already shown — so sub-stone values fall
   * back to total lb. */
  function weightLabel(kg, lb, stone, stoneLb, displayUnit) {
    if (kg == null) return "—";
    const stLbMode = displayUnit === "st-lb";
    const parts = [];
    parts.push(`${fmt1(kg)} kg`);
    if (stLbMode && stone != null && stoneLb != null && Math.round(stone) > 0) {
      parts.push(`${Math.round(stone)} st ${fmt1(stoneLb)} lb`);
    } else if (lb != null) {
      parts.push(`${fmt1(lb)} lb`);
    }
    return parts.length > 1 ? `${parts[0]} (${parts.slice(1).join("; ")})` : parts[0];
  }

  /** Summary rows use prefixed keys: prefix_kg, prefix_lb, prefix_stone, prefix_stone_lb. */
  function summaryLabel(o, prefix, displayUnit) {
    return weightLabel(o[`${prefix}_kg`], o[`${prefix}_lb`], o[`${prefix}_stone`], o[`${prefix}_stone_lb`], displayUnit);
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

  /** API "YYYY-MM-DD" -> "DD/MM/YY" (zero-padded day/month, two-digit year).
   * Null-safe (missing date renders ""); a full timestamp or any other input
   * that starts with an ISO date is formatted from its date part, and
   * non-ISO input passes through unchanged so a contract violation surfaces
   * instead of crashing the UI. */
  function formatDate(isoDate) {
    if (isoDate == null) return "";
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoDate));
    if (!match) return String(isoDate);
    const [, year, month, day] = match;
    return `${day}/${month}/${String(year).slice(-2)}`;
  }

  /** Resolve a persisted unit preference; missing/empty falls back to the
   * project default (kg / cm) so the app opens in the user's format. */
  function unitPref(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : value;
  }

  /** The API returns entries newest-first (the history list shows them that
   * way); the chart reads left -> right in time, so it plots this reversed
   * copy — oldest on the left, newest on the right. Never mutates input. */
  function chronological(entries) {
    return entries.slice().reverse();
  }

  /** The Monday ("YYYY-MM-DD") of the ISO week an entry's date falls in. JS
   * lacks Python's date.isocalendar(), so compute it from the weekday: days
   * since Monday = (getDay() + 6) % 7, then subtract. Parsed as UTC so the
   * result is deterministic in every timezone. */
  function isoWeekStart(isoDate) {
    const [year, month, day] = String(isoDate).slice(0, 10).split("-").map(Number);
    const d = new Date(Date.UTC(year, month - 1, day));
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(d.getUTCDate()).padStart(2, "0");
    return `${d.getUTCFullYear()}-${mm}-${dd}`;
  }

  /** Exercise entries -> total minutes per ISO week. Returns
   * [{ weekStart, minutes }] oldest -> newest; weekStart is the Monday of the
   * entry's ISO week. Input order is irrelevant and the input is never
   * mutated. */
  function exerciseMinutesPerWeek(entries) {
    const byWeek = new Map();
    for (const e of entries) {
      const weekStart = isoWeekStart(e.date);
      byWeek.set(weekStart, (byWeek.get(weekStart) || 0) + e.duration_min);
    }
    return [...byWeek.entries()]
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([weekStart, minutes]) => ({ weekStart, minutes }));
  }

  /** Meal entries -> total calories per calendar date. Returns
   * [{ date, calories }] oldest -> newest. The input is never mutated. */
  function caloriesPerDay(entries) {
    const byDay = new Map();
    for (const e of entries) {
      const date = String(e.date).slice(0, 10);
      byDay.set(date, (byDay.get(date) || 0) + e.calories);
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([date, calories]) => ({ date, calories }));
  }

  const api = { fmt1, weightLabel, summaryLabel, stoneLbToKg, ftInToCm, formatDate, unitPref, chronological, exerciseMinutesPerWeek, caloriesPerDay };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.WeightFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
