"""Player name normalization and matching.

The one real integration risk in this build: an unmatched *drafted* player is
never removed from the pool, so the engine happily recommends someone who is
already gone. Every entry point here fails loudly rather than silently skipping.

Stdlib only -- difflib covers the fuzzy tier, no rapidfuzz needed.
"""

from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from pathlib import Path

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize(name: str) -> str:
    """Fold a display name to a match key.

    'Ja'Marr Chase'      -> 'jamarr chase'
    'Amon-Ra St. Brown'  -> 'amon ra st brown'
    'Kenneth Walker III' -> 'kenneth walker'
    'Chase, Ja'Marr'     -> 'jamarr chase'   (canonical 'Last, First' handled)
    """
    if not name:
        return ""
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    # Strip accents.
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    # Apostrophes join (jamarr); hyphens and periods split (amon ra, st brown).
    name = name.replace("'", "").replace("’", "")
    name = re.sub(r"[^a-z0-9]+", " ", name)
    tokens = [t for t in name.split() if t]
    while len(tokens) > 2 and tokens[-1] in SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def last_name(name: str) -> str:
    """Last token of the normalized name. 'amon ra st brown' -> 'brown'."""
    parts = normalize(name).split()
    return parts[-1] if parts else ""


def initials(name: str) -> str:
    """First letter of each normalized token. 'amon ra st brown' -> 'arsb'."""
    return "".join(t[0] for t in normalize(name).split())


def first_initial_last(name: str) -> str:
    """'christian mccaffrey' -> 'cmccaffrey'. Makes 'cmc' a prefix match."""
    parts = normalize(name).split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[0][0] + "".join(parts[1:])


def load_aliases(path: Path) -> dict[str, str]:
    """Hand-editable overrides: observed_name -> name_norm.

    Missing file is fine -- aliases only exist once a match has failed.
    """
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            observed = (row.get("observed_name") or "").strip()
            target = (row.get("name_norm") or "").strip()
            if observed and target:
                out[normalize(observed)] = target
    return out


class MatchError(Exception):
    """Raised when a name cannot be resolved. Never swallow this."""


def match(
    observed: str,
    pool_rows: list[dict],
    pos: str | None = None,
    team: str | None = None,
    aliases: dict[str, str] | None = None,
    cutoff: float = 0.85,
) -> dict | None:
    """Resolve an observed name against the pool.

    Tiers, in order: alias override, exact (name_norm[, pos]),
    (last, pos, team), then difflib within position.

    Returns the matched row, or None. Callers must treat None as an error
    requiring manual resolution -- never as "skip this pick".
    """
    key = normalize(observed)
    if not key:
        return None

    if aliases and key in aliases:
        target = aliases[key]
        for r in pool_rows:
            if r["name_norm"] == target:
                return r

    def pos_ok(r: dict) -> bool:
        return pos is None or r["pos"] == pos

    exact = [r for r in pool_rows if r["name_norm"] == key and pos_ok(r)]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1 and team:
        narrowed = [r for r in exact if r["team"] == team]
        if len(narrowed) == 1:
            return narrowed[0]
    if exact:
        return exact[0]

    if pos and team:
        last = key.split()[-1]
        cand = [
            r
            for r in pool_rows
            if r["pos"] == pos and r["team"] == team and r["name_norm"].split()[-1] == last
        ]
        if len(cand) == 1:
            return cand[0]

    scope = [r for r in pool_rows if pos_ok(r)]
    names = [r["name_norm"] for r in scope]
    close = difflib.get_close_matches(key, names, n=1, cutoff=cutoff)
    if close:
        for r in scope:
            if r["name_norm"] == close[0]:
                return r
    return None
