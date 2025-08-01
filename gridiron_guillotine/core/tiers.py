"""
Enhanced Tier-Based Drafting System
Research-validated tier boundaries with dynamic scarcity and draft flow analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

from .models import Position
from .config import Config, get_config

logger = logging.getLogger(__name__)


class TierUrgency(Enum):
    """Tier urgency levels for draft decision making"""
    CRITICAL = "critical"    # Last 1-2 players in tier
    HIGH = "high"           # 3-4 players remain
    MODERATE = "moderate"   # 5-7 players remain  
    LOW = "low"            # 8+ players remain


@dataclass
class TierInfo:
    """Information about a player tier"""
    tier_number: int
    players_remaining: int
    vbd_floor: float
    vbd_ceiling: float
    dropoff_magnitude: float
    urgency: TierUrgency
    next_tier_gap: float


@dataclass
class PositionTierState:
    """Current tier state for a position"""
    position: Position
    current_tier: int
    tiers: Dict[int, TierInfo]
    total_quality_remaining: int
    scarcity_multiplier: float


class EnhancedTierCalculator:
    """
    Advanced tier-based drafting calculator with dynamic boundaries
    Research: Target positions where tier drop-offs are steepest
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        
        # Dynamic tier thresholds based on position
        self.position_tier_configs = {
            Position.QB: {'base_threshold': 0.15, 'min_gap': 1.0, 'tier_size_preference': 3},
            Position.RB: {'base_threshold': 0.25, 'min_gap': 2.0, 'tier_size_preference': 4}, 
            Position.WR: {'base_threshold': 0.20, 'min_gap': 1.5, 'tier_size_preference': 5},
            Position.TE: {'base_threshold': 0.30, 'min_gap': 2.5, 'tier_size_preference': 3},
            Position.K: {'base_threshold': 0.10, 'min_gap': 0.5, 'tier_size_preference': 12},
            Position.DEF: {'base_threshold': 0.15, 'min_gap': 1.0, 'tier_size_preference': 12}
        }
    
    def calculate_dynamic_tiers(self, players_df: pd.DataFrame, 
                              current_round: int,
                              picks_remaining_in_round: int,
                              total_picks_until_next_turn: int) -> pd.DataFrame:
        """
        Calculate dynamic tier boundaries with draft flow awareness
        
        Args:
            players_df: DataFrame of available players
            current_round: Current draft round
            picks_remaining_in_round: Picks left in current round
            total_picks_until_next_turn: Total picks until we pick again
        """
        df = players_df.copy()
        df['tier'] = 1
        df['tier_urgency'] = TierUrgency.LOW.value
        df['tier_dropoff_magnitude'] = 0.0
        
        logger.info(f"Calculating dynamic tiers for round {current_round}")
        
        for position in Position:
            if position in [Position.DB, Position.DT, Position.OT, Position.UNKNOWN]:
                continue
                
            pos_players = df[df['position'] == position.value].sort_values('vbd', ascending=False).copy()
            
            if len(pos_players) < 2:
                continue
            
            # Calculate position-specific tiers
            tier_boundaries = self._calculate_position_tier_boundaries(
                pos_players, position, current_round, total_picks_until_next_turn
            )
            
            # Apply tier assignments
            self._apply_tier_assignments(df, pos_players, tier_boundaries, position)
            
        logger.info(f"Dynamic tier calculation complete for {len(df)} players")
        return df
    
    def _calculate_position_tier_boundaries(self, pos_players: pd.DataFrame, 
                                          position: Position,
                                          current_round: int,
                                          picks_until_next_turn: int) -> List[int]:
        """Calculate tier boundary positions for a specific position"""
        config = self.position_tier_configs[position]
        base_threshold = config['base_threshold']
        min_gap = config['min_gap']
        preferred_tier_size = config['tier_size_preference']
        
        # Adjust threshold based on draft flow urgency
        draft_flow_multiplier = self._calculate_draft_flow_multiplier(
            picks_until_next_turn, current_round, position
        )
        
        adjusted_threshold = base_threshold * draft_flow_multiplier
        
        boundaries = []
        vbd_values = pos_players['vbd'].values
        
        current_tier_size = 0
        
        for i in range(1, len(vbd_values)):
            current_vbd = vbd_values[i]
            previous_vbd = vbd_values[i-1]
            current_tier_size += 1
            
            # Calculate percentage drop and absolute gap
            if previous_vbd > 0:
                pct_drop = (previous_vbd - current_vbd) / previous_vbd
                abs_gap = previous_vbd - current_vbd
            else:
                pct_drop = 0
                abs_gap = 0
            
            # Dynamic boundary detection
            should_create_boundary = False
            
            # Standard percentage drop
            if pct_drop > adjusted_threshold and abs_gap > min_gap:
                should_create_boundary = True
            
            # Force boundaries for very large tier sizes
            elif current_tier_size >= preferred_tier_size * 2:
                should_create_boundary = True
            
            # Natural breakpoints (look for inflection points)
            elif i < len(vbd_values) - 1:
                next_vbd = vbd_values[i+1]
                next_drop = (current_vbd - next_vbd) / max(current_vbd, 0.1) if current_vbd > 0 else 0
                
                # If current drop is much larger than next drop, create boundary
                if pct_drop > 0.1 and next_drop < pct_drop * 0.5:
                    should_create_boundary = True
            
            if should_create_boundary:
                boundaries.append(i)
                current_tier_size = 0
                logger.debug(f"{position.value} tier boundary at index {i}: {pct_drop:.1%} drop, {abs_gap:.1f} VBD gap")
        
        return boundaries
    
    def _calculate_draft_flow_multiplier(self, picks_until_next_turn: int, 
                                       current_round: int, 
                                       position: Position) -> float:
        """Calculate how draft flow affects tier urgency"""
        
        # Base multiplier
        multiplier = 1.0
        
        # Early rounds are more sensitive to tier drops
        if current_round <= 6:
            multiplier *= 0.8  # Lower threshold = more sensitive
        elif current_round >= 10:
            multiplier *= 1.3  # Higher threshold = less sensitive in late rounds
        
        # Urgency based on picks until our turn
        if picks_until_next_turn <= 3:
            multiplier *= 0.7  # Much more sensitive when our pick is soon
        elif picks_until_next_turn <= 8:
            multiplier *= 0.9  # Moderately more sensitive
        elif picks_until_next_turn >= 15:
            multiplier *= 1.2  # Less sensitive when we have time
        
        # Position-specific urgency
        if position == Position.RB and current_round <= 2:
            multiplier *= 0.6  # Very sensitive to RB tiers early (Hero-RB)
        elif position in [Position.K, Position.DEF]:
            multiplier *= 2.0  # Much less sensitive for K/DEF
        
        return max(0.3, min(2.0, multiplier))  # Clamp between 0.3x and 2.0x
    
    def _apply_tier_assignments(self, df: pd.DataFrame, pos_players: pd.DataFrame,
                               tier_boundaries: List[int], position: Position):
        """Apply tier assignments and calculate urgency metrics"""
        
        current_tier = 1
        tier_start_idx = 0
        
        # Handle tier 1 (before first boundary)
        if tier_boundaries:
            first_boundary = tier_boundaries[0]
            tier_1_players = pos_players.iloc[tier_start_idx:first_boundary]
            self._assign_tier_to_players(df, tier_1_players, current_tier, position, 
                                       pos_players, tier_start_idx, first_boundary)
            tier_start_idx = first_boundary
            current_tier += 1
        
        # Handle middle tiers
        for i, boundary in enumerate(tier_boundaries[:-1] if len(tier_boundaries) > 1 else []):
            next_boundary = tier_boundaries[i + 1]
            tier_players = pos_players.iloc[boundary:next_boundary]
            self._assign_tier_to_players(df, tier_players, current_tier, position,
                                       pos_players, boundary, next_boundary)
            tier_start_idx = next_boundary
            current_tier += 1
        
        # Handle final tier (after last boundary)
        if tier_boundaries:
            final_tier_players = pos_players.iloc[tier_boundaries[-1]:]
            self._assign_tier_to_players(df, final_tier_players, current_tier, position,
                                       pos_players, tier_boundaries[-1], len(pos_players))
        else:
            # No boundaries - all players in tier 1
            self._assign_tier_to_players(df, pos_players, 1, position, 
                                       pos_players, 0, len(pos_players))
    
    def _assign_tier_to_players(self, df: pd.DataFrame, tier_players: pd.DataFrame,
                               tier_num: int, position: Position, all_pos_players: pd.DataFrame,
                               tier_start: int, tier_end: int):
        """Assign tier number and calculate urgency for a group of players"""
        
        if len(tier_players) == 0:
            return
        
        # Assign tier number
        df.loc[tier_players.index, 'tier'] = tier_num
        
        # Calculate tier urgency
        tier_size = len(tier_players)
        if tier_size <= 2:
            urgency = TierUrgency.CRITICAL
        elif tier_size <= 4:
            urgency = TierUrgency.HIGH
        elif tier_size <= 7:
            urgency = TierUrgency.MODERATE
        else:
            urgency = TierUrgency.LOW
        
        df.loc[tier_players.index, 'tier_urgency'] = urgency.value
        
        # Calculate dropoff magnitude for tier boundary evaluation
        if tier_end < len(all_pos_players):
            tier_floor_vbd = tier_players['vbd'].min()
            next_tier_ceiling_vbd = all_pos_players.iloc[tier_end]['vbd']
            
            if tier_floor_vbd > 0:
                dropoff_magnitude = (tier_floor_vbd - next_tier_ceiling_vbd) / tier_floor_vbd
            else:
                dropoff_magnitude = 0.0
            
            df.loc[tier_players.index, 'tier_dropoff_magnitude'] = dropoff_magnitude
        
        logger.debug(f"{position.value} Tier {tier_num}: {tier_size} players, urgency: {urgency.value}")
    
    def get_position_tier_states(self, available_players: pd.DataFrame) -> Dict[Position, PositionTierState]:
        """Get current tier state for all positions"""
        
        tier_states = {}
        
        for position in Position:
            if position in [Position.DB, Position.DT, Position.OT, Position.UNKNOWN]:
                continue
                
            pos_players = available_players[available_players['position'] == position.value]
            
            if len(pos_players) == 0:
                continue
            
            # Find current best available tier
            current_tier = pos_players['tier'].min()
            
            # Build tier info dictionary
            tiers = {}
            for tier_num in sorted(pos_players['tier'].unique()):
                tier_players = pos_players[pos_players['tier'] == tier_num]
                
                if len(tier_players) == 0:
                    continue
                
                # Calculate tier urgency
                tier_size = len(tier_players)
                if tier_size <= 2:
                    urgency = TierUrgency.CRITICAL
                elif tier_size <= 4:
                    urgency = TierUrgency.HIGH
                elif tier_size <= 7:
                    urgency = TierUrgency.MODERATE
                else:
                    urgency = TierUrgency.LOW
                
                # Get dropoff info
                dropoff_magnitude = tier_players['tier_dropoff_magnitude'].iloc[0] if len(tier_players) > 0 else 0.0
                
                tiers[tier_num] = TierInfo(
                    tier_number=tier_num,
                    players_remaining=tier_size,
                    vbd_floor=tier_players['vbd'].min(),
                    vbd_ceiling=tier_players['vbd'].max(),
                    dropoff_magnitude=dropoff_magnitude,
                    urgency=urgency,
                    next_tier_gap=dropoff_magnitude * tier_players['vbd'].max()
                )
            
            # Calculate quality players remaining and scarcity
            replacement_level = self.config.replacement_levels[position]
            quality_remaining = min(len(pos_players), replacement_level)
            
            scarcity_multiplier = replacement_level / max(quality_remaining, 1)
            
            tier_states[position] = PositionTierState(
                position=position,
                current_tier=current_tier,
                tiers=tiers,
                total_quality_remaining=quality_remaining,
                scarcity_multiplier=scarcity_multiplier
            )
        
        return tier_states
    
    def calculate_tier_urgency_boost(self, player_row: pd.Series, 
                                   tier_states: Dict[Position, PositionTierState],
                                   picks_until_next_turn: int) -> float:
        """
        Calculate tier-based urgency boost for player valuation
        Research: Draft the last high-tier player rather than first low-tier player
        """
        
        position = Position(player_row['position'])
        player_tier = player_row.get('tier', 1)
        tier_urgency = player_row.get('tier_urgency', TierUrgency.LOW.value)
        
        if position not in tier_states:
            return 1.0
        
        tier_state = tier_states[position]
        
        # Base urgency multiplier
        urgency_multipliers = {
            TierUrgency.CRITICAL.value: 1.8,  # 80% boost for last players in tier
            TierUrgency.HIGH.value: 1.4,     # 40% boost 
            TierUrgency.MODERATE.value: 1.2, # 20% boost
            TierUrgency.LOW.value: 1.0       # No boost
        }
        
        base_multiplier = urgency_multipliers.get(tier_urgency, 1.0)
        
        # Additional boost if we're in the current best tier
        if player_tier == tier_state.current_tier:
            base_multiplier *= 1.2
        
        # Reduce multiplier if we have many picks before our turn
        if picks_until_next_turn > 10:
            base_multiplier = 1.0 + (base_multiplier - 1.0) * 0.7
        elif picks_until_next_turn <= 3:
            base_multiplier = 1.0 + (base_multiplier - 1.0) * 1.3
        
        # Cap the maximum boost
        return min(2.5, base_multiplier)
    
    def get_tier_recommendations(self, tier_states: Dict[Position, PositionTierState],
                               picks_until_next_turn: int) -> List[Tuple[Position, str, float]]:
        """
        Get tier-based position recommendations
        Returns list of (position, reason, urgency_score) tuples
        """
        
        recommendations = []
        
        for position, state in tier_states.items():
            if state.current_tier not in state.tiers:
                continue
            
            current_tier_info = state.tiers[state.current_tier]
            urgency_score = 0.0
            reason = ""
            
            # Critical tier situations
            if current_tier_info.urgency == TierUrgency.CRITICAL:
                urgency_score = 10.0
                reason = f"CRITICAL: Only {current_tier_info.players_remaining} tier {state.current_tier} {position.value}s left"
            
            # High urgency with significant dropoff
            elif (current_tier_info.urgency == TierUrgency.HIGH and 
                  current_tier_info.dropoff_magnitude > 0.3):
                urgency_score = 8.0
                reason = f"HIGH: {current_tier_info.players_remaining} tier {state.current_tier} {position.value}s, {current_tier_info.dropoff_magnitude:.1%} dropoff"
            
            # Moderate urgency but with upcoming picks
            elif (current_tier_info.urgency == TierUrgency.MODERATE and 
                  picks_until_next_turn <= 6):
                urgency_score = 6.0
                reason = f"MODERATE: {current_tier_info.players_remaining} tier {state.current_tier} {position.value}s, {picks_until_next_turn} picks until our turn"
            
            # Scarcity-based urgency
            elif state.scarcity_multiplier > 1.5:
                urgency_score = 5.0
                reason = f"SCARCITY: {state.total_quality_remaining} quality {position.value}s remaining"
            
            if urgency_score > 0:
                recommendations.append((position, reason, urgency_score))
        
        # Sort by urgency score descending
        recommendations.sort(key=lambda x: x[2], reverse=True)
        
        return recommendations