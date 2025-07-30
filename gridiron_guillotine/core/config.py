"""
Configuration management for Gridiron Guillotine
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

from .models import Position


@dataclass
class Config:
    """Main configuration class"""
    
    # Data paths
    data_dir: Path = field(default_factory=lambda: Path("data"))
    raw_data_dir: Path = field(default_factory=lambda: Path("data/raw"))
    processed_data_dir: Path = field(default_factory=lambda: Path("data/processed"))
    
    # Main data files
    scored_data_file: str = "scored_data_with_2025_rookies.csv"
    player_ids_file: str = "player_ids.json"
    
    # League settings
    default_teams: int = 12
    default_rounds: int = 15
    default_ppr: bool = True
    
    # Position limits
    position_limits: Dict[Position, int] = field(default_factory=lambda: {
        Position.QB: 1,
        Position.RB: 2,
        Position.WR: 2,
        Position.TE: 1,
        Position.K: 1,
        Position.DEF: 1
    })
    
    # Hero-RB configuration
    elite_hero_rbs: List[str] = field(default_factory=lambda: [
        'McCaffrey, Christian',
        'Kamara, Alvin',
        'Achane, De\'Von',
        'Taylor, Jonathan',
        'Gibbs, Jahmyr',
        'Barkley, Saquon',
        'Henry, Derrick'
    ])
    
    # PPR adjustments
    ppr_pass_catchers: Dict[str, float] = field(default_factory=lambda: {
        'McCaffrey, Christian': 3.0,
        'Kamara, Alvin': 3.0,
        'Ekeler, Austin': 2.5,
        'Achane, De\'Von': 2.0,
        'Gibbs, Jahmyr': 2.0
    })
    
    ppr_pure_rushers: Dict[str, float] = field(default_factory=lambda: {
        'Henry, Derrick': -1.5,
        'Chubb, Nick': -1.0,
        'Jones, Aaron': -0.5
    })
    
    # Advanced metrics
    wopr_weights: Dict[str, float] = field(default_factory=lambda: {
        'target_share': 1.5,
        'air_yards_share': 0.7
    })
    
    # Offensive context
    elite_offenses: List[str] = field(default_factory=lambda: [
        'Buffalo', 'Miami', 'Kansas City', 'Cincinnati', 'Baltimore',
        'San Francisco', 'Detroit', 'Philadelphia', 'Dallas', 'LA Rams',
        'Minnesota', 'Green Bay', 'Houston', 'Atlanta'
    ])
    
    bottom_offenses: List[str] = field(default_factory=lambda: [
        'Carolina', 'New England', 'Chicago', 'Denver', 'NY Giants',
        'Las Vegas', 'Tennessee', 'Jacksonville', 'Arizona', 'Cleveland'
    ])
    
    # Draft position targets
    position_targets: Dict[str, List[str]] = field(default_factory=lambda: {
        'early_rd1': ['Chase, Ja\'Marr', 'Jefferson, Justin', 'Hill, Tyreek'],
        'middle_rd1': ['Gibbs, Jahmyr', 'Thomas Jr., Brian', 'Nacua, Puka'],
        'late_rd1': ['Collins, Nico', 'St. Brown, Amon-Ra', 'Metcalf, DK', 'Cooper, Amari'],
        'late_rd2': ['St. Brown, Amon-Ra', 'Thomas Jr., Brian', 'Wilson, Garrett'],
        'late_rd3': ['Hall, Breece', 'Pollard, Tony', 'Mostert, Raheem']
    })
    
    # Replacement levels
    replacement_levels: Dict[Position, int] = field(default_factory=lambda: {
        Position.QB: 12,
        Position.RB: 24,
        Position.WR: 36,
        Position.TE: 12,
        Position.K: 12,
        Position.DEF: 12,
        # Non-fantasy positions (should be filtered out anyway)
        Position.DB: 0,
        Position.DT: 0,
        Position.OT: 0,
        Position.UNKNOWN: 0
    })
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Yahoo API
    yahoo_oauth_file: str = "nbs/oauth2.json"
    
    # Live draft settings
    polling_interval: int = 20  # seconds
    
    def __post_init__(self):
        """Ensure paths are Path objects"""
        self.data_dir = Path(self.data_dir)
        self.raw_data_dir = Path(self.raw_data_dir)
        self.processed_data_dir = Path(self.processed_data_dir)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create config from environment variables"""
        config = cls()
        
        # Override with environment variables if present
        if os.getenv('GRIDIRON_DATA_DIR'):
            config.data_dir = Path(os.getenv('GRIDIRON_DATA_DIR'))
        
        if os.getenv('GRIDIRON_LOG_LEVEL'):
            config.log_level = os.getenv('GRIDIRON_LOG_LEVEL')
        
        if os.getenv('GRIDIRON_POLLING_INTERVAL'):
            config.polling_interval = int(os.getenv('GRIDIRON_POLLING_INTERVAL'))
        
        return config
    
    def get_data_file_path(self, filename: str) -> Path:
        """Get full path to a data file"""
        return self.data_dir / filename
    
    def get_raw_data_path(self, filename: str) -> Path:
        """Get full path to a raw data file"""
        return self.raw_data_dir / filename
    
    def get_processed_data_path(self, filename: str) -> Path:
        """Get full path to a processed data file"""
        return self.processed_data_dir / filename


# Default configuration instance
DEFAULT_CONFIG = Config()


def get_config() -> Config:
    """Get configuration with environment variable overrides"""
    return Config.from_env()