"""
Live draft monitoring with championship strategy integration
"""

import time
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..api.yahoo import YahooFantasyClient
from ..core.strategy import ChampionshipDraftStrategy
from ..core.models import DraftPick, DraftState, LeagueSettings, Position
from ..core.config import Config, get_config

logger = logging.getLogger(__name__)


@dataclass
class DraftMonitorState:
    """Track draft monitoring state"""
    draft_started: bool = False
    current_round: int = 1
    current_pick: int = 1
    picks_made: List[DraftPick] = field(default_factory=list)
    last_check: datetime = field(default_factory=datetime.now)
    monitoring_active: bool = False
    

class LiveDraftMonitor:
    """Monitor live drafts and provide real-time strategy recommendations"""
    
    def __init__(self, config: Optional[Config] = None, yahoo_client: Optional[YahooFantasyClient] = None):
        self.config = config or get_config()
        self.yahoo_client = yahoo_client or YahooFantasyClient(config)
        self.strategy = ChampionshipDraftStrategy(config)
        self.state = DraftMonitorState()
        
        # Event callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'draft_started': [],
            'pick_made': [],
            'turn_approaching': [],
            'recommendation_updated': [],
            'draft_completed': []
        }
        
    def add_callback(self, event: str, callback: Callable):
        """Add event callback"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
        else:
            logger.warning(f"Unknown event type: {event}")
    
    def start_monitoring(self, draft_position: int, league_settings: Optional[LeagueSettings] = None,
                        polling_interval: int = 20) -> bool:
        """Start monitoring a live draft"""
        try:
            # Initialize Yahoo API connection
            if not self.yahoo_client.authenticate():
                logger.error("Failed to authenticate with Yahoo API")
                return False
            
            league_info = self.yahoo_client.get_league_info()
            if not league_info:
                logger.error("Failed to get league information")
                return False
            
            # Setup league settings
            if not league_settings:
                league_settings = LeagueSettings(
                    league_name=league_info.get('name', 'Unknown'),
                    num_teams=league_info.get('num_teams', 12),
                    draft_position=draft_position,
                    scoring_type=league_info.get('scoring_type', 'ppr')
                )
            
            # Initialize draft state
            draft_state = DraftState(
                current_round=1,
                current_pick=1,
                picks_made=[],
                user_draft_position=draft_position,
                league_settings=league_settings
            )
            
            self.strategy.initialize_draft(draft_state)
            self.state.monitoring_active = True
            
            logger.info(f"Starting draft monitoring (position {draft_position}, polling every {polling_interval}s)")
            
            # Fire draft started callbacks
            for callback in self.callbacks['draft_started']:
                try:
                    callback(league_settings, draft_state)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            # Main monitoring loop
            previous_rosters = {}
            
            while self.state.monitoring_active:
                try:
                    # Get current rosters
                    current_rosters = self.yahoo_client.get_current_rosters()
                    
                    if current_rosters and previous_rosters:
                        # Detect new picks
                        new_picks = self.yahoo_client.detect_draft_picks(previous_rosters, current_rosters)
                        
                        if new_picks:
                            self._process_new_picks(new_picks, draft_state)
                    
                    previous_rosters = current_rosters
                    self.state.last_check = datetime.now()
                    
                    # Check if it's approaching user's turn
                    self._check_turn_approaching(draft_state)
                    
                    # Update recommendations
                    self._update_recommendations(draft_state)
                    
                    time.sleep(polling_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Draft monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error during monitoring: {e}")
                    time.sleep(polling_interval)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start draft monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop draft monitoring"""
        self.state.monitoring_active = False
        logger.info("Draft monitoring stopped")
    
    def _process_new_picks(self, new_picks: List[DraftPick], draft_state: DraftState):
        """Process newly detected picks"""
        for pick in new_picks:
            # Update draft state
            draft_state.picks_made.append(pick)
            self.state.picks_made.append(pick)
            
            # Update round/pick tracking
            total_picks = len(draft_state.picks_made)
            num_teams = draft_state.league_settings.num_teams
            
            self.state.current_round = (total_picks - 1) // num_teams + 1
            self.state.current_pick = total_picks % num_teams + 1
            
            draft_state.current_round = self.state.current_round
            draft_state.current_pick = self.state.current_pick
            
            logger.info(f"Pick detected: {pick.player_name} ({pick.position.value}) to {pick.team_name}")
            
            # Fire pick made callbacks
            for callback in self.callbacks['pick_made']:
                try:
                    callback(pick, draft_state)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def _check_turn_approaching(self, draft_state: DraftState):
        """Check if user's turn is approaching"""
        user_position = draft_state.user_draft_position
        num_teams = draft_state.league_settings.num_teams
        current_round = draft_state.current_round
        current_pick = draft_state.current_pick
        
        # Calculate user's next pick
        if current_round % 2 == 1:  # Odd round (standard order)
            user_pick_in_round = user_position
        else:  # Even round (snake order)
            user_pick_in_round = num_teams - user_position + 1
        
        picks_until_user = user_pick_in_round - current_pick
        
        # Notify if user's turn is approaching (within 2 picks)
        if 0 < picks_until_user <= 2:
            for callback in self.callbacks['turn_approaching']:
                try:
                    callback(picks_until_user, draft_state)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def _update_recommendations(self, draft_state: DraftState):
        """Update strategy recommendations"""
        try:
            recommendations = self.strategy.get_round_strategy(
                draft_state.current_round,
                draft_state.picks_made,
                draft_state.user_draft_position
            )
            
            # Fire recommendation callbacks
            for callback in self.callbacks['recommendation_updated']:
                try:
                    callback(recommendations, draft_state)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating recommendations: {e}")
    
    def get_current_recommendations(self, draft_state: Optional[DraftState] = None) -> Dict[str, Any]:
        """Get current draft recommendations"""
        if not draft_state:
            # Create minimal draft state for testing
            draft_state = DraftState(
                current_round=self.state.current_round,
                current_pick=self.state.current_pick,
                picks_made=self.state.picks_made,
                user_draft_position=1,  # Default
                league_settings=LeagueSettings()
            )
        
        try:
            return self.strategy.get_round_strategy(
                draft_state.current_round,
                draft_state.picks_made,
                draft_state.user_draft_position
            )
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return {}
    
    def simulate_pick(self, player_name: str, position: Position, draft_state: DraftState):
        """Simulate a pick for testing"""
        pick = DraftPick(
            player_name=player_name,
            team_name="User Team",
            position=position,
            round_num=draft_state.current_round,
            pick_num=len(draft_state.picks_made) + 1
        )
        
        self._process_new_picks([pick], draft_state)
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'monitoring_active': self.state.monitoring_active,
            'draft_started': self.state.draft_started,
            'current_round': self.state.current_round,
            'current_pick': self.state.current_pick,
            'picks_made': len(self.state.picks_made),
            'last_check': self.state.last_check.isoformat(),
            'callbacks_registered': {
                event: len(callbacks) 
                for event, callbacks in self.callbacks.items()
            }
        }


