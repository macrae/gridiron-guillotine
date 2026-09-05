"use strict";
/* Research dossiers.
 *
 * Runs in two places from one copy: the standalone /research page, and a tab on
 * the draft board. Everything is inside an IIFE because the board already owns
 * `$`, `render` and `esc` at global scope -- loading this file alongside
 * draft.js without the wrapper silently redefines all three.
 *
 * On the board the payload is ~1MB, so it is fetched once, lazily, the first
 * time the tab is opened -- never at page load, and never again per pick.
 * Drafted state is instead pushed in from the board via syncGone().
 */
(function () {

const $ = id => document.getElementById(id);
const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"];
let DATA = null;
let POS = new Set();

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

let BOOTED = false;

async function boot() {
  if (BOOTED) return;
  BOOTED = true;
  $("rlist").innerHTML = `<div class="shead">loading dossiers…</div>`;
  const r = await fetch("/research-data", { cache: "no-store" });
  DATA = await r.json();
  // The board sets its own accent from league config; only the standalone page
  // needs this, and overwriting it there would repaint the live header.
  if (!ON_BOARD) document.documentElement.style.setProperty("--accent", DATA.accent);
  if ($("rleague")) $("rleague").textContent = DATA.league;
  if ($("rage")) $("rage").textContent = DATA.dossier_age_h == null
    ? "no dossiers — run: python -m gridiron.live.dossier"
    : `dossiers ${DATA.dossier_age_h}h old · ${DATA.players.filter(p => p.dossier).length} of ${DATA.players.length}`;
  $("rpos").innerHTML = POSITIONS.map(p =>
    `<button class="pfilt" data-pos="${p}">${p}</button>`).join("");
  render();
}

function scoreFor(p, mode) {
  if (mode === "adp") return p.adp || 9999;
  if (mode === "risk") return -(p.injury ? p.injury.severity : 0);
  // "value vs ADP": how much later the market takes him than his value implies
  if (mode === "value") return -(p.adp_rank - p.vorp_rank);
  return -p.vorp;
}

function render() {
  if (!DATA) return;
  const q = $("rq").value.trim().toLowerCase();
  const hideGone = $("rhide").checked;
  const riskOnly = $("rrisk").checked;
  const mode = $("rsort").value;

  let rows = DATA.players.filter(p => {
    if (hideGone && p.gone) return false;
    if (riskOnly && !(p.injury && p.injury.severity > 0)) return false;
    if (POS.size && !POS.has(p.pos)) return false;
    if (q && !p.name.toLowerCase().includes(q)) return false;
    return true;
  });
  rows.sort((a, b) => scoreFor(a, mode) - scoreFor(b, mode));

  $("rcount").textContent = `${rows.length} players`;
  $("rlist").innerHTML = rows.map((p, i) => card(p, i + 1)).join("")
    || `<div class="shead">nothing matches</div>`;
}

function card(p, n) {
  const d = p.dossier || {};
  const inj = p.injury;
  const body = inj ? [inj.type, inj.detail].filter(v => v && v !== "Not Specified").join(" ") : "";
  return `<article class="dos ${p.gone ? "gone" : ""}">
    <div class="dhead">
      <span class="rank">${n}</span>
      <span class="nm">${p.sent ? `<span class="lamp ${p.sent.level}" title="${
        esc(p.sent.level.toUpperCase() + " — " + p.sent.reason)}"></span>` : ""}${esc(p.name)}</span>
      <span class="meta">${p.pos} ${p.team} · bye ${p.bye}${p.gone ? " · DRAFTED" : ""}</span>
      <span class="dnums">
        <span><span class="lbl">vorp</span><b>${p.vorp.toFixed(0)}</b></span>
        <span><span class="lbl">proj</span>${p.proj.toFixed(0)}</span>
        <span><span class="lbl">adp</span>${p.adp ? p.adp.toFixed(1) : "—"}</span>
        <span><span class="lbl">val vs adp</span>${p.adp_rank - p.vorp_rank >= 0 ? "+" : ""}${p.adp_rank - p.vorp_rank}</span>
      </span>
    </div>
    ${inj && inj.severity > 0 ? `
      <div class="dinj sev${inj.severity}">
        <div class="top">${esc(inj.status)}${body ? " · " + esc(body) : ""}${
          inj.weeks_out ? " · ~" + inj.weeks_out + "wk" : ""}</div>
        ${inj.note ? `<div class="note">${esc(inj.note)}</div>` : ""}
      </div>` : ""}
    ${d.scouting ? `
      <div class="dsec scout">
        <h4>scouting · ${esc(d.scouting.published)}</h4>
        <p>${esc(d.scouting.headline)}</p>
        ${d.scouting.story ? `<button class="more" data-story="${esc(p.id)}">read the full report</button>
          <p class="story" id="story-${p.id}" hidden>${esc(d.scouting.story)}</p>` : ""}
      </div>` : ""}
    ${d.outlook ? `
      <div class="dsec outlook"><h4>season outlook</h4><p>${esc(d.outlook)}</p></div>` : ""}
    ${(d.news || []).length ? `
      <div class="dsec dnews"><h4>news</h4>
        ${d.news.slice(0, 5).map(x =>
          `<a href="${esc(x.link)}" target="_blank" rel="noopener">
             <span class="dt">${esc(x.published)}</span>${esc(x.headline)}</a>`).join("")}
      </div>` : ""}
    ${d.stats && d.stats["Regular Season"] ? `
      <div class="dstats">${Object.entries(d.stats["Regular Season"]).slice(0, 9)
        .map(([k, v]) => `<span><b>${esc(k)}</b> ${esc(v)}</span>`).join("")}</div>` : ""}
  </article>`;
}

$("rq").addEventListener("input", render);
$("rhide").addEventListener("change", render);
$("rrisk").addEventListener("change", render);
$("rsort").addEventListener("change", render);
$("rpos").addEventListener("click", e => {
  const b = e.target.closest(".pfilt");
  if (!b) return;
  const p = b.dataset.pos;
  POS.has(p) ? POS.delete(p) : POS.add(p);
  b.classList.toggle("on", POS.has(p));
  render();
});
$("rlist").addEventListener("click", e => {
  const b = e.target.closest(".more");
  if (!b) return;
  const el = document.getElementById(`story-${b.dataset.story}`);
  if (el) { el.hidden = !el.hidden; b.textContent = el.hidden ? "read the full report" : "hide"; }
});

// ---- wiring -----------------------------------------------------------
// The board owns the accent and boots this lazily; the standalone page boots
// immediately and paints its own.
const ON_BOARD = document.documentElement.classList.contains("boardpage");

if (ON_BOARD) {
  //: Called by draft.js when the research tab is opened, and again whenever the
  //: pick log changes while it is visible. Drafted state is pushed rather than
  //: refetched -- a 1MB round trip per pick would be absurd.
  window.GGResearch = {
    open() { boot().then(render); },
    syncGone(goneIds) {
      if (!DATA) return;
      let changed = false;
      for (const p of DATA.players) {
        const g = goneIds.has(p.id);
        if (g !== p.gone) { p.gone = g; changed = true; }
      }
      if (changed) render();
    },
  };
} else {
  boot();
}

})();
