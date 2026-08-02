"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  entries: [],
  summary: {},
  rewards: {},
  settings: {},
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch (_e) { /* non-JSON error body */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function setText(id, value) {
  const el = $(`#${id}`);
  if (el) el.textContent = value;
}

// ---- weight ------------------------------------------------------------

async function loadWeight() {
  const data = await api("/api/weight");
  state.entries = data.entries;
  state.summary = data.summary;
  renderSummary();
  renderHistory();
  drawChart();
}

function renderSummary() {
  const s = state.summary;
  const fmt = (v) => (v == null ? "—" : Number(v).toFixed(1));
  setText("stat-baseline", fmt(s.baseline_kg));
  setText("stat-current", fmt(s.current_kg));
  setText("stat-lost", fmt(s.lost_kg));
  setText("stat-target", fmt(s.target_kg));
  setText("stat-remaining", fmt(s.remaining_kg));
}

function renderHistory() {
  const tbody = $("#history-body");
  tbody.innerHTML = "";
  for (const entry of state.entries) {
    const tr = document.createElement("tr");
    const tdDate = document.createElement("td");
    tdDate.textContent = entry.date;
    const tdWeight = document.createElement("td");
    tdWeight.textContent = Number(entry.weight_kg).toFixed(1);
    const tdAction = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "delete-btn";
    btn.textContent = "Delete";
    btn.addEventListener("click", () => deleteWeight(entry.id));
    tdAction.appendChild(btn);
    tr.append(tdDate, tdWeight, tdAction);
    tbody.appendChild(tr);
  }
}

async function addWeight(event) {
  event.preventDefault();
  const message = $("#weight-form-message");
  message.textContent = "";
  message.classList.remove("error");
  const payload = {
    date: $("#weight-date").value,
    weight_kg: parseFloat($("#weight-kg").value),
  };
  if (!payload.date || !(payload.weight_kg > 0)) {
    message.textContent = "Enter a valid date and weight.";
    message.classList.add("error");
    return;
  }
  try {
    await api("/api/weight", { method: "POST", body: JSON.stringify(payload) });
    $("#weight-form").reset();
    $("#weight-date").value = new Date().toISOString().slice(0, 10);
    await loadAll();
  } catch (err) {
    message.textContent = err.message;
    message.classList.add("error");
  }
}

async function deleteWeight(id) {
  try {
    await api(`/api/weight/${id}`, { method: "DELETE" });
    await loadAll();
  } catch (err) {
    alert(err.message);
  }
}

// ---- chart -------------------------------------------------------------

function drawChart() {
  const canvas = $("#chart");
  const empty = $("#chart-empty");
  const entries = state.entries;
  const ordered = [...entries].reverse(); // oldest first
  empty.style.display = ordered.length > 0 ? "none" : "block";
  if (ordered.length === 0) {
    canvas.style.display = "none";
    return;
  }
  canvas.style.display = "block";

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = rect.width;
  const height = 220;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const pad = { left: 42, right: 12, top: 12, bottom: 26 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const values = ordered.map((e) => e.weight_kg);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) { min -= 1; max += 1; }
  const span = max - min;
  min -= span * 0.1;
  max += span * 0.1;

  const x = (i) => pad.left + (ordered.length === 1 ? plotW / 2 : (i / (ordered.length - 1)) * plotW);
  const y = (v) => pad.top + ((max - v) / (max - min)) * plotH;

  ctx.clearRect(0, 0, width, height);

  // gridlines + y labels
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillStyle = "#6b7280";
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  for (let g = 0; g <= 4; g++) {
    const val = max - (g / 4) * (max - min);
    const gy = pad.top + (g / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(pad.left, gy);
    ctx.lineTo(width - pad.right, gy);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(val.toFixed(1), pad.left - 6, gy + 4);
  }

  // x labels (up to ~6)
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(ordered.length / 6));
  ordered.forEach((entry, i) => {
    if (i % step === 0 || i === ordered.length - 1) {
      ctx.fillText(entry.date.slice(5), x(i), height - 8);
    }
  });

  // line
  ctx.strokeStyle = "#2f7d54";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ordered.forEach((entry, i) => {
    const px = x(i);
    const py = y(entry.weight_kg);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();

  // points
  ctx.fillStyle = "#2f7d54";
  ordered.forEach((entry, i) => {
    ctx.beginPath();
    ctx.arc(x(i), y(entry.weight_kg), 3, 0, Math.PI * 2);
    ctx.fill();
  });
}

// ---- rewards -----------------------------------------------------------

async function loadRewards() {
  const data = await api("/api/rewards");
  state.rewards = data;
  renderRewards();
}

function renderRewards() {
  const r = state.rewards;
  setText("reward-total", `${Number(r.reward_total_kg || 0).toFixed(1)} kg`);
  const next = r.next_milestone_kg;
  setText("reward-next", next == null ? "all milestones earned" : `next: ${Number(next).toFixed(1)} kg`);
  const pct = Math.round((r.progress_to_next || 0) * 100);
  $("#reward-progress").style.width = `${Math.min(100, Math.max(0, pct))}%`;

  const ul = $("#milestones");
  ul.innerHTML = "";
  if (!r.milestones || r.milestones.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No milestones yet";
    ul.appendChild(li);
    return;
  }
  for (const m of r.milestones) {
    const li = document.createElement("li");
    li.textContent = `${Number(m.milestone_kg).toFixed(1)} kg`;
    if (m.earned) {
      li.classList.add("earned");
      li.textContent = `✓ ${Number(m.milestone_kg).toFixed(1)} kg`;
    }
    ul.appendChild(li);
  }
}

// ---- settings ----------------------------------------------------------

async function loadSettings() {
  const data = await api("/api/settings");
  state.settings = data;
  $("#set-target").value = data.target_weight ?? "";
  $("#set-step").value = data.milestone_step_kg;
  $("#set-start").value = data.start_weight_override ?? "";
  $("#set-tip").value = data.tip_time;
  $("#set-reminder").value = data.reminder_time;
  $("#set-exercise").value = data.exercise_time;
}

async function saveSettings(event) {
  event.preventDefault();
  const message = $("#settings-message");
  message.textContent = "";
  message.classList.remove("error");
  const payload = {
    target_weight: $("#set-target").value === "" ? null : parseFloat($("#set-target").value),
    milestone_step_kg: parseFloat($("#set-step").value),
    start_weight_override: $("#set-start").value === "" ? null : parseFloat($("#set-start").value),
    tip_time: $("#set-tip").value,
    reminder_time: $("#set-reminder").value,
    exercise_time: $("#set-exercise").value,
  };
  if (!(payload.milestone_step_kg > 0)) {
    message.textContent = "Milestone step must be greater than zero.";
    message.classList.add("error");
    return;
  }
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
    message.textContent = "Settings saved.";
    await Promise.all([loadWeight(), loadRewards()]);
  } catch (err) {
    message.textContent = err.message;
    message.classList.add("error");
  }
}

// ---- notifications -----------------------------------------------------

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

async function enablePush() {
  const message = $("#push-message");
  message.textContent = "";
  message.classList.remove("error");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    message.textContent = "Push notifications are not supported in this browser.";
    message.classList.add("error");
    return;
  }
  try {
    const { public_key } = await api("/api/push/vapid-public-key");
    const registration = await navigator.serviceWorker.register("/static/sw.js");
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        message.textContent = "Notification permission was denied.";
        message.classList.add("error");
        return;
      }
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });
    }
    await api("/api/push/subscribe", {
      method: "POST",
      body: JSON.stringify(subscription.toJSON()),
    });
    message.textContent = "Push notifications enabled for this device.";
  } catch (err) {
    message.textContent = err.message;
    message.classList.add("error");
  }
}

async function testPush() {
  const message = $("#push-message");
  message.textContent = "";
  message.classList.remove("error");
  try {
    const result = await api("/api/push/test", { method: "POST" });
    message.textContent = `Test sent to ${result.sent}/${result.total} subscription(s). Check the browser notification.`;
  } catch (err) {
    message.textContent = err.message;
    message.classList.add("error");
  }
}

// ---- bootstrap ---------------------------------------------------------

async function loadAll() {
  await Promise.all([loadWeight(), loadRewards(), loadSettings()]);
}

function init() {
  $("#weight-date").value = new Date().toISOString().slice(0, 10);
  $("#weight-form").addEventListener("submit", addWeight);
  $("#settings-form").addEventListener("submit", saveSettings);
  $("#enable-push").addEventListener("click", enablePush);
  $("#test-push").addEventListener("click", testPush);
  window.addEventListener("resize", drawChart);
  loadAll().catch((err) => alert(err.message));
}

document.addEventListener("DOMContentLoaded", init);
