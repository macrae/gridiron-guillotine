"use strict";
/* Live draft board client.
 *
 * The name index below is a verbatim port of gridiron/live/names.py. Both are
 * exercised by the same fixture (cmc, arsb, jsn, chase, brown, smith) so they
 * cannot drift apart -- the terminal and the browser must resolve a name
 * identically or the hot spare stops being a hot spare.
 *
 * The server is authoritative for everything that matters. The page holds only
 * the pool (for zero-latency search) and cosmetic UI state. A full repaint from
 * /state is always correct, which is what makes sleep/refresh/restart a non-event.
 */

// ---------------------------------------------------------------- name index

const SUFFIXES = new Set(["jr", "sr", "ii", "iii", "iv", "v"]);

function normalize(name) {
  if (!name) return "";
  const c = name.indexOf(",");
  if (c !== -1) name = name.slice(c + 1).trim() + " " + name.slice(0, c).trim();
  name = name.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  name = name.toLowerCase().replace(/['’]/g, "");
  name = name.replace(/[^a-z0-9]+/g, " ");
  const t = name.split(" ").filter(Boolean);
  while (t.length > 2 && SUFFIXES.has(t[t.length - 1])) t.pop();
  return t.join(" ");
}

function buildKeys(name) {
  const n = normalize(name);
  const p = n ? n.split(" ") : [];
  return {
    full: n.replace(/ /g, ""),
    last: p.length ? p[p.length - 1] : "",
    first: p.length ? p[0] : "",
    fl: p.length === 0 ? "" : (p.length === 1 ? p[0] : p[0][0] + p.slice(1).join("")),
    init: p.map(x => x[0]).join(""),
  };
}

const DECISIVE_RANK_GAP = 50;

function search(query, rows, limit = 6) {
  const q = normalize(query).replace(/ /g, "");
  if (!q) return [];
  const out = [];
  for (const r of rows) {
    const k = r._keys;
    let tier = null;
    if (q === k.full || q === k.init || q === k.fl || q === k.last) tier = 0;
    else if (k.last.startsWith(q)) tier = 100;
    else if (k.fl.startsWith(q) || k.init.startsWith(q)) tier = 200;
    else if (k.first.startsWith(q)) tier = 300;
    else if (k.full.includes(q)) tier = 400;
    if (tier !== null) out.push({ s: tier * 1000 + r.rank, r });
  }
  out.sort((a, b) => a.s - b.s);
  return out.slice(0, limit).map(x => Object.assign({ _score: x.s }, x.r));
}

function isDecisive(hits) {
  if (!hits.length) return false;
  if (hits.length === 1) return true;
  const a = hits[0]._score, b = hits[1]._score;
  if (Math.floor(a / 1000) < Math.floor(b / 1000)) return true;
  return (b - a) >= DECISIVE_RANK_GAP;
}

// ---------------------------------------------------------------- app state

const $ = id => document.getElementById(id);
let BOARD = [];             // full pool, with _keys precomputed
let BY_ID = new Map();
let STATE = null;
let VERSION = "";
let HITS = [];
let CURSOR = 0;
let EDITING = null;         // overall number being corrected, or null
let ANCHOR = null;          // forced overall for the next entry
let POLL_FAILS = 0;

// ---------------------------------------------------------------- transport

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    toast(data.error || `${path} failed`, data.conflict ? "bad" : "warn");
    return null;
  }
  applyState(data);
  return data;
}

async function poll() {
  try {
    const d = await getJSON(`/state?v=${VERSION}`);
    POLL_FAILS = 0;
    setConn("live");
    if (!d.unchanged) applyState(d);
  } catch (e) {
    POLL_FAILS++;
    setConn(POLL_FAILS > 3 ? "down" : "stale");
  }
}

function setConn(cls) {
  const el = $("conn");
  el.className = "pill " + cls;
  el.textContent = cls === "down" ? "!" : "•";
  el.title = { live: "connected", stale: "reconnecting", down: "server unreachable" }[cls];
}

// ---------------------------------------------------------------- rendering

function applyState(d) {
  STATE = d;
  VERSION = d.version;
  document.documentElement.style.setProperty("--accent", d.accent);
  render();
}

