"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => "$" + Math.round(n).toLocaleString("en-US");

const S = { scenarios: [], difficulty: "tough", view: null, busy: false, prevCoach: null, debrief: null };

const KIND = { money: "Negotiation", scam: "Scam defense" };
const METERS = {
  money: [["anchoring", "Anchoring"], ["confidence", "Confidence"], ["justification", "Justification"], ["info_gathering", "Info gathering"]],
  scam: [["skepticism", "Skepticism"], ["verification", "Verification"], ["info_protection", "Info protection"]],
};
const PURPOSE = { coach: "Coach scores your move", counterpart: "Opponent replies", debrief: "Full debrief", custom_scenario: "Builds hidden hand" };
const ACTION_TEXT = { accept: "I accept your offer.", walk: "I'm going to walk away from this.", hangup: "(You hang up the phone.)" };
const OUTCOME = {
  deal: (r) => `You settled at ${fmt(r.result)}.`,
  final_stood: (r) => `Their final offer of ${fmt(r.result)} stood.`,
  they_walked: () => "They walked away from the table.",
  user_walked: (r) => `You walked away. The best offer you saw was ${fmt(r.best_offer)}.`,
};

// ---------- helpers ----------

async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 6000);
}

function show(screen) {
  $("#pick").classList.toggle("hidden", screen !== "pick");
  $("#spar").classList.toggle("hidden", screen !== "spar");
  window.scrollTo(0, 0);
}

function setBusy(busy) {
  S.busy = busy;
  document.querySelectorAll("#send, #quick button, .scenario, #custom-start").forEach((b) => (b.disabled = busy));
}

// ---------- pick screen ----------

async function init() {
  try {
    const data = await api("/api/scenarios");
    S.scenarios = data.scenarios;
    renderPowered(data.models, data.mock);
    renderCards();
  } catch (e) {
    toast(e.message);
  }
}

function renderPowered(models, mock) {
  const short = (id) => esc((id || "?").split("/").pop());
  $("#powered").innerHTML =
    (mock ? '<span class="chip mock">Mock mode</span>' : "") +
    '<span class="chip">Nebius Token Factory</span>' +
    `<span class="chip" title="${esc(models.nano)}">Nano: ${short(models.nano)}</span>` +
    `<span class="chip" title="${esc(models.ultra)}">Ultra: ${short(models.ultra)}</span>`;
}

function renderCards() {
  $("#cards").innerHTML = S.scenarios.map((s) => `
    <button class="scenario" type="button" data-id="${esc(s.id)}">
      <span class="kind">${KIND[s.type]}</span>
      <h2>${esc(s.title)}</h2>
      <p>${esc(s.blurb)}</p>
      <span class="aud">For ${esc(s.audience.charAt(0).toLowerCase() + s.audience.slice(1))}</span>
    </button>`).join("");
}

async function start(id, situation) {
  if (S.busy) return;
  setBusy(true);
  const customBtn = $("#custom-start");
  if (id === "custom") customBtn.textContent = "Ultra is building their hidden hand...";
  try {
    const view = await api("/api/session", { scenario_id: id, difficulty: S.difficulty, situation });
    loadView(view);
    show("spar");
    $("#input").focus();
  } catch (e) {
    toast(e.message);
  } finally {
    customBtn.textContent = "Build my scenario";
    setBusy(false);
  }
}

// ---------- spar screen ----------

function loadView(view) {
  S.view = view;
  S.debrief = null;
  const sc = view.scenario;
  $("#who-name").textContent = sc.counterpart_name;
  $("#who-role").textContent = `${sc.counterpart_role} · ${view.difficulty}`;
  $("#hand").classList.remove("flipped");
  $("#hand-front").textContent = "";
  $("#reveal").classList.add("hidden");
  $("#reveal").innerHTML = "";
  $("#composer").classList.toggle("hidden", view.state.closed);
  $("#input").placeholder = sc.type === "scam" ? "What do you say to the caller?" : `Reply to ${sc.counterpart_name}...`;
  S.prevCoach = view.coach.length > 1 ? view.coach[view.coach.length - 2] : null;
  renderCoach(view.coach[view.coach.length - 1] || null);
  renderChat();
  renderTable(false);
  renderQuick();
  renderCalls(view.calls);
  if (view.reveal) showReveal(view.reveal);
}

