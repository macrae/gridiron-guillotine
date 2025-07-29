import os
import re

import pandas as pd

from fantasy_points_two_minute_drill import (apply_defense_fantasy_scoring,
                                             calculate_fantasy_points)


def process_rookie_data(file_path):
    rookie_df = pd.read_csv(file_path)

    # Extract name, position, and team
    rookie_df['Name'] = rookie_df['RK,ADP,Bye,Age,1yr. Proj,3yr. Proj,5yr. Proj,10yr. Proj,3D Value,DS Analysis,Column_10,Column_11,Column_12'].str.split(
        '\n').str[0]
    rookie_df['Pos'] = rookie_df['RK,ADP,Bye,Age,1yr. Proj,3yr. Proj,5yr. Proj,10yr. Proj,3D Value,DS Analysis,Column_10,Column_11,Column_12'].str.split(
        '\n').str[1].str.split(' ').str[0]
    rookie_df['Team'] = rookie_df['RK,ADP,Bye,Age,1yr. Proj,3yr. Proj,5yr. Proj,10yr. Proj,3D Value,DS Analysis,Column_10,Column_11,Column_12'].str.split(
        '\n').str[1].str.split(' ').str[1]

    # Extract and calculate weighted mean
    rookie_df['weighted_mean'] = rookie_df['RK,ADP,Bye,Age,1yr. Proj,3yr. Proj,5yr. Proj,10yr. Proj,3D Value,DS Analysis,Column_10,Column_11,Column_12'].str.split(
        ',').str[4].astype(float)

    return rookie_df[['Name', 'Pos', 'Team', 'weighted_mean']]


def clean_player_name(name):
    # Find the last occurrence of a name pattern (which should be the abbreviated version)
    abbreviated_match = re.search(r'([A-Z]\.?\s*[-\w]+)$', name)
    if abbreviated_match:
        abbreviated_part = abbreviated_match.group(1)
        # Remove the abbreviated part from the original name
        full_name = name[:name.index(abbreviated_part)].strip()

        # Handle hyphenated last names
        if '-' in abbreviated_part:
            last_name = abbreviated_part.split()[-1]
        else:
            last_name = abbreviated_part.split()[-1]

        # Extract first name by removing last name from full name
        first_name = full_name.replace(last_name, '').strip()

        # Handle cases where the first name includes initials
        if re.match(r'^[A-Z]\.?[A-Z]\.?$', first_name):
            return f"{last_name}, {first_name}"
        else:
            return f"{last_name}, {first_name.split()[-1]}"

    # If the above logic fails, return an error message
    return f"Name format error: {name}"


def split_game(game_str):
    # Splits the 'Game' string into 'Home' and 'Away' teams
    teams = game_str.split('@')
    return teams[0], teams[1] if len(teams) == 2 else (game_str, '')


def read_and_label_csvs(directory, player_directory):
    all_data = pd.DataFrame()
    player_data = pd.DataFrame()

    # Load and concatenate all player data from player_{letter}.csv files
    for filename in os.listdir(player_directory):
        if filename.startswith('players_') and filename.endswith('.csv'):
            df = pd.read_csv(os.path.join(player_directory, filename))
            player_data = pd.concat(
                [player_data, df], ignore_index=True, axis=0)

    for filename in os.listdir(directory):
        if filename.endswith('.csv'):
            df = pd.read_csv(os.path.join(directory, filename))
            # df = pd.read_csv(os.path.join(directory, filename))

            # Determine schema and set prefix
            prefix = ''
            if 'offense' in filename or 'kicker' in filename:
                prefix = 'Off_' if 'offense' in filename else 'Kck_'

                # Apply cleaning to the 'Player' column if present
                if 'Player' in df.columns:
                    df['Player'] = df['Player'].apply(clean_player_name)
                    if 'Game' in df.columns:
                        df[['Home', 'Away']] = df['Game'].apply(
                            lambda x: pd.Series(split_game(x)))
                        df.drop('Game', axis=1, inplace=True)

                # Rename the columns while retaining 'Player', 'Home', 'Away' without prefix
                df.columns = [prefix + col if col not in ['Player',
                                                          'Home', 'Away'] else col for col in df.columns]

                # Assuming format 'offense_2020_1.csv'
                year_week = filename.split('_')[1:]
                year = year_week[0]
                week = year_week[1].split('.')[0]

                df['Season'] = year
                df['Week'] = week

                # Append to the main DataFrame
                all_data = pd.concat([all_data, df], ignore_index=True, axis=0)
                # print(all_data.columns)

    # Merge with player data using 'Player' and 'Name' columns if player_data is not empty
    if not player_data.empty:
        all_data = all_data.merge(player_data, how='left', on='Player')

    return all_data


