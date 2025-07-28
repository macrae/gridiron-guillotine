import yahoo_fantasy_api as yfa
import pandas as pd
from yahoo_oauth import OAuth2
from datetime import datetime
import time

def initialize_yahoo_connection():
    """Initialize OAuth connection to Yahoo Fantasy API"""
    try:
        # Try different paths for oauth2.json
        oauth_paths = ['oauth2.json', 'nbs/oauth2.json']
        oauth = None
        
        for path in oauth_paths:
            try:
                oauth = OAuth2(None, None, from_file=path)
                break
            except FileNotFoundError:
                continue
        
        if oauth is None:
            raise FileNotFoundError("oauth2.json not found in any expected location")
        
        if not oauth.token_is_valid():
            oauth.refresh_access_token()
        
        game = yfa.Game(oauth, 'nfl')
        return game, oauth
    except Exception as e:
        print(f"Error initializing Yahoo connection: {str(e)}")
        return None, None

def get_league_info(game):
    """Get league information and return the league object"""
    try:
        league_ids = game.league_ids()
        if not league_ids:
            print("No leagues found")
            return None
        
        league_id = league_ids[0]  # Use first league
        league = game.to_league(league_id)
        print(f"Connected to league: {league_id}")
        return league
    except Exception as e:
        print(f"Error getting league info: {str(e)}")
        return None

def get_current_rosters(league):
    """Get current rosters for all teams"""
    try:
        teams = league.teams()
        all_rosters = {}
        
        for team_key in teams.keys():
            team = league.to_team(team_key)
            roster = team.roster()
            all_rosters[teams[team_key]['name']] = roster
            time.sleep(0.5)  # Rate limiting
        
        return all_rosters
    except Exception as e:
        print(f"Error getting rosters: {str(e)}")
        return {}

def get_player_stats_alternative(league, week=None):
    """
    Alternative method to get player stats using roster method
    """
    try:
        if week is None:
            week = league.current_week()
        
        # Get all teams
        teams = league.teams()
        all_player_stats = []
        
        for team_key, team_info in teams.items():
            try:
                team_obj = league.to_team(team_key)
                
                # Get roster for this team for this week
                roster = team_obj.roster(week)
                
                for player in roster:
                    if player and isinstance(player, dict):
                        # Extract player information safely
                        player_stat = {
                            'player_id': player.get('player_id', ''),
                            'name': '',
                            'position': player.get('position_type', ''),
                            'team': player.get('editorial_team_abbr', ''),
                            'points': 0,
                            'week': week,
                            'team_name': team_info.get('name', '') if isinstance(team_info, dict) else str(team_info)
                        }
                        
                        # Handle name field (can be dict or string)
                        name_field = player.get('name', '')
                        if isinstance(name_field, dict):
                            player_stat['name'] = name_field.get('full', '')
                        else:
                            player_stat['name'] = str(name_field)
                        
                        # Handle points field (can be nested)
                        points_field = player.get('player_points', 0)
                        if isinstance(points_field, dict):
                            player_stat['points'] = points_field.get('total', 0)
                        else:
                            player_stat['points'] = points_field
                        
                        all_player_stats.append(player_stat)
                        
            except Exception as e:
                print(f"Error getting roster for team {team_key}: {str(e)}")
                continue
            
            time.sleep(0.3)  # Rate limiting
        
        return pd.DataFrame(all_player_stats)
    
    except Exception as e:
        print(f"Error getting player stats for week {week}: {str(e)}")
        return pd.DataFrame()

def get_season_stats(league, start_week=1, end_week=None):
    """Get stats for multiple weeks"""
    if end_week is None:
        end_week = league.current_week()
    
    all_stats = []
    
    for week in range(start_week, end_week + 1):
        print(f"Fetching stats for week {week}...")
        weekly_stats = get_player_stats_alternative(league, week)
        
        if not weekly_stats.empty:
            all_stats.append(weekly_stats)
        
        time.sleep(1)  # Rate limiting between weeks
    
    if all_stats:
        return pd.concat(all_stats, ignore_index=True)
    else:
        return pd.DataFrame()

def main():
    """Main function to demonstrate the fixed Yahoo API usage"""
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
    
    print(f"Current week: {league.current_week()}")
    
    # Get current rosters
    print("Fetching current rosters...")
    rosters = get_current_rosters(league)
    
    if rosters:
        print(f"Found rosters for {len(rosters)} teams")
        for team_name, roster in rosters.items():
            print(f"{team_name}: {len(roster)} players")
    
    # Get player stats for current week
    print("Fetching player stats...")
    current_week = league.current_week()
    stats_df = get_player_stats_alternative(league, current_week)
    
    if not stats_df.empty:
        print(f"Found stats for {len(stats_df)} player performances")
        print("\nTop scorers this week:")
        top_scorers = stats_df.nlargest(10, 'points')[['name', 'position', 'team', 'points']]
        print(top_scorers)
        
        # Save to CSV
        stats_df.to_csv('yahoo_player_stats.csv', index=False)
        print("Stats saved to yahoo_player_stats.csv")
    else:
        print("No stats found")

if __name__ == "__main__":
    main()