function render() {
  const d = STATE;
  if (!d) return;
  const mine = d.on_clock && d.on_clock.mine;
  document.body.classList.toggle("myturn", !!mine);

  $("league").textContent = d.league;
  $("clock").textContent = d.on_clock ? d.on_clock.label : "complete";
  $("turn-flag").textContent = mine ? "YOU'RE UP" : (d.on_clock ? `slot ${d.on_clock.slot}` : "");
  document.title = `${d.league.toUpperCase()} · ${d.on_clock ? d.on_clock.label : "done"}`;

  // turn strip
  if (d.my_next) {
    $("nextpick").innerHTML = d.my_next.until === 0
      ? `<b>on the clock</b>`
      : `your next <b>${d.my_next.label}</b> — ${d.my_next.until} away`;
    $("afterpick").textContent = d.my_after
      ? `then ${d.my_after.label} (${d.my_after.gap} apart)` : "";
  } else {
    $("nextpick").textContent = "no picks left";
    $("afterpick").textContent = "";
  }
  $("remaining").textContent = `${d.picks_remaining} picks left`;

  renderRecs(d);
  renderBest(d);
  renderSlots(d);
  renderLog(d);
  $("pickcount").textContent = `${d.picks_made}/${d.teams * d.rounds}`;
  $("urg").value = d.urgency;
  $("urgval").textContent = Number(d.urgency).toFixed(2);
}

const SERIOUS_INJ = new Set(["OUT", "INJURY_RESERVE", "SUSPENSION", "DOUBTFUL"]);

function chips(r) {
  let s = "";
  if (r.bye_clash) s += `<span class="chip bye">BYE ${r.bye}</span>`;
  // Nacua, McCaffrey, Chase, Jeanty, Love and Hall are all QUESTIONABLE in the
  // live pool -- chipping that is noise that teaches you to ignore chips. It
  // gets a dim dot instead; only genuinely-out players get a red chip.
  if (r.inj && SERIOUS_INJ.has(r.inj)) {
    s += `<span class="chip inj">${r.inj.replace(/_/g, " ")}</span>`;
  } else if (r.inj) {
    s += `<span class="dot q" title="${r.inj.replace(/_/g, " ").toLowerCase()}"></span>`;
  }
  return s;
}

function renderRecs(d) {
  const host = $("recs");
  host.innerHTML = "";
  if (d.done) { host.innerHTML = `<div id="done">draft complete</div>`; return; }
  d.recs.slice(0, 3).forEach((r, i) => {
    if (r.tier_break && i > 0) host.insertAdjacentHTML("beforeend", `<div class="tierbreak"></div>`);
    host.insertAdjacentHTML("beforeend", `
      <div class="card ${i === 0 ? "top" : ""}" data-id="${r.id}">
        <div class="rank">${i + 1}</div>
        <div>
          <div class="name">${esc(r.name)}${chips(r)}</div>
          <div class="pt">${r.pos} ${r.team} · proj ${r.proj.toFixed(0)} · adp ${r.adp.toFixed(1)} · bye ${r.bye}</div>
        </div>
        <div class="nums">
          <span class="score">${r.score.toFixed(1)}</span>
          VORP ${r.vorp.toFixed(0)} · <span class="vona">VONA ${r.vona.toFixed(1)}</span>
        </div>
        <div class="why">${esc(r.reason)}</div>
      </div>`);
  });

  const more = $("morerows");
  more.innerHTML = "";
  d.recs.slice(3, 8).forEach((r, i) => {
    if (r.tier_break) more.insertAdjacentHTML("beforeend", `<div class="tierbreak"></div>`);
    more.insertAdjacentHTML("beforeend", `
      <div class="mrow" data-id="${r.id}">
        <span class="mr">${i + 4}</span>
        <span class="mn">${esc(r.name)}${chips(r)}</span>
        <span class="mp">${r.pos} ${r.team}</span>
        <span class="ms">${r.score.toFixed(1)}</span>
      </div>`);
  });
}

function renderBest(d) {
  const host = $("bestrows");
  host.innerHTML = "";
  // The cliff column is the reasoning made visible: it is why a 76-VORP TE can
  // outrank three ~90-VORP RBs.
  const maxCliff = Math.max(1, ...Object.values(d.best_at).map(b => b.cliff));
  for (const pos of ["QB", "RB", "WR", "TE", "K", "DST"]) {
    const b = d.best_at[pos];
    if (!b || !b.name) continue;
    const hot = b.cliff >= 10 && b.cliff >= maxCliff * 0.6;
    host.insertAdjacentHTML("beforeend", `
      <div class="brow ${hot ? "hot" : ""}" data-pos="${pos}" data-id="${b.id}">
        <span class="bp">${pos}</span>
        <span class="bn">${esc(b.name)}</span>
        <span class="bc">${b.count}</span>
        <span class="bk">cliff ${b.cliff.toFixed(1)}</span>
      </div>`);
  }
}

