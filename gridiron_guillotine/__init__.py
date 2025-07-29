"""
Gridiron Guillotine: Championship Fantasy Football Draft Strategy
Research-validated Hero-RB strategy with advanced metrics and live draft monitoring
"""

__version__ = "2.0.0"
__author__ = "Gridiron Guillotine Project"

# Core imports for easy access
from .core.strategy import ChampionshipDraftStrategy
from .core.models import Player, DraftPick, LeagueSettings

__all__ = [
    "ChampionshipDraftStrategy",
    "Player", 
    "DraftPick",
    "LeagueSettings",
]