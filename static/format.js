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

  /** The imperial form of one weight WITHOUT the kg prefix: "181.9 lb" in lb
   * mode, or "13 st 0.4 lb" in st-lb mode when there is at least one whole
   * stone (sub-stone values fall back to total lb, mirroring weightLabel).
   * Pure display helper for summary sub-lines; null lb -> "". */
  function weightImperial(lb, stone, stoneLb, displayUnit) {
    if (lb == null) return "";
    if (displayUnit === "st-lb" && stone != null && Math.round(stone) > 0) {
      return `${Math.round(stone)} st ${fmt1(stoneLb)} lb`;
    }
    return `${fmt1(lb)} lb`;
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

  /** Target kg for a BMI at a height — mirrors units.weight_kg_from_bmi:
   * round(bmi*(h/100)**2, 1). None when either input is unset. Drives the
   * wizard's BMI-mode derived-weight hint, so it must match the server. */
  function weightKgFromBmi(bmi, heightCm) {
    if (bmi == null || heightCm == null) return null;
    const meters = heightCm / 100;
    return Math.round(bmi * meters * meters * 10) / 10;
  }

  /** BMI = kg / (m)^2 — mirrors units.calculate_bmi; None when the weight is
   * unset or the height is unset/non-positive. */
  function bmiFromKg(weightKg, heightCm) {
    if (weightKg == null || heightCm == null || heightCm <= 0) return null;
    const meters = heightCm / 100;
    return weightKg / (meters * meters);
  }

  /** Healthy BMI band (18.5-24.9) expressed in kg — mirrors
   * units.healthy_weight_range. [minKg, maxKg]; null when height is unset. */
  function healthyRange(heightCm) {
    if (heightCm == null) return null;
    const meters = heightCm / 100;
    return [
      Math.round(18.5 * meters * meters * 10) / 10,
      Math.round(24.9 * meters * meters * 10) / 10,
    ];
  }

  /** BMI bucket: underweight (<18.5), healthy (18.5-24.9), overweight (>=25)
   * — mirrors units.classify_bmi. Null input -> null. */
  function classifyBmi(bmi) {
    if (bmi == null) return null;
    if (bmi < 18.5) return "underweight";
    if (bmi <= 24.9) return "healthy";
    return "overweight";
  }

  /** Shared healthy-range hint used by the onboarding wizard AND the settings
   * goal form. targetStatus is the classification ("healthy" |
   * "underweight" | "overweight"): the API's summary.target_status when
   * available, otherwise classifyBmi() of the entered target. Returns null
   * when the healthy range is unknown (height unset); with a target it flags
   * under/overweight targets, without one it still surfaces the range. */
  function targetRangeHint(targetKg, healthyMinKg, healthyMaxKg, targetStatus) {
    if (healthyMinKg == null || healthyMaxKg == null) return null;
    const range = `${fmt1(healthyMinKg)}-${fmt1(healthyMaxKg)} kg`;
    if (targetKg == null || targetStatus == null) {
      return { outOfRange: false, status: null, message: `Healthy range: ${range}.` };
    }
    if (targetStatus === "underweight" || targetStatus === "overweight") {
      const side = targetStatus === "overweight" ? "above" : "below";
      return {
        outOfRange: true,
        status: targetStatus,
        message: `Target is ${side} the healthy range (${range}).`,
      };
    }
    return {
      outOfRange: false,
      status: "healthy",
      message: `Target is within the healthy range (${range}).`,
    };
  }

  /** Python's round(x, 4) — round half to even (banker's rounding). Mirrors
   * rewards.checkpoint_thresholds' `round(..., 4)` so threshold kg matches
   * the server. Private: not part of the public api surface. */
  function round4(value) {
    const factor = 10000;
    const scaled = value * factor;
    const floored = Math.floor(scaled);
    const frac = scaled - floored;
    if (frac < 0.5) return floored / factor;
    if (frac > 0.5) return (floored + 1) / factor;
    return (floored % 2 === 0 ? floored : floored + 1) / factor;
  }

  /** 0..1 goal progress: (baseline − current) / (baseline − target), clamped
   * to 0..1 so overshoot never exceeds 100% and weight gain floors at 0;
   * null when any input is missing OR baseline <= target (no loss goal). */
  function goalProgress(baseline, current, target) {
    if (baseline == null || current == null || target == null || baseline <= target) {
      return null;
    }
    const pct = (baseline - current) / (baseline - target);
    return Math.max(0, Math.min(1, pct));
  }

  /** Threshold kg per checkpoint — mirrors rewards.checkpoint_thresholds:
   * baseline − (p/100)·(baseline − target), banker's-rounded to 4dp, for p in
   * 10/25/50/75/100; [] when inputs are missing or target >= baseline. */
  function checkpointThresholds(baseline, target) {
    if (baseline == null || target == null || target >= baseline) return [];
    const totalLoss = baseline - target;
    return [10, 25, 50, 75, 100].map((percent) =>
      round4(baseline - (percent / 100) * totalLoss)
    );
  }

  /** kg -> {lb, stone, stoneLb} — mirrors units.kg_to_stone incl. the 14-lb
   * carry snap (a float epsilon a hair below an exact stone lands on the
   * whole stone, not "9 st 14 lb"). Raw values; display rounding is the
   * SPA's job. Null-safe. */
  function kgToImperial(kg) {
    if (kg == null) return null;
    const lb = kg * 2.2046226218;
    let stone = Math.floor(lb / 14);
    let stoneLb = lb - 14 * stone;
    if (stoneLb >= 14 - 1e-6) {
      stone += 1;
      stoneLb = 0.0;
    }
    return { lb, stone, stoneLb };
  }

  /** The milestone strip's next line: "Next: 50% at 90.0 kg (14 st 2.4 lb)"
   * from the raw threshold kg + display unit (same weightLabel path the
   * milestone dots use). The all-earned copy ("All checkpoints earned!") is
   * the caller's concern — it has no percent. Null-safe: missing percent or
   * kg -> "" (no goal data renders no next line). */
  function milestoneNextLabel(percent, kg, displayUnit) {
    if (percent == null || kg == null) return "";
    const imp = kgToImperial(kg);
    return `Next: ${percent}% at ${weightLabel(kg, imp.lb, imp.stone, imp.stoneLb, displayUnit)}`;
  }

  /** Confetti eligibility gate (design §Confetti): "fire" only when the
   * earned checkpoint count increased since the previous load; the first
   * render (null/undefined previous count) is always "suppress". Equal or
   * lower counts are also suppressed. */
  function shouldCelebrate(prevEarned, curEarned) {
    if (prevEarned == null) return "suppress";
    return curEarned > prevEarned ? "fire" : "suppress";
  }

  /** Resolve a three-state theme preference to a concrete light/dark choice.
   * An explicit light/dark pref always wins; "system" (or any unknown pref)
   * follows the OS color scheme via systemPref ("dark" | "light"); an
   * unavailable/null systemPref resolves to light (the no-JS default). */
  function resolveTheme(pref, systemPref) {
    if (pref === "dark") return "dark";
    if (pref === "light") return "light";
    return systemPref === "dark" ? "dark" : "light";
  }

  const api = { fmt1, weightLabel, summaryLabel, weightImperial, stoneLbToKg, ftInToCm, formatDate, unitPref, chronological, exerciseMinutesPerWeek, caloriesPerDay, weightKgFromBmi, bmiFromKg, healthyRange, classifyBmi, targetRangeHint, goalProgress, checkpointThresholds, kgToImperial, milestoneNextLabel, shouldCelebrate, resolveTheme };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.WeightFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
