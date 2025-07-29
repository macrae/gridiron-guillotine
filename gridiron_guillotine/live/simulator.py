"""
Draft simulation and scenario testing
"""

import random
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from copy import deepcopy

from ..core.strategy import ChampionshipDraftStrategy
from ..core.models import DraftPick, DraftState, LeagueSettings, Position, Player
from ..core.config import Config, get_config
from ..data.loaders import PlayerDataLoader

logger = logging.getLogger(__name__)


@dataclass
class SimulationTeam:
    """Represents a team in draft simulation"""
    team_id: int
    team_name: str
    drafted_players: List[Player] = field(default_factory=list)
    strategy_type: str = "balanced"  # balanced, rb_heavy, wr_heavy, etc.
    

@dataclass
class SimulationResults:
    """Results from draft simulation"""
    draft_picks: List[DraftPick]
    user_roster: List[Player]
    simulation_id: str
    user_draft_position: int
    total_rounds: int
    strategy_effectiveness: Dict[str, float]
    position_breakdown: Dict[str, int]
    

class DraftSimulator:
    """Simulate draft scenarios for strategy testing"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.strategy = ChampionshipDraftStrategy(config)
        self.data_loader = PlayerDataLoader(config)
        self.players_data = None
        
    def load_player_data(self) -> bool:
        """Load player data for simulation"""
        try:
            self.players_data = self.data_loader.load_scored_data()
            if self.players_data is None or len(self.players_data) == 0:
                logger.error("No player data available for simulation")
                return False
            
            logger.info(f"Loaded {len(self.players_data)} players for simulation")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load player data: {e}")
            return False
    
    def simulate_draft(self, user_position: int, num_teams: int = 12, num_rounds: int = 15,
                      league_settings: Optional[LeagueSettings] = None) -> Optional[SimulationResults]:
        """Simulate a complete draft"""
        
        if not self.players_data:
            if not self.load_player_data():
                return None
        
        # Setup league settings
        if not league_settings:
            league_settings = LeagueSettings(
                league_name=f"Simulation League",
                num_teams=num_teams,
                draft_position=user_position,
                scoring_type="ppr"
            )
        
        # Initialize teams
        teams = self._create_simulation_teams(num_teams, user_position)
        
        # Initialize draft state
        draft_state = DraftState(
            current_round=1,
            current_pick=1,
            picks_made=[],
            user_draft_position=user_position,
            league_settings=league_settings
        )
        
        self.strategy.initialize_draft(draft_state)
        
        # Track available players
        available_players = self._get_available_players()
        
        # Simulate draft rounds
        all_picks = []
        
        for round_num in range(1, num_rounds + 1):
            round_picks = self._simulate_round(
                round_num, teams, available_players, draft_state
            )
            all_picks.extend(round_picks)
            
            # Update draft state
            draft_state.picks_made.extend(round_picks)
            draft_state.current_round = round_num + 1
        
        # Get user's roster
        user_team = teams[user_position - 1]
        user_roster = user_team.drafted_players
        
        # Calculate results
        results = SimulationResults(
            draft_picks=all_picks,
            user_roster=user_roster,
            simulation_id=f"sim_{random.randint(1000, 9999)}",
            user_draft_position=user_position,
            total_rounds=num_rounds,
            strategy_effectiveness=self._calculate_strategy_effectiveness(user_roster),
            position_breakdown=self._get_position_breakdown(user_roster)
        )
        
        return results
    
    def simulate_multiple_drafts(self, user_position: int, num_simulations: int = 10,
                               **kwargs) -> List[SimulationResults]:
        """Run multiple draft simulations"""
        results = []
        
        for i in range(num_simulations):
            logger.info(f"Running simulation {i + 1}/{num_simulations}")
            
            result = self.simulate_draft(user_position, **kwargs)
            if result:
                results.append(result)
        
        return results
    
    def _create_simulation_teams(self, num_teams: int, user_position: int) -> List[SimulationTeam]:
        """Create teams for simulation"""
        teams = []
        
        for i in range(num_teams):
            is_user = (i + 1) == user_position
            strategy_type = "hero_rb" if is_user else self._get_random_strategy()
            
            team = SimulationTeam(
                team_id=i + 1,
                team_name=f"Team {i + 1}" if not is_user else "User Team",
                strategy_type=strategy_type
            )
            teams.append(team)
        
        return teams
    
    def _get_random_strategy(self) -> str:
        """Get random strategy for opponent teams"""
        strategies = ["balanced", "rb_heavy", "wr_heavy", "late_qb", "early_te"]
        weights = [0.4, 0.2, 0.2, 0.1, 0.1]  # Most teams use balanced
        
        return random.choices(strategies, weights=weights)[0]
    
    def _get_available_players(self) -> List[Player]:
        """Get list of available players for draft"""
        players = []
        
        for _, row in self.players_data.iterrows():
            player = Player(
                name=row.get('name', ''),
                position=Position(row.get('position', 'UNKNOWN')),
                team=row.get('team', ''),
                projected_points=row.get('projected_points', 0.0),
                vbd=row.get('vbd', 0.0),
                floor=row.get('floor', 0.0),
                ceiling=row.get('ceiling', 0.0)
            )
            players.append(player)
        
        # Sort by VBD for draft order
        players.sort(key=lambda p: p.vbd, reverse=True)
        return players
    
    def _simulate_round(self, round_num: int, teams: List[SimulationTeam], 
                       available_players: List[Player], draft_state: DraftState) -> List[DraftPick]:
        """Simulate a single round of drafting"""
        picks = []
        
        # Determine pick order (snake draft)
        if round_num % 2 == 1:  # Odd rounds - normal order
            pick_order = list(range(len(teams)))
        else:  # Even rounds - reverse order
            pick_order = list(reversed(range(len(teams))))
        
        for pick_in_round, team_idx in enumerate(pick_order, 1):
            team = teams[team_idx]
            
            # Select player
            if team.team_name == "User Team":
                # Use championship strategy for user
                selected_player = self._select_player_with_strategy(
                    team, available_players, round_num, draft_state
                )
            else:
                # Use opponent strategy
                selected_player = self._select_player_opponent_strategy(
                    team, available_players, round_num
                )
            
            if selected_player:
                # Create pick
                pick = DraftPick(
                    player_name=selected_player.name,
                    team_name=team.team_name,
                    position=selected_player.position,
                    round_num=round_num,
                    pick_num=len(picks) + 1
                )
                
                picks.append(pick)
                
                # Add to team roster
                team.drafted_players.append(selected_player)
                
                # Remove from available players
                available_players.remove(selected_player)
                
                logger.debug(f"Round {round_num}, Pick {pick_in_round}: {team.team_name} selects {selected_player.name} ({selected_player.position.value})")
        
        return picks
    
    def _select_player_with_strategy(self, team: SimulationTeam, available_players: List[Player],
                                   round_num: int, draft_state: DraftState) -> Optional[Player]:
        """Select player using championship strategy"""
        try:
            # Get strategy recommendations
            recommendations = self.strategy.get_round_strategy(
                round_num, draft_state.picks_made, draft_state.user_draft_position
            )
            
            top_picks = recommendations.get('top_picks', [])
            
            # Find first available player from recommendations
            for rec in top_picks:
                player_name = rec.get('name', '')
                for player in available_players:
                    if player.name == player_name:
                        return player
            
            # Fallback: select highest VBD available
            if available_players:
                return available_players[0]
            
        except Exception as e:
            logger.error(f"Error selecting player with strategy: {e}")
        
        return None
    
    def _select_player_opponent_strategy(self, team: SimulationTeam, available_players: List[Player],
                                       round_num: int) -> Optional[Player]:
        """Select player using opponent strategy"""
        if not available_players:
            return None
        
        # Filter by strategy type
        if team.strategy_type == "rb_heavy":
            # Prioritize RBs in early rounds
            if round_num <= 6:
                rbs = [p for p in available_players if p.position == Position.RB]
                if rbs:
                    return rbs[0]
        
        elif team.strategy_type == "wr_heavy":
            # Prioritize WRs
            if round_num <= 6:
                wrs = [p for p in available_players if p.position == Position.WR]
                if wrs:
                    return wrs[0]
        
        elif team.strategy_type == "early_te":
            # Take TE early
            if round_num <= 4:
                tes = [p for p in available_players if p.position == Position.TE]
                if tes and len([p for p in team.drafted_players if p.position == Position.TE]) == 0:
                    return tes[0]
        
        elif team.strategy_type == "late_qb":
            # Avoid QB until late
            if round_num >= 8:
                qbs = [p for p in available_players if p.position == Position.QB]
                if qbs and len([p for p in team.drafted_players if p.position == Position.QB]) == 0:
                    return qbs[0]
        
        # Default: best available player (balanced strategy)
        return available_players[0]
    
    def _calculate_strategy_effectiveness(self, roster: List[Player]) -> Dict[str, float]:
        """Calculate how effective the draft strategy was"""
        if not roster:
            return {}
        
        total_vbd = sum(player.vbd for player in roster)
        total_projected = sum(player.projected_points for player in roster)
        
        # Position-specific analysis
        rb_count = len([p for p in roster if p.position == Position.RB])
        wr_count = len([p for p in roster if p.position == Position.WR])
        
        return {
            'total_vbd': total_vbd,
            'total_projected_points': total_projected,
            'average_vbd_per_player': total_vbd / len(roster),
            'rb_drafted': rb_count,
            'wr_drafted': wr_count,
            'hero_rb_success': 1.0 if rb_count >= 2 else 0.5 if rb_count >= 1 else 0.0
        }
    
    def _get_position_breakdown(self, roster: List[Player]) -> Dict[str, int]:
        """Get position breakdown of roster"""
        breakdown = {}
        
        for position in Position:
            count = len([p for p in roster if p.position == position])
            if count > 0:
                breakdown[position.value] = count
        
        return breakdown
    
    def analyze_simulation_results(self, results: List[SimulationResults]) -> Dict[str, Any]:
        """Analyze results from multiple simulations"""
        if not results:
            return {}
        
        # Aggregate metrics
        total_vbd = [r.strategy_effectiveness.get('total_vbd', 0) for r in results]
        total_projected = [r.strategy_effectiveness.get('total_projected_points', 0) for r in results]
        hero_rb_success = [r.strategy_effectiveness.get('hero_rb_success', 0) for r in results]
        
        # Position drafting patterns
        rb_drafted = [r.strategy_effectiveness.get('rb_drafted', 0) for r in results]
        wr_drafted = [r.strategy_effectiveness.get('wr_drafted', 0) for r in results]
        
        return {
            'simulations_run': len(results),
            'average_total_vbd': sum(total_vbd) / len(total_vbd),
            'average_projected_points': sum(total_projected) / len(total_projected),
            'hero_rb_success_rate': sum(hero_rb_success) / len(hero_rb_success),
            'average_rbs_drafted': sum(rb_drafted) / len(rb_drafted),
            'average_wrs_drafted': sum(wr_drafted) / len(wr_drafted),
            'vbd_range': {
                'min': min(total_vbd),
                'max': max(total_vbd),
                'std': (sum((x - sum(total_vbd)/len(total_vbd))**2 for x in total_vbd) / len(total_vbd))**0.5
            }
        }
    
    def test_draft_position_performance(self, positions: List[int], num_simulations: int = 5) -> Dict[int, Dict[str, Any]]:
        """Test performance across different draft positions"""
        results = {}
        
        for position in positions:
            logger.info(f"Testing draft position {position}")
            
            sim_results = self.simulate_multiple_drafts(
                user_position=position,
                num_simulations=num_simulations
            )
            
            analysis = self.analyze_simulation_results(sim_results)
            results[position] = analysis
        
        return results