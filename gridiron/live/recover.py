"""Rebuild a draft from its append-only audit log.

The pick store is a SQLite file, and any number of ordinary events destroy it:
a `--reset` on relaunch, a crashed machine, a stray double-click. The audit log
is append-only and survives all of them, so a draft is never actually lost --
but only if there is a tool to read it back, which there was not until a machine
restart took 28 live picks.

Replays through the running server's HTTP API rather than writing to the SQLite
file underneath it, because the server caches state and a write behind its back
would leave the two disagreeing.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def load_events(path: Path) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                      # a torn final line is not a reason to fail
    return out


def last_session(events: list[dict]) -> list[dict]:
    """The appends belonging to the most recent run that actually had picks.

    Walks back past trailing resets -- a relaunch with --reset writes one before
    a single pick is made, so the newest reset is usually not the interesting
    boundary. Returns appends in recorded order.
    """
    def op(e):
        return e.get("op") or e.get("action")

    end = len(events)
    while True:
        start = -1
        for i in range(end - 1, -1, -1):
            if op(events[i]) == "reset":
                start = i
                break
        block = [e for e in events[start + 1:end] if op(e) == "append"]
        if block:
            return block
        if start <= 0:
            return []
        end = start                        # that window was empty; look further back


def restore(base_url: str, picks: list[dict], dry_run: bool = False) -> tuple[int, list[str]]:
    """POST each pick back. Returns (restored, errors)."""
    errors: list[str] = []
    done = 0
    for e in picks:
        pid = e.get("player_id")
        if pid is None:
            continue                       # an unknown-pick placeholder
        body = json.dumps({"player_id": int(pid), "overall": e.get("overall"),
                           "mine": bool(e.get("mine"))}).encode()
        if dry_run:
            done += 1
            continue
        req = urllib.request.Request(f"{base_url}/pick", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10).read()
            done += 1
        except urllib.error.HTTPError as ex:
            errors.append(f"pick {e.get('overall')} player {pid}: {ex.read()[:120]!r}")
        except OSError as ex:
            errors.append(f"pick {e.get('overall')} player {pid}: {ex}")
    return done, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay a draft from its audit log.")
    ap.add_argument("--league", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    log = a.log or Path(f"data/2026/draft_{a.league}.log.jsonl")
    if not log.exists():
        print(f"no audit log at {log}")
        return 1
    picks = last_session(load_events(log))
    if not picks:
        print("no picks found to restore")
        return 1

    print(f"{len(picks)} picks in the last session with any"
          f" ({sum(1 for p in picks if p.get('mine'))} claimed as yours)")
    base = f"http://127.0.0.1:{a.port}"
    done, errors = restore(base, picks, a.dry_run)
    print(f"{'would restore' if a.dry_run else 'restored'} {done}")
    for e in errors:
        print(f"  FAILED {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
