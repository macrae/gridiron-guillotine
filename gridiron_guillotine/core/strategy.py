"""
Championship Draft Strategy Engine
Research-validated Hero-RB strategy with PPR optimization and advanced metrics
Based on championship analysis showing 20.2% advance rates vs 16.7% baseline
"""

import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

from .models import Player, DraftPick, LeagueSettings, Position, HeroRBPhase, DraftState
from .config import Config, get_config
from .metrics import AdvancedMetrics, DraftPositionAnalyzer
from .tiers import EnhancedTierCalculator, PositionTierState

logger = logging.getLogger(__name__)


class ChampionshipDraftStrategy:
    """
    Research-validated Championship Draft Strategy Engine
    Implements Hero-RB strategy (20.2% advance rate vs 16.7% baseline)
    Includes PPR optimization, advanced metrics, and position flexibility
    """
    
    def __init__(self, 
                 draft_position: int,
                 league_settings: Optional[LeagueSettings] = None,
                 config: Optional[Config] = None):
        """
        Initialize championship draft strategy
        
        Args:
            draft_position: Your position in the draft (1-based)
            league_settings: League configuration
            config: Strategy configuration
        """
        self.draft_position = draft_position
        self.league_settings = league_settings or LeagueSettings()
        self.config = config or get_config()
        
        # Initialize components
        self.advanced_metrics = AdvancedMetrics(self.config)
        self.position_analyzer = DraftPositionAnalyzer(self.config)
        self.tier_calculator = EnhancedTierCalculator(self.config)
        
        # Initialize draft state
        self.draft_state = DraftState()
        self._initialize_team_rosters()
        
        logger.info(f"Championship strategy initialized for position {draft_position} "
                   f"(Hero-RB + Advanced Metrics + Enhanced Tiers + Position Logic enabled)")
    
    def _initialize_team_rosters(self):
        """Initialize empty rosters for all teams"""
        self.draft_state.team_rosters = {}
        
        for i in range(1, self.league_settings.teams + 1):
            self.draft_state.team_rosters[f'Team{i}'] = {
                pos: [] for pos in self.league_settings.position_limits.keys()
            }
    
    def get_my_roster(self) -> Dict[Position, List[str]]:
        """Get current roster for my team"""
        return self.draft_state.team_rosters.get(f'Team{self.draft_position}', {})
    
    def _determine_hero_rb_phase(self, current_round: int) -> HeroRBPhase:
        """
        Determine Hero-RB phase based on research
        Research: Hero-RB strategy phases for optimal execution
        """
        if current_round <= 2 and not self.draft_state.hero_rb_acquired:
            return HeroRBPhase.HERO_ACQUISITION
        elif current_round <= 6:
            return HeroRBPhase.PIVOT_PHASE
        else:
            return HeroRBPhase.DEPTH_PHASE
    
    def calculate_positional_scarcity(self, available_players: pd.DataFrame) -> Dict[Position, float]:
        """
        Calculate positional scarcity factors based on available players
        Higher scarcity = more valuable to draft early
        """
        scarcity_factors = {}
        
        for position in Position:
            pos_players = available_players[available_players['position'] == position.value]
            
            if len(pos_players) == 0:
                scarcity_factors[position] = 1.0
                continue
            
            # Calculate scarcity based on VBD distribution and remaining draft capital
            total_needed = self.config.replacement_levels[position]
            available_count = len(pos_players)
            
            if available_count == 0:
                scarcity_factors[position] = 2.0  # Maximum scarcity
            else:
                # Higher scarcity when fewer quality players available
                quality_threshold = pos_players['vbd'].quantile(0.6) if 'vbd' in pos_players.columns else 0
                quality_count = len(pos_players[pos_players['vbd'] >= quality_threshold]) if 'vbd' in pos_players.columns else available_count
                scarcity_ratio = total_needed / max(quality_count, 1)
                scarcity_factors[position] = min(2.0, max(0.5, scarcity_ratio))
        
        # Hero-RB scarcity adjustments (Research-based)
        hero_phase = self._determine_hero_rb_phase(self.draft_state.current_round)
        
        if hero_phase == HeroRBPhase.HERO_ACQUISITION:
            scarcity_factors[Position.RB] *= 1.5  # Boost elite RB scarcity
        elif hero_phase == HeroRBPhase.PIVOT_PHASE:
            scarcity_factors[Position.RB] *= 0.6  # Reduce RB scarcity (avoid RB2 trap)
        else:  # DEPTH_PHASE
            scarcity_factors[Position.RB] *= 1.3  # Boost RB depth scarcity
        
        logger.debug(f"Hero-RB Phase: {hero_phase.value}, Scarcity factors: {scarcity_factors}")
        return scarcity_factors
    
    def calculate_tier_dropoffs(self, available_players: pd.DataFrame, 
                               picks_until_next_turn: int = 12) -> Dict[Position, float]:
        """
        Calculate enhanced tier urgency using research-validated tier analysis
        Research: Draft last high-tier player rather than first low-tier player
        """
        if 'tier' not in available_players.columns:
            logger.warning("Tier information not found, using legacy calculation")
            return {pos: 0.0 for pos in Position}
        
        # Get current tier states for all positions
        tier_states = self.tier_calculator.get_position_tier_states(available_players)
        
        tier_dropoffs = {}
        
        for position in Position:
            if position not in tier_states:
                tier_dropoffs[position] = 0.0
                continue
                
            state = tier_states[position]
            
            # Calculate tier urgency boost based on research
            urgency_boost = 0.0
            
            if state.current_tier in state.tiers:
                current_tier_info = state.tiers[state.current_tier]
                
                # Critical tier urgency (last few players)
                if current_tier_info.players_remaining <= 2:
                    urgency_boost = 0.8  # 80% urgency boost
                elif current_tier_info.players_remaining <= 4:
                    urgency_boost = 0.5  # 50% urgency boost
                elif current_tier_info.players_remaining <= 7:
                    urgency_boost = 0.3  # 30% urgency boost
                
                # Add dropoff magnitude factor
                urgency_boost += min(0.4, current_tier_info.dropoff_magnitude)
                
                # Adjust for draft flow
                if picks_until_next_turn <= 5:
                    urgency_boost *= 1.5  # Increase urgency when our pick is soon
                elif picks_until_next_turn >= 15:
                    urgency_boost *= 0.7  # Reduce urgency when we have time
            
            tier_dropoffs[position] = min(1.0, urgency_boost)
        
        logger.debug(f"Enhanced tier urgency calculated: {tier_dropoffs}")
        return tier_dropoffs
    
    def calculate_vbd(self, players_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Value-Based Drafting scores for all players"""
        df = players_df.copy()
        
        # Ensure projected_points column exists and handle missing values
        if 'projected_points' not in df.columns:
            logger.warning("projected_points column not found, using weighted_mean")
            df['projected_points'] = df.get('weighted_mean', 0)
        
        # Fill NaN values with 0
        df['projected_points'] = df['projected_points'].fillna(0)
        
        for position in Position:
            pos_players = df[df['position'] == position.value].copy()
            
            if len(pos_players) == 0:
                continue
            
            logger.debug(f"Processing {position.value}: {len(pos_players)} total players")
            
            # Filter out players with zero or negative projected points for replacement calculation
            valid_pos_players = pos_players[pos_players['projected_points'] > 0]
            
            logger.debug(f"{position.value}: {len(valid_pos_players)} valid players with projected_points > 0")
            
            if len(valid_pos_players) == 0:
                # No valid players for this position, set VBD to 0
                mask = df['position'] == position.value
                df.loc[mask, 'vbd'] = 0
                logger.debug(f"{position.value}: No valid players, setting VBD to 0")
                continue
            
            # Use configured replacement levels
            replacement_level = self.config.replacement_levels[position]
            
            logger.debug(f"{position.value}: Replacement level = {replacement_level}, Valid players = {len(valid_pos_players)}")
            
            try:
                if len(valid_pos_players) >= replacement_level and replacement_level > 0:
                    # Get the replacement player's points
                    sorted_players = valid_pos_players.nlargest(replacement_level, 'projected_points')
                    if len(sorted_players) >= replacement_level:
                        replacement_points = sorted_players.iloc[-1]['projected_points']
                    else:
                        replacement_points = valid_pos_players['projected_points'].min()
                else:
                    # If fewer players than replacement level, use minimum of valid players
                    replacement_points = valid_pos_players['projected_points'].min()
                
                logger.debug(f"{position.value}: Replacement points = {replacement_points}")
                
            except (IndexError, KeyError, ValueError) as e:
                logger.warning(f"Error calculating replacement points for {position.value}: {e}")
                logger.warning(f"  Valid players shape: {valid_pos_players.shape}")
                logger.warning(f"  Projected points range: {valid_pos_players['projected_points'].min()} - {valid_pos_players['projected_points'].max()}")
                replacement_points = 0.0  # Fallback
            
            # Calculate VBD
            mask = df['position'] == position.value
            df.loc[mask, 'vbd'] = df.loc[mask, 'projected_points'] - replacement_points
        
        # Ensure VBD column exists with default 0 values
        if 'vbd' not in df.columns:
            df['vbd'] = 0
        df['vbd'] = df['vbd'].fillna(0)
        
        return df
    
    def initialize_tiers(self, players_df: pd.DataFrame, current_round: int = 1, 
                        picks_until_next_turn: int = 12) -> pd.DataFrame:
        """
        Initialize enhanced dynamic tiers with draft flow awareness
        Research: Target positions where tier drop-offs are steepest
        """
        picks_remaining_in_round = max(1, self.league_settings.teams - (self.draft_position - 1))
        
        return self.tier_calculator.calculate_dynamic_tiers(
            players_df, 
            current_round, 
            picks_remaining_in_round,
            picks_until_next_turn
        )
    
    def adjust_player_value(self, player_row: pd.Series, scarcity_factors: Dict[Position, float],
                          tier_dropoffs: Dict[Position, float], current_round: int) -> float:
        """
        Comprehensive player value adjustment considering multiple factors
        Integrates Hero-RB, PPR, Advanced Metrics, and Position Logic
        """
        base_value = player_row.get('vbd', 0)
        position = Position(player_row['position'])
        player_name = player_row.get('name', '')
        
        # Scarcity boost
        scarcity_boost = scarcity_factors.get(position, 1.0)
        
        # Enhanced Tier urgency boost (Research: Draft last high-tier vs first low-tier)
        tier_urgency = tier_dropoffs.get(position, 0.0)
        tier_boost = tier_urgency * 0.5  # Up to 50% boost for critical tier situations
        
        # Additional tier-specific boost if we have tier urgency info
        if hasattr(player_row, 'tier_urgency') and player_row.get('tier_urgency'):
            urgency_multipliers = {
                'critical': 0.4,  # 40% additional boost for critical tier
                'high': 0.25,     # 25% boost for high urgency
                'moderate': 0.15, # 15% boost for moderate
                'low': 0.0        # No additional boost
            }
            tier_boost += urgency_multipliers.get(player_row.get('tier_urgency', 'low'), 0.0)
        
        # Hero-RB Strategy Boost (Research: 20.2% advance rate)
        position_boost = 1.0
        hero_phase = self._determine_hero_rb_phase(current_round)
        
        if position == Position.RB:
            if hero_phase == HeroRBPhase.HERO_ACQUISITION:
                # Massive boost for elite Hero RBs only
                if player_name in self.config.elite_hero_rbs:
                    position_boost = 1.8  # 80% boost for hero candidates
                else:
                    position_boost = 0.7  # Penalty for non-elite RBs
            elif hero_phase == HeroRBPhase.PIVOT_PHASE:
                # Research key: AVOID RBs in rounds 3-6
                position_boost = 0.4  # Heavy penalty during pivot
            else:  # DEPTH_PHASE
                position_boost = 1.4  # Boost for RB depth accumulation
                
        elif position == Position.WR:
            if hero_phase == HeroRBPhase.HERO_ACQUISITION:
                position_boost = 1.0  # Neutral if no Hero RB yet
            elif hero_phase == HeroRBPhase.PIVOT_PHASE:
                position_boost = 1.3  # Major boost during pivot phase
            else:  # DEPTH_PHASE
                position_boost = 1.1  # Moderate boost for WR depth
                
        elif position in [Position.K, Position.DEF]:
            # Always penalize K/DEF early (research-validated)
            if current_round < 13:
                position_boost = 0.3
        
        # Roster need boost
        my_roster = self.get_my_roster()
        position_count = len(my_roster.get(position, []))
        position_limit = self.league_settings.position_limits.get(position, 1)
        
        if position_count == 0:
            roster_need_boost = 1.5  # High boost for unfilled positions
        elif position_count < position_limit:
            roster_need_boost = 1.2  # Moderate boost for partially filled
        else:
            roster_need_boost = 0.8  # Penalty for filled positions
        
        # Upside/ceiling boost for high-variance players
        upside_boost = 1.0
        if 'ceiling' in player_row and 'floor' in player_row:
            ceiling = player_row.get('ceiling', player_row.get('projected_points', 0))
            floor = player_row.get('floor', player_row.get('projected_points', 0))
            projected_points = player_row.get('projected_points', 0)
            
            if projected_points > 0:
                variance = (ceiling - floor) / projected_points
                upside_boost = 1 + min(0.2, variance * 0.1)  # Up to 20% boost
        
        # Rookie boost in later rounds
        rookie_boost = 1.0
        if player_row.get('rookie', False) and current_round > 10:
            rookie_boost = 1.1
        
        # PPR adjustments (Research: 6-8 weekly point advantage)
        ppr_boost = 0
        if self.league_settings.ppr:
            # Pass-catching RB bonuses (Research: massive PPR value)
            for name, bonus in self.config.ppr_pass_catchers.items():
                if name.split(',')[0] in player_name:
                    ppr_boost += bonus
                    break
            
            # Pure rusher penalties (Research: reduced PPR value)
            for name, penalty in self.config.ppr_pure_rushers.items():
                if name.split(',')[0] in player_name:
                    ppr_boost += penalty  # penalty is negative
                    break
            
            # General PPR position boosts
            if position == Position.WR:
                ppr_boost += 1.0  # Research: WRs gain 6-8 points weekly
        
        # Advanced Metrics Integration (Research: WOPR + Expected Points + Context)
        advanced_boost = 0
        if 'advanced_score' in player_row:
            advanced_score = player_row.get('advanced_score', 0)
            projected_points = player_row.get('projected_points', 0)
            
            if projected_points > 0:
                # Advanced metrics provide up to 20% boost based on research validation
                advanced_ratio = advanced_score / projected_points
                advanced_boost = min(0.2, max(-0.1, (advanced_ratio - 1.0) * 0.5))
        
        # Draft Position Specific Adjustments (Research: Different strategies by position)
        position_adjustment = self.position_analyzer.calculate_position_adjustment(
            Player(name=player_name, position=position, team=player_row.get('team', ''), 
                  projected_points=player_row.get('projected_points', 0)),
            self.draft_position, current_round
        )
        
        # Combine all factors
        final_value = (base_value * scarcity_boost * (1 + tier_boost) * 
                      position_boost * roster_need_boost * upside_boost * rookie_boost * 
                      (1 + advanced_boost)) + ppr_boost + position_adjustment
        
        return max(0, final_value)
    
    def get_round_strategy(self, player_df: pd.DataFrame, current_round: int, 
                          top_n: int = 12, picks_until_next_turn: int = 12) -> pd.DataFrame:
        """
        Generate strategy for a specific round with comprehensive player evaluation
        Integrates Hero-RB + PPR + Advanced Metrics for championship-level analysis
        """
        # Update draft state
        self.draft_state.current_round = current_round
        self.draft_state.hero_rb_phase = self._determine_hero_rb_phase(current_round)
        
        # Process player data with enhanced tiers
        player_df = self.calculate_vbd(player_df)
        player_df = self.initialize_tiers(player_df, current_round, picks_until_next_turn)
        player_df = self.advanced_metrics.calculate_for_dataframe(player_df)
        
        # Filter to available players
        available_players = player_df[~player_df['name'].isin(self.draft_state.drafted_players)].copy()
        
        # Calculate strategy factors with enhanced tier analysis
        scarcity_factors = self.calculate_positional_scarcity(available_players)
        tier_dropoffs = self.calculate_tier_dropoffs(available_players, picks_until_next_turn)
        
        # Calculate adjusted values
        available_players['adjusted_value'] = available_players.apply(
            lambda row: self.adjust_player_value(row, scarcity_factors, tier_dropoffs, current_round),
            axis=1
        )
        
        # Apply round-specific filtering
        priority_positions = self._get_priority_positions(current_round)
        my_roster = self.get_my_roster()
        
        # Filter by priority and roster limits
        strategy_players = available_players[
            (available_players['position'].isin([pos.value for pos in priority_positions])) &
            (available_players.apply(lambda x: len(my_roster.get(Position(x['position']), [])) < 
                                   self.league_settings.position_limits.get(Position(x['position']), 1), axis=1))
        ]
        
        # If not enough players, expand criteria
        if len(strategy_players) < top_n:
            remaining = available_players[~available_players.index.isin(strategy_players.index)]
            additional_needed = top_n - len(strategy_players)
            strategy_players = pd.concat([
                strategy_players, 
                remaining.nlargest(additional_needed, 'adjusted_value')
            ])
        
        # Return top players with comprehensive data including enhanced tier info
        columns = ['name', 'position', 'team', 'projected_points', 'vbd', 'adjusted_value', 'tier']
        
        # Add enhanced tier columns if available
        if 'tier_urgency' in strategy_players.columns:
            columns.append('tier_urgency')
        if 'tier_dropoff_magnitude' in strategy_players.columns:
            columns.append('tier_dropoff_magnitude')
            
        # Add advanced metrics columns if available
        if 'advanced_score' in strategy_players.columns:
            columns.extend(['advanced_score', 'wopr', 'expected_points', 'context_multiplier'])
        
        result = strategy_players.nlargest(top_n, 'adjusted_value')[columns].reset_index(drop=True)
        
        logger.info(f"Round {current_round} strategy generated with {len(result)} players")
        return result
    
    def get_tier_recommendations(self, available_players: pd.DataFrame, 
                               picks_until_next_turn: int = 12) -> List[str]:
        """
        Get tier-based position recommendations for current draft state
        Research: Target positions where tier drop-offs are steepest
        """
        if 'tier' not in available_players.columns:
            return ["Enhanced tier data not available - use initialize_tiers() first"]
        
        recommendations = self.tier_calculator.get_tier_recommendations(
            self.tier_calculator.get_position_tier_states(available_players),
            picks_until_next_turn
        )
        
        tier_messages = []
        for position, reason, urgency_score in recommendations[:3]:  # Top 3 recommendations
            tier_messages.append(f"🎯 {reason} (Score: {urgency_score:.1f})")
        
        if not tier_messages:
            tier_messages.append("✅ No critical tier situations - draft best available value")
        
        return tier_messages
    
    def _get_priority_positions(self, current_round: int) -> List[Position]:
        """Get priority positions for a given round"""
        my_roster = self.get_my_roster()
        
        if current_round <= 5:
            # Early rounds: Focus on RB/WR, elite TE if available  
            priority = [Position.RB, Position.WR]
            # Add TE if elite options available (would need tier analysis)
            priority.append(Position.TE)
        elif current_round <= 9:
            # Middle rounds: Add QB if needed, otherwise RB/WR depth
            priority = [Position.RB, Position.WR]
            if len(my_roster.get(Position.QB, [])) == 0:
                priority.insert(0, Position.QB)  # Prioritize QB if none drafted
        elif current_round <= 12:
            # Late-middle: All positions except K/DEF
            priority = [Position.QB, Position.RB, Position.WR, Position.TE]
        else:
            # Final rounds: K/DEF only
            priority = [Position.K, Position.DEF]
        
        return priority
    
    def simulate_pick(self, player_name: str, team_number: Optional[int] = None):
        """Simulate a draft pick and update Hero-RB state"""
        if team_number is None:
            team_number = self.draft_position
        
        self.draft_state.drafted_players.add(player_name)
        
        # Update Hero-RB state tracking
        if player_name in self.config.elite_hero_rbs:
            if self.draft_state.current_round <= 2 and not self.draft_state.hero_rb_acquired:
                self.draft_state.hero_rb_acquired = True
                self.draft_state.hero_rb_phase = HeroRBPhase.PIVOT_PHASE
                logger.info(f"🏆 HERO RB ACQUIRED: {player_name} in Round {self.draft_state.current_round}")
        
        # Update phase based on round
        if self.draft_state.current_round >= 7:
            self.draft_state.hero_rb_phase = HeroRBPhase.DEPTH_PHASE
        elif self.draft_state.current_round >= 3:
            if self.draft_state.hero_rb_acquired:
                self.draft_state.hero_rb_phase = HeroRBPhase.PIVOT_PHASE
            else:
                self.draft_state.hero_rb_phase = HeroRBPhase.HERO_ACQUISITION
        
        logger.debug(f"Pick: {player_name} (Team{team_number}) - Hero Phase: {self.draft_state.hero_rb_phase.value}")


# Compatibility alias for existing code
DraftStrategy = ChampionshipDraftStrategy