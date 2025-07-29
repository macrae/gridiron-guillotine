"""
Advanced metrics calculations for fantasy football analysis
Research-based WOPR, Expected Fantasy Points, and context analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

from .models import Player, Position
from .config import Config, get_config

logger = logging.getLogger(__name__)


class WOPRCalculator:
    """
    Weighted Opportunity Rating Calculator
    Research: 0.746 R² correlation with WR performance
    Formula: WOPR = 1.5 × (Target Share) + 0.7 × (Air Yards Share)
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.weights = self.config.wopr_weights
    
    def calculate(self, player: Player) -> float:
        """Calculate WOPR for a player"""
        if player.position != Position.WR:
            return 0.0
        
        target_share = player.target_share / 100  # Convert percentage
        air_yards_share = player.air_yards_share / 100
        
        wopr = (self.weights['target_share'] * target_share + 
                self.weights['air_yards_share'] * air_yards_share)
        
        return wopr
    
    def calculate_for_dataframe(self, df: pd.DataFrame) -> pd.Series:
        """Calculate WOPR for a DataFrame of players"""
        wopr_scores = []
        
        for _, row in df.iterrows():
            if row.get('position') == 'WR':
                target_share = row.get('target_share', 0) / 100
                air_yards_share = row.get('air_yards_share', 0) / 100
                
                wopr = (self.weights['target_share'] * target_share + 
                       self.weights['air_yards_share'] * air_yards_share)
                wopr_scores.append(wopr)
            else:
                wopr_scores.append(0.0)
        
        return pd.Series(wopr_scores, index=df.index)


class ExpectedPointsCalculator:
    """
    Expected Fantasy Points Calculator
    Research: "Most predictive stat I've ever seen" - Scott Barrett (PFF)
    Uses opportunity metrics for projections
    """
    
    def calculate(self, player: Player) -> float:
        """Calculate expected fantasy points for a player"""
        base_projection = player.projected_points
        adjustments = 0.0
        
        # Red zone opportunity boost
        adjustments += (player.red_zone_targets * 0.8) + (player.red_zone_carries * 1.2)
        
        # Air yards adjustment (deep target value)
        if player.position == Position.WR and player.air_yards_per_target > 12:
            adjustments += player.air_yards_per_target * 0.1
        
        # Goal line carries (RB specific)
        if player.position == Position.RB:
            adjustments += player.goal_line_carries * 2.5
        
        return base_projection + adjustments
    
    def calculate_for_dataframe(self, df: pd.DataFrame) -> pd.Series:
        """Calculate expected points for a DataFrame"""
        expected_points = []
        
        for _, row in df.iterrows():
            position = row.get('position')
            base_projection = row.get('projected_points', 0)
            
            adjustments = 0.0
            
            # Red zone opportunities
            red_zone_targets = row.get('red_zone_targets', 0)
            red_zone_carries = row.get('red_zone_carries', 0)
            adjustments += (red_zone_targets * 0.8) + (red_zone_carries * 1.2)
            
            # Air yards adjustment
            air_yards = row.get('air_yards_per_target', 0)
            if position == 'WR' and air_yards > 12:
                adjustments += air_yards * 0.1
            
            # Goal line carries
            if position == 'RB':
                goal_line_carries = row.get('goal_line_carries', 0)
                adjustments += goal_line_carries * 2.5
            
            expected_points.append(base_projection + adjustments)
        
        return pd.Series(expected_points, index=df.index)


