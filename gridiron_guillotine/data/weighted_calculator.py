"""
Multi-Year Weighted Fantasy Score Calculator
Based on expert methodologies and statistical research
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import glob

from ..core.config import Config, get_config
from ..core.models import Position
from .processors import ScoreCalculator

logger = logging.getLogger(__name__)


class WeightedMultiYearCalculator:
    """Calculate weighted fantasy scores using multiple seasons of data"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.base_calculator = ScoreCalculator(config)
        
        # Expert-validated season weights
        self.season_weights = {
            2025: 0.65,  # Most recent season - highest predictive value
            2024: 0.25,  # Previous season - moderate weight
            2023: 0.10   # Two years ago - context only
        }
        
        # Position volatility adjustments (based on year-to-year consistency)
        self.position_adjustments = {
            Position.QB: 1.10,   # Most consistent position
            Position.WR: 1.00,   # Baseline consistency 
            Position.TE: 0.95,   # Slightly less predictable
            Position.RB: 0.90    # Most volatile due to usage/injury
        }
        
        logger.info(f"Initialized weighted calculator with season weights: {self.season_weights}")
    
    def load_historical_data(self, seasons: List[int] = None) -> Dict[int, pd.DataFrame]:
        """Load historical offense data for specified seasons"""
        if seasons is None:
            seasons = [2023, 2024, 2025]
        
        historical_data = {}
        
        for season in seasons:
            logger.info(f"Loading {season} season data...")
            season_data = self._load_season_data(season)
            
            if not season_data.empty:
                historical_data[season] = season_data
                logger.info(f"Loaded {len(season_data)} player records for {season}")
            else:
                logger.warning(f"No data found for {season} season")
        
        return historical_data
    
    def _load_season_data(self, season: int) -> pd.DataFrame:
        """Load all weeks of data for a specific season"""
        data_path = self.config.data_dir
        pattern = str(data_path / f"offense_{season}_*.csv")
        
        season_files = glob.glob(pattern)
        if not season_files:
            logger.warning(f"No offense files found for {season} season")
            return pd.DataFrame()
        
        all_weeks = []
        
        for file_path in season_files:
            try:
                week_data = pd.read_csv(file_path)
                
                # Extract week number from filename
                week = int(file_path.split('_')[-1].replace('.csv', ''))
                week_data['Week'] = week
                week_data['Season'] = season
                
                all_weeks.append(week_data)
                
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                continue
        
        if all_weeks:
            season_df = pd.concat(all_weeks, ignore_index=True)
            logger.debug(f"Combined {len(all_weeks)} weeks for {season} season")
            return season_df
        
        return pd.DataFrame()
    
    def calculate_weighted_projections(self, historical_data: Dict[int, pd.DataFrame]) -> pd.DataFrame:
        """Calculate weighted projections using multi-year data"""
        logger.info("Calculating weighted multi-year projections...")
        
        # Aggregate season totals for each player
        season_totals = {}
        
        for season, data in historical_data.items():
            logger.info(f"Processing {season} season data...")
            totals = self._aggregate_season_totals(data, season)
            season_totals[season] = totals
        
        # Calculate weighted averages
        weighted_projections = self._calculate_weighted_averages(season_totals)
        
        logger.info(f"Generated weighted projections for {len(weighted_projections)} players")
        return weighted_projections
    
    def _aggregate_season_totals(self, season_data: pd.DataFrame, season: int) -> pd.DataFrame:
        """Aggregate individual games into season totals per player"""
        if season_data.empty:
            return pd.DataFrame()
        
        # Clean player names (remove position abbreviations)
        season_data['CleanPlayer'] = season_data['Player'].str.replace(r'[A-Z]\. [A-Z][a-z]+$', '', regex=True)
        
        # Group by player and sum statistics
        agg_columns = {
            'Pts*': 'sum',
            'Passing_Att': 'sum',
            'Passing_Cmp': 'sum', 
            'Passing_Yds': 'sum',
            'Passing_TD': 'sum',
            'Passing_Int': 'sum',
            'Rushing_Att': 'sum',
            'Rushing_Yds': 'sum',
            'Rushing_TD': 'sum',
            'Receiving_Rec': 'sum',
            'Receiving_Yds': 'sum',
            'Receiving_TD': 'sum',
            'Fumble_FL': 'sum',
            'Game': 'count'  # Games played
        }
        
        player_totals = season_data.groupby('CleanPlayer').agg(agg_columns).reset_index()
        player_totals['Season'] = season
        player_totals.rename(columns={'Game': 'GamesPlayed'}, inplace=True)
        
        # Calculate per-game averages for ALL relevant stats
        per_game_columns = [
            'Pts*', 'Passing_Yds', 'Passing_TD', 'Passing_Int',
            'Rushing_Yds', 'Rushing_TD', 'Receiving_Yds', 'Receiving_TD', 'Receiving_Rec'
        ]
        
        for col in per_game_columns:
            if col in player_totals.columns:
                # Avoid division by zero
                games_played = player_totals['GamesPlayed'].replace(0, 1)
                player_totals[f'{col}_PerGame'] = player_totals[col] / games_played
        
        logger.debug(f"Aggregated {len(player_totals)} players for {season}")
        return player_totals
    
    def _calculate_weighted_averages(self, season_totals: Dict[int, pd.DataFrame]) -> pd.DataFrame:
        """Calculate weighted averages across seasons for each player"""
        if not season_totals:
            return pd.DataFrame()
        
        # Get all unique players across all seasons
        all_players = set()
        for totals in season_totals.values():
            all_players.update(totals['CleanPlayer'].unique())
        
        weighted_projections = []
        
        for player in all_players:
            player_seasons = {}
            
            # Collect data for this player across seasons
            for season, totals in season_totals.items():
                player_data = totals[totals['CleanPlayer'] == player]
                if not player_data.empty:
                    player_seasons[season] = player_data.iloc[0]
            
            if len(player_seasons) >= 1:  # At least one season of data
                weighted_stats = self._compute_weighted_stats(player, player_seasons)
                if weighted_stats:
                    weighted_projections.append(weighted_stats)
        
        if weighted_projections:
            result_df = pd.DataFrame(weighted_projections)
            logger.info(f"Calculated weighted averages for {len(result_df)} players")
            return result_df
        
        return pd.DataFrame()
    
    def _compute_weighted_stats(self, player_name: str, player_seasons: Dict[int, pd.Series]) -> Optional[Dict]:
        """Compute weighted statistics for a single player using per-game averages"""
        try:
            # Determine primary position (for volatility adjustment)
            position = self._infer_position(player_seasons)
            position_adj = self.position_adjustments.get(position, 1.0)
            
            # Calculate weighted averages for key stats
            weighted_stats = {
                'Player': player_name,
                'Position': position.value if position else 'UNKNOWN',
                'SeasonsPlayed': len(player_seasons)
            }
            
            # Use PER-GAME stats for weighting (this is the key fix!)
            per_game_stat_columns = [
                'Pts*_PerGame', 'Passing_Yds_PerGame', 'Passing_TD_PerGame', 'Passing_Int_PerGame',
                'Rushing_Yds_PerGame', 'Rushing_TD_PerGame', 'Receiving_Rec_PerGame', 
                'Receiving_Yds_PerGame', 'Receiving_TD_PerGame'
            ]
            
            # Also track season totals for context
            season_stat_columns = [
                'Pts*', 'Passing_Yds', 'Passing_TD', 'Passing_Int',
                'Rushing_Yds', 'Rushing_TD', 'Receiving_Rec', 'Receiving_Yds', 
                'Receiving_TD', 'GamesPlayed'
            ]
            
            total_weight = 0
            
            # Calculate per-game weighted averages (primary projections)
            for stat in per_game_stat_columns:
                weighted_value = 0
                stat_weight = 0
                
                for season, data in player_seasons.items():
                    if stat in data and pd.notna(data[stat]):
                        # Only weight non-zero values, but include zeros in the calculation
                        season_weight = self.season_weights.get(season, 0)
                        weighted_value += data[stat] * season_weight
                        stat_weight += season_weight
                
                if stat_weight > 0:
                    # Apply position volatility adjustment to per-game stats
                    final_value = (weighted_value / stat_weight) * position_adj
                    weighted_stats[f'Weighted_{stat}'] = final_value
                    total_weight = max(total_weight, stat_weight)
            
            # Also calculate season totals for context (but don't use for projections)
            for stat in season_stat_columns:
                weighted_value = 0
                stat_weight = 0
                
                for season, data in player_seasons.items():
                    if stat in data and pd.notna(data[stat]):
                        season_weight = self.season_weights.get(season, 0)
                        weighted_value += data[stat] * season_weight
                        stat_weight += season_weight
                
                if stat_weight > 0:
                    final_value = (weighted_value / stat_weight) * position_adj
                    weighted_stats[f'Weighted_{stat}'] = final_value
            
            weighted_stats['TotalWeight'] = total_weight
            
            # Use the actual weighted per-game points instead of recalculating from components
            # This preserves the true weighted average of actual fantasy points
            if 'Weighted_Pts*_PerGame' in weighted_stats:
                projected_points_per_game = weighted_stats['Weighted_Pts*_PerGame']
            else:
                # Fallback to component calculation if direct points not available
                projected_points_per_game = self._calculate_projected_points_per_game(weighted_stats)
            
            # Project to full season (16 games standard)  
            projected_season_points = projected_points_per_game * 16
            
            weighted_stats['ProjectedPointsPerGame'] = projected_points_per_game
            weighted_stats['ProjectedPoints'] = projected_season_points
            
            return weighted_stats
            
        except Exception as e:
            logger.error(f"Error computing weighted stats for {player_name}: {e}")
            return None
    
    def _infer_position(self, player_seasons: Dict[int, pd.Series]) -> Position:
        """Infer player position from statistics"""
        # Get most recent season data
        latest_season = max(player_seasons.keys())
        latest_data = player_seasons[latest_season]
        
        # Simple position inference based on stats
        passing_att = latest_data.get('Passing_Att', 0) or 0
        rushing_att = latest_data.get('Rushing_Att', 0) or 0  
        receiving_rec = latest_data.get('Receiving_Rec', 0) or 0
        
        if passing_att > 50:  # Significant passing attempts
            return Position.QB
        elif rushing_att > receiving_rec and rushing_att > 20:  # More rushing than receiving
            return Position.RB
        elif receiving_rec > 0:  # Any receptions
            # Could be WR or TE - use simple heuristic
            rec_yds = latest_data.get('Receiving_Yds', 0) or 0
            if receiving_rec > 0:
                yds_per_rec = rec_yds / receiving_rec
                return Position.TE if yds_per_rec < 12 else Position.WR
        
        return Position.RB  # Default fallback
    
    def _calculate_projected_points_per_game(self, weighted_stats: Dict) -> float:
        """Calculate projected fantasy points PER GAME from weighted per-game statistics"""
        try:
            stats_for_scoring = {}
            
            # Map weighted PER-GAME stats to scoring categories
            per_game_stat_mapping = {
                'Weighted_Passing_Yds_PerGame': 'passing_yards',
                'Weighted_Passing_TD_PerGame': 'passing_tds',
                'Weighted_Passing_Int_PerGame': 'interceptions',
                'Weighted_Rushing_Yds_PerGame': 'rushing_yards',
                'Weighted_Rushing_TD_PerGame': 'rushing_tds',
                'Weighted_Receiving_Yds_PerGame': 'receiving_yards',
                'Weighted_Receiving_TD_PerGame': 'receiving_tds',
                'Weighted_Receiving_Rec_PerGame': 'receptions'
            }
            
            for weighted_stat, scoring_category in per_game_stat_mapping.items():
                if weighted_stat in weighted_stats and pd.notna(weighted_stats[weighted_stat]):
                    stats_for_scoring[scoring_category] = weighted_stats[weighted_stat]
            
            # Calculate points per game using base calculator
            return self.base_calculator.calculate_fantasy_points(stats_for_scoring)
            
        except Exception as e:
            logger.error(f"Error calculating projected points per game: {e}")
            return 0.0
    
    def _calculate_projected_points(self, weighted_stats: Dict) -> float:
        """Calculate projected fantasy points from weighted statistics (legacy method)"""
        try:
            stats_for_scoring = {}
            
            # Map weighted stats to scoring categories
            stat_mapping = {
                'Weighted_Passing_Yds': 'passing_yards',
                'Weighted_Passing_TD': 'passing_tds',
                'Weighted_Passing_Int': 'interceptions',
                'Weighted_Rushing_Yds': 'rushing_yards',
                'Weighted_Rushing_TD': 'rushing_tds',
                'Weighted_Receiving_Yds': 'receiving_yards',
                'Weighted_Receiving_TD': 'receiving_tds',
                'Weighted_Receiving_Rec': 'receptions',
                'Weighted_Fumble_FL': 'fumbles_lost'
            }
            
            for weighted_stat, scoring_category in stat_mapping.items():
                if weighted_stat in weighted_stats:
                    stats_for_scoring[scoring_category] = weighted_stats[weighted_stat]
            
            # Calculate points using base calculator
            return self.base_calculator.calculate_fantasy_points(stats_for_scoring)
            
        except Exception as e:
            logger.error(f"Error calculating projected points: {e}")
            return 0.0
    
    def save_weighted_projections(self, projections: pd.DataFrame, filename: str = "weighted_projections_2026.csv") -> bool:
        """Save weighted projections to CSV file"""
        try:
            output_path = self.config.data_dir / filename
            projections.to_csv(output_path, index=False)
            logger.info(f"Saved weighted projections to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving projections: {e}")
            return False


def run_weighted_calculation():
    """Main function to run weighted multi-year calculation"""
    logger.info("Starting weighted multi-year fantasy calculation...")
    
    calculator = WeightedMultiYearCalculator()
    
    # Load 3 years of historical data
    historical_data = calculator.load_historical_data([2023, 2024, 2025])
    
    if not historical_data:
        logger.error("No historical data loaded")
        return False
    
    # Calculate weighted projections
    projections = calculator.calculate_weighted_projections(historical_data)
    
    if projections.empty:
        logger.error("No projections calculated")
        return False
    
    # Save results
    success = calculator.save_weighted_projections(projections)
    
    if success:
        logger.info(f"Weighted calculation complete! Generated projections for {len(projections)} players")
        return True
    
    return False


if __name__ == "__main__":
    run_weighted_calculation()