/* Weight Loss Tracker — vanilla JS SPA.
 * Formats the API's raw values (kg + lb + stone + BMI) for display.
 * Rounding to one decimal is done here, never in the API. */
"use strict";

const $ = (id) => document.getElementById(id);
const toastEl = $("toast");

/* ---- formatting -------------------------------------------------------- */
/* fmt1/weightLabel/summaryLabel live in static/format.js (index.html loads it
 * before app.js) so node:test can pin the exact display contract. */
const { fmt1, weightLabel, summaryLabel } = globalThis.WeightFormat;

function bmiLabel(bmi) {
  return bmi == null ? "—" : fmt1(bmi);
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (toastEl.hidden = true), 3000);
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) {
      /* keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

/* ---- data -------------------------------------------------------------- */

async function loadData() {
  const [weight, rewards, settings] = await Promise.all([
    fetchJson("/api/weight"),
    fetchJson("/api/rewards"),
    fetchJson("/api/settings"),
  ]);
  renderSummary(weight.summary);
  renderHistory(weight.entries);
  drawChart(weight.entries, weight.summary);
  renderRewards(rewards);
  renderSettings(settings);
}

/* ---- summary ----------------------------------------------------------- */

const SUMMARY_ROWS = [
  ["current", "Current"],
  ["baseline", "Baseline"],
  ["target", "Target"],
  ["lost", "Lost"],
  ["remaining", "Remaining"],
];

function renderSummary(s) {
  const grid = $("summary-stats");
  grid.innerHTML = "";
  for (const [key, label] of SUMMARY_ROWS) {
    const stat = document.createElement("div");
    stat.className = "stat";
    const value = document.createElement("div");
    value.className = "stat-value";
    value.textContent = summaryLabel(s, key);
    const name = document.createElement("div");
    name.className = "stat-label";
    name.textContent = label;
    stat.append(value, name);
    // *_bmi is always present on real weights (baseline/current/target) but
    // null when height is unset; render the line so the spec's "BMI —"
    // shows instead of nothing. Deltas (lost/remaining) never carry a bmi key.
    if (s[`${key}_bmi`] !== undefined) {
      const bmi = document.createElement("div");
      bmi.className = "stat-sub";
      bmi.textContent = `BMI ${bmiLabel(s[`${key}_bmi`])}`;
      stat.append(bmi);
    }
    grid.append(stat);
  }
}

/* ---- history ----------------------------------------------------------- */

function renderHistory(entries) {
  const list = $("entry-list");
  list.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No entries yet — log your first weight above.";
    list.append(empty);
    return;
  }
  for (const e of entries) {
    const li = document.createElement("li");
    li.className = "entry-row";
    const date = document.createElement("span");
    date.className = "entry-date";
    date.textContent = e.date;
    const weight = document.createElement("span");
    weight.className = "entry-weight";
    weight.textContent = weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb);
    const bmi = document.createElement("span");
    bmi.className = "entry-bmi";
    bmi.textContent = `BMI ${bmiLabel(e.bmi)}`;
    const del = document.createElement("button");
    del.type = "button";
    del.className = "entry-delete";
    del.textContent = "×";
    del.title = "Delete entry";
    del.addEventListener("click", () => deleteEntry(e.id));
    li.append(date, weight, bmi, del);
    list.append(li);
  }
}

async function deleteEntry(id) {
  try {
    await fetchJson(`/api/weight/${id}`, { method: "DELETE" });
    toast("Entry deleted");
    await loadData();
  } catch (err) {
    toast(`Delete failed: ${err.message}`);
  }
}

/* ---- chart ------------------------------------------------------------- */

