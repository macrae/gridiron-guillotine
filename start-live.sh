#!/bin/sh
# Live draft launcher. Deliberately has NO --reset: a relaunch must reopen the
# existing board, never clear it. Use rundraft.py directly for testing.
set -e
cd "$(dirname "$0")"
.venv/bin/python rundraft.py --league 2MinuteDrill --slot "${1:?usage: ./start-live.sh <2MD-seat> [FD-seat]}" \
  --port 8100 --accent "#c0392b" --peer FirstDown:8101 &
.venv/bin/python rundraft.py --league FirstDown --slot "${2:-0}" \
  --port 8101 --accent "#1f6feb" --peer 2MinuteDrill:8100 &
wait
