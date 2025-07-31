"""
Enhanced player database with persistent storage for pre-computed scores, news, and LLM analysis
"""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum

from ..core.models import Player, Position
from ..core.config import get_config


class DraftStatus(str, Enum):
    """Player draft status"""
    AVAILABLE = "available"
    DRAFTED = "drafted"
    TARGETED = "targeted"  # User has marked as target
    AVOID = "avoid"  # User wants to avoid


class NewsImpact(str, Enum):
    """News impact on player value"""
    POSITIVE = "positive"
    NEGATIVE = "negative"  
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass
class PlayerNews:
    """Player news information"""
    headline: str
    content: str
    source: str
    published_date: datetime
    impact: NewsImpact = NewsImpact.UNKNOWN
    severity: Optional[float] = None  # 0-10 scale
    url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            'headline': self.headline,
            'content': self.content,
            'source': self.source,
            'published_date': self.published_date.isoformat(),
            'impact': self.impact.value,
            'severity': self.severity,
            'url': self.url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerNews':
        """Create from dictionary"""
        return cls(
            headline=data['headline'],
            content=data['content'],
            source=data['source'],
            published_date=datetime.fromisoformat(data['published_date']),
            impact=NewsImpact(data.get('impact', 'unknown')),
            severity=data.get('severity'),
            url=data.get('url')
        )


@dataclass
class LLMAnalysis:
    """LLM analysis results"""
    rating: float  # 1-5 scale
    confidence: float  # 0-1 scale
    reasoning: str
    model_used: str
    analysis_date: datetime
    prompt_version: str = "v1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            'rating': self.rating,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'model_used': self.model_used,
            'analysis_date': self.analysis_date.isoformat(),
            'prompt_version': self.prompt_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMAnalysis':
        """Create from dictionary"""
        return cls(
            rating=data['rating'],
            confidence=data['confidence'],
            reasoning=data['reasoning'],
            model_used=data['model_used'],
            analysis_date=datetime.fromisoformat(data['analysis_date']),
            prompt_version=data.get('prompt_version', 'v1.0')
        )