function drawChart(entries, summary) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth;
  canvas.height = 260;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!entries.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "14px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Log entries to see your progress chart", canvas.width / 2, canvas.height / 2);
    return;
  }

  const pad = { top: 16, right: 16, bottom: 28, left: 44 };
  const w = canvas.width - pad.left - pad.right;
  const h = canvas.height - pad.top - pad.bottom;
  const kgs = entries.map((e) => e.weight_kg);
  const min = Math.min(...kgs) - 1;
  const max = Math.max(...kgs) + 1;
  const xAt = (i) => pad.left + (entries.length === 1 ? w / 2 : (i / (entries.length - 1)) * w);
  const yAt = (v) => pad.top + h - ((v - min) / (max - min)) * h;

  // grid lines
  ctx.strokeStyle = "#e2e8f0";
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "right";
  for (let g = 0; g <= 4; g++) {
    const v = min + ((max - min) / 4) * g;
    const y = yAt(v);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(canvas.width - pad.right, y);
    ctx.stroke();
    ctx.fillText(fmt1(v), pad.left - 6, y + 4);
  }

  // line + points
  ctx.strokeStyle = "#2f7d54";
  ctx.lineWidth = 2;
  ctx.beginPath();
  entries.forEach((e, i) => (i === 0 ? ctx.moveTo(xAt(i), yAt(e.weight_kg)) : ctx.lineTo(xAt(i), yAt(e.weight_kg))));
  ctx.stroke();

  ctx.fillStyle = "#2f7d54";
  for (const [i, e] of entries.entries()) {
    ctx.beginPath();
    ctx.arc(xAt(i), yAt(e.weight_kg), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // x labels (sparse)
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(entries.length / 6));
  for (let i = 0; i < entries.length; i += step) {
    ctx.fillText(entries[i].date.slice(5), xAt(i), canvas.height - 8);
  }

  // tooltip
  canvas.onmousemove = (ev) => {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    let nearest = 0;
    let best = Infinity;
    entries.forEach((e, i) => {
      const d = Math.abs(xAt(i) - mx);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    if (best > w / entries.length) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    drawChart(entries, summary);
    const e = entries[nearest];
    const label = `${e.date}\n${weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb)}\nBMI ${bmiLabel(e.bmi)}`;
    const box = { x: xAt(nearest) + 10, y: Math.max(pad.top, yAt(e.weight_kg) - 30), w: 0, h: 0 };
    ctx.font = "11px system-ui, sans-serif";
    const lines = label.split("\n");
    ctx.textAlign = "left";
    const lineH = 14;
    box.w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 12;
    box.h = lines.length * lineH + 10;
    if (box.x + box.w > canvas.width - 4) box.x = xAt(nearest) - box.w - 10;
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.fillStyle = "#f8fafc";
    lines.forEach((l, i) => ctx.fillText(l, box.x + 6, box.y + 14 + i * lineH));
  };
  canvas.onmouseleave = () => drawChart(entries, summary);
}

/* ---- rewards ----------------------------------------------------------- */

function renderRewards(r) {
  const el = $("rewards-content");
  el.innerHTML = "";
  const earned = document.createElement("p");
  earned.className = "rewards-count";
  earned.textContent = `${r.earned_count} of 5 checkpoints earned`;
  el.append(earned);

  if (r.next_checkpoint) {
    const nxt = r.next_checkpoint;
    const row = document.createElement("p");
    row.className = "rewards-next";
    row.textContent = `Next checkpoint (${nxt.percent}%): ${weightLabel(nxt.threshold_kg, nxt.threshold_lb, nxt.threshold_stone, nxt.threshold_stone_lb)}`;
    el.append(row);

    const track = document.createElement("div");
    track.className = "progress-track";
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    const pct = Math.round((r.progress_to_next || 0) * 100);
    fill.style.width = `${pct}%`;
    track.append(fill);
    const pctLabel = document.createElement("div");
    pctLabel.className = "progress-label";
    pctLabel.textContent = `${pct}% of the way to the next checkpoint`;
    el.append(track, pctLabel);
  } else {
    const done = document.createElement("p");
    done.className = "rewards-done";
    done.textContent = "All checkpoints earned — great work! 🎉";
    el.append(done);
  }

  if (r.active_checkpoints.length) {
    const list = document.createElement("ul");
    list.className = "checkpoint-list";
    for (const cp of r.active_checkpoints) {
      const li = document.createElement("li");
      const badge = document.createElement("span");
      badge.className = "checkpoint-badge";
      badge.textContent = `${cp.percent}%`;
      const label = document.createElement("span");
      label.className = "checkpoint-label";
      label.textContent = weightLabel(cp.threshold_kg, cp.threshold_lb, cp.threshold_stone, cp.threshold_stone_lb);
      const when = document.createElement("span");
      when.className = "checkpoint-when";
      when.textContent = cp.earned_at ? `earned ${cp.earned_at.slice(0, 10)}` : "pending";
      li.append(badge, label, when);
      list.append(li);
    }
    el.append(list);
  }
}

/* ---- settings ---------------------------------------------------------- */

function renderSettings(s) {
  $("target-weight").value = s.target_weight ?? "";
  $("height-cm").value = s.height_cm ?? "";
  $("tip-time").value = s.tip_time ?? "";
  $("reminder-time").value = s.reminder_time ?? "";
  $("exercise-time").value = s.exercise_time ?? "";
  $("start-override").value = s.start_weight_override ?? "";
}

async function saveSettings(ev) {
  ev.preventDefault();
  const num = (id) => {
    const v = $(id).value.trim();
    return v === "" ? null : Number(v);
  };
  const time = (id) => {
    // Empty input disables the schedule (the "" sentinel); never null,
    // which would remove the override and restore the default instead.
    const v = $(id).value.trim();
    return v;
  };
  try {
    await fetchJson("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_weight: num("target-weight"),
        height_cm: num("height-cm"),
        tip_time: time("tip-time"),
        reminder_time: time("reminder-time"),
        exercise_time: time("exercise-time"),
        start_weight_override: num("start-override"),
      }),
    });
    toast("Settings saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- entries ----------------------------------------------------------- */

function todayLocal() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

async function addEntry(ev) {
  ev.preventDefault();
  const date = $("entry-date").value || todayLocal();
  const weightKg = Number($("entry-weight").value);
  try {
    await fetchJson("/api/weight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, weight_kg: weightKg }),
    });
    $("entry-weight").value = "";
    toast("Entry saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- push notifications ------------------------------------------------ */

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function enablePush() {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("Push notifications are not supported in this browser");
    }
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const { public_key: publicKey } = await fetchJson("/api/push/vapid-public-key");
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    await fetchJson("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: sub.endpoint,
        p256dh: btoa(String.fromCharCode(...new Uint8Array(sub.getKey("p256dh")))),
        auth: btoa(String.fromCharCode(...new Uint8Array(sub.getKey("auth")))),
      }),
    });
    toast("Notifications enabled");
    setPushUi(true);
  } catch (err) {
    toast(`Could not enable notifications: ${err.message}`);
  }
}

