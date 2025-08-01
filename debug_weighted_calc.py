#!/usr/bin/env python3
"""
Debug script to investigate weighted calculation issues
"""

import pandas as pd
import glob
from gridiron_guillotine.data.weighted_calculator import WeightedMultiYearCalculator

def debug_mccaffrey():
    """Debug McCaffrey's weighted calculation step by step"""
    
    # Load raw McCaffrey games
    print("=== RAW MCCAFFREY DATA ===")
    all_games = []
    for year in ['2023', '2024', '2025']:
        files = glob.glob(f'/Users/smacrae/gridiron-guillotine/data/offense_{year}_*.csv')
        for file in files:
            df = pd.read_csv(file)
            mccaffrey_games = df[df['Player'].str.contains('McCaffrey', case=False, na=False)]
            if not mccaffrey_games.empty:
                mccaffrey_games = mccaffrey_games.copy()
                mccaffrey_games['Year'] = int(year)
                mccaffrey_games['Week'] = int(file.split('_')[-1].replace('.csv', ''))
                all_games.append(mccaffrey_games)

    if all_games:
        combined = pd.concat(all_games, ignore_index=True)
        
        print(f"Total games found: {len(combined)}")
        for year in [2023, 2024, 2025]:
            year_games = combined[combined['Year'] == year]
            print(f"  {year}: {len(year_games)} games, avg {year_games['Pts*'].mean():.1f} pts/game")
        
        print(f"Overall average: {combined['Pts*'].mean():.1f} pts/game")
    
    # Test the weighted calculator aggregation
    print("\n=== WEIGHTED CALCULATOR AGGREGATION ===")
    calculator = WeightedMultiYearCalculator()
    
    # Load historical data using the calculator
    historical_data = calculator.load_historical_data([2023, 2024, 2025])
    
    for season, data in historical_data.items():
        print(f"\n{season} season data:")
        print(f"  Total records: {len(data)}")
        
        # Find McCaffrey in this season
        mccaffrey_data = data[data['CleanPlayer'].str.contains('McCaffrey', case=False, na=False)]
        if not mccaffrey_data.empty:
            print(f"  McCaffrey records: {len(mccaffrey_data)}")
            print(f"  Sample data: {mccaffrey_data[['CleanPlayer', 'Pts*', 'Week', 'Season']].head(3)}")
    
    # Test season aggregation
    print("\n=== SEASON AGGREGATION TEST ===")
    for season, data in historical_data.items():
        print(f"\nProcessing {season}...")
        season_totals = calculator._aggregate_season_totals(data, season)
        
        mccaffrey_totals = season_totals[season_totals['CleanPlayer'].str.contains('McCaffrey', case=False, na=False)]
        if not mccaffrey_totals.empty:
            mccaffrey = mccaffrey_totals.iloc[0]
            print(f"  McCaffrey {season}:")
            print(f"    Games Played: {mccaffrey['GamesPlayed']}")
            print(f"    Total Points: {mccaffrey['Pts*']:.1f}")
            print(f"    Points Per Game: {mccaffrey['Pts*_PerGame']:.1f}")
    
    # Test weighted calculation
    print("\n=== WEIGHTED CALCULATION TEST ===")
    season_totals = {}
    for season, data in historical_data.items():
        totals = calculator._aggregate_season_totals(data, season)
        season_totals[season] = totals
    
    # Find McCaffrey across all seasons
    mccaffrey_seasons = {}
    for season, totals in season_totals.items():
        mccaffrey_data = totals[totals['CleanPlayer'].str.contains('McCaffrey', case=False, na=False)]
        if not mccaffrey_data.empty:
            mccaffrey_seasons[season] = mccaffrey_data.iloc[0]
    
    if mccaffrey_seasons:
        print("McCaffrey season data:")
        for season, data in mccaffrey_seasons.items():
            print(f"  {season}: {data['GamesPlayed']} games, {data['Pts*_PerGame']:.1f} pts/game")
        
        # Test the weighted stats calculation
        weighted_stats = calculator._compute_weighted_stats("McCaffrey, Christian", mccaffrey_seasons)
        if weighted_stats:
            print(f"\nWeighted calculation results:")
            print(f"  Weighted Games Played: {weighted_stats.get('Weighted_GamesPlayed', 'N/A')}")
            print(f"  Projected Points Per Game: {weighted_stats.get('ProjectedPointsPerGame', 'N/A')}")
            print(f"  Total Weight: {weighted_stats.get('TotalWeight', 'N/A')}")

if __name__ == "__main__":
    debug_mccaffrey()