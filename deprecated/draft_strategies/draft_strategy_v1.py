from typing import Dict, List, Tuple

import pandas as pd

# Initialize draft state
POSITION_LIMITS = {'QB': 1, 'RB': 2, 'WR': 2,
                   'TE': 1, 'FLEX': 1, 'K': 1, 'DEF': 1}
DRAFT_POSITION = 4
TOTAL_TEAMS = 12


def generate_draft_strategy(player_df: pd.DataFrame, draft_position: int, total_teams: int, num_rounds: int) -> pd.DataFrame:
    """
    Generate a dynamic draft strategy table based on player data and draft position.

    This function simulates the entire draft process, updating the strategy after each pick.

    Args:
    player_df (pd.DataFrame): DataFrame containing player data (name, position, projected_points, vbd, adp, sentiment)
    draft_position (int): Your position in the draft order
    total_teams (int): Total number of teams in the league
    num_rounds (int): Number of rounds in the draft

    Returns:
    pd.DataFrame: A draft strategy table with top 12 picks for each round

    TODO:
    - Implement color-coding for positions in the strategy table
    - Add a "panic meter" for neglected positions
    - Include a summary of current roster alongside the table
    """
    strategy_table = pd.DataFrame(index=range(
        1, num_rounds + 1), columns=range(1, 13))

    for round in range(1, num_rounds + 1):
        for pick in range(1, draft_state['total_teams'] + 1):
            current_pick = (round - 1) * draft_state['total_teams'] + pick
            draft_state['current_pick'] = current_pick

            # Update positional scarcity and VBD
            scarcity_factors = calculate_positional_scarcity(
                player_df, draft_state)
            player_df = calculate_vbd(
                player_df, draft_state, value_column='vbd')

            if is_my_pick(draft_state, round, pick):
                draft_state, player_df = update_my_roster(
                    draft_state, player_df)

                # Update strategy table for my pick
                top_players = get_top_players_for_pick(
                    player_df, draft_state, current_pick)
                for i, player in enumerate(top_players[:12]):
                    strategy_table.at[round, i +
                                      1] = f"{player['index']} ({player['pos']}) - {player['adjusted_value']:.1f}"
            else:
                draft_state, player_df = simulate_opponent_pick(
                    player_df, draft_state)

            print(
                f"Round {round}, Pick {pick}: Team{draft_state['draft_order'][current_pick - 1]} is picking")

            draft_state['current_pick'] += 1
        draft_state['current_round'] += 1

    return strategy_table


