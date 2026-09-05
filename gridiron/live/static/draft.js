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
let TAB = localStorage.getItem("gg:tab") || "board";
let POSFILTER = localStorage.getItem("gg:pos") || "RB";
let CLAIM = false;          // next commit claims the player for my roster
// Players just marked from the position list. They stay rendered, struck
// through, so the rows beneath them do NOT shift up under a moving cursor --
// otherwise clicking quickly down the list marks the wrong players.
let STUCK = new Set();
let SELCELL = null;         // overall of the grid cell currently selected

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
  let d;
  try {
    d = await getJSON(`/state?v=${VERSION}`);
    POLL_FAILS = 0;
    setConn("live");
  } catch (e) {
    // ONLY network failures belong here. Wrapping the render in this catch too
    // made a rendering bug look like a connection problem: the page silently
    // stopped drawing and the only symptom was a dot changing colour.
    POLL_FAILS++;
    setConn(POLL_FAILS > 3 ? "down" : "stale");
    return;
  }
  if (d.unchanged) return;
  try {
    applyState(d);
  } catch (err) {
    console.error("render failed", err);
    banner(`display error: ${err.message} — the picks are safe on the server, `
           + `reload the page`);
    throw err;                       // keep it in the console, unswallowed
  }
}

function banner(msg) {
  let el = document.getElementById("errbar");
  if (!el) {
    el = document.createElement("div");
    el.id = "errbar";
    document.body.prepend(el);
  }
  el.textContent = msg;
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
  // The buttons say what they will do, so a mid-draft undo is never a guess.
  const ub = $("undob"), rb = $("redob");
  ub.disabled = !d.undo; rb.disabled = !d.redo;
  ub.title = d.undo ? `undo — ${d.undo}` : "nothing to undo";
  rb.title = d.redo ? `redo — ${d.redo}` : "nothing to redo";
  // Same-tab navigation: state is server-side, so leaving loses nothing.
  $("peers").innerHTML = (d.peers || []).map(p =>
    `<a class="peer" href="${esc(p.url)}" title="switch to ${esc(p.name)}">${esc(p.name)} &rarr;</a>`
  ).join("");

  // turn strip
  if (d.my_next) {
    $("nextpick").innerHTML = d.my_next.until === 0
      ? `<b>on the clock</b>`
      : `your next <b>${d.my_next.label}</b> — ${d.my_next.until} away`;
    $("afterpick").textContent = d.my_after
      ? `then ${d.my_after.label} (+${d.my_after.gap})` : "";
  } else {
    $("nextpick").textContent = "no picks left";
    $("afterpick").textContent = "";
  }
  $("remaining").textContent = `${d.picks_remaining} left`;

  renderRecs(d);
  renderBest(d);
  renderSlots(d);
  renderLog(d);
  renderRemaining(d);
  renderSnakeStrip(d);
  renderGrid(d);
  renderPos(d);
  renderMine(d);
  renderInjuries(d);
  renderNews(d);
  $("pickcount").textContent = `${d.picks_made}`;
  $("minecount").textContent = `${(d.log || []).filter(p => p.mine).length}`;
  $("urg").value = d.urgency;
  $("urgval").textContent = Number(d.urgency).toFixed(2);
}

const SERIOUS_INJ = new Set(["OUT", "INJURY_RESERVE", "SUSPENSION", "DOUBTFUL"]);

function lamp(sent) {
  if (!sent) return "";
  const s = typeof sent === "string" ? {level: sent, reason: ""} : sent;
  const tip = s.reason ? `${s.level.toUpperCase()} — ${s.reason}` +
                         (s.detail ? `\n\n${s.detail}` : "") : s.level;
  return `<span class="lamp ${s.level}" title="${esc(tip)}"></span>`;
}

