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
            include_rookies: Whether to load data with 2025 rookies
            
        Returns:
            DataFrame with player projections and VBD scores
        """
        if include_rookies:
            filename = "scored_data_with_2025_rookies.csv"
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