function renderTable(bump) {
  const { scenario: sc, state } = S.view;
  const el = $("#on-table");
  if (sc.type === "money") {
    el.innerHTML = `<div class="lbl">On the table${state.final_made ? '<span class="badge">Final</span>' : ""}</div>
      <div class="amt">${fmt(state.current)}</div>`;
  } else {
    el.innerHTML = `<div class="lbl">At risk</div><div class="amt">${fmt(sc.amount || 0)}</div>`;
  }
  if (bump) {
    const amt = $(".amt", el);
    amt.classList.add("bump");
    setTimeout(() => amt.classList.remove("bump"), 300);
  }
}

function renderQuick() {
  const { scenario: sc, state } = S.view;
  $("#quick").innerHTML = sc.type === "money"
    ? `<button type="button" class="btn good" data-action="accept">Accept ${fmt(state.current)}</button>
       <button type="button" class="btn danger" data-action="walk">Walk away</button>`
    : '<button type="button" class="btn danger" data-action="hangup">Hang up</button>';
}

function annotationHTML(turn) {
  const a = S.debrief && S.debrief.annotations.find((x) => x.turn === turn);
  if (!a) return "";
  const tp = S.debrief.turning_point === turn;
  return `<div class="annot ${esc(a.verdict)} ${tp ? "turning" : ""}">
    <span class="verdict">${tp ? "Turning point · " : ""}${esc(a.verdict)}</span>
    <div>${esc(a.note)}</div>
    ${a.better_line ? `<div class="better"><b>Try:</b> "${esc(a.better_line)}"</div>` : ""}
    <button type="button" class="btn" data-replay="${turn}">Replay from turn ${turn}</button>
  </div>`;
}

function renderChat(typing = false) {
  const { scenario: sc, messages } = S.view;
  let lastOffer = null;
  const html = messages.map((m) => {
    if (m.role === "them") {
      let offer = "";
      if (sc.type === "money" && m.offer != null && m.offer !== lastOffer) {
        offer = `<span class="offer">${fmt(m.offer)} on the table</span>`;
        lastOffer = m.offer;
      }
      return `<div class="msg them"><div class="bubble">${esc(m.text)}</div>
        <div class="meta"><span>${esc(sc.counterpart_name)}</span>${offer}</div></div>`;
    }
    return `<div class="msg user ${m.action ? "action" : ""}"><div class="bubble">${esc(m.text)}</div>
      <div class="meta"><span>You · turn ${m.turn}</span></div>${annotationHTML(m.turn)}</div>`;
  });
  if (typing) {
    html.push(`<div class="msg them typing"><div class="bubble">${esc(sc.counterpart_name)} is typing<span class="dots"></span></div></div>`);
  }
  $("#chat").innerHTML = html.join("");
}

function renderCoach(c) {
  const type = S.view.scenario.type;
  const prev = S.prevCoach;
  $("#meters").innerHTML = METERS[type].map(([key, label]) => {
    const v = c ? c[key] : null;
    const d = c && prev ? v - prev[key] : 0;
    const cls = v == null ? "" : v < 4 ? "low" : v < 7 ? "mid" : "";
    const delta = d ? `<span class="delta ${d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${d}</span>` : "";
    return `<div class="meter ${cls}"><div class="row"><span>${label}</span><span>${v == null ? "-" : v + "/10"}${delta}</span></div>
      <div class="bar"><span data-w="${(v || 0) * 10}"></span></div></div>`;
  }).join("");
  requestAnimationFrame(() => document.querySelectorAll("#meters .bar span").forEach((s) => (s.style.width = s.dataset.w + "%")));

  const tip = $("#tip");
  if (c && c.tip) {
    tip.textContent = c.tip;
    tip.classList.remove("fresh");
    void tip.offsetWidth;
    tip.classList.add("fresh");
  } else if (!c) {
    tip.textContent = "Make your first move. The coach scores every message you send.";
  }

  let lev = "";
  if (c && type === "money") {
    lev = `Leverage this turn <b>×${Number(c.leverage).toFixed(1)}</b>. Your move sets how far the opponent is allowed to move.`;
    if (c.user_ask) lev += ` The coach heard you ask for <b>${fmt(c.user_ask)}</b>.`;
  } else if (c && type === "scam" && c.called_out.length) {
    lev = `You called out: <b>${c.called_out.map(esc).join(", ")}</b>`;
  }
  $("#leverage").innerHTML = lev;
}

