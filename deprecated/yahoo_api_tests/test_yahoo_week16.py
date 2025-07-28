from yahoo_api_fixed import initialize_yahoo_connection, get_league_info, get_player_stats_alternative

def test_week_16():
    """Test getting data from week 16 which should have points"""
    # Initialize connection
    game, oauth = initialize_yahoo_connection()
    if not game:
        print("Failed to initialize Yahoo connection")
        return
    
    # Get league
    league = get_league_info(game)
    if not league:
        print("Failed to get league info")
        return
    
    # Get player stats for week 16
    print("Fetching player stats for week 16...")
    stats_df = get_player_stats_alternative(league, 16)
    
    if not stats_df.empty:
        print(f"Found stats for {len(stats_df)} player performances")
        
        # Filter to players with points > 0
        scoring_players = stats_df[stats_df['points'] > 0]
        print(f"{len(scoring_players)} players scored points")
        
        if not scoring_players.empty:
            print("\nTop scorers week 16:")
            top_scorers = scoring_players.nlargest(10, 'points')[['name', 'position', 'team', 'points']]
            print(top_scorers)
            
            # Save to CSV
            stats_df.to_csv('yahoo_week16_stats.csv', index=False)
            print("Stats saved to yahoo_week16_stats.csv")
        else:
            print("No players with points found")
    else:
        print("No stats found")

if __name__ == "__main__":
    test_week_16()