function lastName(n) {
  const p = String(n || "").trim().split(/\s+/);
  return p.length ? p[p.length - 1] : "";
}

function renderSlots(d) {
  $("slots").innerHTML = d.roster_slots.map(s =>
    `<span class="slot ${s.filled ? "filled" : ""} ${s.slot === "BN" ? "bn" : ""}"
      title="${esc(s.name || (s.slot + " — empty"))}">${
        s.slot === "BN" ? esc(lastName(s.name)) : s.slot}</span>`
  ).join("") || `<span class="slot">empty</span>`;
}

function renderLog(d) {
  const host = $("log");
  const keep = host.scrollTop;
  // Merge real picks with gap placeholders, newest first. A gap is a pick slot
  // the clock has moved past without ever being filled -- those players are
  // still in the pool, silently corrupting every recommendation, so the hole
  // has to be visible and clickable.
  const rows = d.log.map(p => ({ overall: p.overall, pick: p }));
  for (const g of (d.gaps || [])) rows.push({ overall: g, pick: null });
  rows.sort((a, b) => b.overall - a.overall);

  host.innerHTML = rows.map(({ overall, pick: p }) => {
    if (!p) {
      return `<div class="lrow gap" data-overall="${overall}">
        <span class="ll">#${overall}</span>
        <span class="ln">missing — click to fill</span>
        <span class="lp">⚠</span></div>`;
    }
    return `<div class="lrow ${p.mine ? "mine" : ""} ${p.unknown ? "unknown" : ""} ${
      EDITING === p.overall ? "editing" : ""}" data-overall="${p.overall}">
      <span class="ll">${p.label.split(" ")[0]}${p.mine ? " ★" : ""}</span>
      <span class="ln">${esc(p.name)}</span>
      <span class="lp">${p.pos ? p.pos + " " + p.team : "—"}</span>
    </div>`;
  }).join("");
  host.scrollTop = keep;

  const n = (d.gaps || []).length;
  $("gapwarn").textContent = n ? `${n} missing` : "";
  $("gapwarn").hidden = !n;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------------------------------------------------------------- toasts

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function flashRow(overall) {
  const el = document.querySelector(`.lrow[data-overall="${overall}"]`);
  if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1200); }
}

// ---------------------------------------------------------------- dropdown

function draftedMap() {
  const m = new Map();
  for (const p of (STATE ? STATE.log : [])) if (p.id) m.set(p.id, p.label);
  return m;
}

function firstLive(hits, from = 0) {
  for (let i = from; i < hits.length; i++) if (!hits[i]._taken) return i;
  for (let i = 0; i < hits.length; i++) if (!hits[i]._taken) return i;
  return -1;
}

function refreshDrop() {
  const q = $("q").value;
  const drop = $("drop"), hint = $("hint");
  if (q.startsWith("/") || !q.trim()) {
    drop.hidden = true; HITS = [];
    hint.textContent = EDITING !== null
      ? `fixing pick ${EDITING} — type the correct player, Esc to cancel`
      : (ANCHOR !== null ? `next entry → overall #${ANCHOR}` : "");
    hint.className = EDITING !== null ? "warn" : "";
    return;
  }
  const gone = draftedMap();
  HITS = search(q, BOARD, 6);
  for (const h of HITS) h._taken = gone.get(h.id) || null;
  CURSOR = HITS.length && !HITS[0]._taken ? 0 : -1;

  if (!HITS.length) {
    drop.hidden = true;
    hint.textContent = `no match for "${q}"`;
    hint.className = "bad";
    return;
  }
  drop.hidden = false;
  drop.innerHTML = HITS.map((h, i) => `
    <div class="hit ${i === CURSOR ? "on" : ""} ${h._taken ? "gone" : ""}" data-i="${i}">
      <span class="nm">${esc(h.name)}</span>
      <span class="meta">${h._taken
        ? "taken " + h._taken
        : `${h.pos} ${h.team} · vorp ${h.vorp} · adp ${h.adp}`}</span>
    </div>`).join("");

  if (CURSOR === -1) {
    hint.textContent = HITS[0]._taken
      ? `${HITS[0].name} — already taken ${HITS[0]._taken}. ↓ to choose someone else`
      : "↓ to choose";
    hint.className = "warn";
    return;
  }
  // Decisiveness is judged on the players still available, not on the raw hits.
  const live = HITS.filter(h => !h._taken);
  if (isDecisive(live)) {
    hint.textContent = `Enter → ${HITS[CURSOR].name}`;
    hint.className = "";
  } else {
    hint.textContent = `ambiguous — pick one with ↓ then Enter`;
    hint.className = "warn";
  }
}