function renderCalls(calls) {
  S.view.calls = calls;
  const by = (tier) => calls.filter((c) => c.tier === tier);
  const avg = (list) => (list.length ? Math.round(list.reduce((a, c) => a + c.ms, 0) / list.length) : 0);
  const sum = (key) => calls.reduce((a, c) => a + c[key], 0);
  const money4 = (n) => "$" + (n < 0.01 ? n.toFixed(5) : n.toFixed(3));
  const nano = by("nano");
  const ultra = by("ultra");
  const cost = sum("cost");
  const allUltra = sum("ultra_cost");
  const save = allUltra > 0 ? Math.round(100 * (1 - cost / allUltra)) : 0;
  $("#router-summary").innerHTML = calls.length
    ? `<b>${calls.length}</b> calls · <span class="tier nano">Nano</span> ×${nano.length} avg ${avg(nano)}ms · <span class="tier ultra">Ultra</span> ×${ultra.length} avg ${avg(ultra)}ms<br>
       Est. cost <b>${money4(cost)}</b> vs <b>${money4(allUltra)}</b> if everything ran on Ultra ${save > 0 ? `<span class="save">−${save}%</span>` : ""}`
    : "Every model call shows up here: which Nemotron tier ran it, how long it took, and what it cost.";
  $("#calls").innerHTML = calls.slice().reverse().map((c) => `
    <li><span class="tier ${esc(c.tier)}">${esc(c.tier)}</span>
      <span class="purpose" title="${esc(c.model)}">${esc(PURPOSE[c.purpose] || c.purpose)}</span>
      <span class="num">${c.ms}ms · ${c.prompt_tokens + c.completion_tokens} tok</span></li>`).join("");
}

// ---------- turns ----------

async function sendTurn(text, action) {
  const view = S.view;
  if (S.busy || !view || view.state.closed) return;
  if (!text && !action) return;
  setBusy(true);
  const turn = view.state.turn + 1;
  view.messages.push({ role: "user", text: text || ACTION_TEXT[action], turn, action: text ? null : action });
  $("#input").value = "";
  renderChat(action !== "hangup");
  scrollChat();
  let failed = false;
  try {
    const res = await fetch("/api/turn", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: view.session_id, text, action }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line && handleEvent(JSON.parse(line)) === "error") failed = true;
      }
    }
  } catch (e) {
    toast(e.message);
    failed = true;
  }
  if (failed) {
    view.messages = view.messages.filter((m) => m.turn <= view.state.turn);
    view.coach = view.coach.filter((c) => c.turn <= view.state.turn);
    $("#input").value = text;
  }
  if (!view.state.closed) renderChat();
  setBusy(false);
  if (!view.state.closed) $("#input").focus();
}

function handleEvent(ev) {
  const view = S.view;
  switch (ev.type) {
    case "coach":
      S.prevCoach = view.coach[view.coach.length - 1] || null;
      view.coach.push({ turn: ev.turn, ...ev.coach });
      renderCoach(ev.coach);
      break;
    case "reply":
      view.messages.push(ev.message);
      view.state = ev.state;
      renderChat();
      renderTable(true);
      renderQuick();
      setBusy(true);
      scrollChat();
      break;
    case "closed":
      view.state = ev.state;
      view.reveal = ev.reveal;
      renderChat();
      showReveal(ev.reveal);
      break;
    case "calls":
      renderCalls(ev.calls);
      break;
    case "error":
      toast(ev.message);
      return "error";
  }
  return null;
}

