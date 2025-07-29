def calculate_fantasy_points(player_stats):
    """
    Calculate fantasy points based on player statistics using a comprehensive scoring system.
    player_stats: dict containing player game stats with keys matching scoring categories.
    """
    scoring_rules = {
        'Passing Yards': lambda yards: yards / 25,
        'Passing TDs': lambda tds: tds * 6,
        'Passing Interceptions': lambda interceptions: interceptions * -2,
        'Passing 2-Point Conversions': lambda conversions: conversions * 2,
        'Rushing Yards': lambda yards: yards / 10,
        'Rushing TDs': lambda tds: tds * 6,
        'Rushing 2-Point Conversions': lambda conversions: conversions * 2,
        'Receptions': lambda receptions: receptions,
        'Receiving Yards': lambda yards: yards / 10,
        'Receiving TDs': lambda tds: tds * 6,
        'Receiving 2-Point Conversions': lambda conversions: conversions * 2,
        'Offensive Fumble Recovery TD': lambda tds: tds * 6,
        'Fumbles Lost': lambda fumbles: fumbles * -2,
        'Kicking PATs': lambda points: points,
        'Kicking FGs': lambda yards: 5 if yards >= 50 else 3,
        'Defense/Special Teams TDs': lambda tds: tds * 6,
        'Defensive Interception': lambda interceptions: interceptions * 2,
        'Defensive Sack': lambda sacks: sacks,
        'Defensive Fumble Recovery': lambda recoveries: recoveries * 2,
        'Defensive Blocked Kick': lambda blocks: blocks * 2,
        'Defensive Safety': lambda safeties: safeties * 2,
        'Defensive PAT': lambda points: points * 2,
        'Defensive Points Allowed': lambda points: 10 if points <= 6 else 7 if points <= 13 else 4 if points <= 20 else 1 if points <= 27 else 0
    }

    points = 0
    for stat, value in player_stats.items():
        if stat in scoring_rules:
            points += scoring_rules[stat](value)
    return points
