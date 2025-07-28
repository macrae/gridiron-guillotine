from yahoo_api_fixed import initialize_yahoo_connection, get_league_info
import json

def debug_yahoo_data():
    """Debug what data structure we get from Yahoo API"""
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
    
    # Get first team's data
    teams = league.teams()
    first_team_key = list(teams.keys())[0]
    first_team = league.to_team(first_team_key)
    
    print(f"Debugging team: {teams[first_team_key]['name']}")
    
    # Get roster for week 16
    print("\nGetting roster for week 16...")
    roster = first_team.roster(16)
    
    # Print first few players' full data structure
    print("\nFirst 3 players' data structure:")
    for i, player in enumerate(roster[:3]):
        print(f"\n=== Player {i+1} ===")
        print(json.dumps(player, indent=2, default=str))
        
    # Try to get team stats/scores for week 16
    print("\n=== Trying team stats ===")
    try:
        team_stats = first_team.stats(16)
        print("Team stats for week 16:")
        print(json.dumps(team_stats, indent=2, default=str))
    except Exception as e:
        print(f"Error getting team stats: {e}")
    
    # Try matchup data
    print("\n=== Trying matchup data ===")
    try:
        matchups = league.matchups(16)
        print("Matchup data structure (first matchup):")
        if matchups:
            print(json.dumps(matchups[0], indent=2, default=str))
    except Exception as e:
        print(f"Error getting matchups: {e}")

if __name__ == "__main__":
    debug_yahoo_data()