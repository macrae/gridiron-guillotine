"""
NFL News Integration System for Player Database

Connects the NewsAggregator with the PlayerDatabase to provide real-time 
NFL news updates for all players in the fantasy database.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..news.aggregator import NewsAggregator
from ..news.models import PlayerNews, NewsType, InjuryStatus
from .database import PlayerDatabase, EnhancedPlayer, NewsImpact
from .database import PlayerNews as DatabasePlayerNews  # Avoid naming conflict

logger = logging.getLogger(__name__)


class NewsIntegrationEngine:
    """
    Integrates NFL news with the fantasy player database
    
    Features:
    - Bulk news updates for all players
    - Individual player news updates  
    - News impact classification (positive/negative/neutral)
    - Fantasy relevance scoring
    - Automatic database updates
    """
    
    def __init__(self, database: Optional[PlayerDatabase] = None):
        """Initialize the news integration engine"""
        self.database = database or PlayerDatabase()
        self.news_aggregator = NewsAggregator()
        
        # News impact keywords for classification
        self.positive_keywords = {
            'cleared', 'activated', 'healthy', 'ready', 'practicing', 'expected to play',
            'no injury', 'full practice', 'upgraded', 'recovered', 'back', 'return',
            'starting', 'increased role', 'promotion', 'opportunity'
        }
        
        self.negative_keywords = {
            'injured', 'hurt', 'out', 'doubtful', 'questionable', 'surgery',
            'ir', 'injured reserve', 'suspended', 'benched', 'demoted',
            'limited', 'setback', 'concern', 'week-to-week', 'day-to-day',
            'did not practice', 'dnp', 'missed practice'
        }
        
        logger.info("NewsIntegrationEngine initialized")
    
    def update_player_news(self, player_name: str, limit: int = 10) -> bool:
        """
        Update news for a specific player
        
        Args:
            player_name: Name of player to update
            limit: Maximum number of news items to fetch
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Updating news for {player_name}")
            
            # Get player from database
            player = self.database.get_player(player_name)
            if not player:
                logger.warning(f"Player '{player_name}' not found in database")
                return False
            
            # Convert "Last, First" to "First Last" format for news search
            search_name = self._convert_name_for_search(player_name)
            
            # Fetch news from aggregator
            news_collection = self.news_aggregator.get_player_news(
                search_name, 
                limit_per_source=min(limit // 3 + 1, 5),  # Distribute across 3 sources
                max_age_days=14
            )
            
            if not news_collection or not news_collection.news_items:
                logger.info(f"No news found for {player_name} - clearing old news")
                # Clear old news since no current news was found
                player.update_news([])  # Empty list clears news
                player.overall_news_impact = NewsImpact.NEUTRAL
                player.news_last_updated = datetime.now()
                self.database.upsert_player(player)
                return True
            
            # Convert news items to database format
            db_news_items = []
            for news_item in news_collection.news_items[:limit]:
                db_news = self._convert_news_to_database_format(news_item)
                db_news_items.append(db_news)
            
            # Update player with news
            player.update_news(db_news_items)
            
            # Classify overall news impact
            player.overall_news_impact = self._classify_news_impact(news_collection.news_items)
            
            # Save to database
            self.database.upsert_player(player)
            
            logger.info(f"Successfully updated news for {player_name}: {len(db_news_items)} items")
            return True
            
        except Exception as e:
            logger.error(f"Error updating news for {player_name}: {e}")
            return False
    
    def bulk_update_news(self, 
                        player_names: Optional[List[str]] = None,
                        limit_per_player: int = 5,
                        max_players: int = 100,
                        max_workers: int = 5) -> Dict[str, bool]:
        """
        Update news for multiple players in parallel
        
        Args:
            player_names: Specific players to update (None = top players)
            limit_per_player: News items per player
            max_players: Maximum players to update
            max_workers: Concurrent update threads
            
        Returns:
            Dictionary of player_name -> success status
        """
        logger.info(f"Starting bulk news update for up to {max_players} players")
        
        # Get players to update
        if player_names:
            target_players = [name for name in player_names[:max_players]]
        else:
            # Get top fantasy-relevant players
            all_players = self.database.get_top_players(limit=max_players * 2)
            # Filter to skill positions (QB, RB, WR, TE)
            skill_players = [p for p in all_players if p.position.value in ['QB', 'RB', 'WR', 'TE']]
            target_players = [p.name for p in skill_players[:max_players]]
        
        if not target_players:
            logger.warning("No players found to update")
            return {}
        
        logger.info(f"Updating news for {len(target_players)} players")
        
        # Update players in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_player = {
                executor.submit(self.update_player_news, player_name, limit_per_player): player_name
                for player_name in target_players
            }
            
            # Process completed tasks
            for i, future in enumerate(as_completed(future_to_player), 1):
                player_name = future_to_player[future]
                try:
                    success = future.result()
                    results[player_name] = success
                    
                    if i % 10 == 0:
                        logger.info(f"Processed {i}/{len(target_players)} players")
                        
                except Exception as e:
                    logger.error(f"Error updating {player_name}: {e}")
                    results[player_name] = False
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"Bulk update complete: {successful}/{len(target_players)} successful")
        
        return results
    
    def update_injury_reports(self) -> List[EnhancedPlayer]:
        """
        Get latest injury reports and update relevant players
        
        Returns:
            List of players with updated injury information
        """
        logger.info("Updating injury reports")
        
        try:
            # Get injury news from aggregator
            injury_news = self.news_aggregator.get_injury_reports(limit=50)
            
            if not injury_news:
                logger.info("No injury reports found")
                return []
            
            updated_players = []
            
            for news_item in injury_news:
                # Find player in database
                player = self.database.get_player(news_item.player_name)
                if not player:
                    continue
                
                # Convert and add news
                db_news = self._convert_news_to_database_format(news_item)
                
                # Update player news (add to existing news)
                if not player.latest_news:
                    player.latest_news = []
                
                # Add to front of list (most recent first)
                player.latest_news.insert(0, db_news)
                
                # Keep only last 10 news items
                player.latest_news = player.latest_news[:10]
                
                # Update overall impact
                all_news_items = [news_item]  # Start with new item
                player.overall_news_impact = self._classify_news_impact(all_news_items)
                player.news_last_updated = datetime.now()
                
                # Save player
                self.database.upsert_player(player)
                updated_players.append(player)
            
            logger.info(f"Updated injury information for {len(updated_players)} players")
            return updated_players
            
        except Exception as e:
            logger.error(f"Error updating injury reports: {e}")
            return []
    
    def _convert_news_to_database_format(self, news_item: PlayerNews) -> DatabasePlayerNews:
        """Convert NewsAggregator format to database format"""
        
        # Map news impact
        impact = self._classify_single_news_impact(news_item)
        
        return DatabasePlayerNews(
            headline=news_item.headline,
            content=news_item.content,
            source=news_item.source.value,
            published_date=news_item.published_date,
            impact=impact,
            severity=news_item.severity_score,
            url=news_item.url
        )
    
    def _classify_news_impact(self, news_items: List[PlayerNews]) -> NewsImpact:
        """
        Classify overall news impact for a player
        
        Args:
            news_items: List of news items for the player
            
        Returns:
            Overall impact classification
        """
        if not news_items:
            return NewsImpact.NEUTRAL
        
        # Weight recent news more heavily
        positive_score = 0.0
        negative_score = 0.0
        
        for news_item in news_items:
            # Calculate recency weight (more recent = higher weight)
            # Handle timezone-aware vs naive datetime comparison
            from datetime import timezone
            now = datetime.now(timezone.utc)
            pub_date = news_item.published_date
            
            # If published_date is naive, assume UTC
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            
            days_old = (now - pub_date).days
            recency_weight = max(0.1, 1.0 / (1 + days_old * 0.2))  # Decay over time
            
            impact = self._classify_single_news_impact(news_item)
            
            if impact == NewsImpact.POSITIVE:
                positive_score += recency_weight
            elif impact == NewsImpact.NEGATIVE:
                negative_score += recency_weight
        
        # Determine overall impact
        if positive_score > negative_score * 1.2:  # Bias slightly toward positive
            return NewsImpact.POSITIVE
        elif negative_score > positive_score:
            return NewsImpact.NEGATIVE
        else:
            return NewsImpact.NEUTRAL
    
    def _classify_single_news_impact(self, news_item: PlayerNews) -> NewsImpact:
        """Classify impact of a single news item"""
        
        # Combine headline and content for analysis
        text = f"{news_item.headline} {news_item.content}".lower()
        
        # Check for explicit injury status
        if news_item.injury_status:
            if news_item.injury_status in [InjuryStatus.HEALTHY]:
                return NewsImpact.POSITIVE
            elif news_item.injury_status in [InjuryStatus.OUT, InjuryStatus.INJURED_RESERVE, 
                                           InjuryStatus.SUSPENDED]:
                return NewsImpact.NEGATIVE
            elif news_item.injury_status in [InjuryStatus.QUESTIONABLE, InjuryStatus.DOUBTFUL]:
                return NewsImpact.NEGATIVE
        
        # Check keywords
        positive_matches = sum(1 for keyword in self.positive_keywords if keyword in text)
        negative_matches = sum(1 for keyword in self.negative_keywords if keyword in text)
        
        # Weight by news type
        if news_item.news_type == NewsType.INJURY:
            negative_matches += 1  # Injury news tends to be negative
        elif news_item.news_type in [NewsType.TRANSACTION, NewsType.TRADE]:
            # Transactions can be positive or negative, rely on keywords
            pass
        
        # Classify based on keyword matches
        if positive_matches > negative_matches:
            return NewsImpact.POSITIVE
        elif negative_matches > positive_matches:
            return NewsImpact.NEGATIVE
        else:
            return NewsImpact.NEUTRAL
    
    def get_news_summary(self, days_back: int = 7) -> Dict[str, any]:
        """
        Get summary of recent news activity
        
        Args:
            days_back: Days to look back for news
            
        Returns:
            Summary statistics
        """
        try:
            # Get players with recent news updates
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Query database for players with recent news
            import sqlite3
            stats = {
                'total_players_with_news': 0,
                'players_with_positive_news': 0,
                'players_with_negative_news': 0,
                'players_with_neutral_news': 0,
                'most_recent_update': None,
                'injury_concerns': []
            }
            
            with sqlite3.connect(self.database.db_path) as conn:
                # Count players with news
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM players 
                    WHERE news_last_updated IS NOT NULL 
                    AND news_last_updated > ?
                """, (cutoff_date.isoformat(),))
                stats['total_players_with_news'] = cursor.fetchone()[0]
                
                # Count by impact
                for impact in ['positive', 'negative', 'neutral']:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM players 
                        WHERE overall_news_impact = ? 
                        AND news_last_updated > ?
                    """, (impact, cutoff_date.isoformat()))
                    stats[f'players_with_{impact}_news'] = cursor.fetchone()[0]
                
                # Get most recent update
                cursor = conn.execute("""
                    SELECT MAX(news_last_updated) FROM players 
                    WHERE news_last_updated IS NOT NULL
                """)
                result = cursor.fetchone()[0]
                if result:
                    stats['most_recent_update'] = datetime.fromisoformat(result)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting news summary: {e}")
            return {}
    
    def cleanup_old_news(self, days_to_keep: int = 30) -> int:
        """
        Clean up old news items from database
        
        Args:
            days_to_keep: Number of days of news to keep
            
        Returns:
            Number of players updated
        """
        logger.info(f"Cleaning up news older than {days_to_keep} days")
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        updated_count = 0
        
        try:
            # Get all players with news
            all_players = self.database.get_top_players(limit=10000)
            
            for player in all_players:
                if not player.latest_news:
                    continue
                
                # Filter out old news
                old_count = len(player.latest_news)
                player.latest_news = [
                    news for news in player.latest_news 
                    if news.published_date > cutoff_date
                ]
                
                # Update if we removed any news
                if len(player.latest_news) < old_count:
                    # Recalculate news impact with remaining items
                    if player.latest_news:
                        # Convert back to PlayerNews format for classification
                        news_items = []  # Would need conversion logic here
                        player.overall_news_impact = NewsImpact.NEUTRAL  # Simplified
                    else:
                        player.overall_news_impact = NewsImpact.NEUTRAL
                        player.news_last_updated = None
                    
                    self.database.upsert_player(player)
                    updated_count += 1
            
            logger.info(f"Cleaned up old news for {updated_count} players")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old news: {e}")
            return 0
    
    def _convert_name_for_search(self, player_name: str) -> str:
        """
        Convert player name from database format to news search format
        
        Database: "Jackson, Lamar" 
        News search: "Lamar Jackson"
        """
        if ',' in player_name:
            parts = player_name.split(',', 1)
            if len(parts) == 2:
                last_name = parts[0].strip()
                first_name = parts[1].strip()
                return f"{first_name} {last_name}"
        
        # If no comma, return as-is
        return player_name


