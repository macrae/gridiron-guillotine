#!/usr/bin/env python3
"""
Aggregate scored player data into season projections
Processes scored_player_data.csv to create scored_data.csv with 2024 rookies included
"""

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def aggregate_player_data():
    """Aggregate weekly player data into season projections"""
    logger.info("Loading scored player data...")
    
    # Load the detailed player data
    df = pd.read_csv('scored_player_data.csv')
    
    # Group by player and calculate season aggregates
    logger.info("Aggregating player statistics by season...")
    
    # Define aggregation functions
    agg_functions = {
        'fantasy_points': 'mean',  # Average fantasy points per game
        'Off_Pts*': 'mean',
        'Season': 'first',
        'Pos': 'first', 
        'Team': 'first',
        'College': 'first'
    }
    
    # Aggregate by player
    player_aggregates = df.groupby('Player').agg(agg_functions).reset_index()
    
    # Calculate game counts by year
    logger.info("Calculating game counts by year...")
    game_counts = df.groupby(['Player', 'Season']).size().reset_index(name='games')
    game_counts_pivot = game_counts.pivot(index='Player', columns='Season', values='games').fillna(0)
    
    # Ensure we have columns for all years 2020-2024
    for year in [2020, 2021, 2022, 2023, 2024]:
        if year not in game_counts_pivot.columns:
            game_counts_pivot[year] = 0
    
    # Rename game count columns
    game_count_cols = {
        2020: 'game_count_2020',
        2021: 'game_count_2021', 
        2022: 'game_count_2022',
        2023: 'game_count_2023',
        2024: 'game_count_2024'
    }
    game_counts_pivot = game_counts_pivot.rename(columns=game_count_cols)
    
    # Merge aggregates with game counts
    result = player_aggregates.merge(game_counts_pivot, left_on='Player', right_index=True, how='left')
    
    # Fill any missing game counts with 0
    for col in game_count_cols.values():
        if col not in result.columns:
            result[col] = 0
        result[col] = result[col].fillna(0)
    
    # Calculate weighted game count (more recent years weighted higher)
    weights = {
        'game_count_2020': 0.1,
        'game_count_2021': 0.2, 
        'game_count_2022': 0.3,
        'game_count_2023': 0.4,
        'game_count_2024': 1.0
    }
    
    result['weighted_game_count'] = 0
    total_games = 0
    for col, weight in weights.items():
        if col in result.columns:
            result['weighted_game_count'] += result[col] * weight
            total_games += result[col]
    
    # Normalize by total games
    result['weighted_game_count'] = result['weighted_game_count'] / (total_games + 1)  # +1 to avoid division by zero
    
    # Use fantasy_points as the projection (weighted_mean)
    result['weighted_mean'] = result['fantasy_points']
    
    # Create confidence intervals (simple approach)
    result['ci_lower'] = result['weighted_mean'] * 0.75
    result['ci_upper'] = result['weighted_mean'] * 1.25  
    result['discounted_ci_lower'] = result['ci_lower'] * 0.9
    
    # Add placeholder columns for defense stats (needed for compatibility)
    defense_cols = ['Avg_Sacks', 'Avg_Interceptions', 'Avg_Fumble_Recoveries', 'Avg_Defensive_TDs', 'Avg_Points_Allowed']
    for col in defense_cols:
        result[col] = np.nan
    
    # Reorder columns to match expected format
    final_columns = [
        'Player', 'Pos', 'Team', 'weighted_mean', 'ci_lower', 'ci_upper',
        'game_count_2020', 'game_count_2021', 'game_count_2022', 'game_count_2023', 'game_count_2024',
        'weighted_game_count', 'discounted_ci_lower'
    ] + defense_cols
    
    # Add any missing columns
    for col in final_columns:
        if col not in result.columns:
            result[col] = np.nan
    
    result = result[final_columns]
    
    # Filter out players with very low projections (< 0.5 points)
    result = result[result['weighted_mean'] >= 0.5]
    
    # Sort by projected points
    result = result.sort_values('weighted_mean', ascending=False)
    
    logger.info(f"Processed {len(result)} players")
    
    # Check for 2024 rookies
    rookies_2024 = result[
        (result['game_count_2020'] == 0) & 
        (result['game_count_2021'] == 0) & 
        (result['game_count_2022'] == 0) & 
        (result['game_count_2023'] == 0) &
        (result['game_count_2024'] > 0)
    ]
    
    logger.info(f"Found {len(rookies_2024)} players with 2024 rookie patterns")
    logger.info("Top 2024 rookies:")
    for _, rookie in rookies_2024.nlargest(10, 'weighted_mean').iterrows():
        logger.info(f"  {rookie['Player']} ({rookie['Pos']}, {rookie['Team']}) - {rookie['weighted_mean']:.1f} avg")
    
    return result

def main():
    """Main execution"""
    logger.info("Starting player data aggregation...")
    
    # Aggregate the data
    aggregated_data = aggregate_player_data()
    
    # Save to the expected filename
    output_file = 'scored_data.csv'
    aggregated_data.to_csv(output_file, index=False)
    logger.info(f"Saved aggregated data to {output_file}")
    
    print(f"\n✅ Data aggregation complete!")
    print(f"📊 Total players: {len(aggregated_data)}")
    print(f"📈 Top player: {aggregated_data.iloc[0]['Player']} ({aggregated_data.iloc[0]['weighted_mean']:.1f} avg)")
    print(f"📁 Output file: {output_file}")
    
    # Check for key 2024 rookies
    key_rookies = ['Daniels, Jayden', 'Williams, Caleb', 'Harrison, Marvin', 'Nabers, Malik', 'Bowers, Brock']
    print(f"\n🏈 2024 Rookie Check:")
    for rookie_name in key_rookies:
        matches = aggregated_data[aggregated_data['Player'].str.contains(rookie_name, na=False)]
        if len(matches) > 0:
            player = matches.iloc[0]
            print(f"   ✅ {player['Player']} ({player['Pos']}, {player['Team']}) - {player['weighted_mean']:.1f} avg")
        else:
            print(f"   ❌ {rookie_name} - Not found")

if __name__ == "__main__":
    main()