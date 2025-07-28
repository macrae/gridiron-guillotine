import logging
from typing import Dict, List, Tuple

import pandas as pd

POSITION_LIMITS = {'QB': 1, 'RB': 2, 'WR': 2,
                   'TE': 1, 'FLEX': 1, 'K': 1, 'DEF': 1}
TOTAL_TEAMS = 12


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def generate_advanced_draft_strategy(player_df: pd.DataFrame, draft_position: int, num_rounds: int) -> List[pd.DataFrame]:
    """
    Generate an advanced draft strategy for each round based on VBD, positional scarcity, and tier-based drafting.

    Args:
    player_df (pd.DataFrame): DataFrame containing player data
    draft_position (int): Your position in the draft order
    num_rounds (int): Number of rounds in the draft

    Returns:
    List[pd.DataFrame]: A list of DataFrames, each containing top 12 picks for a round
    """
    strategies = []
    drafted_players = set()
    draft_state = initialize_draft_state(
        draft_position, TOTAL_TEAMS, POSITION_LIMITS)
    logging.info(f"Draft state initialized with {draft_state}")

    player_df = initialize_tiers(player_df)
    logging.info("Player tiers initialized.")

    for round in range(1, num_rounds + 1):
        logging.info(f"Starting round {round}")

        player_df = calculate_dynamic_vbd(player_df)
        scarcity_factors = calculate_positional_scarcity(player_df)
        tier_dropoffs = calculate_tier_dropoffs(player_df, drafted_players)

        player_df['adjusted_value'] = player_df.apply(
            lambda row: adjust_player_value(
                row, scarcity_factors, tier_dropoffs, draft_state['rosters'][f'Team{draft_position}'], round),
            axis=1
        )

        # Explicitly filter out K and DEF before round 13
        if round < 13:
            available_players = player_df[~player_df['position'].isin(['K', 'DEF'])]
        else:
            available_players = player_df

        top_players = get_top_players(
            available_players, drafted_players, draft_state['rosters'][f'Team{draft_position}'], round, TOTAL_TEAMS)

        strategy_df = pd.DataFrame({
            'Rank': range(1, 13),
            'Player': top_players['name'],
            'Position': top_players['position'],
            'Team': top_players['team'],  # Added Team
            'Value': top_players['adjusted_value'].round(2),
            'VBD': top_players['vbd'].round(2),  # Added VBD
            'Tier': top_players['tier'],
            'Rating': top_players['rating'],
            'Analyst Rating': top_players['analyst_rating'],
            'Rookie': top_players['rookie']
        }).reset_index(drop=True)

        strategies.append(strategy_df)

        if round % 2 == 1:
            pick_index = draft_position - 1
        else:
            pick_index = TOTAL_TEAMS - draft_position

        drafted_player = top_players.iloc[pick_index]
        draft_state['rosters'][f'Team{draft_position}'][drafted_player['position']].append(
            drafted_player['name'])
        drafted_players.add(drafted_player['name'])

        top_players = top_players.drop(top_players.index[pick_index])
        for team in range(1, TOTAL_TEAMS + 1):
            if team != draft_position:
                if not top_players.empty:
                    team_pick_index = 0
                    next_pick = top_players.iloc[team_pick_index]
                    draft_state['rosters'][f'Team{team}'][next_pick['position']].append(
                        next_pick['name'])
                    drafted_players.add(next_pick['name'])
                    top_players = top_players.drop(
                        top_players.index[team_pick_index])

        player_df = player_df[~player_df['name'].isin(drafted_players)]
        draft_state['current_round'] += 1

    return strategies


def initialize_draft_state(draft_position: int, total_teams: int, position_limits: Dict[str, int]) -> Dict:
    """Initialize the draft state."""
    return {
        'draft_position': draft_position,
        'total_teams': total_teams,
        'position_limits': position_limits,
        'current_round': 1,
        'rosters': {f'Team{i}': {pos: [] for pos in position_limits.keys()} for i in range(1, total_teams + 1)}
    }


