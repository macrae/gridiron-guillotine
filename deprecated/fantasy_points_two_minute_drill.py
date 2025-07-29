def calculate_fantasy_points(player_stats):
    """
    Calculate fantasy points based on player statistics using the correct league scoring system.
    player_stats: dict containing player game stats with keys matching scoring categories.
    """
    def passing_yards_points(yards):
        points = yards // 25
        if yards >= 450:
            points += 10
        elif yards >= 350:
            points += 5
        return points

    def rushing_receiving_yards_points(yards):
        points = yards // 10
        if yards >= 150:
            points += 10
        elif yards >= 100:
            points += 5
        return points

    def points_allowed_points(points):
        if points == 0:
            return 10
        elif points <= 6:
            return 7
        elif points <= 13:
            return 4
        elif points <= 20:
            return 1
        elif points <= 27:
            return 0
        elif points <= 34:
            return -1
        else:
            return -4

    scoring_rules = {
        'Passing Yards': passing_yards_points,
        'Passing TDs': lambda tds: tds * 6,
        'Interceptions': lambda ints: ints * -1,
        'Rushing Yards': rushing_receiving_yards_points,
        'Rushing TDs': lambda tds: tds * 6,
        'Receptions': lambda recs: recs * 1,
        'Receiving Yards': rushing_receiving_yards_points,
        'Receiving TDs': lambda tds: tds * 6,
        '2-Point Conversions': lambda convs: convs * 2,
        'Fumbles Lost': lambda fumbs: fumbs * -2,
        'Offensive Fumble Return TD': lambda tds: tds * 6,
        'FG Made': lambda pts: pts,  # Now pre-calculated in apply_fantasy_scoring
        'PAT Made': lambda pats: pats * 1,
        'FG Missed': lambda misses: misses * -1,  # Simplified to -1 for all misses
        'PAT Missed': lambda misses: misses * -1,
        'Sack': lambda sacks: sacks * 1,
        'Interception': lambda ints: ints * 2,
        'Fumble Recovery': lambda recov: recov * 2,
        'Defensive TD': lambda tds: tds * 6,
        'Safety': lambda safes: safes * 2,
        'Block Kick': lambda blocks: blocks * 2,
        'Points Allowed': points_allowed_points,
        'Yards Allowed': lambda yards: 0  # Placeholder, adjust if needed
    }

    points = 0
    for stat, value in player_stats.items():
        if stat in scoring_rules:
            points += scoring_rules[stat](value)
    return points


def apply_defense_fantasy_scoring(row):
    points = 0

    # Example scoring rules (adjust according to your league settings)
    points += row['Def_Sack'] * 1  # 1 point per sack
    points += row['Def_Int'] * 2   # 2 points per interception
    points += row['Def_Saf'] * 2   # 2 points per safety
    points += row['Def_FR'] * 2    # 2 points per fumble recovery
    points += row['Def_Blk'] * 2   # 2 points per blocked kick
    points += row['Def_TD'] * 6    # 6 points per defensive touchdown

    # Points allowed scoring (example)
    pa = row['Def_PA']
    if pa == 0:
        points += 10
    elif pa <= 6:
        points += 7
    elif pa <= 13:
        points += 4
    elif pa <= 20:
        points += 1
    elif pa <= 27:
        points += 0
    elif pa <= 34:
        points -= 1
    else:
        points -= 4

    # You can add more scoring rules based on yards allowed, etc.

    return points
