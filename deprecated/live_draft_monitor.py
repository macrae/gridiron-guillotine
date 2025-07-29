"""
Live Draft Monitoring System for Yahoo Fantasy Football
Detects draft picks via API polling and roster comparison
"""

import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
import logging
from yahoo_api_fixed import initialize_yahoo_connection, get_league_info, get_current_rosters
from draft_strategy_consolidated import DraftStrategy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DraftPick:
    """Represents a detected draft pick"""
    def __init__(self, player_name: str, team_name: str, position: str, round_num: int, pick_num: int):
        self.player_name = player_name
        self.team_name = team_name
        self.position = position
        self.round_num = round_num
        self.pick_num = pick_num
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"Round {self.round_num}, Pick {self.pick_num}: {self.team_name} selects {self.player_name} ({self.position})"

class LiveDraftMonitor:
    """
    Monitors live Yahoo Fantasy draft via API polling
    Detects picks and updates draft strategy in real-time
    """
    
    def __init__(self, polling_interval: int = 20, my_team_name: str = None):
        self.polling_interval = polling_interval
        self.my_team_name = my_team_name
        self.previous_rosters = {}
        self.detected_picks = []
        self.draft_strategy = None
        self.league = None
        self.current_round = 1
        self.current_pick = 1
        self.total_teams = 12
        self.is_monitoring = False
        
    def initialize_connection(self) -> bool:
        """Initialize Yahoo API connection and league"""
        try:
            game, oauth = initialize_yahoo_connection()
            if not game:
                logger.error("Failed to initialize Yahoo connection")
                return False
                
            self.league = get_league_info(game)
            if not self.league:
                logger.error("Failed to connect to league")
                return False
                
            logger.info(f"Successfully connected to league")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing connection: {str(e)}")
            return False
    
    def initialize_draft_strategy(self, data_file: str = "scored_data_with_2025_rookies.csv"):
        """Initialize the draft strategy engine"""
        try:
            self.draft_strategy = DraftStrategy(draft_position=4)  # Configurable
            logger.info("Draft strategy engine initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing draft strategy: {str(e)}")
            return False
    
    def get_roster_snapshot(self) -> Dict[str, Set[str]]:
        """Get current roster snapshot for all teams"""
        try:
            rosters = get_current_rosters(self.league)
            roster_snapshot = {}
            
            for team_name, roster in rosters.items():
                # Extract player names from roster data
                players = set()
                if roster and isinstance(roster, list):
                    for player in roster:
                        if isinstance(player, dict):
                            # Handle different name formats from Yahoo API
                            name = self._extract_player_name(player)
                            if name:
                                players.add(name)
                
                roster_snapshot[team_name] = players
                
            return roster_snapshot
            
        except Exception as e:
            logger.error(f"Error getting roster snapshot: {str(e)}")
            return {}
    
    def _extract_player_name(self, player_data: dict) -> Optional[str]:
        """Extract player name from Yahoo API player data"""
        try:
            # Yahoo API can return name in different formats
            name_field = player_data.get('name', '')
            
            if isinstance(name_field, dict):
                # Format: {'full': 'Christian McCaffrey', 'first': 'Christian', 'last': 'McCaffrey'}
                return name_field.get('full', '')
            elif isinstance(name_field, str):
                return name_field
            else:
                # Try alternative fields
                full_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip()
                return full_name if full_name != " " else None
                
        except Exception as e:
            logger.debug(f"Error extracting player name: {str(e)}")
            return None
    
    def compare_rosters(self, previous: Dict[str, Set[str]], current: Dict[str, Set[str]]) -> List[DraftPick]:
        """Compare roster snapshots to detect new draft picks"""
        detected_picks = []
        
        try:
            for team_name in current.keys():
                if team_name not in previous:
                    continue
                    
                # Find new players added to this team
                new_players = current[team_name] - previous[team_name]
                
                for player_name in new_players:
                    # Create draft pick object
                    pick = DraftPick(
                        player_name=player_name,
                        team_name=team_name,
                        position="Unknown",  # We'd need to look this up
                        round_num=self.current_round,
                        pick_num=self.current_pick
                    )
                    
                    detected_picks.append(pick)
                    logger.info(f"PICK DETECTED: {pick}")
                    
                    # Update draft tracking
                    self.current_pick += 1
                    if self.current_pick > self.total_teams:
                        self.current_round += 1
                        self.current_pick = 1
            
            return detected_picks
            
        except Exception as e:
            logger.error(f"Error comparing rosters: {str(e)}")
            return []
    
    def update_strategy_engine(self, picks: List[DraftPick]):
        """Update draft strategy engine with detected picks"""
        if not self.draft_strategy:
            logger.warning("Draft strategy not initialized")
            return
            
        try:
            for pick in picks:
                # Convert player name to format expected by strategy engine
                formatted_name = self._format_player_name_for_strategy(pick.player_name)
                self.draft_strategy.simulate_pick(formatted_name)
                logger.info(f"Updated strategy: {formatted_name} drafted")
                
        except Exception as e:
            logger.error(f"Error updating strategy engine: {str(e)}")
    
    def _format_player_name_for_strategy(self, player_name: str) -> str:
        """Convert Yahoo player name to our strategy engine format"""
        # Our engine expects "Last, First" format
        # Yahoo might give us "First Last"
        
        try:
            if ", " in player_name:
                return player_name  # Already in correct format
            
            parts = player_name.strip().split()
            if len(parts) >= 2:
                first_name = " ".join(parts[:-1])
                last_name = parts[-1]
                return f"{last_name}, {first_name}"
            else:
                return player_name  # Single name, return as-is
                
        except Exception as e:
            logger.debug(f"Error formatting player name {player_name}: {str(e)}")
            return player_name
    
    def get_updated_recommendations(self, data_file: str = "scored_data_with_2025_rookies.csv") -> Optional[pd.DataFrame]:
        """Get updated draft recommendations based on current state"""
        if not self.draft_strategy:
            logger.warning("Draft strategy not initialized")
            return None
            
        try:
            # Load player data (this should be cached/optimized in production)
            data = pd.read_csv(data_file)
            
            # Get current round strategy
            recommendations = self.draft_strategy.get_round_strategy(
                data, 
                current_round=self.current_round,
                top_n=12
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            return None
    
    def is_my_turn(self) -> bool:
        """Check if it's my turn to pick"""
        if not self.my_team_name:
            return False
            
        # Calculate which team should pick based on current pick number
        # This is simplified - real logic would depend on draft order
        return False  # Placeholder
    
    def start_monitoring(self, data_file: str = "scored_data_with_2025_rookies.csv"):
        """Start live draft monitoring"""
        logger.info(f"🔴 STARTING LIVE DRAFT MONITORING (polling every {self.polling_interval}s)")
        
        if not self.initialize_connection():
            logger.error("Failed to initialize connection")
            return False
            
        if not self.initialize_draft_strategy(data_file):
            logger.error("Failed to initialize draft strategy")
            return False
        
        # Get initial roster snapshot
        self.previous_rosters = self.get_roster_snapshot()
        if not self.previous_rosters:
            logger.error("Failed to get initial roster snapshot")
            return False
            
        logger.info(f"📊 Initial snapshot: {len(self.previous_rosters)} teams found")
        self.is_monitoring = True
        
        try:
            while self.is_monitoring:
                # Get current roster state
                current_rosters = self.get_roster_snapshot()
                
                if current_rosters:
                    # Detect new picks
                    new_picks = self.compare_rosters(self.previous_rosters, current_rosters)
                    
                    if new_picks:
                        # Update strategy engine
                        self.update_strategy_engine(new_picks)
                        self.detected_picks.extend(new_picks)
                        
                        # Get updated recommendations
                        recommendations = self.get_updated_recommendations(data_file)
                        if recommendations is not None:
                            logger.info("📈 UPDATED RECOMMENDATIONS:")
                            print(recommendations[['name', 'position', 'team', 'projected_points', 'adjusted_value']].head())
                    
                    # Update previous state
                    self.previous_rosters = current_rosters
                
                # Wait before next poll
                logger.debug(f"⏱️  Waiting {self.polling_interval}s until next poll...")
                time.sleep(self.polling_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring stopped by user")
            self.is_monitoring = False
        except Exception as e:
            logger.error(f"Error during monitoring: {str(e)}")
            self.is_monitoring = False
            
        return True
    
    def stop_monitoring(self):
        """Stop live draft monitoring"""
        self.is_monitoring = False
        logger.info("🛑 Live draft monitoring stopped")
    
    def get_draft_summary(self) -> Dict:
        """Get summary of detected picks"""
        return {
            'total_picks': len(self.detected_picks),
            'current_round': self.current_round,
            'current_pick': self.current_pick,
            'picks': [str(pick) for pick in self.detected_picks]
        }

def main():
    """Test the live draft monitor"""
    monitor = LiveDraftMonitor(
        polling_interval=15,  # Poll every 15 seconds
        my_team_name="Your Team Name"  # Configure this
    )
    
    # Start monitoring
    monitor.start_monitoring()

if __name__ == "__main__":
    main()