def calculate_positional_scarcity(player_df: pd.DataFrame, vbd_column: str = 'vbd') -> Dict[str, float]:
    """
    Calculate scarcity factor for each position based on VBD (Value Based Drafting).

    Args:
    player_df (pd.DataFrame): DataFrame containing available players
    vbd_column (str): Name of the column containing VBD scores. Defaults to 'vbd'.

    Returns:
    Dict[str, float]: Scarcity factors for each position
    """
    positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
    scarcity_factors = {}

    for pos in positions:
        pos_players = player_df[player_df['position'] == pos]
        if not pos_players.empty:
            # Calculate the total VBD for the top 12 players (or all if less than 12)
            top_12_vbd = pos_players.nlargest(12, vbd_column)[vbd_column].sum()
            scarcity_factors[pos] = top_12_vbd
        else:
            scarcity_factors[pos] = 0

    # Calculate FLEX scarcity (top 24 RB/WR/TE combined)
    flex_players = player_df[player_df['position'].isin(['RB', 'WR', 'TE'])]
    top_24_flex_vbd = flex_players.nlargest(24, vbd_column)[vbd_column].sum()
    scarcity_factors['FLEX'] = top_24_flex_vbd

    # Normalize scarcity factors
    total_vbd = sum(scarcity_factors.values())
    scarcity_factors = {pos: factor / total_vbd for pos,
                        factor in scarcity_factors.items()}

    return scarcity_factors


def initialize_tiers(player_df: pd.DataFrame, tier_dropoff_percentage: float = 0.2) -> pd.DataFrame:
    """
    Initialize tiers for each position based on VBD scores and add tier information to the player DataFrame.

    Args:
    player_df (pd.DataFrame): DataFrame containing player data
    tier_dropoff_percentage (float): The percentage dropoff that defines a new tier

    Returns:
    pd.DataFrame: Updated DataFrame with tier information added
    """
    positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']

    for position in positions:
        pos_players = player_df[player_df['position'] ==
                                position].sort_values('vbd', ascending=False)
        tier = 1
        tier_start = pos_players['vbd'].iloc[0]

        tiers = []
        for i, vbd in enumerate(pos_players['vbd']):
            if i > 0 and vbd < tier_start * (1 - tier_dropoff_percentage):
                tier += 1
                tier_start = vbd
            tiers.append(tier)

        player_df.loc[pos_players.index, 'tier'] = tiers

    return player_df


def calculate_tier_dropoffs(player_df: pd.DataFrame, drafted_players: set) -> Dict[str, float]:
    """Calculate tier dropoff bonuses for each position."""
    remaining_players = player_df[~player_df['name'].isin(drafted_players)]
    tier_dropoffs = {}
    for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
        pos_players = remaining_players[remaining_players['position'] == position]
        if len(pos_players) == 0:
            tier_dropoffs[position] = 0
            continue
        top_tier = pos_players['tier'].min()
        next_tier_player = pos_players[pos_players['tier'] > top_tier]
        if len(next_tier_player) > 0:
            tier_dropoffs[position] = (pos_players['vbd'].max(
            ) - next_tier_player['vbd'].max()) / pos_players['vbd'].max()
        else:
            tier_dropoffs[position] = 0
    return tier_dropoffs