function chips(r) {
  let s = "";
  if (r.bye_clash) s += `<span class="chip bye">BYE ${r.bye}</span>`;
  if ((r.news || []).some(n => n.risky)) s += `<span class="chip news">NEWS</span>`;
  const rep = r.injury;
  if (rep && rep.severity > 0) {
    s += `<span class="chip inj sev${rep.severity}" title="${esc(rep.note || "")}">`
       + `${esc((rep.type || rep.status || "").toUpperCase())}`
       + `${rep.weeks_out ? " ~" + rep.weeks_out + "wk" : ""}</span>`;
  }
  // Nacua, McCaffrey, Chase, Jeanty, Love and Hall are all QUESTIONABLE in the
  // live pool -- chipping that is noise that teaches you to ignore chips. It
  // gets a dim dot instead; only genuinely-out players get a red chip.
  if (!r.injury || !r.injury.severity) {
    // Only fall back to the bare status when the injury report has nothing
    // richer to say; otherwise the chip below carries it.
    if (r.inj && SERIOUS_INJ.has(r.inj)) {
      s += `<span class="chip inj">${String(r.inj).replace(/_/g, " ")}</span>`;
    } else if (r.inj) {
      s += `<span class="dot q" title="${String(r.inj).replace(/_/g, " ").toLowerCase()}"></span>`;
    }
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
          <div class="name">${lamp(r.sent)}${esc(r.name)}${chips(r)}</div>
          <div class="pt">${r.pos} ${r.team} · proj ${r.proj.toFixed(0)} · adp ${r.adp.toFixed(1)} · bye ${r.bye}</div>
        </div>
        <div class="nums">
          <span class="score">${r.score.toFixed(1)}</span>
          <span class="vorpline">VORP <b>${r.vorp.toFixed(0)}</b></span>
          <span class="vonaline">urg ${r.vona >= 0 ? "+" : ""}${r.vona.toFixed(0)} ·
            ${(r.survival * 100).toFixed(0)}% to last</span>
          <button class="mineb" type="button" title="claim for your roster">+ MINE</button>
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
        <span class="mn">${lamp(r.sent)}${esc(r.name)}${chips(r)}</span>
        <span class="mp">${r.pos} ${r.team}</span>
        <span class="ms">${r.score.toFixed(1)}</span>
        <button class="mineb" type="button" title="claim for your roster">+</button>
      </div>`);
  });
}

function renderRemaining(d) {
  const r = d.remaining || {};
  // Thin = fewer left than picks before your next turn, i.e. the position could
  // empty out before you get another shot at it.
  const until = d.my_next ? d.my_next.until : 0;
  $("remstrip").innerHTML = ["QB", "RB", "WR", "TE", "K", "DST"].map(p => {
    const n = r[p] || 0;
    return `<span class="${n <= Math.max(3, until) ? "thin" : ""}">${p} <b>${n}</b></span>`;
  }).join("");
}

function goneSet() {
  return new Set((STATE ? STATE.log : []).filter(p => p.id).map(p => p.id));
}

function cellClass(c, mySlot) {
  const cls = ["cel", c.st];
  if (c.m) cls.push("mine");
  if (c.s === mySlot) cls.push("seat");
  return cls.join(" ");
}

function cellTitle(c, teams) {
  const label = `${Math.floor((c.o - 1) / teams) + 1}.${String((c.o - 1) % teams + 1).padStart(2, "0")} (#${c.o})`;
  if (c.st === "taken") return `${label} · ${c.n}${c.p ? ` (${c.p} ${c.t})` : ""}${c.m ? " — YOURS" : ""}`;
  if (c.st === "unknown") return `${label} · unknown pick`;
  if (c.st === "gap") return `${label} · MISSING — click to fill`;
  if (c.st === "clock") return `${label} · on the clock`;
  return `${label} · upcoming`;
}

function renderSnakeStrip(d) {
  const g = d.grid && d.grid.rounds;
  if (!g || !d.on_clock) { $("snakestrip").hidden = true; return; }
  $("snakestrip").hidden = false;
  const rnd = d.on_clock.round;
  const row = g[rnd - 1] || [];
  $("snakeround").textContent = `R${rnd}`;
  $("snakecells").innerHTML = row.map(c =>
    `<span class="${cellClass(c, d.my_slot)}" title="${esc(cellTitle(c, d.teams))}"></span>`
  ).join("");
  const until = d.my_next ? d.my_next.until : null;
  $("snaketogo").textContent = until === null ? ""
    : until === 0 ? "YOU'RE UP" : `${until} to your pick`;
}

function renderGrid(d) {
  const g = d.grid && d.grid.rounds;
  if (!g) return;
  const head = `<div class="gcolhead"><span class="rlab"></span>` +
    Array.from({ length: d.teams }, (_, i) =>
      `<span class="c ${i + 1 === d.my_slot ? "me" : ""}">${i + 1}</span>`).join("") +
    `</div>`;
  $("gridtable").innerHTML = head + g.map((row, i) =>
    `<div class="grow"><span class="rlab">R${i + 1}</span>` +
    row.map(c =>
      `<span class="${cellClass(c, d.my_slot)}${c.s === d.my_slot ? " myseat" : ""}"
        data-o="${c.o}" data-st="${c.st}"
        title="${esc(cellTitle(c, d.teams))}"></span>`).join("") +
    `</div>`).join("");
  $("gridlegend").innerHTML =
    `<span class="lg" style="background:#2b6b3a"></span>taken` +
    `<span class="lg" style="background:var(--mine)"></span>yours` +
    `<span class="lg" style="background:var(--warn)"></span>on clock` +
    `<span class="lg" style="background:#7a2b2f"></span>missing` +
    `<span class="lg" style="background:#1b2230"></span>upcoming`;
  renderCellBar(d);
}

function renderCellBar(d) {
  const bar = $("cellbar");
  if (SELCELL === null) {
    bar.innerHTML = `<span class="hintlet">click a cell — a taken pick can be `
      + `corrected or removed, an empty one filled</span>`;
    return;
  }
  const cell = (d.grid.rounds.flat() || []).find(c => c.o === SELCELL);
  if (!cell) { SELCELL = null; return renderCellBar(d); }
  const lab = cellTitle(cell, d.teams).split(" · ")[0];
  if (cell.st === "taken" || cell.st === "unknown") {
    bar.innerHTML = `<span>${lab}</span><b>${esc(cell.n)}</b>`
      + (cell.m
          ? `<button data-act="release">not mine</button>`
          : `<button data-act="claim" class="good">claim as MINE</button>`)
      + `<button data-act="correct">correct</button>`
      + `<button data-act="remove" class="danger">remove</button>`
      + `<button data-act="cancel">esc</button>`;
  } else {
    bar.innerHTML = `<span>${lab}</span><span>empty</span>`
      + `<button data-act="fill">fill this pick</button>`
      + `<button data-act="cancel">esc</button>`;
  }
}

function renderPos(d) {
  const chips = ["QB", "RB", "WR", "TE", "K", "DST"];
  $("poschips").innerHTML = chips.map(p =>
    `<button class="pchip ${p === POSFILTER ? "on" : ""}" data-pos="${p}">${p} ${
      (d.remaining || {})[p] || 0}</button>`).join("");
  const gone = goneSet();
  const claimed = new Set((d.log || []).filter(p => p.mine && p.id).map(p => p.id));
  const rows = BOARD
    .filter(p => p.pos === POSFILTER && p.draftable
                 && (!gone.has(p.id) || STUCK.has(p.id)))
    .sort((a, b) => b.vorp - a.vorp)
    .slice(0, 60);
  let prev = null, n = 0;
  $("posrows").innerHTML = rows.map(p => {
    const isGone = gone.has(p.id);
    let out = "";
    if (!isGone) {
      if (prev !== null && (prev - p.vorp) >= 10) out += `<div class="tierbreak"></div>`;
      prev = p.vorp;
      n += 1;
    }
    const cls = isGone ? (claimed.has(p.id) ? "prow taken claimed" : "prow taken") : "prow";
    out += `<div class="${cls}" data-id="${p.id}">
      <span class="pr">${isGone ? "" : n}</span>
      <span class="pn">${lamp(p.sent)}${esc(p.name)}</span>
      <span class="pp">${isGone ? (claimed.has(p.id) ? "MINE" : "gone") : p.team}</span>
      <span class="pv">${p.vorp.toFixed(0)}</span>
      <span class="pa">${p.adp ? p.adp.toFixed(0) : "—"}</span>
      ${isGone ? "" : '<button class="mineb" type="button" title="claim">+</button>'}</div>`;
    return out;
  }).join("") || `<div class="shead">none left</div>`;
}

function renderMine(d) {
  const mine = (d.log || []).filter(p => p.mine).sort((a, b) => a.overall - b.overall);
  $("myrows").innerHTML = mine.map(p => {
    const full = BY_ID.get(p.id) || {};
    return `<div class="prow claimed" data-overall="${p.overall}">
      <span class="pr">${p.pos || "?"}</span>
      <span class="pn">${lamp(p.sent)}${esc(p.name)}</span>
      <span class="pp">${p.team || ""}</span>
      <span class="pv">${full.vorp != null ? full.vorp.toFixed(0) : ""}</span>
      <span class="pa">bye ${full.bye || "—"}</span></div>`;
  }).join("") || `<div class="shead">nothing claimed yet — type <b>+name</b> or shift-Enter</div>`;
}

const SEV_LABEL = {4: "sev", 3: "out", 2: "q", 1: "dtd"};

function renderInjuries(d) {
  const items = (d.risk || []).filter(x => !x.gone);
  $("injage").textContent = d.inj_age_h == null
    ? "not cached — run: python -m gridiron.live.injuries"
    : `${d.inj_age_h}h old · ${items.length} available players hurt`;
  $("injlist").innerHTML = items.map(x => {
    const body = [x.type, x.detail].filter(v => v && v !== "Not Specified").join(" ");
    const wk = x.weeks_out ? `~${x.weeks_out}wk` : "";
    return `<div class="irow sev${x.severity}" data-id="${x.id}">
      <span class="ipos">${x.pos}</span>
      <span class="iname">${esc(x.name)}</span>
      <span class="istat">${esc(x.status)}</span>
      <span class="ivorp">${x.vorp.toFixed(0)}</span>
      <div class="ibody">${esc(body)}${wk ? " · " + wk : ""}</div>
      ${x.note ? `<div class="inote">${esc(x.note)}</div>` : ""}
    </div>`;
  }).join("") || `<div class="shead">nobody available is hurt</div>`;
}

function renderNews(d) {
  const items = d.news_risky || [];
  const live = items.filter(x => !x.gone);
  const hurt = (d.risk || []).filter(x => !x.gone).length;
  $("newscount").textContent = hurt ? `${hurt}` : (live.length ? `${live.length}` : "");
  $("newsage").textContent = d.news_age_h == null
    ? "no news cached — run: python -m gridiron.live.news"
    : `${d.news_age_h}h old`;
  $("newsrisky").innerHTML = items.map(x =>
    `<div class="nrow ${x.gone ? "taken" : ""}" data-id="${x.id}">
       <span class="npos">${x.pos}</span>
       <span class="nname">${esc(x.name)}</span>
       <span class="nvorp">${x.vorp.toFixed(0)}</span>
       <div class="nhead">${esc(x.headline)}</div>
     </div>`).join("") || `<div class="shead">nothing flagged</div>`;
}

function showTab(name) {
  TAB = name;
  localStorage.setItem("gg:tab", name);
  for (const el of document.querySelectorAll(".tab"))
    el.classList.toggle("on", el.dataset.tab === name);
  for (const el of document.querySelectorAll(".tabpane"))
    el.hidden = el.id !== `t-${name}`;
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
        <button class="mineb" type="button" title="claim for your roster">+</button>
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
      <button class="rmb" data-rm="${p.overall}" title="remove — frees the player, leaves the slot empty">x</button>
    </div>`;
  }).join("");
  host.scrollTop = keep;

  const n = (d.gaps || []).length;
  $("gapwarn").textContent = n ? `\u26a0 ${n}` : "";
  $("gapwarn").title = n ? `${n} unfilled pick slot(s) -- those players are still counted as available` : "";
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

function queryText() {
  const raw = $("q").value;
  return raw.startsWith("+") ? raw.slice(1) : raw;
}

function refreshDrop() {
  const raw = $("q").value;
  const q = queryText();
  CLAIM = raw.startsWith("+");
  document.body.classList.toggle("claiming", CLAIM);
  const drop = $("drop"), hint = $("hint");
  $("q").classList.toggle("claiming", CLAIM);
  if (raw.startsWith("/") || !q.trim()) {
    drop.hidden = true; HITS = [];
    hint.textContent = EDITING !== null
      ? `fixing pick ${EDITING} — type the correct player, Esc to cancel`
      : (ANCHOR !== null ? `next entry → overall #${ANCHOR}`
                         : (CLAIM ? "claiming for your roster — type a name" : ""));
    hint.className = EDITING !== null ? "warn" : (CLAIM ? "good" : "");
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
    hint.textContent = CLAIM
      ? `Enter → CLAIM ${HITS[CURSOR].name} for your roster`
      : `Enter → ${HITS[CURSOR].name} gone   (shift-Enter or +name = mine)`;
    hint.className = CLAIM ? "good" : "";
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
    $("hint").textContent = (CLAIM ? "Enter → CLAIM " : "Enter → ") + HITS[CURSOR].name;
    $("hint").className = CLAIM ? "good" : "";
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
    const mine = CLAIM;
    const d = await post("/pick", { player_id: player.id, overall: at, mine });
    if (d) {
      const p = d.log[0];
      toast(mine ? `MINE — ${player.name}` : `gone — ${player.name}`,
            mine ? "good" : "");
      flashRow(p ? p.overall : null);
    }
  }
  CLAIM = false;
  clearInput();
}

