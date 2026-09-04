"""Local draft server: stdlib http.server, no dependencies.

Deliberately boring. The dominant failure mode on draft morning is an install
that doesn't work, and this has nothing to install. It ships with the
interpreter that already runs the engine.

Every response is built from scratch (measured 1.28 ms over 542 players, a 0.2%
duty cycle at a 750 ms poll). Nothing is cached, so there is nothing to
invalidate and undo is simply "drop a pick and recompute". Every mutation
returns the complete new state, so the acting client repaints immediately
instead of waiting for its next poll.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import snake, vona
from .pool import PlayerPool, load_pool
from .recommend import DEFAULT_URGENCY, recommend
from .store import PickConflict, PickStore
from .vorp import LeagueConfig, compute_vorp, roster_counts, unfilled_mandatory

STATIC = Path(__file__).parent / "static"
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")

# A visible break in the list where the score drop says "these are equivalent,
# then it falls off". Tuned against the real 2026 board, where RB6-RB14 sit
# inside 19 VORP and the gaps above RB5 are 13-26.
TIER_GAP = 10.0

# Standard Yahoo starting lineup, in display order.
SLOT_ORDER = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DST")
FLEX_ELIGIBLE = ("RB", "WR", "TE")


class DraftSession:
    """Everything one league needs. Guarded by a single lock."""

    def __init__(self, league: str, pool: PlayerPool, config: LeagueConfig,
                 store: PickStore, accent: str = "#c0392b",
                 peers: list[dict] | None = None):
        self.league = league
        #: Other leagues running right now, as [{"name", "url"}]. Purely a
        #: navigation convenience -- the processes stay fully independent, which
        #: is what keeps one crashing from touching the other.
        self.peers = peers or []
        self.pool = pool
        self.config = config
        self.store = store
        self.accent = accent
        self.urgency = DEFAULT_URGENCY
        # Version carries a per-process boot id. A bare counter restarts at 0,
        # so after a server restart a client holding version=5 would send ?v=5,
        # the server would compare 0 <= 5, reply "unchanged", and the page would
        # silently freeze forever. String compare makes a restart a guaranteed
        # full repaint.
        self.boot = secrets.token_hex(4)
        self.counter = 0
        self.lock = threading.Lock()
        self.replacement = compute_vorp(pool, config)
        self._rank = {p.player_id: i for i, p in enumerate(pool.players)}

    @property
    def version(self) -> str:
        return f"{self.boot}:{self.counter}"

    def bump(self) -> None:
        self.counter += 1

    def gaps(self) -> list[int]:
        """Pick slots below the clock that were never filled.

        store.next_overall() is MAX(overall)+1 by design, so recording a pick
        out of order leaves silent holes: the clock moves on and those players
        stay in the pool, quietly corrupting every recommendation. Surfacing the
        holes is the only way the user can know to fill them.
        """
        have = {p.overall for p in self.store.snapshot()}
        return [o for o in range(1, self.store.next_overall()) if o not in have]

    # -- derived views -----------------------------------------------------

    def my_roster(self):
        """Players explicitly claimed, never inferred from snake position.

        Inferring ownership from `slot` means a single missed pick silently
        reassigns the whole roster -- and in a fast draft, missed picks are the
        normal case rather than the exception.
        """
        return [self.pool.by_id[pid] for pid in self.store.my_players()
                if pid in self.pool.by_id]

    def roster_slots(self, roster) -> list[dict]:
        """Fill the starting lineup greedily so empty slots read as holes."""
        remaining = sorted(roster, key=lambda p: -p.vorp)
        out = []
        for slot in SLOT_ORDER:
            eligible = FLEX_ELIGIBLE if slot == "FLEX" else (slot,)
            taken = next((p for p in remaining if p.pos in eligible), None)
            if taken:
                remaining.remove(taken)
            out.append({
                "slot": slot,
                "filled": taken is not None,
                "name": taken.name if taken else None,
                "pos": taken.pos if taken else None,
            })
        for p in remaining:  # anything beyond the starters is bench
            out.append({"slot": "BN", "filled": True, "name": p.name, "pos": p.pos})
        return out

    def board_rows(self) -> list[dict]:
        """One-time payload for client-side type-ahead."""
        return [
            {"id": p.player_id, "name": p.name, "pos": p.pos, "team": p.team,
             "vorp": round(p.vorp, 1), "adp": p.adp, "bye": p.bye_week,
             "rank": self._rank[p.player_id], "inj": p.injury_status,
             "draftable": p.draftable}
            for p in self.pool.players
        ]

    def grid(self) -> dict:
        """The board in display order: rounds down, slots across, snake applied.

        Built server-side on purpose. The JS already carries one ported
        algorithm (the name index) and its parity risk; duplicating pick
        arithmetic in the browser would add a second for no benefit. Here a
        cell's horizontal position IS its real seat, by construction.
        """
        cfg = self.config
        by_overall = {pk.overall: pk for pk in self.store.snapshot()}
        clock = self.store.next_overall()
        rows = []
        for rnd in range(1, cfg.rounds + 1):
            row = []
            for slot in range(1, cfg.num_teams + 1):
                o = snake.overall_of(rnd, slot, cfg.num_teams)
                pk = by_overall.get(o)
                if pk is not None:
                    pl = self.pool.by_id.get(pk.player_id) if pk.player_id else None
                    row.append({
                        "o": o, "s": slot,
                        "st": "taken" if pl else "unknown",
                        "n": pl.name if pl else (pk.observed_name or "unknown"),
                        "p": pl.pos if pl else None,
                        "t": pl.team if pl else None,
                        "m": pk.mine,
                    })
                elif o == clock:
                    row.append({"o": o, "s": slot, "st": "clock", "n": None,
                                "p": None, "t": None, "m": False})
                elif o < clock:
                    # Below the clock with nothing recorded: a hole. Either a
                    # pick entered out of order, or one just removed.
                    row.append({"o": o, "s": slot, "st": "gap", "n": None,
                                "p": None, "t": None, "m": False})
                else:
                    row.append({"o": o, "s": slot, "st": "future", "n": None,
                                "p": None, "t": None, "m": False})
            rows.append(row)
        return {"rounds": rows}

    def state(self) -> dict:
        cfg = self.config
        store = self.store
        cur = store.next_overall()
        done = cur > cfg.total_picks

        roster = self.my_roster()
        drafted = store.drafted_ids()
        roster_byes = {p.bye_week for p in roster if p.bye_week}

        my_next = snake.next_pick_at_or_after(cur, cfg.num_teams, cfg.my_slot, cfg.rounds)
        my_after = (
            snake.next_pick_after(my_next, cfg.num_teams, cfg.my_slot, cfg.rounds)
            if my_next else None
        )
        # The gap that VONA is measured over: from THIS pick to my next one.
        next_after_current = snake.next_pick_after(
            cur, cfg.num_teams, cfg.my_slot, cfg.rounds
        )

        order = [(self.pool.by_id[pk.player_id], pk.overall)
                 for pk in store.snapshot()
                 if pk.player_id in self.pool.by_id]
        recs = [] if done else recommend(
            self.pool, drafted, roster, cfg, cur, top_n=10, urgency=self.urgency,
            drafted_order=order,
        )
        rec_rows = []
        prev = None
        for r in recs:
            p = r.player
            rec_rows.append({
                "id": p.player_id, "name": p.name, "pos": p.pos, "team": p.team,
                "proj": p.proj_points, "adp": p.adp, "bye": p.bye_week,
                "bye_clash": p.bye_week in roster_byes and p.bye_week > 0,
                "inj": p.injury_status if p.is_injured() else None,
                "score": r.score, "vorp": r.vorp, "vona": r.vona,
                "survival": r.survival_at_next, "cliff": r.cliff,
                "reason": r.reason,
                # A rule above this row when the drop from the previous one is
                # large: "these are equivalent, then it falls off".
                "tier_break": prev is not None and (prev - r.score) >= TIER_GAP,
            })
            prev = r.score

        best_at = {}
        for pos in POSITIONS:
            cand = self.pool.at_position(pos, drafted)
            best_at[pos] = {
                "name": cand[0].name if cand else None,
                "id": cand[0].player_id if cand else None,
                "team": cand[0].team if cand else None,
                "vorp": round(cand[0].vorp, 1) if cand else 0.0,
                "count": len(cand),
                "cliff": round(vona.position_cliff(cand, next_after_current), 1),
            }

        log = []
        for pk in reversed(store.snapshot()):
            pl = self.pool.by_id.get(pk.player_id) if pk.player_id else None
            log.append({
                "overall": pk.overall, "label": snake.label(pk.overall, cfg.num_teams),
                "slot": pk.slot, "round": pk.round,
                "id": pk.player_id,
                "name": pl.name if pl else (pk.observed_name or "unknown"),
                "pos": pl.pos if pl else None,
                "team": pl.team if pl else None,
                "mine": pk.mine,
                "unknown": pk.player_id is None,
                "source": pk.source,
            })

        return {
            "version": self.version,
            "league": self.league,
            "accent": self.accent,
            "peers": self.peers,
            "done": done,
            "teams": cfg.num_teams,
            "rounds": cfg.rounds,
            "my_slot": cfg.my_slot,
            "urgency": self.urgency,
            "on_clock": None if done else {
                "overall": cur,
                "label": snake.label(cur, cfg.num_teams),
                "round": snake.round_of(cur, cfg.num_teams),
                "slot": snake.slot_on_clock(cur, cfg.num_teams),
                "mine": snake.slot_on_clock(cur, cfg.num_teams) == cfg.my_slot,
            },
            "my_next": None if my_next is None else {
                "overall": my_next,
                "label": snake.label(my_next, cfg.num_teams),
                "until": my_next - cur,
            },
            "my_after": None if my_after is None else {
                "overall": my_after,
                "label": snake.label(my_after, cfg.num_teams),
                "gap": my_after - my_next,
            },
            "picks_remaining": snake.picks_remaining(
                cur, cfg.num_teams, cfg.my_slot, cfg.rounds),
            "picks_made": store.count(),
            "gaps": self.gaps(),
            # How far this room is running ahead of (or behind) national ADP.
            "adp_drift": round(vona.adp_drift(order), 1),
            "recs": rec_rows,
            "best_at": best_at,
            "remaining": {
                pos: len(self.pool.at_position(pos, drafted)) for pos in POSITIONS
            },
            "grid": self.grid(),
            "roster_slots": self.roster_slots(roster),
            "counts": roster_counts(roster),
            "needs": unfilled_mandatory(roster, cfg),
            "replacement": {k: round(v, 1) for k, v in self.replacement.items()},
            "log": log,
        }

    def team_roster(self, slot: int) -> dict:
        picks = self.store.picks_for_slot(slot)
        players = []
        for pk in picks:
            pl = self.pool.by_id.get(pk.player_id) if pk.player_id else None
            players.append({
                "label": snake.label(pk.overall, self.config.num_teams),
                "name": pl.name if pl else (pk.observed_name or "unknown"),
                "pos": pl.pos if pl else None,
                "team": pl.team if pl else None,
                "bye": pl.bye_week if pl else None,
            })
        counts: dict[str, int] = {}
        for pk in picks:
            pl = self.pool.by_id.get(pk.player_id) if pk.player_id else None
            if pl:
                counts[pl.pos] = counts.get(pl.pos, 0) + 1
        return {"slot": slot, "mine": slot == self.config.my_slot,
                "players": players, "counts": counts}


class DraftHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    session: DraftSession = None  # injected by serve()

    # 80 lines a minute of request logging makes the terminal useless.
    def log_message(self, *args) -> None:
        pass

    # -- plumbing ----------------------------------------------------------

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))  # HTTP/1.1 hangs without
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _static(self, name: str) -> None:
        path = STATIC / name
        if not path.is_file() or ".." in name:
            self._json({"error": "not found"}, 404)
            return
        ctype = {".html": "text/html", ".js": "text/javascript",
                 ".css": "text/css"}.get(path.suffix, "text/plain")
        self._send(200, path.read_bytes(), f"{ctype}; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    # -- routes ------------------------------------------------------------

    def do_GET(self) -> None:
        url = urlparse(self.path)
        route = url.path
        s = self.session

        if route in ("/", "/index.html"):
            return self._static("draft.html")
        if route.startswith("/static/"):
            return self._static(route[len("/static/"):])
        if route == "/board":
            return self._json({"players": s.board_rows(),
                               "teams": s.config.num_teams,
                               "rounds": s.config.rounds})
        if route == "/state":
            want = parse_qs(url.query).get("v", [""])[0]
            with s.lock:
                if want and want == s.version:
                    return self._json({"unchanged": True, "version": s.version})
                return self._json(s.state())
        if route == "/team":
            slot = int(parse_qs(url.query).get("slot", ["1"])[0])
            with s.lock:
                return self._json(s.team_roster(slot))
        if route == "/health":
            with s.lock:
                return self._json({"ok": True, "league": s.league,
                                   "board_rows": len(s.pool.players),
                                   "picks": s.store.count(),
                                   "version": s.version})
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        s = self.session
        body = self._body()

        with s.lock:
            try:
                if route == "/pick":
                    pid = body.get("player_id")
                    if pid is None:
                        return self._json({"error": "player_id required"}, 400)
                    s.store.append(int(pid), overall=body.get("overall"),
                                   mine=bool(body.get("mine", False)))
                elif route == "/mine":
                    # Claim or release a player already recorded as gone.
                    pid = body.get("player_id")
                    overall = body.get("overall")
                    if overall is None and pid is not None:
                        hit = next((p for p in s.store.snapshot()
                                    if p.player_id == int(pid)), None)
                        if hit is None:
                            return self._json({"error": "player is not drafted"}, 400)
                        overall = hit.overall
                    if overall is None:
                        return self._json({"error": "overall or player_id required"}, 400)
                    s.store.set_mine(int(overall), bool(body.get("mine", True)))
                elif route == "/skip":
                    s.store.append(None, overall=body.get("overall"),
                                   source="unknown", observed_name="unknown")
                elif route == "/undo":
                    if s.store.undo_last() is None:
                        return self._json({"error": "nothing to undo"}, 400)
                elif route == "/correct":
                    s.store.correct(int(body["overall"]), int(body["player_id"]))
                elif route == "/remove":
                    # Leaves the slot empty so gaps() surfaces it as refillable.
                    gone = s.store.remove(int(body["overall"]))
                    if gone is None:
                        return self._json({"error": "no pick there"}, 400)
                elif route == "/delete":
                    s.store.delete_shift(int(body["overall"]))
                elif route == "/config":
                    if "urgency" in body:
                        s.urgency = max(0.0, min(1.0, float(body["urgency"])))
                    if "my_slot" in body:
                        slot = int(body["my_slot"])
                        if not 1 <= slot <= s.config.num_teams:
                            return self._json({"error": "slot out of range"}, 400)
                        s.config.my_slot = slot
                elif route == "/reset":
                    s.store.reset()
                else:
                    return self._json({"error": "not found"}, 404)
            except PickConflict as e:
                # Surfaced, never swallowed: if the board disagrees with what was
                # typed, the user's mental model is wrong too and they need to see it.
                return self._json({"error": str(e), "conflict": True}, 409)
            except (KeyError, ValueError, TypeError) as e:
                return self._json({"error": str(e)}, 400)

            s.bump()
            return self._json(s.state())


class DraftServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True   # Ctrl-C then immediate restart


def serve(session: DraftSession, port: int = 8100, host: str = "127.0.0.1") -> None:
    handler = type("BoundHandler", (DraftHandler,), {"session": session})
    server = DraftServer((host, port), handler)
    print(f"  {session.league}: http://{host}:{port}"
          f"   slot {session.config.my_slot}/{session.config.num_teams}"
          f"   {len(session.pool.players)} players", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


def build_session(league: str, pool_csv: Path, db_path: Path,
                  config: LeagueConfig, accent: str = "#c0392b",
                  peers: list[dict] | None = None) -> DraftSession:
    pool = load_pool(pool_csv)
    store = PickStore(db_path, config.num_teams)
    return DraftSession(league, pool, config, store, accent, peers)