def main():
    """CLI entry point for news integration"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='NFL News Integration System')
    parser.add_argument('--player', type=str, help='Update news for specific player')
    parser.add_argument('--bulk', action='store_true', help='Bulk update top players')
    parser.add_argument('--injuries', action='store_true', help='Update injury reports')
    parser.add_argument('--summary', action='store_true', help='Show news summary')
    parser.add_argument('--cleanup', type=int, help='Clean up news older than N days')
    parser.add_argument('--limit', type=int, default=50, help='Limit for bulk updates')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    engine = NewsIntegrationEngine()
    
    if args.player:
        success = engine.update_player_news(args.player)
        print(f"✅ Updated news for {args.player}" if success else f"❌ Failed to update {args.player}")
    
    elif args.bulk:
        results = engine.bulk_update_news(max_players=args.limit)
        successful = sum(1 for success in results.values() if success)
        print(f"✅ Bulk update complete: {successful}/{len(results)} successful")
    
    elif args.injuries:
        updated_players = engine.update_injury_reports()
        print(f"✅ Updated injury reports for {len(updated_players)} players")
    
    elif args.summary:
        summary = engine.get_news_summary()
        print("📰 News Summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    
    elif args.cleanup is not None:
        count = engine.cleanup_old_news(args.cleanup)
        print(f"🧹 Cleaned up old news for {count} players")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()