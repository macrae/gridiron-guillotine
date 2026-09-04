"""Player news from ESPN, keyed by athlete id.

Projections price in what is known and modellable. They do not tell you a back
is in a committee, a receiver is holding out, or a starter got demoted in camp.
That is what this is for -- risk you would otherwise only learn from having read
the news all summer.

ESPN's news feed tags each article with the athletes it concerns, and those
athlete ids are the SAME ids the fantasy projections use. So the join is exact:
no name matching, no fuzzy fallback, none of the failure modes that make name
joins dangerous.

Two honest limits:
  - The feed returns ~50 articles regardless of the limit requested, so this is
    "what is being talked about right now", not per-player coverage of the pool.
  - It is national NFL news, not a fantasy risk database. Absence of news is not
    evidence a player is safe.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

FEED = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news"

#: Phrases that make an item a draft RISK rather than general interest. Used
#: only to flag, never to hide -- every item for a player is still shown.
#:
#: Deliberately specific. A first pass used bare "return", "role", "starter"
#: and "practice", which flagged "Can Geno Smith rewrite his narrative in
#: RETURN to Jets?" as an injury. A flag that fires on ordinary coverage trains
#: you to ignore flags, which is worse than having none.
RISK_WORDS = (
    "injur", "surgery", "tear", " acl", "hamstring", "ankle", "knee",
    "concussion", "doubtful", "questionable", "sidelin", "setback", "rehab",
    "placed on ir", "on the pup", "will miss", "expected to miss", "out for",
    "suspend", "holdout", "hold out", "contract dispute",
    "traded", "released", "waived", "demot", "benched",
    "committee", "timeshare", "split carries", "lost the starting",
    "backup role", "depth chart",
)


@dataclass(frozen=True)
class NewsItem:
    headline: str
    published: str
    link: str
    risky: bool

    def as_dict(self) -> dict:
        return {"headline": self.headline, "published": self.published,
                "link": self.link, "risky": self.risky}


def _is_risky(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in RISK_WORDS)


def fetch(limit: int = 50, timeout: int = 25) -> list[dict]:
    resp = requests.get(FEED, params={"limit": limit}, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("articles", [])


def index_by_athlete(articles: list[dict]) -> dict[int, list[NewsItem]]:
    """athlete_id -> items, newest first. Ids are ESPN's, matching the pool."""
    out: dict[int, list[NewsItem]] = {}
    for art in articles:
        headline = (art.get("headline") or "").strip()
        if not headline:
            continue
        item = NewsItem(
            headline=headline,
            published=(art.get("published") or "")[:10],
            link=((art.get("links") or {}).get("web") or {}).get("href", ""),
            risky=_is_risky(headline + " " + (art.get("description") or "")),
        )
        for cat in art.get("categories") or []:
            if cat.get("type") != "athlete":
                continue
            aid = (cat.get("athlete") or {}).get("id")
            if aid is None:
                continue
            out.setdefault(int(aid), []).append(item)
    for items in out.values():
        items.sort(key=lambda i: i.published, reverse=True)
    return out


def build(out_path: Path, limit: int = 50) -> tuple[Path, int, int]:
    """Fetch and cache. Returns (path, articles, athletes_covered)."""
    articles = fetch(limit)
    idx = index_by_athlete(articles)
    payload = {
        "fetched_at": time.time(),
        "articles": len(articles),
        "players": {str(k): [i.as_dict() for i in v] for k, v in idx.items()},
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path, len(articles), len(idx)


def load(path: Path) -> dict[int, list[dict]]:
    """Cached news by player id. Missing or unreadable cache is not an error --
    news is a bonus, and it must never be able to stop a draft."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {int(k): v for k, v in (data.get("players") or {}).items()}


def age_hours(path: Path) -> float | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return (time.time() - json.loads(p.read_text(encoding="utf-8"))["fetched_at"]) / 3600
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Cache ESPN player news.")
    ap.add_argument("--out", type=Path, default=Path("data/2026/news.json"))
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args(argv)
    path, n, players = build(args.out, args.limit)
    print(f"  {n} articles covering {players} players -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