class OffensiveContextCalculator:
    """
    Offensive Context Multiplier Calculator
    Research: Target players in top-14 NFL offenses regardless of talent
    Only 2 of 9 top-36 WRs in bottom-10 offenses met expectations
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.elite_offenses = set(self.config.elite_offenses)
        self.bottom_offenses = set(self.config.bottom_offenses)
    
    def calculate(self, player: Player) -> float:
        """Calculate offensive context multiplier for a player"""
        if player.team in self.elite_offenses:
            return 1.15  # 15% boost for elite offense
        elif player.team in self.bottom_offenses:
            return 0.85  # 15% penalty for bottom offenses
        else:
            return 1.0   # Neutral for middle-tier offenses
    
    def calculate_for_dataframe(self, df: pd.DataFrame) -> pd.Series:
        """Calculate context multipliers for a DataFrame"""
        multipliers = []
        
        for _, row in df.iterrows():
            team = row.get('team', '')
            
            if team in self.elite_offenses:
                multipliers.append(1.15)
            elif team in self.bottom_offenses:
                multipliers.append(0.85)
            else:
                multipliers.append(1.0)
        
        return pd.Series(multipliers, index=df.index)


class AdvancedMetrics:
    """
    Comprehensive advanced metrics calculator
    Combines WOPR, Expected Points, and Offensive Context
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.wopr_calc = WOPRCalculator(config)
        self.expected_calc = ExpectedPointsCalculator()
        self.context_calc = OffensiveContextCalculator(config)
    
    def calculate_for_player(self, player: Player) -> Player:
        """Calculate all advanced metrics for a player"""
        player.wopr = self.wopr_calc.calculate(player)
        player.expected_points = self.expected_calc.calculate(player)
        player.context_multiplier = self.context_calc.calculate(player)
        
        # Create composite advanced score
        player.advanced_score = (
            player.expected_points * 
            player.context_multiplier * 
            (1 + player.wopr * 0.1)  # WOPR as 10% modifier
        )
        
        return player
    
    def calculate_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all advanced metrics to a DataFrame"""
        data = df.copy()
        
        # Calculate individual metrics
        data['wopr'] = self.wopr_calc.calculate_for_dataframe(data)
        data['expected_points'] = self.expected_calc.calculate_for_dataframe(data)
        data['context_multiplier'] = self.context_calc.calculate_for_dataframe(data)
        
        # Create composite advanced score
        data['advanced_score'] = (
            data['expected_points'] * 
            data['context_multiplier'] * 
            (1 + data['wopr'] * 0.1)
        )
        
        logger.debug(f"Applied advanced metrics to {len(data)} players")
        return data


class DraftPositionAnalyzer:
    """
    Draft position-specific strategy analysis
    Research: Different approaches for early/middle/late positions
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.position_strategies = {
            'early': [1, 2, 3],         # Positions 1-3
            'middle': [4, 5, 6, 7, 8],  # Positions 4-8
            'late': [9, 10, 11, 12]     # Positions 9-12
        }
    
    def get_position_category(self, draft_position: int) -> str:
        """Determine draft position category"""
        if draft_position in self.position_strategies['early']:
            return 'early'
        elif draft_position in self.position_strategies['middle']:
            return 'middle'
        else:
            return 'late'
    
    def get_position_targets(self, draft_position: int, round_num: int) -> List[str]:
        """Get research-validated targets for position and round"""
        category = self.get_position_category(draft_position)
        
        if category == 'early' and round_num == 1:
            return self.config.position_targets['early_rd1']
        elif category == 'middle' and round_num == 1:
            return self.config.position_targets['middle_rd1']
        elif category == 'late':
            target_key = f'late_rd{round_num}'
            return self.config.position_targets.get(target_key, [])
        
        return []
    
    def calculate_position_adjustment(self, player: Player, draft_position: int, 
                                   current_round: int) -> float:
        """Calculate draft position-specific value adjustment"""
        category = self.get_position_category(draft_position)
        adjustment = 0.0
        
        # Early positions (1-3): Elite WR focus
        if category == 'early' and current_round <= 2:
            targets = self.get_position_targets(draft_position, current_round)
            if any(target in player.name for target in targets):
                adjustment += 2.0  # Major boost for elite targets
            elif player.position in [Position.QB, Position.TE] and current_round == 1:
                adjustment -= 1.0  # Penalty for reaches
        
        # Middle positions (4-8): BPA flexibility
        elif category == 'middle' and current_round <= 2:
            targets = self.get_position_targets(draft_position, current_round)
            if any(target in player.name for target in targets):
                adjustment += 1.5  # Moderate boost for value targets
        
        # Late positions (9-12): PPR pairs and back-to-back advantage
        elif category == 'late' and current_round <= 3:
            targets = self.get_position_targets(draft_position, current_round)
            if any(target in player.name for target in targets):
                adjustment += 2.5  # Largest boost for strategic pairs
            
            # PPR-specific boost for high-target players
            if player.position == Position.WR and current_round <= 2:
                adjustment += 1.0
        
        return adjustment