def initialize_draft_state(draft_position, total_teams, position_limits):
    """
    Initialize the draft state with empty rosters and draft order.

    This function sets up the initial state of the draft, including roster structures and draft order.

    Args:
    draft_position (int): Your position in the draft order
    total_teams (int): Total number of teams in the league
    position_limits (dict): Dictionary specifying the number of slots for each position

    Returns:
    Dict: Initial draft state
    """
    num_rounds = sum(position_limits.values())
    draft_state = {
        'draft_position': draft_position,
        'total_teams': total_teams,
        'num_rounds': num_rounds,
        'current_round': 1,
        'current_pick': 1,
        'position_limits': position_limits,
        'rosters': {f'Team{i}': {pos: [] for pos in position_limits.keys()} for i in range(1, total_teams + 1)},
        'draft_order': list(range(1, total_teams + 1)) + list(range(total_teams, 0, -1)) * (num_rounds // 2)
    }
    return draft_state


def generate_strategy_table(player_df: pd.DataFrame, draft_state: Dict) -> pd.DataFrame:
    """
    Generate the draft strategy table based on current player values and draft state.

    This function creates a DataFrame with rows for each round and columns for the top 12 picks.

    TODO:
    - Implement multi-round view to show players across multiple rounds
    - Add visual indicators for particularly good values
    """
    strategy_table = pd.DataFrame(index=range(
        1, draft_state['num_rounds'] + 1), columns=range(1, 13))

    for round in range(1, draft_state['num_rounds'] + 1):
        top_players = get_top_players_for_round(player_df, draft_state, round)
        for col in range(1, 13):
            if col <= len(top_players):
                player = top_players[col - 1]
                strategy_table.at[round,
                                  col] = f"{player['name']} ({player['position']}) - {player['adjusted_value']:.1f}"

    return strategy_table


def calculate_positional_scarcity(player_df: pd.DataFrame, draft_state: Dict, pos_column: str = 'pos') -> Dict[str, float]:
    """
    Calculate scarcity factor for each position based on remaining players and roster needs, accounting for FLEX.

    This function determines how scarce each position is based on available players and roster needs.

    Args:
    player_df (pd.DataFrame): DataFrame containing available players
    draft_state (Dict): Current state of the draft including rosters
    pos_column (str): Name of the column containing position information. Defaults to 'pos'.

    Returns:
    Dict[str, float]: Scarcity factors for each position

    TODO:
    - Consider incorporating tier dropoffs into scarcity calculations
    """
    positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
    scarcity_factors = {}

    # Calculate basic scarcity for each position
    for pos in positions:
        available = player_df[player_df[pos_column] == pos].shape[0]
        needed = sum(len(roster[pos]) < draft_state['position_limits'][pos]
                     for roster in draft_state['rosters'].values())

        # Add FLEX needs to RB, WR, and TE
        if pos in ['RB', 'WR', 'TE']:
            flex_needed = sum(len(roster['FLEX']) < draft_state['position_limits']['FLEX']
                              for roster in draft_state['rosters'].values())
            needed += flex_needed

        scarcity_factors[pos] = needed / \
            available if available > 0 else float('inf')

    # Calculate FLEX scarcity
    flex_available = player_df[player_df[pos_column].isin(
        ['RB', 'WR', 'TE'])].shape[0]
    flex_needed = sum(len(roster['FLEX']) < draft_state['position_limits']['FLEX']
                      for roster in draft_state['rosters'].values())
    scarcity_factors['FLEX'] = flex_needed / \
        flex_available if flex_available > 0 else float('inf')

    # Normalize scarcity factors
    max_scarcity = max(scarcity_factors.values())
    scarcity_factors = {pos: factor / max_scarcity for pos,
                        factor in scarcity_factors.items()}

    return scarcity_factors


def calculate_vbd(player_df, draft_state, pos_column='pos', value_column='weighted_mean'):
    # Data cleaning and preparation
    df_clean = player_df.copy()
    df_clean[value_column] = pd.to_numeric(
        df_clean[value_column], errors='coerce')
    df_clean.dropna(subset=[pos_column, value_column], inplace=True)

    # Calculate roster spots
    total_roster_spots = {pos: draft_state['position_limits'][pos] *
                          draft_state['total_teams'] for pos in draft_state['position_limits']}
    filled_spots = {pos: sum(len(team[pos]) for team in draft_state['rosters'].values(
    )) for pos in draft_state['position_limits']}
    remaining_spots = {
        pos: total_roster_spots[pos] - filled_spots[pos] for pos in total_roster_spots}

    # Flex position adjustments
    flex_eligible_positions = ['RB', 'WR', 'TE']
    total_flex_spots = draft_state['position_limits']['FLEX'] * \
        draft_state['total_teams']
    filled_flex_spots = sum(len(team['FLEX'])
                            for team in draft_state['rosters'].values())
    remaining_flex_spots = total_flex_spots - filled_flex_spots
    for pos in flex_eligible_positions:
        remaining_spots[pos] += remaining_flex_spots

    # VBD calculation per group using 'new_vbd' to avoid merge conflicts
    def calc_group_vbd(group):
        pos = group[pos_column].iloc[0]
        baseline_rank = max(1, remaining_spots[pos])
        baseline_value = group.nlargest(baseline_rank, value_column)[
            value_column].iloc[-1] if len(group) >= baseline_rank else group[value_column].min()
        group['new_vbd'] = group[value_column] - baseline_value
        return group

    df_vbd = df_clean.groupby(
        pos_column, group_keys=False).apply(calc_group_vbd)

    # Merge results ensuring 'index' is available as a column and handle 'vbd'
    if 'index' not in player_df.columns:
        player_df.reset_index(inplace=True)  # Ensure 'index' is a column
    result = pd.merge(
        player_df, df_vbd[['index', 'new_vbd']], on='index', how='left')

    # Drop the original 'vbd' if it exists to avoid conflicts
    if 'vbd' in result.columns:
        result.drop('vbd', axis=1, inplace=True)

    # Rename 'new_vbd' to 'vbd'
    result.rename(columns={'new_vbd': 'vbd'}, inplace=True)

    # Debugging print statements
    print("After VBD Calculation:", df_vbd.columns)  # Debug
    print("Merged Result Columns:", result.columns)  # Debug

    # Sorting and final adjustments
    result.sort_values('vbd', ascending=False, inplace=True)
    result.reset_index(drop=True, inplace=True)

    return result


def get_top_players_for_pick(player_df: pd.DataFrame, draft_state: Dict, current_pick: int) -> List[Dict]:
    """
    Get the top players for a specific pick, considering positional needs and value.

    This function determines the best available players for a given pick, taking into account various factors such as scarcity and draft round.

    Args:
    player_df (pd.DataFrame): DataFrame containing player data
    draft_state (Dict): Current state of the draft
    current_pick (int): The current overall pick number

    Returns:
    List[Dict]: List of top 12 players for the pick, each as a dictionary
    """
    current_round = (current_pick - 1) // draft_state['total_teams'] + 1
    scarcity_factors = calculate_positional_scarcity(player_df, draft_state)

    # Exclude drafted players
    drafted_players = set(player for team in draft_state['rosters'].values(
    ) for pos in team.values() for player in pos)
    available_players = player_df[~player_df['index'].isin(drafted_players)]

    print(
        f"Current Round: {current_round}, Current Pick: {current_pick}, Total Teams: {draft_state['total_teams']}")

    # Calculate adjusted values based on scarcity and round
    def calculate_player_value(row):
        scarcity_boost = scarcity_factors.get(row['pos'], 1.0)
        base_value = row['vbd'] * (1 + scarcity_boost)
        if current_round <= 5:
            return base_value
        elif current_round <= 10:
            return base_value * 0.5  # Adjust value for mid-rounds
        else:
            # Adjust value with upside for late rounds
            return base_value * (1 + 0.2 * row.get('upside', 0))

    available_players['adjusted_value'] = available_players.apply(
        calculate_player_value, axis=1)

    # Select top players based on the adjusted values and round specifics
    if current_round <= 5:
        priority_positions = ['RB', 'WR', 'TE']
        top_players = available_players[available_players['pos'].isin(
            priority_positions)].nlargest(12, 'adjusted_value')
    elif current_round <= 10:
        top_players = available_players.nlargest(12, 'adjusted_value')
    else:
        available_players['late_round_value'] = available_players['adjusted_value'] * (
            1 + available_players.get('upside', 0))
        top_players = available_players.nlargest(12, 'late_round_value')

    # Example adjustment within get_top_players_for_pick to handle late_round_value
    if current_round > 10:
        player_df['late_round_value'] = player_df['adjusted_value'] * \
            (1 + player_df.get('upside', 0))
        top_players = player_df.nlargest(12, 'late_round_value')
        output_columns = ['index', 'pos', 'late_round_value']
    else:
        top_players = player_df.nlargest(12, 'adjusted_value')
        output_columns = ['index', 'pos', 'adjusted_value']

    return top_players[output_columns].to_dict('records')


def update_player_values(player_df: pd.DataFrame, draft_state: Dict) -> pd.DataFrame:
    """
    Update player values based on current draft state, positional scarcity, and sentiment.

    This function recalculates player values after each pick to reflect the changing draft landscape.

    TODO:
    - Implement tier dropoff adjustments
    - Incorporate sentiment scores from recent news
    - Apply round-specific adjustments (e.g., prioritize upside in later rounds)
    """
    # Implementation needed


def update_my_roster(draft_state: Dict, player_name: str, player_position: str):
    """
    Update your roster by drafting the specified player.

    Args:
    draft_state (Dict): Current state of the draft.
    player_name (str): Name of the player to draft.
    player_position (str): Position of the player to draft.

    Returns:
    Dict: Updated draft state.

    Note:
    - Assumes validity checks and player selection have been handled externally.
    """
    my_team = f"Team{draft_state['draft_position']}"

    # Determine if the player can be added to the position or needs to go to FLEX
    if len(draft_state['rosters'][my_team][player_position]) < draft_state['position_limits'][player_position]:
        # Add to the specific position if not full
        draft_state['rosters'][my_team][player_position].append(player_name)
    else:
        # Add to FLEX if the specific position is full (ensure FLEX isn't also full)
        if len(draft_state['rosters'][my_team]['FLEX']) < draft_state['position_limits']['FLEX']:
            draft_state['rosters'][my_team]['FLEX'].append(player_name)
        else:
            print("No available spots to draft this player.")

    print(
        f"You drafted {player_name} ({player_position}) in round {draft_state['current_round']}")
    print("Updated Roster:")
    for pos, players in draft_state['rosters'][my_team].items():
        print(f"{pos}: {', '.join(players)}")

    return draft_state


def is_my_pick(draft_state, round, pick):
    current_pick = (round - 1) * draft_state['total_teams'] + pick
    return draft_state['draft_order'][current_pick - 1] == draft_state['draft_position']


def simulate_opponent_pick(player_df: pd.DataFrame, draft_state: Dict) -> Tuple[Dict, pd.DataFrame]:
    current_pick = draft_state['current_pick']
    current_team = f"Team{draft_state['draft_order'][current_pick - 1]}"
    top_players = get_top_players_for_pick(
        player_df, draft_state, current_pick)

    for player in top_players:
        player_name = player['index']
        player_position = player['pos']

        if can_draft_position(draft_state, current_team, player_position):
            if player_position in ['RB', 'WR', 'TE'] and len(draft_state['rosters'][current_team][player_position]) >= draft_state['position_limits'][player_position]:
                draft_state['rosters'][current_team]['FLEX'].append(
                    player_name)
            else:
                draft_state['rosters'][current_team][player_position].append(
                    player_name)

            # Remove the drafted player from the DataFrame
            player_df = player_df[player_df.index != player_name]

            print(
                f"Team {current_team} drafted {player_name} ({player_position})")
            break
    else:
        print("No available players to draft.")

    return draft_state, player_df


def can_draft_position(draft_state: Dict, team: str, position: str) -> bool:
    roster = draft_state['rosters'][team]
    limits = draft_state['position_limits']

    if position in ['RB', 'WR', 'TE']:
        return len(roster[position]) < limits[position] or (len(roster['FLEX']) < limits['FLEX'] and sum(len(roster[pos]) for pos in ['RB', 'WR', 'TE']) < sum(limits[pos] for pos in ['RB', 'WR', 'TE']) + limits['FLEX'])
    else:
        return len(roster[position]) < limits[position]


def calculate_tier_dropoff(player_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate tier dropoff bonuses for players at each position.

    TODO: Implement this function to identify and quantify tier dropoffs.
    """
    # Implementation needed


def calculate_upside_factor(player_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'upside' column to the dataframe based on ceiling projections and consistency.

    Args:
    player_df (pd.DataFrame): DataFrame containing player data with columns for 'ceiling' and 'consistency'.

    Returns:
    pd.DataFrame: Updated DataFrame with an additional 'upside' column.
    """
    # Check if necessary columns are present
    if not {'ceiling', 'consistency'}.issubset(player_df.columns):
        raise ValueError(
            "Player DataFrame must include 'ceiling' and 'consistency' columns")

    # Normalize ceiling and consistency values to a scale of 0 to 1
    player_df['norm_ceiling'] = (player_df['ceiling'] - player_df['ceiling'].min()) / (
        player_df['ceiling'].max() - player_df['ceiling'].min())
    player_df['norm_consistency'] = (player_df['consistency'] - player_df['consistency'].min()) / (
        player_df['consistency'].max() - player_df['consistency'].min())

    # Calculate the upside as a weighted average of normalized ceiling and consistency
    # Adjust weights as needed based on the draft strategy or statistical analysis
    player_df['upside'] = 0.6 * player_df['norm_ceiling'] + \
        0.4 * player_df['norm_consistency']

    return player_df


def get_positional_needs(roster: Dict) -> Dict:
    """
    Determine positional needs based on current roster composition.

    TODO: Implement this function to assess which positions need prioritization.
    """
    # Implementation needed


# Main execution
if __name__ == "__main__":
    # Load player data
    player_df = pd.read_csv("player_data.csv")

    # Set draft parameters
    draft_position = 4
    total_teams = 12
    num_rounds = 9

    # Generate draft strategy
    draft_strategy = generate_draft_strategy(
        player_df, draft_position, total_teams, num_rounds)

    # Display or save the draft strategy
    print(draft_strategy)
    draft_strategy.to_csv("draft_strategy.csv", index=False)

    # TODO: Implement visualization of the draft strategy (e.g., color-coding, graphical representation)