function moveCursor(delta) {
  if (!HITS.length) return;
  if (CURSOR < 0) {                      // nothing selected yet
    const first = firstLive(HITS);
    if (first === -1) return;
    CURSOR = first;
    paintCursor();
    return;
  }
  let i = CURSOR;
  for (let n = 0; n < HITS.length; n++) {
    i = (i + delta + HITS.length) % HITS.length;
    if (!HITS[i]._taken) break;
  }
  CURSOR = i;
  paintCursor();
}

function paintCursor() {
  [...document.querySelectorAll(".hit")].forEach((el, i) =>
    el.classList.toggle("on", i === CURSOR));
  if (CURSOR >= 0) {
    $("hint").textContent = `Enter → ${HITS[CURSOR].name}`;
    $("hint").className = "";
  }
}

function clearInput() {
  $("q").value = "";
  $("drop").hidden = true;
  HITS = []; CURSOR = 0;
  refreshDrop();
}

// ---------------------------------------------------------------- actions

async function commit(player) {
  if (!player) return;
  if (player._taken) {
    toast(`${player.name} was already taken at ${player._taken}`, "warn");
    return;
  }
  if (EDITING !== null) {
    const target = EDITING;
    EDITING = null;
    const d = await post("/correct", { overall: target, player_id: player.id });
    if (d) { toast(`pick ${target} → ${player.name}`, "good"); flashRow(target); }
  } else {
    const at = ANCHOR; ANCHOR = null;
    const d = await post("/pick", { player_id: player.id, overall: at });
    if (d) {
      const p = d.log[0];
      if (p && p.mine) toast(`${p.label} ${player.name} — yours`, "good");
      flashRow(p ? p.overall : null);
    }
  }
  clearInput();
}

async function doUndo() {
  const before = STATE && STATE.log[0];
  const d = await post("/undo", {});
  if (d && before) toast(`undid ${before.label} · ${before.name}`, "warn");
}

async function runCommand(raw) {
  const parts = raw.slice(1).trim().split(/\s+/);
  const cmd = (parts[0] || "").toLowerCase();
  const arg = parts[1];
  switch (cmd) {
    case "u": await doUndo(); break;
    case "s": await post("/skip", { overall: ANCHOR }); ANCHOR = null;
              toast("recorded unknown pick", "warn"); break;
    case "j":
      if (arg) { ANCHOR = parseInt(arg, 10); toast(`next entry → #${ANCHOR}`, "warn"); }
      break;
    case "t":
      if (arg) await openDrawer(parseInt(arg, 10));
      break;
    case "d":
      if (arg && confirm(`Delete pick ${arg}? Everything after it shifts back one.`))
        await post("/delete", { overall: parseInt(arg, 10) });
      break;
    case "l":
      if (arg) await post("/config", { urgency: parseFloat(arg) });
      break;
    case "slot":
      if (arg) { await post("/config", { my_slot: parseInt(arg, 10) });
                 toast(`your slot → ${arg}`, "good"); }
      break;
    case "r": await openDrawer(STATE.my_slot); break;
    case "h": case "?": toggleHelp(true); break;
    default: toast(`unknown command /${cmd}`, "warn");
  }
  clearInput();
}

async function openDrawer(slot) {
  if (!slot || slot < 1 || slot > STATE.teams) return toast("bad slot", "warn");
  const t = await getJSON(`/team?slot=${slot}`);
  $("drawertitle").textContent = `team ${slot}${t.mine ? " (you)" : ""}`;
  const counts = Object.entries(t.counts).map(([k, v]) => `${k}${v}`).join("  ") || "—";
  $("drawerbody").innerHTML =
    `<div class="shead">${esc(counts)}</div>` +
    (t.players.length
      ? t.players.map(p => `
        <div class="lrow"><span class="ll">${p.label.split(" ")[0]}</span>
        <span class="ln">${esc(p.name)}</span>
        <span class="lp">${p.pos ? p.pos + " " + p.team : "—"}</span></div>`).join("")
      : `<div class="shead">no picks yet</div>`);
  $("drawer").hidden = false;
}

function toggleHelp(on) { $("helpcard").hidden = !on; }

function closeOverlays() {
  $("drawer").hidden = true;
  toggleHelp(false);
}

// ---------------------------------------------------------------- keyboard

$("q").addEventListener("input", refreshDrop);

