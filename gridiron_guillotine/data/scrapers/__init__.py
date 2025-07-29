"""
Web scraping modules for NFL data collection
"""

from .base import BaseScraper
from .offense import OffenseScraper  
from .defense import DefenseScraper
from .kickers import KickerScraper
from .players import PlayerScraper

__all__ = [
    "BaseScraper",
    "OffenseScraper",
    "DefenseScraper", 
    "KickerScraper",
    "PlayerScraper",
]