class ConsoleMonitorDisplay:
    """Console display for live draft monitoring"""
    
    def __init__(self, monitor: LiveDraftMonitor):
        self.monitor = monitor
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup console display callbacks"""
        self.monitor.add_callback('draft_started', self._on_draft_started)
        self.monitor.add_callback('pick_made', self._on_pick_made)
        self.monitor.add_callback('turn_approaching', self._on_turn_approaching)
        self.monitor.add_callback('recommendation_updated', self._on_recommendations_updated)
    
    def _on_draft_started(self, league_settings: LeagueSettings, draft_state: DraftState):
        """Handle draft started event"""
        print(f"\n🏈 DRAFT STARTED - {league_settings.league_name}")
        print(f"Position: {league_settings.draft_position}/{league_settings.num_teams}")
        print(f"Scoring: {league_settings.scoring_type.upper()}")
        print("=" * 50)
    
    def _on_pick_made(self, pick: DraftPick, draft_state: DraftState):
        """Handle pick made event"""
        print(f"Round {pick.round_num}: {pick.player_name} ({pick.position.value}) → {pick.team_name}")
    
    def _on_turn_approaching(self, picks_until_user: int, draft_state: DraftState):
        """Handle turn approaching event"""
        print(f"\n⚡ YOUR TURN IN {picks_until_user} PICK{'S' if picks_until_user > 1 else ''}!")
        print("Get ready to draft!")
    
    def _on_recommendations_updated(self, recommendations: Dict[str, Any], draft_state: DraftState):
        """Handle recommendations updated event"""
        if recommendations.get('top_picks'):
            print(f"\n📊 TOP RECOMMENDATIONS (Round {draft_state.current_round}):")
            for i, player in enumerate(recommendations['top_picks'][:5], 1):
                print(f"{i}. {player.get('name', 'Unknown')} ({player.get('position', '?')}) - {player.get('adjusted_value', 0):.1f}")