$("q").addEventListener("keydown", async e => {
  const q = $("q").value;
  if (e.key === "Escape") {
    e.preventDefault();
    if (EDITING !== null) { EDITING = null; toast("edit cancelled"); render(); }
    ANCHOR = null;
    clearInput(); closeOverlays();
    return;
  }
  if (e.key === "ArrowDown" || (e.key === "Tab" && !e.shiftKey && HITS.length)) {
    e.preventDefault(); moveCursor(1); return;
  }
  if (e.key === "ArrowUp" || (e.key === "Tab" && e.shiftKey && HITS.length)) {
    e.preventDefault(); moveCursor(-1); return;
  }
  if (e.key === " " && !q) {
    // A pick happened and you did not catch who. Record it, keep the clock right.
    e.preventDefault();
    await post("/skip", { overall: ANCHOR }); ANCHOR = null;
    toast("unknown pick recorded — clock advanced", "warn");
    return;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    if (!q.trim()) return;
    if (q.startsWith("/")) return runCommand(q);
    if (!HITS.length) { toast(`no match for "${q}"`, "bad"); return; }
    if (CURSOR < 0) {
      toast(HITS[0]._taken
        ? `${HITS[0].name} already taken ${HITS[0]._taken} — ↓ to choose another`
        : "choose a row with ↓", "warn");
      return;
    }
    // Refuse a blind Enter on an ambiguous query: silently committing the wrong
    // player is the one failure that actually loses a draft.
    if (!isDecisive(HITS) && CURSOR === 0 && !HITS[0]._picked) {
      const exact = HITS.findIndex(h => normalize(h.name) === normalize(q));
      if (exact === -1) {
        toast("ambiguous — choose with ↓", "warn");
        moveCursor(0);
        $("hint").textContent = "ambiguous — choose with ↓ then Enter";
        $("hint").className = "warn";
        HITS[0]._picked = true;   // a second Enter accepts the highlighted row
        return;
      }
      CURSOR = exact;
    }
    await commit(HITS[CURSOR]);
  }
});

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();          // else the browser's form undo eats it
    doUndo();
    return;
  }
  if (e.key === "Escape") { closeOverlays(); return; }
  // Keep the keyboard in the input no matter where focus wandered.
  if (!e.metaKey && !e.ctrlKey && !e.altKey && e.key.length === 1 &&
      document.activeElement !== $("q")) {
    $("q").focus();
  }
});

// ---------------------------------------------------------------- mouse

$("drop").addEventListener("click", e => {
  const el = e.target.closest(".hit");
  if (el) commit(HITS[parseInt(el.dataset.i, 10)]);
});

$("log").addEventListener("click", e => {
  const el = e.target.closest(".lrow");
  if (!el) return;
  const overall = parseInt(el.dataset.overall, 10);
  if (el.classList.contains("gap")) {
    // A hole has no pick to correct -- the next name typed gets appended there.
    ANCHOR = overall; EDITING = null;
    toast(`next entry fills #${overall}`, "warn");
  } else {
    EDITING = overall; ANCHOR = null;
  }
  $("q").focus();
  render();
  refreshDrop();
});

$("bestrows").addEventListener("click", e => {
  const el = e.target.closest(".brow");
  if (el) { $("q").value = ""; $("q").focus(); openPositionHint(el.dataset.pos); }
});

function openPositionHint(pos) {
  const b = STATE.best_at[pos];
  if (b && b.name) { $("q").value = b.name; refreshDrop(); }
}

$("recs").addEventListener("click", e => {
  const el = e.target.closest(".card");
  if (el) { const p = BY_ID.get(parseInt(el.dataset.id, 10)); if (p) commit(p); }
});
$("morerows").addEventListener("click", e => {
  const el = e.target.closest(".mrow");
  if (el) { const p = BY_ID.get(parseInt(el.dataset.id, 10)); if (p) commit(p); }
});

$("urg").addEventListener("change", e => post("/config", { urgency: parseFloat(e.target.value) }));
$("urg").addEventListener("input", e => { $("urgval").textContent = Number(e.target.value).toFixed(2); });
$("helpbtn").addEventListener("click", () => toggleHelp($("helpcard").hidden));
$("drawerclose").addEventListener("click", closeOverlays);

// A wake from sleep is indistinguishable from a normal tick, because /state
// always returns everything.
document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });

// ---------------------------------------------------------------- boot

(async function boot() {
  const b = await getJSON("/board");
  BOARD = b.players.map(p => Object.assign({ _keys: buildKeys(p.name) }, p));
  BY_ID = new Map(BOARD.map(p => [p.id, p]));
  await poll();
  setInterval(poll, 750);
  $("q").focus();
})();