def calculate_dynamic_vbd(player_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate dynamic VBD based on remaining players."""
    baseline_values = {'QB': 12, 'RB': 24,
                       'WR': 24, 'TE': 12, 'K': 12, 'DEF': 12}
    for pos in baseline_values:
        baseline = player_df[player_df['position'] == pos]['projected_points'].nlargest(
            baseline_values[pos]).min()
        player_df.loc[player_df['position'] == pos,
                      'vbd'] = player_df['projected_points'] - baseline
    return player_df


def adjust_player_value(player: pd.Series, scarcity_factors: Dict[str, float], tier_dropoffs: Dict[str, float], my_roster: Dict[str, List[str]], round: int) -> float:
    """
    Adjust player value based on scarcity, tier dropoffs, and roster needs.

    Args:
    player (pd.Series): Player data
    scarcity_factors (Dict[str, float]): Scarcity factors for each position
    tier_dropoffs (Dict[str, float]): Tier dropoff values for each position
    my_roster (Dict[str, List[str]]): Current roster
    round (int): Current draft round

    Returns:
    float: Adjusted player value
    """
    scarcity_boost = scarcity_factors.get(player['position'], 1.0)
    tier_boost = tier_dropoffs.get(player['position'], 0.0)

    # Positional adjustments for early rounds
    position_boost = 1.0
    if round <= 5:
        if player['position'] in ['RB', 'WR', 'TE']:
            position_boost = 1.1

    # Roster needs adjustment
    roster_need_boost = 1.0
    if len(my_roster.get(player['position'], [])) < POSITION_LIMITS.get(player['position'], 0):
        roster_need_boost = 1.2

    # Increase value for unfilled positions
    if len(my_roster[player['position']]) == 0:
        roster_need_boost *= 1.5

    # Late round upside boost and specialists
    upside_boost = 1.0
    if round > 10:
        ceiling = player.get('ceiling', 0)
        floor = player.get('floor', 0)
        # Default to 1 if not available
        projected_points = player.get('projected_points', 1)
        if projected_points > 0:
            upside_boost = 1 + (ceiling - floor) / projected_points
        else:
            # Fallback if projected_points is 0
            upside_boost = 1 + (ceiling - floor)

        if player['position'] in ['K', 'DEF']:
            upside_boost *= 1.2
        elif player.get('handcuff_to') in my_roster['RB']:
            upside_boost *= 1.3

    return player.get('vbd', 0) * scarcity_boost * (1 + tier_boost) * position_boost * roster_need_boost * upside_boost


def get_top_players(player_df: pd.DataFrame, drafted_players: set, my_roster: Dict[str, List[str]], round: int, n: int) -> pd.DataFrame:
    """Get top n players that haven't been drafted yet, considering roster balance, positional limits, and strategic round considerations."""
    available_players = player_df[~player_df['name'].isin(
        drafted_players)].copy()

    # Adjust player values based on ratings, emphasizing rookies in later rounds for potential upside
    available_players['adjusted_value'] = available_players.apply(
        lambda x: x['adjusted_value'] *
        (x['rating'] * 0.2 + (0.5 if x['rookie'] and round > 10 else 0)),
        axis=1
    )

    # Filter out positions that have reached their limit in the roster
    available_players = available_players[
        available_players.apply(lambda x: len(
            my_roster[x['position']]) < POSITION_LIMITS[x['position']], axis=1)
    ]

    # Implement roster balance logic, adjusting to strategic considerations per round
    if round <= 5:
        # Early rounds focus: Secure core RBs and WRs, consider an elite TE if available
        priority_positions = ['RB', 'WR'] + (['TE'] if any(
            available_players['position'] == 'TE') and max(available_players['rating']) >= 4 else [])
    elif round >= 13:  # Push K and DEF to later rounds
        # Only consider K and DEF in the last three rounds
        priority_positions = ['K', 'DEF']
    elif 6 <= round <= 9:
        # Middle rounds: Focus on QB if not drafted yet, otherwise RB/WR depth
        if 'QB' not in my_roster or len(my_roster['QB']) == 0:
            priority_positions = ['QB', 'RB', 'WR']
        else:
            priority_positions = ['RB', 'WR']
    else:
        # For all other rounds, exclude K and DEF, focus on best available RB/WR/TE/QB
        priority_positions = ['RB', 'WR', 'TE', 'QB']

    # Filter players based on priority positions
    priority_players = available_players[available_players['position'].isin(
        priority_positions)]

    # Boost RB values in middle rounds to ensure depth
    if 4 <= round <= 10:
        priority_players.loc[priority_players['position']
                             == 'RB', 'adjusted_value'] *= 1.2

    # Ensure we have at least n players
    if len(priority_players) < n:
        remaining_players = available_players[~available_players.index.isin(
            priority_players.index)]
        priority_players = pd.concat([priority_players, remaining_players.nlargest(
            n - len(priority_players), 'adjusted_value')])

    # If we still don't have enough players, consider adding back players from filled positions
    if len(priority_players) < n:
        filled_position_players = player_df[~player_df['name'].isin(
            drafted_players) & ~player_df.index.isin(priority_players.index)]
        priority_players = pd.concat([priority_players, filled_position_players.nlargest(
            n - len(priority_players), 'adjusted_value')])

    # Sort by adjusted_value and return top n players
    return priority_players.nlargest(n, 'adjusted_value')