@dataclass
class EnhancedPlayer:
    """Enhanced player data with persistent scoring, news, and LLM analysis"""
    # Core player data (from existing Player model)
    name: str
    position: Position
    team: str
    projected_points: float
    vbd: float = 0.0
    tier: int = 1
    floor: Optional[float] = None
    ceiling: Optional[float] = None
    rookie: bool = False
    
    # Advanced metrics (from existing Player model)
    wopr: float = 0.0
    expected_points: float = 0.0
    context_multiplier: float = 1.0
    advanced_score: float = 0.0
    adjusted_value: float = 0.0
    target_share: float = 0.0
    air_yards_share: float = 0.0
    red_zone_targets: int = 0
    red_zone_carries: int = 0
    goal_line_carries: int = 0
    air_yards_per_target: float = 0.0
    
    # NEW: Persistent scoring data
    pre_computed_scores: Dict[int, float] = None  # Position -> adjusted score
    strategy_version: str = "v1.0"
    score_computed_date: Optional[datetime] = None
    
    # NEW: Draft management
    draft_status: DraftStatus = DraftStatus.AVAILABLE
    drafted_by: Optional[str] = None
    drafted_round: Optional[int] = None
    drafted_pick: Optional[int] = None
    user_notes: str = ""
    
    # NEW: News integration
    latest_news: List[PlayerNews] = None
    news_last_updated: Optional[datetime] = None
    overall_news_impact: NewsImpact = NewsImpact.NEUTRAL
    
    # NEW: LLM analysis
    llm_analysis: Optional[LLMAnalysis] = None
    
    # Metadata
    created_date: datetime = None
    last_updated: datetime = None
    
    def __post_init__(self):
        """Initialize defaults after creation"""
        if self.floor is None:
            self.floor = self.projected_points * 0.8
        if self.ceiling is None:
            self.ceiling = self.projected_points * 1.2
        if self.pre_computed_scores is None:
            self.pre_computed_scores = {}
        if self.latest_news is None:
            self.latest_news = []
        if self.created_date is None:
            self.created_date = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def to_player(self) -> Player:
        """Convert to original Player model for compatibility"""
        return Player(
            name=self.name,
            position=self.position,
            team=self.team,
            projected_points=self.projected_points,
            vbd=self.vbd,
            tier=self.tier,
            floor=self.floor,
            ceiling=self.ceiling,
            rookie=self.rookie,
            wopr=self.wopr,
            expected_points=self.expected_points,
            context_multiplier=self.context_multiplier,
            advanced_score=self.advanced_score,
            adjusted_value=self.adjusted_value,
            target_share=self.target_share,
            air_yards_share=self.air_yards_share,
            red_zone_targets=self.red_zone_targets,
            red_zone_carries=self.red_zone_carries,
            goal_line_carries=self.goal_line_carries,
            air_yards_per_target=self.air_yards_per_target
        )
    
    @classmethod
    def from_player(cls, player: Player) -> 'EnhancedPlayer':
        """Create from existing Player model"""
        return cls(
            name=player.name,
            position=player.position,
            team=player.team,
            projected_points=player.projected_points,
            vbd=player.vbd,
            tier=player.tier,
            floor=player.floor,
            ceiling=player.ceiling,
            rookie=player.rookie,
            wopr=player.wopr,
            expected_points=player.expected_points,
            context_multiplier=player.context_multiplier,
            advanced_score=player.advanced_score,
            adjusted_value=player.adjusted_value,
            target_share=player.target_share,
            air_yards_share=player.air_yards_share,
            red_zone_targets=player.red_zone_targets,
            red_zone_carries=player.red_zone_carries,
            goal_line_carries=player.goal_line_carries,
            air_yards_per_target=player.air_yards_per_target
        )
    
    def get_position_score(self, draft_position: int) -> float:
        """Get pre-computed score for a specific draft position"""
        return self.pre_computed_scores.get(draft_position, self.adjusted_value)
    
    def update_news(self, news_items: List[PlayerNews]) -> None:
        """Update player news and recalculate impact"""
        self.latest_news = news_items[-10:]  # Keep last 10 news items
        self.news_last_updated = datetime.now()
        self.last_updated = datetime.now()
        
        # Calculate overall news impact
        if not news_items:
            self.overall_news_impact = NewsImpact.NEUTRAL
        else:
            positive_count = sum(1 for n in news_items if n.impact == NewsImpact.POSITIVE)
            negative_count = sum(1 for n in news_items if n.impact == NewsImpact.NEGATIVE)
            
            if positive_count > negative_count:
                self.overall_news_impact = NewsImpact.POSITIVE
            elif negative_count > positive_count:
                self.overall_news_impact = NewsImpact.NEGATIVE
            else:
                self.overall_news_impact = NewsImpact.NEUTRAL
    
    def mark_drafted(self, team_name: str, round_num: int, pick_num: int) -> None:
        """Mark player as drafted"""
        self.draft_status = DraftStatus.DRAFTED
        self.drafted_by = team_name
        self.drafted_round = round_num
        self.drafted_pick = pick_num
        self.last_updated = datetime.now()
    
    def is_available(self) -> bool:
        """Check if player is still available for draft"""
        return self.draft_status == DraftStatus.AVAILABLE


