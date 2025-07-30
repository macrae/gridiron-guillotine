"""
Data models for NFL news and reports system
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class NewsType(str, Enum):
    """Types of NFL news"""
    INJURY = "injury"
    TRANSACTION = "transaction"
    SUSPENSION = "suspension"
    TRADE = "trade"
    PRACTICE_STATUS = "practice_status"
    GENERAL = "general"
    ANALYSIS = "analysis"
    DEPTH_CHART = "depth_chart"


class NewsSource(str, Enum):
    """News sources"""
    ESPN = "espn"
    NFL_OFFICIAL = "nfl_official"
    ROTOWIRE = "rotowire"
    ROTOBALLER = "rotoballer"
    NBC_SPORTS = "nbc_sports"
    YAHOO_SPORTS = "yahoo_sports"


class InjuryStatus(str, Enum):
    """Player injury status categories"""
    HEALTHY = "healthy"
    QUESTIONABLE = "questionable"
    DOUBTFUL = "doubtful"
    OUT = "out"
    INJURED_RESERVE = "injured_reserve"
    PHYSICALLY_UNABLE = "physically_unable"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


@dataclass
class PlayerNews:
    """Represents a news item about an NFL player"""
    player_name: str
    headline: str
    content: str
    news_type: NewsType
    source: NewsSource
    published_date: datetime
    url: Optional[str] = None
    
    # Injury-specific fields
    injury_status: Optional[InjuryStatus] = None
    body_part: Optional[str] = None
    expected_return: Optional[str] = None
    
    # Fantasy relevance
    fantasy_impact: Optional[str] = None
    severity_score: Optional[float] = None  # 0-10 scale
    
    # Metadata
    tags: List[str] = None
    team: Optional[str] = None
    position: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @property
    def is_injury_related(self) -> bool:
        """Check if this news item is injury related"""
        return (self.news_type == NewsType.INJURY or 
                self.injury_status is not None or
                any(keyword in self.headline.lower() for keyword in 
                    ['injury', 'hurt', 'injured', 'questionable', 'doubtful', 'out']))
    
    def is_recent(self, days: int = 7) -> bool:
        """Check if news is recent (within specified days)"""
        if not self.published_date:
            return False
        
        # Handle timezone-aware vs naive datetime comparison
        from datetime import timezone
        now = datetime.now(timezone.utc)
        pub_date = self.published_date
        
        # If published_date is naive, assume UTC
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        
        return (now - pub_date).days <= days
    
    @property
    def fantasy_relevance_score(self) -> float:
        """Calculate fantasy relevance score (0-10)"""
        score = 5.0  # Base score
        
        # Recent news is more relevant
        if self.is_recent(1):
            score += 2.0
        elif self.is_recent(3):
            score += 1.0
        
        # Injury news is highly relevant
        if self.is_injury_related:
            score += 2.0
            
        # Severity impacts relevance
        if self.severity_score:
            score += self.severity_score * 0.3
            
        # Transaction news is relevant
        if self.news_type in [NewsType.TRANSACTION, NewsType.TRADE]:
            score += 1.5
            
        return min(10.0, max(0.0, score))


@dataclass
class PlayerNewsCollection:
    """Collection of news items for a player"""
    player_name: str
    news_items: List[PlayerNews]
    last_updated: datetime
    
    @property
    def latest_injury_status(self) -> Optional[InjuryStatus]:
        """Get the most recent injury status"""
        injury_news = [news for news in self.news_items if news.is_injury_related]
        if not injury_news:
            return None
        
        # Sort by date and get most recent
        latest = sorted(injury_news, key=lambda x: x.published_date, reverse=True)[0]
        return latest.injury_status
    
    @property
    def top_headlines(self, limit: int = 3) -> List[PlayerNews]:
        """Get top headlines by relevance"""
        sorted_news = sorted(self.news_items, 
                           key=lambda x: x.fantasy_relevance_score, 
                           reverse=True)
        return sorted_news[:limit]
    
    @property
    def injury_summary(self) -> str:
        """Generate injury summary for the player"""
        injury_news = [news for news in self.news_items if news.is_injury_related]
        if not injury_news:
            return "No injury concerns"
        
        latest = sorted(injury_news, key=lambda x: x.published_date, reverse=True)[0]
        
        if latest.injury_status:
            status = latest.injury_status.value.replace('_', ' ').title()
            if latest.body_part:
                return f"{status} - {latest.body_part}"
            return status
        
        return "Injury status unclear"