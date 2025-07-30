"""
News aggregator that combines multiple sources for comprehensive player news
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from .models import PlayerNews, PlayerNewsCollection, NewsType, NewsSource
from .sources import BaseNewsSource, ESPNNewsSource, NFLNewsSource, RotoWireNewsSource

logger = logging.getLogger(__name__)


class NewsAggregator:
    """
    Aggregates NFL player news from multiple sources
    
    Provides unified interface for fetching player news, injury reports,
    and other relevant information for fantasy football analysis.
    """
    
    def __init__(self, 
                 sources: Optional[List[BaseNewsSource]] = None,
                 cache_duration_hours: int = 1,
                 max_workers: int = 3):
        """
        Initialize news aggregator
        
        Args:
            sources: List of news sources to use
            cache_duration_hours: How long to cache results
            max_workers: Maximum concurrent requests
        """
        self.sources = sources or [
            ESPNNewsSource(),
            NFLNewsSource(), 
            RotoWireNewsSource()
        ]
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.max_workers = max_workers
        
        # Cache for news results
        self._player_cache: Dict[str, PlayerNewsCollection] = {}
        self._injury_cache: List[PlayerNews] = []
        self._injury_cache_time: Optional[datetime] = None
        
        logger.info(f"NewsAggregator initialized with {len(self.sources)} sources")
    
    def get_player_news(self, 
                       player_name: str, 
                       limit_per_source: int = 5,
                       max_age_days: int = 14,
                       use_cache: bool = True) -> PlayerNewsCollection:
        """
        Get comprehensive news for a specific player
        
        Args:
            player_name: Name of the player
            limit_per_source: Maximum news items per source
            max_age_days: Only include news from last N days
            use_cache: Whether to use cached results
            
        Returns:
            PlayerNewsCollection with aggregated news
        """
        cache_key = f"{player_name.lower()}_{limit_per_source}_{max_age_days}"
        
        # Check cache
        if use_cache and cache_key in self._player_cache:
            cached = self._player_cache[cache_key] 
            if datetime.now() - cached.last_updated < self.cache_duration:
                logger.debug(f"Using cached news for {player_name}")
                return cached
        
        logger.info(f"Fetching fresh news for {player_name}")
        
        # Fetch from all sources concurrently
        all_news = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {
                executor.submit(source.fetch_player_news, player_name, limit_per_source): source
                for source in self.sources
            }
            
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    news_items = future.result(timeout=30)  # 30 second timeout
                    all_news.extend(news_items)
                    logger.debug(f"Got {len(news_items)} items from {source.__class__.__name__}")
                except Exception as e:
                    if "ESPN" in source.__class__.__name__:
                        logger.error(f"Error fetching from {source.__class__.__name__}: {e}")
                    else:
                        logger.debug(f"{source.__class__.__name__} not implemented: {e}")
        
        # Filter by age and deduplicate
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        filtered_news = self._filter_and_deduplicate(all_news, cutoff_date)
        
        # Create collection
        collection = PlayerNewsCollection(
            player_name=player_name,
            news_items=filtered_news,
            last_updated=datetime.now()
        )
        
        # Cache result
        self._player_cache[cache_key] = collection
        
        logger.info(f"Aggregated {len(filtered_news)} news items for {player_name}")
        return collection
    
    def get_injury_reports(self, 
                          team: Optional[str] = None,
                          use_cache: bool = True) -> List[PlayerNews]:
        """
        Get current injury reports across the league
        
        Args:
            team: Specific team to filter by (optional)
            use_cache: Whether to use cached results
            
        Returns:
            List of injury-related news items
        """
        # Check cache
        if (use_cache and self._injury_cache and self._injury_cache_time and 
            datetime.now() - self._injury_cache_time < self.cache_duration):
            logger.debug("Using cached injury reports")
            cached_reports = self._injury_cache
        else:
            logger.info("Fetching fresh injury reports")
            
            # Fetch from all sources concurrently
            all_injuries = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_source = {
                    executor.submit(source.fetch_injury_reports, team): source
                    for source in self.sources
                }
                
                for future in as_completed(future_to_source):
                    source = future_to_source[future]
                    try:
                        injury_items = future.result(timeout=30)
                        all_injuries.extend(injury_items)
                        logger.debug(f"Got {len(injury_items)} injuries from {source.__class__.__name__}")
                    except Exception as e:
                        if "ESPN" in source.__class__.__name__:
                            logger.error(f"Error fetching injuries from {source.__class__.__name__}: {e}")
                        else:
                            logger.debug(f"{source.__class__.__name__} injuries not implemented: {e}")
            
            # Deduplicate and cache
            cached_reports = self._deduplicate_injuries(all_injuries)
            self._injury_cache = cached_reports
            self._injury_cache_time = datetime.now()
        
        # Filter by team if specified
        if team:
            team_reports = [injury for injury in cached_reports 
                          if injury.team and injury.team.lower() == team.lower()]
            logger.info(f"Filtered to {len(team_reports)} injury reports for {team}")
            return team_reports
        
        logger.info(f"Retrieved {len(cached_reports)} total injury reports")
        return cached_reports
    
    def get_player_summary(self, player_name: str) -> Dict[str, any]:
        """
        Get a comprehensive summary for a player including news and injury status
        
        Args:
            player_name: Name of the player
            
        Returns:
            Dictionary with player summary information
        """
        news_collection = self.get_player_news(player_name)
        
        return {
            'player_name': player_name,
            'total_news_items': len(news_collection.news_items),
            'latest_injury_status': news_collection.latest_injury_status.value if news_collection.latest_injury_status else 'unknown',
            'injury_summary': news_collection.injury_summary,
            'top_headlines': [
                {
                    'headline': news.headline,
                    'date': news.published_date.strftime('%Y-%m-%d'),
                    'source': news.source.value,
                    'type': news.news_type.value,
                    'relevance_score': news.fantasy_relevance_score
                }
                for news in news_collection.top_headlines
            ],
            'last_updated': news_collection.last_updated.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _filter_and_deduplicate(self, 
                               news_items: List[PlayerNews], 
                               cutoff_date: datetime) -> List[PlayerNews]:
        """Filter news by date and remove duplicates"""
        # Filter by date
        recent_news = [news for news in news_items if news.published_date >= cutoff_date]
        
        # Deduplicate by headline similarity
        deduplicated = []
        seen_headlines = set()
        
        for news in sorted(recent_news, key=lambda x: x.published_date, reverse=True):
            # Create a normalized headline for comparison
            normalized = self._normalize_headline(news.headline)
            
            if normalized not in seen_headlines:
                deduplicated.append(news)
                seen_headlines.add(normalized)
        
        return deduplicated
    
    def _deduplicate_injuries(self, injury_items: List[PlayerNews]) -> List[PlayerNews]:
        """Deduplicate injury reports"""
        # Group by player name
        player_injuries: Dict[str, List[PlayerNews]] = {}
        
        for injury in injury_items:
            player_key = injury.player_name.lower()
            if player_key not in player_injuries:
                player_injuries[player_key] = []
            player_injuries[player_key].append(injury)
        
        # Keep most recent injury report per player
        deduplicated = []
        for player_name, injuries in player_injuries.items():
            if injuries:
                latest = max(injuries, key=lambda x: x.published_date)
                deduplicated.append(latest)
        
        return deduplicated
    
    def _normalize_headline(self, headline: str) -> str:
        """Normalize headline for deduplication"""
        import re
        
        # Convert to lowercase
        normalized = headline.lower()
        
        # Remove common prefixes/suffixes
        prefixes = ['report:', 'breaking:', 'update:', 'fantasy:', 'nfl:']
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Remove punctuation and extra spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def clear_cache(self):
        """Clear all cached news data"""
        self._player_cache.clear()
        self._injury_cache.clear()
        self._injury_cache_time = None
        logger.info("News cache cleared")
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        return {
            'player_cache_size': len(self._player_cache),
            'injury_cache_size': len(self._injury_cache),
            'injury_cache_age_minutes': (
                (datetime.now() - self._injury_cache_time).total_seconds() / 60
                if self._injury_cache_time else None
            ),
            'cache_duration_hours': self.cache_duration.total_seconds() / 3600
        }