def score_player_data(row):
    # Construct the player stats dictionary, using get to provide a default value if key is missing
    row = row.fillna(0.)
    player_stats = {
        'Passing Yards': row.get('Off_Passing_Yds', 0),
        'Passing TDs': row.get('Off_Passing_TD', 0),
        'Interceptions': row.get('Off_Passing_Int', 0),
        'Rushing Yards': row.get('Off_Rushing_Yds', 0),
        'Rushing TDs': row.get('Off_Rushing_TD', 0),
        'Receptions': row.get('Off_Receiving_Rec', 0),
        'Receiving Yards': row.get('Off_Receiving_Yds', 0),
        'Receiving TDs': row.get('Off_Receiving_TD', 0),
        # This field might need to be added to raw data
        'Return TDs': row.get('Off_Return_TD', 0),
        '2-Point Conversions': row.get('Off_Passing_2Pt', 0) + row.get('Off_Rushing_2Pt', 0) + row.get('Off_Receiving_2Pt', 0),
        'Fumbles Lost': row.get('Off_Fumble_FL', 0),
        'Offensive Fumble Return TD': row.get('Off_Fumble_TD', 0),
        # This field might need to be added to raw data
        'Pick Sixes Thrown': row.get('Off_Passing_Pick6', 0),
    }

    # Kicker scoring
    fg_0_49 = row.get('Kck_FGM', 0) - row.get('Kck_50+',
                                              0)  # FGs made from 0-49 yards
    fg_50_plus = row.get('Kck_50+', 0)  # FGs made from 50+ yards

    player_stats.update({
        # 3 points for 0-49 yards, 5 points for 50+ yards
        'FG Made': fg_0_49 * 3 + fg_50_plus * 5,
        'PAT Made': row.get('Kck_XPM', 0),
        # All missed FGs
        'FG Missed': row.get('Kck_FGA', 0) - row.get('Kck_FGM', 0),
        'PAT Missed': row.get('Kck_XPA', 0) - row.get('Kck_XPM', 0),
    })

    # Handle defense/special teams stats if present
    if 'Sack' in row.index:  # Check if it's a defensive entry
        player_stats.update({
            'Sack': row.get('Sack', 0),
            'Interception': row.get('Int', 0),
            'Fumble Recovery': row.get('FR', 0),
            'Defensive TD': row.get('TD', 0),
            'Safety': row.get('Saf', 0),
            'Block Kick': row.get('Blk', 0),
            'Points Allowed': row.get('PA', 0),
            'Yards Allowed': row.get('TotYds', 0)  # Total yards allowed
        })

    return calculate_fantasy_points(player_stats)


def read_defense_data(directory):
    all_defense_data = pd.DataFrame()

    for filename in os.listdir(directory):
        if filename.endswith('.csv') and 'defense' in filename:
            df = pd.read_csv(os.path.join(directory, filename))

            # # Clean up the Team and Game columns
            # df[['Team', 'Game']] = df['Team'].str.extract(
            #     r'(.*[A-Z]{3})\s*([A-Z]{3}@?[A-Z]{3})?')
            df['Team'] = df['Team'].str.strip()

            # Function to split game into home and away
            def split_game(game):
                if pd.isna(game) or '@' not in game:
                    return pd.Series({'Away': '', 'Home': ''})
                away, home = game.split('@')
                return pd.Series({'Away': away, 'Home': home})

            # Apply the split_game function if Game column exists
            if 'Game' in df.columns:
                df[['Away', 'Home']] = df['Game'].apply(split_game)

            # Rename columns to add 'Def_' prefix
            df.columns = ['Def_' + col if col not in ['Team',
                                                      'Home', 'Away', 'Game'] else col for col in df.columns]

            # Drop the 'Game' column as we've extracted what we need
            if 'Game' in df.columns:
                df = df.drop('Game', axis=1)

            # Assuming format 'defense_2020_1.csv'
            year_week = filename.split('_')[1:]
            year = year_week[0]
            week = year_week[1].split('.')[0]

            df['Season'] = year
            df['Week'] = week

            # Append to the main DataFrame
            all_defense_data = pd.concat(
                [all_defense_data, df], ignore_index=True, axis=0)

    return all_defense_data


# Specify the directory containing your CSV files
directory = 'data'

# Read, label, and compile all player data
player_df = read_and_label_csvs(directory, player_directory=directory)
player_df['fantasy_points'] = player_df.apply(score_player_data, axis=1)

# Read, label, and compile all defense data
defense_df = read_defense_data(directory)

# Apply fantasy scoring to defense data (you'll need to create this function)
defense_df['fantasy_points'] = defense_df.apply(
    apply_defense_fantasy_scoring, axis=1)

# Optionally, save the scored DataFrames to new CSVs
player_df.to_csv('scored_player_data.csv', index=False)
defense_df.to_csv('scored_defense_data.csv', index=False)

print("Player data:")
print(player_df.head())
print("\nDefense data:")
print(defense_df.head())
