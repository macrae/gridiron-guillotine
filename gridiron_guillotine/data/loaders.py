"""
Data loading and caching functionality
"""

import pandas as pd
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

from ..core.config import Config, get_config
from ..core.models import Position

logger = logging.getLogger(__name__)


class DataLoader:
    """Base data loader with caching capabilities"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
    
    @lru_cache(maxsize=32)
    def load_csv(self, file_path: str, **kwargs) -> pd.DataFrame:
        """Load CSV with caching"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.config.data_dir / path
            
            df = pd.read_csv(path, **kwargs)
            logger.debug(f"Loaded {len(df)} rows from {path}")
            return df
        except Exception as e:
            logger.error(f"Error loading CSV {file_path}: {e}")
            raise
    
    @lru_cache(maxsize=16)
    def load_json(self, file_path: str) -> Dict[str, Any]:
        """Load JSON with caching"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.config.data_dir / path
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            logger.debug(f"Loaded JSON from {path}")
            return data
        except Exception as e:
            logger.error(f"Error loading JSON {file_path}: {e}")
            raise


class PlayerDataLoader(DataLoader):
    """Specialized loader for player data"""
    
    def load_scored_data(self, include_rookies: bool = True) -> pd.DataFrame:
        """
        Load main player scoring data
        
        Args:
            include_rookies: Whether to load data with 2026 rookies
            
        Returns:
            DataFrame with player projections and VBD scores
        """
        if include_rookies:
            filename = "scored_data_with_2026_rookies.csv"
        else:
            filename = "scored_data.csv"
        
        try:
            df = self.load_csv(filename)
            df = self._standardize_player_data(df)
            
            logger.info(f"Loaded {len(df)} players from {filename}")
            return df
            
        except FileNotFoundError:
            logger.warning(f"{filename} not found, falling back to scored_data.csv")
            df = self.load_csv("scored_data.csv")
            df = self._standardize_player_data(df)
            return df
    
    def _standardize_player_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize player data format"""
        # Handle different column name formats
        column_mapping = {}
        
        if 'index' in df.columns and 'name' not in df.columns:
            column_mapping['index'] = 'name'
        
        # Handle Player column - prefer 'name' if it exists and has more data
        if 'Player' in df.columns and 'name' in df.columns:
            # Use the column with more non-null values
            if df['name'].notna().sum() >= df['Player'].notna().sum():
                # Keep 'name', drop 'Player'
                df = df.drop(columns=['Player'], errors='ignore')
            else:
                # Use 'Player' as 'name'
                column_mapping['Player'] = 'name'
        elif 'Player' in df.columns and 'name' not in df.columns:
            column_mapping['Player'] = 'name'
        
        if 'pos' in df.columns and 'position' not in df.columns:
            column_mapping['pos'] = 'position'
        
        if 'weighted_mean' in df.columns and 'projected_points' not in df.columns:
            column_mapping['weighted_mean'] = 'projected_points'
            
        if 'ci_lower' in df.columns and 'floor' not in df.columns:
            column_mapping['ci_lower'] = 'floor'
            
        if 'ci_upper' in df.columns and 'ceiling' not in df.columns:
            column_mapping['ci_upper'] = 'ceiling'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Ensure required columns exist
        required_columns = ['name', 'position', 'projected_points']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Assign positions to 2026 rookies before filtering
        self._assign_rookie_positions(df)
        
        # Clean up data
        df = df.dropna(subset=required_columns)
        df['projected_points'] = pd.to_numeric(df['projected_points'], errors='coerce')
        df = df[df['projected_points'] > 0]  # Filter out zero/negative projections
        
        # Standardize position names
        position_mapping = {
            'WR': 'WR', 'RB': 'RB', 'QB': 'QB', 'TE': 'TE',
            'K': 'K', 'DEF': 'DEF', 'DST': 'DEF'
        }
        df['position'] = df['position'].map(position_mapping).fillna(df['position'])
        
        # Add default values for missing optional columns
        if 'tier' not in df.columns:
            df['tier'] = 1
        if 'rookie' not in df.columns:
            df['rookie'] = False
            
        # Identify 2026 NFL Draft rookies (players with no game history 2021-2025)
        self._identify_2026_rookies(df)
        
        # Scale rookie points to per-game format to match veterans
        self._scale_rookie_points(df)
        if 'team' not in df.columns:
            df['team'] = ''
        if 'floor' not in df.columns:
            df['floor'] = df['projected_points'] * 0.8
        if 'ceiling' not in df.columns:
            df['ceiling'] = df['projected_points'] * 1.2
        
        # Initialize advanced metrics columns
        for col in ['wopr', 'expected_points', 'context_multiplier', 'advanced_score']:
            if col not in df.columns:
                df[col] = 0.0
        
        return df
    
    def _identify_2026_rookies(self, df: pd.DataFrame) -> None:
        """
        Identify and mark 2026 NFL Draft rookies based on game history
        
        2026 rookies are players with 0 games in all previous years (2021-2025)
        These are college players entering their first NFL season
        """
        # Check if we have game count columns (only in data with rookies)
        game_count_cols = ['game_count_2021', 'game_count_2022', 'game_count_2023', 'game_count_2024', 'game_count_2025']
        
        if all(col in df.columns for col in game_count_cols):
            # Mark players with 0 games in all previous years as rookies
            # Use <= 0 to handle floating point precision issues
            rookie_mask = (
                (df['game_count_2021'] <= 0) & 
                (df['game_count_2022'] <= 0) & 
                (df['game_count_2023'] <= 0) & 
                (df['game_count_2024'] <= 0) & 
                (df['game_count_2025'] <= 0)
            )
            
            df.loc[rookie_mask, 'rookie'] = True
            
            # Log the rookies identified
            rookies = df[df['rookie'] == True]
            if len(rookies) > 0:
                logger.info(f"Identified {len(rookies)} 2026 NFL Draft rookies")
                for _, rookie in rookies.head(10).iterrows():  # Show first 10
                    logger.debug(f"  🌟 2026 Rookie: {rookie['name']}")
            else:
                logger.debug("No 2026 rookies found in data")
        else:
            logger.debug("Game count columns not found - cannot identify 2026 rookies")
    
    def _assign_rookie_positions(self, df: pd.DataFrame) -> None:
        """
        Assign positions to 2026 rookie prospects who are missing position data
        
        These are college players who haven't been assigned NFL positions yet
        """
        # Dictionary mapping known 2026 rookie names to their likely positions
        rookie_position_map = {
            'Jeanty, Ashton': 'RB',      # Boise State RB - Heisman candidate
            'Ward, Cam': 'QB',           # Miami QB - top QB prospect  
            'Hampton, Omarion': 'RB',    # North Carolina RB
            'Johnson, Kaleb': 'RB',      # Iowa RB
            'Harvey, RJ': 'RB',          # UCF RB
            'Milroe, Jalen': 'QB',       # Alabama QB
            'Judkins, Quinshon': 'RB',   # Ohio State RB (transfer from Ole Miss)
            'Beck, Carson': 'QB',        # Georgia QB 
            'McMillan, Tetairoa': 'WR',  # Arizona WR
            'Skattebo, Cam': 'RB',       # Arizona State RB
            'Henderson, TreVeyon': 'RB', # Ohio State RB
            'Hunter, Travis': 'WR',      # Colorado WR/CB (Heisman winner)
            'Golden, Matthew': 'WR',     # Texas WR
            'Brooks, Antwane': 'WR',     # Estimated WR
            'Thompson, Bryson': 'WR',    # Wyoming WR  
            'Warren, Tyler': 'TE',       # Penn State TE
            'Neyor, Isaiah': 'WR',       # Texas WR
            "Worthy, Ja'Marr": 'WR',     # Alabama WR
            'Wilson, Malachi': 'WR',     # Virginia Tech WR
            'Sanders, Emeka': 'WR'       # Estimated WR
        }
        
        # Check if we have the position column to assign to
        position_col = 'position' if 'position' in df.columns else 'pos'
        if position_col not in df.columns:
            logger.debug("No position column found for rookie position assignment")
            return
        
        # Assign positions to rookies
        assignments_made = 0
        for name, position in rookie_position_map.items():
            mask = (df['name'] == name) & df[position_col].isna()
            if mask.any():
                df.loc[mask, position_col] = position
                assignments_made += 1
                logger.debug(f"  🎯 Assigned position {position} to rookie {name}")
        
        if assignments_made > 0:
            logger.info(f"Assigned positions to {assignments_made} 2026 rookie prospects")
    
    def _scale_rookie_points(self, df: pd.DataFrame) -> None:
        """
        Scale rookie season projections to per-game averages to match veteran format
        
        Rookies come with season total projections (~270 pts) while veterans have
        per-game averages (~22 pts). Convert rookies to per-game scale.
        """
        rookie_mask = df['rookie'] == True
        
        if rookie_mask.any():
            # Assume 17-game NFL season for rookies
            NFL_SEASON_GAMES = 17
            
            # Scale rookie projected_points from season totals to per-game averages
            df.loc[rookie_mask, 'projected_points'] = df.loc[rookie_mask, 'projected_points'] / NFL_SEASON_GAMES
            
            # Also scale floor and ceiling if they exist
            if 'floor' in df.columns:
                df.loc[rookie_mask, 'floor'] = df.loc[rookie_mask, 'floor'] / NFL_SEASON_GAMES
            if 'ceiling' in df.columns:
                df.loc[rookie_mask, 'ceiling'] = df.loc[rookie_mask, 'ceiling'] / NFL_SEASON_GAMES
            
            scaled_rookies = df[rookie_mask]
            if len(scaled_rookies) > 0:
                logger.info(f"Scaled {len(scaled_rookies)} rookie projections from season totals to per-game averages")
                # Show a few examples
                for _, rookie in scaled_rookies.head(3).iterrows():
                    original = rookie['projected_points'] * NFL_SEASON_GAMES
                    scaled = rookie['projected_points']
                    logger.debug(f"  📊 {rookie['name']}: {original:.1f} season → {scaled:.1f} per-game")
    
    def load_historical_data(self, position: str, year: int, week: Optional[int] = None) -> pd.DataFrame:
        """
        Load historical data for a specific position and time period
        
        Args:
            position: Position type ('offense', 'defense', 'kickers')
            year: Year to load
            week: Specific week (optional)
            
        Returns:
            DataFrame with historical data
        """
        if week is not None:
            filename = f"{position}_{year}_{week}.csv"
        else:
            # Load all weeks for the year
            dfs = []
            for w in range(1, 18):  # NFL weeks 1-17
                try:
                    week_file = f"{position}_{year}_{w}.csv"
                    week_df = self.load_csv(week_file)
                    week_df['week'] = w
                    dfs.append(week_df)
                except FileNotFoundError:
                    continue
            
            if not dfs:
                raise FileNotFoundError(f"No {position} data found for {year}")
            
            return pd.concat(dfs, ignore_index=True)
        
        return self.load_csv(filename)
    
    def load_player_ids(self) -> Dict[str, Any]:
        """Load player ID mapping"""
        return self.load_json(self.config.player_ids_file)
    
    def load_rookie_rankings(self, year: int = 2025) -> pd.DataFrame:
        """Load rookie rankings for a specific year"""
        filename = f"rookie_rankings_{year}.csv"
        return self.load_csv(filename)


def load_and_prepare_data(data_path: Optional[str] = None, 
                         config: Optional[Config] = None) -> pd.DataFrame:
    """
    Convenience function to load and prepare player data
    Maintains compatibility with existing code
    """
    loader = PlayerDataLoader(config)
    
    if data_path:
        return loader.load_csv(data_path)
    else:
        return loader.load_scored_data(include_rookies=True)