async function disablePush() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) {
      setPushUi(false);
      toast("Notifications are already off");
      return;
    }
    await fetchJson("/api/push/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint }),
    });
    await sub.unsubscribe();
    toast("Notifications disabled");
    setPushUi(false);
  } catch (err) {
    toast(`Could not disable notifications: ${err.message}`);
  }
}

async function testPush() {
  try {
    const res = await fetchJson("/api/push/test", { method: "POST" });
    toast(`Test notification sent to ${res.sent} device${res.sent === 1 ? "" : "s"}`);
  } catch (err) {
    toast(`Test failed: ${err.message}`);
  }
}

function setPushUi(enabled) {
  $("enable-push").hidden = enabled;
  $("disable-push").hidden = !enabled;
  $("test-push").hidden = !enabled;
}

/* ---- init -------------------------------------------------------------- */

async function init() {
  $("entry-form").addEventListener("submit", addEntry);
  $("settings-form").addEventListener("submit", saveSettings);
  $("enable-push").addEventListener("click", enablePush);
  $("disable-push").addEventListener("click", disablePush);
  $("test-push").addEventListener("click", testPush);
  $("entry-date").value = todayLocal();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* push stays optional */
    });
  }

  try {
    await loadData();
  } catch (err) {
    toast(`Could not load data: ${err.message}`);
  }
}

init();