class PlayerDatabase:
    """Enhanced player database with persistent storage"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database"""
        if db_path is None:
            config = get_config()
            db_path = config.data_dir / "enhanced_players.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    name TEXT PRIMARY KEY,
                    position TEXT NOT NULL,
                    team TEXT,
                    projected_points REAL NOT NULL,
                    vbd REAL DEFAULT 0.0,
                    tier INTEGER DEFAULT 1,
                    floor REAL,
                    ceiling REAL,
                    rookie BOOLEAN DEFAULT FALSE,
                    
                    -- Advanced metrics
                    wopr REAL DEFAULT 0.0,
                    expected_points REAL DEFAULT 0.0,
                    context_multiplier REAL DEFAULT 1.0,
                    advanced_score REAL DEFAULT 0.0,
                    adjusted_value REAL DEFAULT 0.0,
                    target_share REAL DEFAULT 0.0,
                    air_yards_share REAL DEFAULT 0.0,
                    red_zone_targets INTEGER DEFAULT 0,
                    red_zone_carries INTEGER DEFAULT 0,
                    goal_line_carries INTEGER DEFAULT 0,
                    air_yards_per_target REAL DEFAULT 0.0,
                    
                    -- Persistent scoring
                    pre_computed_scores TEXT,  -- JSON
                    strategy_version TEXT DEFAULT 'v1.0',
                    score_computed_date TEXT,
                    
                    -- Draft management
                    draft_status TEXT DEFAULT 'available',
                    drafted_by TEXT,
                    drafted_round INTEGER,
                    drafted_pick INTEGER,
                    user_notes TEXT DEFAULT '',
                    
                    -- News integration
                    latest_news TEXT,  -- JSON
                    news_last_updated TEXT,
                    overall_news_impact TEXT DEFAULT 'neutral',
                    
                    -- LLM analysis
                    llm_analysis TEXT,  -- JSON
                    
                    -- Metadata
                    created_date TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Create indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_position ON players(position)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_draft_status ON players(draft_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vbd ON players(vbd DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_adjusted_value ON players(adjusted_value DESC)")
    
    def upsert_player(self, player: EnhancedPlayer) -> None:
        """Insert or update player in database"""
        player.last_updated = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            # Convert complex fields to JSON
            pre_computed_scores_json = json.dumps(player.pre_computed_scores) if player.pre_computed_scores else "{}"
            latest_news_json = json.dumps([n.to_dict() for n in player.latest_news]) if player.latest_news else "[]"
            llm_analysis_json = json.dumps(player.llm_analysis.to_dict()) if player.llm_analysis else None
            
            conn.execute("""
                INSERT OR REPLACE INTO players VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                player.name, player.position.value, player.team, player.projected_points,
                player.vbd, player.tier, player.floor, player.ceiling, player.rookie,
                player.wopr, player.expected_points, player.context_multiplier,
                player.advanced_score, player.adjusted_value, player.target_share,
                player.air_yards_share, player.red_zone_targets, player.red_zone_carries,
                player.goal_line_carries, player.air_yards_per_target,
                pre_computed_scores_json, player.strategy_version,
                player.score_computed_date.isoformat() if player.score_computed_date else None,
                player.draft_status.value, player.drafted_by, player.drafted_round,
                player.drafted_pick, player.user_notes,
                latest_news_json, 
                player.news_last_updated.isoformat() if player.news_last_updated else None,
                player.overall_news_impact.value,
                llm_analysis_json,
                player.created_date.isoformat(), player.last_updated.isoformat()
            ))
    
    def get_player(self, name: str) -> Optional[EnhancedPlayer]:
        """Get player by name"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM players WHERE name = ?", (name,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_player(row)
    
    def get_available_players(self, position: Optional[Position] = None) -> List[EnhancedPlayer]:
        """Get all available players, optionally filtered by position"""
        query = "SELECT * FROM players WHERE draft_status = 'available'"
        params = []
        
        if position:
            query += " AND position = ?"
            params.append(position.value)
        
        query += " ORDER BY adjusted_value DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_player(row) for row in cursor.fetchall()]
    
    def get_top_players(self, limit: int = 100, position: Optional[Position] = None) -> List[EnhancedPlayer]:
        """Get top players by adjusted value"""
        query = "SELECT * FROM players WHERE draft_status = 'available'"
        params = []
        
        if position:
            query += " AND position = ?"
            params.append(position.value)
        
        query += " ORDER BY adjusted_value DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_player(row) for row in cursor.fetchall()]
    
    def mark_player_drafted(self, name: str, team_name: str, round_num: int, pick_num: int) -> bool:
        """Mark a player as drafted"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE players 
                SET draft_status = 'drafted', drafted_by = ?, drafted_round = ?, 
                    drafted_pick = ?, last_updated = ?
                WHERE name = ?
            """, (team_name, round_num, pick_num, datetime.now().isoformat(), name))
            
            return cursor.rowcount > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total players
            stats['total_players'] = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            
            # Available players
            stats['available_players'] = conn.execute(
                "SELECT COUNT(*) FROM players WHERE draft_status = 'available'"
            ).fetchone()[0]
            
            # Drafted players
            stats['drafted_players'] = conn.execute(
                "SELECT COUNT(*) FROM players WHERE draft_status = 'drafted'"
            ).fetchone()[0]
            
            # By position
            cursor = conn.execute("""
                SELECT position, COUNT(*) as count 
                FROM players WHERE draft_status = 'available'
                GROUP BY position 
                ORDER BY count DESC
            """)
            stats['available_by_position'] = dict(cursor.fetchall())
            
            # With LLM analysis
            stats['with_llm_analysis'] = conn.execute(
                "SELECT COUNT(*) FROM players WHERE llm_analysis IS NOT NULL"
            ).fetchone()[0]
            
            # With recent news
            stats['with_recent_news'] = conn.execute(
                "SELECT COUNT(*) FROM players WHERE news_last_updated IS NOT NULL"
            ).fetchone()[0]
            
            return stats
    
    def _row_to_player(self, row: sqlite3.Row) -> EnhancedPlayer:
        """Convert database row to EnhancedPlayer"""
        # Parse JSON fields
        pre_computed_scores = json.loads(row['pre_computed_scores']) if row['pre_computed_scores'] else {}
        latest_news = [PlayerNews.from_dict(n) for n in json.loads(row['latest_news'])] if row['latest_news'] else []
        llm_analysis = LLMAnalysis.from_dict(json.loads(row['llm_analysis'])) if row['llm_analysis'] else None
        
        return EnhancedPlayer(
            name=row['name'],
            position=Position(row['position']),
            team=row['team'] or '',
            projected_points=row['projected_points'],
            vbd=row['vbd'],
            tier=row['tier'],
            floor=row['floor'],
            ceiling=row['ceiling'],
            rookie=bool(row['rookie']),
            wopr=row['wopr'],
            expected_points=row['expected_points'],
            context_multiplier=row['context_multiplier'],
            advanced_score=row['advanced_score'],
            adjusted_value=row['adjusted_value'],
            target_share=row['target_share'],
            air_yards_share=row['air_yards_share'],
            red_zone_targets=row['red_zone_targets'],
            red_zone_carries=row['red_zone_carries'],
            goal_line_carries=row['goal_line_carries'],
            air_yards_per_target=row['air_yards_per_target'],
            pre_computed_scores=pre_computed_scores,
            strategy_version=row['strategy_version'],
            score_computed_date=datetime.fromisoformat(row['score_computed_date']) if row['score_computed_date'] else None,
            draft_status=DraftStatus(row['draft_status']),
            drafted_by=row['drafted_by'],
            drafted_round=row['drafted_round'],
            drafted_pick=row['drafted_pick'],
            user_notes=row['user_notes'] or '',
            latest_news=latest_news,
            news_last_updated=datetime.fromisoformat(row['news_last_updated']) if row['news_last_updated'] else None,
            overall_news_impact=NewsImpact(row['overall_news_impact']),
            llm_analysis=llm_analysis,
            created_date=datetime.fromisoformat(row['created_date']),
            last_updated=datetime.fromisoformat(row['last_updated'])
        )