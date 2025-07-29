"""
Data models for fantasy football draft strategy
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Union
from enum import Enum


class Position(str, Enum):
    """Player positions"""
    QB = "QB"
    RB = "RB" 
    WR = "WR"
    TE = "TE"
    K = "K"
    DEF = "DEF"
    # Additional positions that may appear in data
    DB = "DB"  # Defensive back
    DT = "DT"  # Defensive tackle  
    OT = "OT"  # Offensive tackle
    UNKNOWN = "UNKNOWN"  # Fallback for unknown positions


class HeroRBPhase(str, Enum):
    """Hero-RB strategy phases"""
    HERO_ACQUISITION = "hero_acquisition"
    PIVOT_PHASE = "pivot_phase"
    DEPTH_PHASE = "depth_phase"


@dataclass
class Player:
    """Represents a fantasy football player"""
    name: str
    position: Position
    team: str
    projected_points: float
    vbd: float = 0.0
    tier: int = 1
    floor: Optional[float] = None
    ceiling: Optional[float] = None
    rookie: bool = False
    
    # Advanced metrics
    wopr: float = 0.0
    expected_points: float = 0.0
    context_multiplier: float = 1.0
    advanced_score: float = 0.0
    adjusted_value: float = 0.0
    
    # Additional data
    target_share: float = 0.0
    air_yards_share: float = 0.0
    red_zone_targets: int = 0
    red_zone_carries: int = 0
    goal_line_carries: int = 0
    air_yards_per_target: float = 0.0
    
    def __post_init__(self):
        """Set defaults after initialization"""
        if self.floor is None:
            self.floor = self.projected_points * 0.8
        if self.ceiling is None:
            self.ceiling = self.projected_points * 1.2
        if self.expected_points == 0.0:
            self.expected_points = self.projected_points


@dataclass 
class DraftPick:
    """Represents a draft pick"""
    player_name: str
    team_name: str
    position: Position
    round_num: int
    pick_num: int
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def __str__(self) -> str:
        return f"Round {self.round_num}, Pick {self.pick_num}: {self.team_name} selects {self.player_name} ({self.position.value})"


@dataclass
class LeagueSettings:
    """League configuration settings"""
    teams: int = 12
    rounds: int = 15
    ppr: bool = True
    position_limits: Dict[Position, int] = None
    scoring: Dict[str, float] = None
    
    def __post_init__(self):
        if self.position_limits is None:
            self.position_limits = {
                Position.QB: 1,
                Position.RB: 2,
                Position.WR: 2, 
                Position.TE: 1,
                Position.K: 1,
                Position.DEF: 1
            }
        
        if self.scoring is None:
            # Default PPR scoring
            self.scoring = {
                'passing_yards': 0.04,
                'passing_tds': 4.0,
                'interceptions': -2.0,
                'rushing_yards': 0.1,
                'rushing_tds': 6.0,
                'receiving_yards': 0.1,
                'receiving_tds': 6.0,
                'receptions': 1.0,  # PPR
                'fumbles_lost': -2.0,
            }


@dataclass
class DraftState:
    """Represents the current state of a draft"""
    current_round: int = 1
    current_pick: int = 1
    drafted_players: set = None
    team_rosters: Dict[str, Dict[Position, List[str]]] = None
    
    # Hero-RB specific state
    hero_rb_acquired: bool = False
    total_rbs_drafted: int = 0
    hero_rb_phase: HeroRBPhase = HeroRBPhase.HERO_ACQUISITION
    
    def __post_init__(self):
        if self.drafted_players is None:
            self.drafted_players = set()
        if self.team_rosters is None:
            self.team_rosters = {}