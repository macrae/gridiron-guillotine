"""
Data validation functionality
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..core.config import Config, get_config
from ..core.models import Position

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates data integrity and format"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
    
    def validate_file(self, filepath: Path) -> Dict[str, Any]:
        """
        Validate a data file
        
        Returns:
            Dict with validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            if filepath.suffix.lower() == '.csv':
                result = self._validate_csv(filepath)
            elif filepath.suffix.lower() == '.json':
                result = self._validate_json(filepath)
            else:
                result['errors'].append(f"Unsupported file type: {filepath.suffix}")
                
        except Exception as e:
            result['errors'].append(f"Validation error: {str(e)}")
        
        return result
    
    def _validate_csv(self, filepath: Path) -> Dict[str, Any]:
        """Validate CSV file format and content"""
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            df = pd.read_csv(filepath)
            
            # Check if file is empty
            if len(df) == 0:
                result['errors'].append("File is empty")
                result['valid'] = False
                return result
            
            # Validate player data files
            if 'scored_data' in filepath.name:
                result = self._validate_player_data(df, result)
            
            # Check for duplicate entries
            if 'name' in df.columns:
                duplicates = df[df.duplicated(subset=['name'], keep=False)]
                if len(duplicates) > 0:
                    result['warnings'].append(f"Found {len(duplicates)} duplicate player names")
            
            # Check for missing values in key columns
            key_columns = []
            if 'name' in df.columns:
                key_columns.append('name')
            if 'position' in df.columns:
                key_columns.append('position')
            if 'projected_points' in df.columns:
                key_columns.append('projected_points')
            
            for col in key_columns:
                missing = df[col].isna().sum()
                if missing > 0:
                    result['warnings'].append(f"Column '{col}' has {missing} missing values")
            
        except Exception as e:
            result['errors'].append(f"Error reading CSV: {str(e)}")
            result['valid'] = False
        
        return result
    
    def _validate_player_data(self, df: pd.DataFrame, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate player data specific requirements"""
        
        # Required columns for player data
        required_columns = ['name', 'position', 'projected_points']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            result['errors'].extend([f"Missing required column: {col}" for col in missing_columns])
            result['valid'] = False
        
        # Validate positions
        if 'position' in df.columns:
            valid_positions = [pos.value for pos in Position]
            invalid_positions = df[~df['position'].isin(valid_positions)]['position'].unique()
            
            if len(invalid_positions) > 0:
                result['warnings'].append(f"Invalid positions found: {list(invalid_positions)}")
        
        # Validate projected points
        if 'projected_points' in df.columns:
            negative_points = df[df['projected_points'] < 0]
            if len(negative_points) > 0:
                result['warnings'].append(f"Found {len(negative_points)} players with negative projected points")
            
            zero_points = df[df['projected_points'] == 0]
            if len(zero_points) > 0:
                result['warnings'].append(f"Found {len(zero_points)} players with zero projected points")
        
        return result
    
    def _validate_json(self, filepath: Path) -> Dict[str, Any]:
        """Validate JSON file format"""
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                result['warnings'].append("JSON root is not a dictionary")
                
        except json.JSONDecodeError as e:
            result['errors'].append(f"Invalid JSON format: {str(e)}")
            result['valid'] = False
        except Exception as e:
            result['errors'].append(f"Error reading JSON: {str(e)}")
            result['valid'] = False
        
        return result