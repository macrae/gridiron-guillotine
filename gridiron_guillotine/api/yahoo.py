"""
Yahoo Fantasy API integration
Modernized version of the legacy yahoo_api_fixed.py
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base import BaseAPIClient
from ..core.config import Config, get_config
from ..core.models import DraftPick, Position

logger = logging.getLogger(__name__)


class YahooFantasyClient(BaseAPIClient):
    """Modern Yahoo Fantasy API client"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        super().__init__()
        self.game = None
        self.oauth = None
        self.league = None
    
    def setup_client(self):
        """Initialize Yahoo API client"""
        try:
            # Import Yahoo API modules
            from yahoo_oauth import OAuth2
            from yahoo_fantasy_api import Game
            
            # Setup OAuth
            oauth_file = Path(self.config.yahoo_oauth_file)
            if not oauth_file.exists():
                raise FileNotFoundError(f"OAuth file not found: {oauth_file}")
            
            self.oauth = OAuth2(None, None, from_file=str(oauth_file))
            self.game = Game(self.oauth, 'nfl')
            
            logger.info("Yahoo API client initialized successfully")
            
        except ImportError as e:
            logger.error(f"Yahoo API dependencies not available: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Yahoo API client: {e}")
            raise
    
    def authenticate(self) -> bool:
        """Authenticate with Yahoo API"""
        try:
            if not self.oauth:
                self.setup_client()
            
            # Test authentication by making a simple request
            self.oauth.session.get("https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1")
            logger.info("Yahoo API authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Yahoo API authentication failed: {e}")
            return False
    
    def get_league_info(self) -> Optional[Dict[str, Any]]:
        """Get league information"""
        try:
            if not self.game:
                self.setup_client()
            
            # Get user's leagues
            leagues = self.game.league_ids()
            if not leagues:
                logger.warning("No leagues found for user")
                return None
            
            # Use first league found
            league_id = leagues[0]
            self.league = self.game.to_league(league_id)
            
            league_info = {
                'league_id': league_id,
                'name': getattr(self.league, 'name', 'Unknown'),
                'num_teams': getattr(self.league, 'num_teams', 12),
                'scoring_type': getattr(self.league, 'scoring_type', 'head'),
            }
            
            logger.info(f"Connected to league: {league_info['name']}")
            return league_info
            
        except Exception as e:
            self.handle_api_error(e, "Getting league info")
            return None
    
    def get_current_rosters(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current rosters for all teams"""
        try:
            if not self.league:
                self.get_league_info()
            
            if not self.league:
                return {}
            
            rosters = {}
            teams = self.league.teams()
            
            for team in teams:
                team_name = team.get('name', f"Team_{team.get('team_id', 'Unknown')}")
                roster = team.get('roster', [])
                
                # Extract player information
                players = []
                for player in roster:
                    player_info = {
                        'name': self._extract_player_name(player),
                        'position': player.get('position', 'Unknown'),
                        'team': player.get('editorial_team_abbr', ''),
                    }
                    players.append(player_info)
                
                rosters[team_name] = players
            
            logger.debug(f"Retrieved rosters for {len(rosters)} teams")
            return rosters
            
        except Exception as e:
            self.handle_api_error(e, "Getting current rosters")
            return {}
    
    def _extract_player_name(self, player_data: Dict[str, Any]) -> str:
        """Extract player name from Yahoo API data"""
        try:
            name_field = player_data.get('name', {})
            
            if isinstance(name_field, dict):
                return name_field.get('full', '')
            elif isinstance(name_field, str):
                return name_field
            else:
                # Try alternative fields
                first = player_data.get('first_name', '')
                last = player_data.get('last_name', '')
                return f"{first} {last}".strip() if first or last else "Unknown"
                
        except Exception:
            return "Unknown"
    
    def detect_draft_picks(self, previous_rosters: Dict[str, List[Dict]], 
                          current_rosters: Dict[str, List[Dict]]) -> List[DraftPick]:
        """Detect new draft picks by comparing rosters"""
        detected_picks = []
        
        try:
            for team_name in current_rosters.keys():
                if team_name not in previous_rosters:
                    continue
                
                # Get player names for comparison
                prev_players = {p['name'] for p in previous_rosters[team_name]}
                curr_players = {p['name'] for p in current_rosters[team_name]}
                
                # Find new players
                new_players = curr_players - prev_players
                
                for player_name in new_players:
                    # Find player details
                    player_data = next(
                        (p for p in current_rosters[team_name] if p['name'] == player_name),
                        {}
                    )
                    
                    pick = DraftPick(
                        player_name=player_name,
                        team_name=team_name,
                        position=Position(player_data.get('position', 'Unknown')),
                        round_num=1,  # Would need additional logic to determine
                        pick_num=1    # Would need additional logic to determine
                    )
                    
                    detected_picks.append(pick)
                    logger.info(f"Detected pick: {pick}")
            
            return detected_picks
            
        except Exception as e:
            logger.error(f"Error detecting draft picks: {e}")
            return []
    
    def monitor_draft(self, callback_fn=None, polling_interval: int = 20) -> bool:
        """Monitor draft for new picks"""
        import time
        
        try:
            previous_rosters = self.get_current_rosters()
            if not previous_rosters:
                logger.error("Could not get initial roster snapshot")
                return False
            
            logger.info(f"Starting draft monitoring (polling every {polling_interval}s)")
            
            while True:
                time.sleep(polling_interval)
                
                current_rosters = self.get_current_rosters()
                if not current_rosters:
                    continue
                
                new_picks = self.detect_draft_picks(previous_rosters, current_rosters)
                
                if new_picks and callback_fn:
                    callback_fn(new_picks)
                
                previous_rosters = current_rosters
                
        except KeyboardInterrupt:
            logger.info("Draft monitoring stopped by user")
            return True
        except Exception as e:
            self.handle_api_error(e, "Draft monitoring")
            return False


# Legacy compatibility function
def initialize_yahoo_connection():
    """Legacy compatibility function"""
    client = YahooFantasyClient()
    client.setup_client()
    return client.game, client.oauth


def get_league_info(game):
    """Legacy compatibility function"""  
    client = YahooFantasyClient()
    client.game = game
    return client.get_league_info()


def get_current_rosters(league):
    """Legacy compatibility function"""
    client = YahooFantasyClient()
    client.league = league
    return client.get_current_rosters()