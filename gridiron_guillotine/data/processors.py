"""
Data processing and calculation functionality
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, List

from ..core.config import Config, get_config
from ..core.models import Position

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """Calculate fantasy scores from NFL statistics"""
    
    def __init__(self, config: Optional[Config] = None, scoring_system: Optional[Dict[str, float]] = None):
        self.config = config or get_config()
        self.scoring = scoring_system or self._get_default_scoring()
    
    def _get_default_scoring(self) -> Dict[str, float]:
        """Get default PPR scoring system"""
        return {
            'passing_yards': 0.04,
            'passing_tds': 4.0,
            'interceptions': -2.0,
            'rushing_yards': 0.1,
            'rushing_tds': 6.0,
            'receiving_yards': 0.1,
            'receiving_tds': 6.0,
            'receptions': 1.0,  # PPR
            'fumbles_lost': -2.0,
            # Kicking
            'field_goals': 3.0,
            'extra_points': 1.0,
            # Defense
            'defensive_tds': 6.0,
            'interception_returns': 2.0,
            'fumble_recoveries': 2.0,
            'sacks': 1.0,
            'safeties': 2.0,
        }
    
    def calculate_fantasy_points(self, stats: Dict[str, float]) -> float:
        """Calculate fantasy points from statistics"""
        total_points = 0.0
        
        for stat, value in stats.items():
            if stat in self.scoring and value is not None:
                total_points += self.scoring[stat] * value
        
        return total_points
    
    def calculate_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate fantasy points for entire dataframe"""
        result_df = df.copy()
        
        if 'fantasy_points' not in result_df.columns:
            result_df['fantasy_points'] = 0.0
        
        for idx, row in result_df.iterrows():
            stats = row.to_dict()
            points = self.calculate_fantasy_points(stats)
            result_df.at[idx, 'fantasy_points'] = points
        
        return result_df


class VBDCalculator:
    """Calculate Value-Based Drafting scores"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.replacement_levels = self.config.replacement_levels
    
    def calculate_vbd(self, players_df: pd.DataFrame, points_column: str = 'projected_points') -> pd.DataFrame:
        """
        Calculate VBD scores for all players
        
        Args:
            players_df: DataFrame with player data
            points_column: Column name containing fantasy points
            
        Returns:
            DataFrame with VBD scores added
        """
        df = players_df.copy()
        df['vbd'] = 0.0
        
        for position in Position:
            pos_players = df[df['position'] == position.value]
            
            if len(pos_players) == 0:
                continue
            
            # Sort by points to find replacement level
            pos_players_sorted = pos_players.sort_values(points_column, ascending=False)
            replacement_level = self.replacement_levels[position]
            
            if len(pos_players_sorted) >= replacement_level:
                # Get the replacement player's points
                replacement_points = pos_players_sorted.iloc[replacement_level - 1][points_column]
            else:
                # If fewer players than replacement level, use minimum
                replacement_points = pos_players_sorted[points_column].min()
            
            # Calculate VBD for this position
            mask = df['position'] == position.value
            df.loc[mask, 'vbd'] = df.loc[mask, points_column] - replacement_points
        
        logger.info(f"Calculated VBD for {len(df)} players")
        return df
    
    def get_replacement_level_player(self, position: Position, players_df: pd.DataFrame, 
                                   points_column: str = 'projected_points') -> Optional[pd.Series]:
        """Get the replacement level player for a position"""
        pos_players = players_df[players_df['position'] == position.value]
        
        if len(pos_players) == 0:
            return None
        
        pos_players_sorted = pos_players.sort_values(points_column, ascending=False)
        replacement_level = self.replacement_levels[position]
        
        if len(pos_players_sorted) >= replacement_level:
            return pos_players_sorted.iloc[replacement_level - 1]
        else:
            return pos_players_sorted.iloc[-1]  # Last player available


class SeasonAggregator:
    """Aggregate weekly data into season projections"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
    
    def aggregate_weekly_data(self, weekly_data: List[pd.DataFrame], 
                            weights: Optional[List[float]] = None) -> pd.DataFrame:
        """
        Aggregate weekly data with optional weighting
        
        Args:
            weekly_data: List of weekly DataFrames
            weights: Optional weights for each week (must sum to 1.0)
            
        Returns:
            Aggregated DataFrame with season projections
        """
        if not weekly_data:
            raise ValueError("No weekly data provided")
        
        if weights and len(weights) != len(weekly_data):
            raise ValueError("Weights length must match weekly data length")
        
        # If no weights provided, use equal weighting
        if not weights:
            weights = [1.0 / len(weekly_data)] * len(weekly_data)
        
        # Combine all weekly data
        combined_df = pd.concat(weekly_data, ignore_index=True)
        
        # Group by player and aggregate
        numeric_columns = combined_df.select_dtypes(include=[np.number]).columns
        
        # Calculate weighted averages
        aggregated = combined_df.groupby(['name', 'position']).agg({
            col: 'mean' if col in numeric_columns else 'first' 
            for col in combined_df.columns if col not in ['name', 'position']
        }).reset_index()
        
        # Apply confidence intervals based on sample size
        aggregated = self._add_confidence_intervals(aggregated, combined_df)
        
        return aggregated
    
    def _add_confidence_intervals(self, aggregated_df: pd.DataFrame, 
                                combined_df: pd.DataFrame) -> pd.DataFrame:
        """Add confidence intervals based on data variability"""
        df = aggregated_df.copy()
        
        # Calculate standard deviation for each player
        points_col = 'fantasy_points' if 'fantasy_points' in combined_df.columns else combined_df.select_dtypes(include=[np.number]).columns[0]
        
        std_data = combined_df.groupby(['name', 'position']).agg({
            points_col: ['std', 'count']
        }).reset_index()
        
        # Flatten column names
        std_data.columns = ['name', 'position', 'std_points', 'sample_count']
        
        # Merge with aggregated data
        df = df.merge(std_data, on=['name', 'position'], how='left')
        
        # Calculate confidence intervals (assuming normal distribution)
        # Use larger intervals for smaller sample sizes
        points_col = 'fantasy_points' if 'fantasy_points' in df.columns else 'projected_points'
        
        if points_col in df.columns:
            df['floor'] = df[points_col] - (df['std_points'].fillna(df[points_col] * 0.2) * 1.5)
            df['ceiling'] = df[points_col] + (df['std_points'].fillna(df[points_col] * 0.2) * 1.5)
            
            # Ensure floor is not negative
            df['floor'] = df['floor'].clip(lower=0)
        
        return df