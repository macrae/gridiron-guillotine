"""Traffic-light risk sentiment, collapsed from the research into one signal.

    red     serious — expected to miss multiple weeks, or a role loss
    amber   concern — a one-to-two game question, or committee/role risk
    green   nothing flagged

That last wording is deliberate. Green is NOT a claim that a player is healthy;
it means neither the injury report nor the scouting note nor the headlines said
anything. The feeds do not cover every player equally, so absence of evidence is
not evidence of absence, and the UI says so.

Every verdict carries the reason that produced it, and the rules below are
ordered and explicit rather than a blended score -- a coloured dot you cannot
interrogate is worse than no dot, because you will trust it.
"""

from __future__ import annotations

RED, AMBER, GREEN = "red", "amber", "green"

#: Multi-week absence. Anything at or beyond this is red on its own.
RED_WEEKS = 3

#: Statuses that mean the player is not currently available at all.
OUT_STATUSES = {"Injured Reserve", "Suspension", "Out", "Doubtful"}

#: Phrases that describe losing snaps rather than losing health. A player can be
#: fully fit and still be a bad start, which is what "ability to start
#: regularly" actually asks about.
ROLE_RISK = (
    "committee", "timeshare", "split carries", "split time", "rotation",
    "lost the starting", "backup role", "second string", "demot", "benched",
    "lose snaps", "losing snaps", "battle for the starting", "competing for",
)

#: Health language strong enough to matter even with no formal status.
HEALTH_RISK = (
    "did not practice", "didn't practice", "limited in practice", "sat out",
    "held out", "expected to miss", "will miss", "out for", "surgery",
    "setback", "re-injur", "reinjur", "placed on ir",
)


def _hit(text: str, phrases) -> str | None:
    low = (text or "").lower()
    for p in phrases:
        if p in low:
            return p
    return None


def assess(injury: dict | None, dossier: dict | None,
           news: list[dict] | None = None) -> dict:
    """Return {level, reason, detail} for one player.

    Ordered rules, first match wins, so the verdict is always traceable to a
    single stated cause.
    """
    inj = injury or {}
    status = inj.get("status")
    weeks = inj.get("weeks_out")
    sev = inj.get("severity") or 0
    note = (inj.get("note") or "")
    scout = ((dossier or {}).get("scouting") or {})
    # HEADLINE ONLY, never the story body. A scouting story about one player
    # routinely discusses his teammates' injuries, so matching the body flagged
    # healthy players: Etienne's own headline says "fully healthy" while his
    # story mentions "Ty Chandler is out for the season". The headline is about
    # the subject; the body is about the depth chart.
    scout_text = scout.get("headline", "") or ""

    # 1. Formally unavailable for multiple weeks.
    if sev >= 4:
        return _v(RED, f"{status}", note or "on the reserve list")
    if weeks is not None and weeks >= RED_WEEKS:
        return _v(RED, f"{status or 'injured'} — about {weeks} weeks out", note)

    # 2. Out or doubtful with no stated return is an open-ended absence.
    if status in OUT_STATUSES:
        if weeks is None:
            return _v(RED, f"{status}, no return date", note)
        return _v(AMBER, f"{status} — about {weeks} week{'s' if weeks != 1 else ''}", note)

    # 3. Role risk beats a clean bill of health: fit but splitting snaps is
    #    still a bad start, which is what the question actually asks.
    role = _hit(scout_text, ROLE_RISK) or _hit(note, ROLE_RISK)
    if role:
        return _v(AMBER, f"role risk — “{role}”", scout.get("headline") or note)

    # 4. A formal questionable tag, or practice-participation language.
    #
    #    Gate on SEVERITY, not on the presence of a status. The injury report
    #    lists healthy players explicitly as "Active", so `or status` marked
    #    every listed player as a concern -- 82% of the top 190 came back amber,
    #    including Gibbs, which makes the light meaningless.
    if sev >= 1:
        return _v(AMBER, f"{status or 'questionable'}"
                  + (f" — about {weeks} week{'s' if weeks != 1 else ''}" if weeks else ""),
                  note)
    health = _hit(scout_text, HEALTH_RISK)
    if health:
        return _v(AMBER, f"practice concern — “{health}”", scout.get("headline"))

    # 5. Nothing in any feed. Not a clean bill of health -- just silence.
    return _v(GREEN, "nothing flagged", None)


def _v(level: str, reason: str, detail: str | None) -> dict:
    return {"level": level, "reason": reason, "detail": (detail or "")[:280] or None}