function scrollChat() {
  const last = $("#chat").lastElementChild;
  if (last) last.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------- reveal & debrief ----------

function showReveal(rv) {
  $("#composer").classList.add("hidden");
  $("#hand-front").textContent = rv.type === "money" ? fmt(rv.walk_away) : "SCAM";
  setTimeout(() => $("#hand").classList.add("flipped"), 150);

  let body;
  if (rv.type === "money") {
    const left = rv.left_on_table;
    const got = rv.result != null ? rv.result : rv.best_offer;
    const pct = Math.max(0, Math.min(100, rv.captured_pct));
    body = `
      <div class="kicker">The cards are down · their max was ${fmt(rv.walk_away)}</div>
      <div class="big ${left > 0 ? "bad" : "good"}">${left > 0 ? `${fmt(left)} left on the table` : "You got everything they had."}</div>
      <p>${esc(OUTCOME[rv.outcome] ? OUTCOME[rv.outcome](rv) : "")} You captured <b>${rv.captured_pct}%</b> of the room they really had.</p>
      <div class="range" aria-hidden="true">
        <div class="fill" style="width:0" data-w="${pct}"></div>
        <span class="tick" style="left:0;transform:none">Opening <b>${fmt(rv.opening)}</b></span>
        <span class="tick" style="left:100%;transform:translateX(-100%)">Their max <b>${fmt(rv.walk_away)}</b></span>
        <span class="pin" style="left:${pct}%"></span>
        <span class="tick low" style="left:${pct}%">${rv.result != null ? "You" : "Best offer"} <b>${fmt(got)}</b></span>
      </div>
      <p class="story">${esc(rv.hidden_story)}</p>`;
  } else {
    const flags = rv.red_flags.map((f) => {
      const [cls, label] = f.used ? (f.spotted ? ["spotted", "Spotted"] : ["missed", "Missed"]) : ["unused", "Not used"];
      return `<li><span class="st ${cls}">${label}</span><span>${esc(f.label)}</span></li>`;
    }).join("");
    const safe = rv.outcome === "safe";
    body = `
      <div class="kicker">The cards are down · it was a scam</div>
      <div class="big ${safe ? "good" : "bad"}">${safe ? "You hung up on a scammer." : `You just lost ${fmt(rv.amount)}.`}</div>
      <p class="story">${esc(rv.hidden_story)}</p>
      <ul class="flags">${flags}</ul>
      ${rv.shared ? `<p>You shared personal details <b>${rv.shared}</b> time${rv.shared > 1 ? "s" : ""}. Scammers reuse that.</p>` : ""}`;
  }
  const el = $("#reveal");
  el.innerHTML = `${body}
    <div class="debrief" id="debrief"><p class="loading">Nemotron Ultra is reviewing every turn...</p></div>
    <div class="reveal-actions">
      <button type="button" class="btn primary hidden" id="replay-tp"></button>
      <button type="button" class="btn" data-replay="1">Try again from the start</button>
      <button type="button" class="btn" id="new-scenario">New scenario</button>
    </div>`;
  el.classList.remove("hidden");
  requestAnimationFrame(() => {
    const fill = $(".range .fill", el);
    if (fill) fill.style.width = fill.dataset.w + "%";
  });
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  loadDebrief();
}

async function loadDebrief() {
  const view = S.view;
  try {
    const d = await api("/api/debrief", { session_id: view.session_id });
    if (S.view !== view) return;
    S.debrief = d.debrief;
    renderCalls(d.calls);
    const db = d.debrief;
    $("#debrief").innerHTML = `
      <h4>${esc(db.headline)}</h4>
      ${db.lessons.length ? `<ul>${db.lessons.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : ""}
      <p class="loading">Turn-by-turn notes are pinned to your messages below.</p>`;
    if (db.turning_point) {
      const btn = $("#replay-tp");
      btn.textContent = `Replay from the turning point (turn ${db.turning_point})`;
      btn.dataset.replay = db.turning_point;
      btn.classList.remove("hidden");
    }
    renderChat();
  } catch (e) {
    $("#debrief").innerHTML = `<p class="loading">Debrief unavailable: ${esc(e.message)}</p>`;
  }
}

async function replay(turn) {
  if (S.busy) return;
  const ann = S.debrief && S.debrief.annotations.find((a) => a.turn === turn);
  setBusy(true);
  try {
    const view = await api("/api/replay", { session_id: S.view.session_id, turn });
    loadView(view);
    window.scrollTo({ top: 0, behavior: "smooth" });
    const input = $("#input");
    input.value = ann && ann.better_line ? ann.better_line : "";
    input.focus();
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
  }
}

// ---------- wiring ----------

document.querySelectorAll(".difficulty button").forEach((b) => b.addEventListener("click", () => {
  S.difficulty = b.dataset.diff;
  document.querySelectorAll(".difficulty button").forEach((x) => {
    x.classList.toggle("active", x === b);
    x.setAttribute("aria-checked", String(x === b));
  });
}));
$("#cards").addEventListener("click", (e) => {
  const card = e.target.closest(".scenario");
  if (card) start(card.dataset.id);
});
$("#custom-start").addEventListener("click", () => start("custom", $("#situation").value));
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  sendTurn($("#input").value.trim(), null);
});
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});
$("#quick").addEventListener("click", (e) => {
  const b = e.target.closest("[data-action]");
  if (b) sendTurn("", b.dataset.action);
});
$("#spar").addEventListener("click", (e) => {
  const r = e.target.closest("[data-replay]");
  if (r) return replay(Number(r.dataset.replay));
  if (e.target.closest("#new-scenario")) show("pick");
});
$("#home").addEventListener("click", () => show("pick"));

init();