async function doUndo() {
  const what = STATE && STATE.undo;
  if (!what) { toast("nothing to undo", "warn"); return; }
  const d = await post("/undo", {});
  if (d) toast(`undid — ${what}`, "warn");
}

async function doRedo() {
  const what = STATE && STATE.redo;
  if (!what) { toast("nothing to redo", "warn"); return; }
  const d = await post("/redo", {});
  if (d) toast(`redid — ${what}`, "good");
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

async function markPlayer(id, mine) {
  if (!BOARD.length) { toast("still loading the board…", "warn"); return; }
  const player = BY_ID.get(Number(id));
  if (!player) { toast("unknown player", "bad"); return; }
  const gone = goneSet();
  if (gone.has(player.id)) {
    // Already off the board -- flip ownership instead of erroring.
    await post("/mine", { player_id: player.id, mine });
    toast(mine ? `MINE — ${player.name}` : `released — ${player.name}`,
          mine ? "good" : "warn");
    return;
  }
  const d = await post("/pick", { player_id: player.id, mine });
  if (d) toast(mine ? `MINE — ${player.name}` : `gone — ${player.name}`,
               mine ? "good" : "");
}

// Any row or card carrying data-id: click marks gone, shift-click claims, and
// an explicit .mineb button claims regardless of modifier.
function wireMarkable(hostId) {
  $(hostId).addEventListener("click", e => {
    const btn = e.target.closest(".mineb");
    const el = e.target.closest("[data-id]");
    if (!el) return;
    markPlayer(el.dataset.id, !!btn || e.shiftKey);
  });
}

function toggleHelp(on) { $("helpcard").hidden = !on; }

function closeOverlays() {
  $("drawer").hidden = true;
  toggleHelp(false);
}

// ---------------------------------------------------------------- keyboard

$("q").addEventListener("input", refreshDrop);

$("q").addEventListener("keydown", async e => {
  const q = $("q").value;          // raw: '/' and '+' prefixes intact
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
    if (e.shiftKey) CLAIM = true;
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
    if (e.shiftKey) doRedo(); else doUndo();
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "y") {
    e.preventDefault(); doRedo(); return;
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

$("log").addEventListener("click", async e => {
  const rm = e.target.closest(".rmb");
  if (rm) {
    const overall = Number(rm.dataset.rm);
    const row = (STATE.log || []).find(p => p.overall === overall);
    const d = await post("/remove", { overall });
    if (d) toast(`removed ${row ? row.name : "pick"} — #${overall} is now empty`, "warn");
    return;
  }
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

wireMarkable("recs");
wireMarkable("morerows");
wireMarkable("bestrows");

document.getElementById("tabs").addEventListener("click", e => {
  const b = e.target.closest(".tab");
  if (b) { STUCK.clear(); showTab(b.dataset.tab); render(); $("q").focus(); }
});

$("poschips").addEventListener("click", e => {
  const b = e.target.closest(".pchip");
  if (!b) return;
  POSFILTER = b.dataset.pos;
  localStorage.setItem("gg:pos", POSFILTER);
  STUCK.clear();               // fresh list, no held places
  renderPos(STATE);
});

// A row click marks the player gone; shift-click claims them. This is the
// fast path when you can read a name off the draft board but cannot type it.
$("posrows").addEventListener("click", e => {
  const row = e.target.closest(".prow");
  if (!row || row.classList.contains("taken")) return;
  STUCK.add(Number(row.dataset.id));   // hold its place; rows below must not move
  markPlayer(row.dataset.id, !!e.target.closest(".mineb") || e.shiftKey);
});

$("myrows").addEventListener("click", async e => {
  const row = e.target.closest(".prow");
  if (!row) return;
  await post("/mine", { overall: parseInt(row.dataset.overall, 10), mine: false });
  toast("un-claimed", "warn");
});

$("undob").addEventListener("click", doUndo);
$("redob").addEventListener("click", doRedo);

$("gridtable").addEventListener("click", e => {
  const cell = e.target.closest(".cel");
  if (!cell) return;
  SELCELL = Number(cell.dataset.o);
  renderCellBar(STATE);
});

$("cellbar").addEventListener("click", async e => {
  const b = e.target.closest("button");
  if (!b || SELCELL === null) return;
  const overall = SELCELL;
  if (b.dataset.act === "cancel") { SELCELL = null; renderCellBar(STATE); return; }
  if (b.dataset.act === "fill") {
    ANCHOR = overall; SELCELL = null;
    showTab("board"); $("q").focus(); refreshDrop();
    toast(`next entry fills #${overall}`, "warn");
    return;
  }
  if (b.dataset.act === "claim" || b.dataset.act === "release") {
    const mine = b.dataset.act === "claim";
    const cell = STATE.grid.rounds.flat().find(c => c.o === overall);
    const d = await post("/mine", { overall, mine });
    if (d) toast(`${mine ? "MINE" : "released"} — ${cell ? cell.n : "pick"}`,
                 mine ? "good" : "warn");
    return;
  }
  if (b.dataset.act === "correct") {
    EDITING = overall; SELCELL = null;
    showTab("board"); $("q").focus(); refreshDrop();
    toast(`type the correct player for #${overall}`, "warn");
    return;
  }
  if (b.dataset.act === "remove") {
    const cell = STATE.grid.rounds.flat().find(c => c.o === overall);
    const who = cell ? cell.n : "pick";
    const d = await post("/remove", { overall });
    if (d) {
      SELCELL = null;
      // The slot stays; it becomes a hole you can refill. Nothing renumbers.
      toast(`removed ${who} — #${overall} is now empty, ${who} is back on the board`,
            "warn");
    }
  }
});

$("urg").addEventListener("change", e => post("/config", { urgency: parseFloat(e.target.value) }));
$("urg").addEventListener("input", e => { $("urgval").textContent = Number(e.target.value).toFixed(2); });
// Two-step, not a modal: a modal is slow under a clock, and a bare click on a
// destructive control is too easy. The button becomes its own confirmation and
// reverts after 4s if you walk away from it.
let RESET_ARMED = null;
$("resetbtn").addEventListener("click", async () => {
  const b = $("resetbtn");
  if (!RESET_ARMED) {
    RESET_ARMED = setTimeout(() => {
      RESET_ARMED = null; b.textContent = "reset"; b.classList.remove("armed");
    }, 4000);
    b.textContent = "erase all picks?";
    b.classList.add("armed");
    return;
  }
  clearTimeout(RESET_ARMED); RESET_ARMED = null;
  b.textContent = "reset"; b.classList.remove("armed");
  const n = STATE ? STATE.picks_made : 0;
  const d = await post("/reset", {});
  if (d) {
    STUCK.clear(); SELCELL = null; EDITING = null; ANCHOR = null;
    clearInput();
    toast(`draft cleared — ${n} picks erased. \u21b6 undo restores them`, "warn");
  }
});

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
  showTab(TAB);
  setInterval(poll, 750);
  $("q").focus();
})();
