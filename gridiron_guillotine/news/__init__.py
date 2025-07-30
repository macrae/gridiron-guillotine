"""
NFL News and Reports Retrieval System

This module provides comprehensive news aggregation for NFL players,
including injury reports, transactions, and analysis-relevant updates.
"""

from .aggregator import NewsAggregator
from .sources import ESPNNewsSource, NFLNewsSource, RotoWireNewsSource
from .models import PlayerNews, NewsType, NewsSource

__all__ = [
    'NewsAggregator',
    'ESPNNewsSource', 
    'NFLNewsSource',
    'RotoWireNewsSource',
    'PlayerNews',
    'NewsType',
    'NewsSource'
]