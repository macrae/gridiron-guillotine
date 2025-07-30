"""
CLI commands for NFL news and player reports
"""

import click
import logging
from typing import Optional

from ..news import NewsAggregator
from ..core.config import get_config

logger = logging.getLogger(__name__)


@click.group()
def news_cli():
    """NFL news and player reports commands"""
    pass


@news_cli.command('player')
@click.argument('player_name')
@click.option('--limit', '-l', default=5, help='Number of news items per source')
@click.option('--days', '-d', default=14, help='Maximum age in days')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.pass_context
def get_player_news(ctx, player_name: str, limit: int, days: int, verbose: bool):
    """Get news for a specific player"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        click.echo(f"Fetching news for {player_name}...")
        
        aggregator = NewsAggregator()
        news_collection = aggregator.get_player_news(
            player_name=player_name,
            limit_per_source=limit,
            max_age_days=days
        )
        
        click.echo(f"\\n📰 NEWS FOR {player_name.upper()}")
        click.echo("=" * 60)
        
        if not news_collection.news_items:
            click.echo("No recent news found for this player.")
            return
        
        click.echo(f"Total news items: {len(news_collection.news_items)}")
        click.echo(f"Injury status: {news_collection.latest_injury_status.value if news_collection.latest_injury_status else 'Unknown'}")
        click.echo(f"Injury summary: {news_collection.injury_summary}")
        click.echo(f"Last updated: {news_collection.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        
        click.echo("\\n🏆 TOP HEADLINES:")
        click.echo("-" * 40)
        
        for i, news in enumerate(news_collection.top_headlines, 1):
            click.echo(f"\\n{i}. {news.headline}")
            click.echo(f"   📅 {news.published_date.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"   📰 {news.source.value.upper()} | {news.news_type.value.upper()}")
            click.echo(f"   🎯 Relevance: {news.fantasy_relevance_score:.1f}/10")
            
            if verbose and news.content:
                click.echo(f"   📝 {news.content[:200]}{'...' if len(news.content) > 200 else ''}")
            
            if news.injury_status:
                click.echo(f"   🏥 Status: {news.injury_status.value}")
        
        if verbose:
            click.echo("\\n📊 ALL NEWS ITEMS:")
            click.echo("-" * 40)
            
            for i, news in enumerate(news_collection.news_items, 1):
                click.echo(f"\\n{i:2d}. [{news.source.value.upper()}] {news.headline}")
                click.echo(f"     Date: {news.published_date.strftime('%Y-%m-%d %H:%M')}")
                click.echo(f"     Type: {news.news_type.value} | Score: {news.fantasy_relevance_score:.1f}")
                
                if news.url:
                    click.echo(f"     URL: {news.url}")
        
    except Exception as e:
        click.echo(f"Error fetching news: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


@news_cli.command('injuries')
@click.option('--team', '-t', help='Filter by team')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.pass_context  
def get_injury_reports(ctx, team: Optional[str], verbose: bool):
    """Get current NFL injury reports"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        click.echo("Fetching NFL injury reports...")
        
        aggregator = NewsAggregator()
        injury_reports = aggregator.get_injury_reports(team=team)
        
        click.echo(f"\\n🏥 NFL INJURY REPORTS")
        click.echo("=" * 60)
        
        if not injury_reports:
            click.echo("No injury reports found.")
            return
        
        click.echo(f"Total injury reports: {len(injury_reports)}")
        if team:
            click.echo(f"Filtered for team: {team.upper()}")
        
        click.echo("\\n📋 INJURY LIST:")
        click.echo("-" * 40)
        
        # Group by team
        team_injuries = {}
        for injury in injury_reports:
            team_name = injury.team or "Unknown"  
            if team_name not in team_injuries:
                team_injuries[team_name] = []
            team_injuries[team_name].append(injury)
        
        for team_name, injuries in sorted(team_injuries.items()):
            click.echo(f"\\n🏈 {team_name.upper()}:")
            
            for injury in sorted(injuries, key=lambda x: x.player_name):
                status = injury.injury_status.value if injury.injury_status else "unknown"
                body_part = f" ({injury.body_part})" if injury.body_part else ""
                
                click.echo(f"  • {injury.player_name} - {status.upper()}{body_part}")
                
                if verbose:
                    click.echo(f"    Headline: {injury.headline}")
                    click.echo(f"    Date: {injury.published_date.strftime('%Y-%m-%d %H:%M')}")
                    click.echo(f"    Source: {injury.source.value}")
                    if injury.content:
                        click.echo(f"    Details: {injury.content[:150]}{'...' if len(injury.content) > 150 else ''}")
        
    except Exception as e:
        click.echo(f"Error fetching injury reports: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


@news_cli.command('summary')
@click.argument('player_name')
@click.pass_context
def get_player_summary(ctx, player_name: str):
    """Get a comprehensive summary for a player"""
    try:
        click.echo(f"Generating summary for {player_name}...")
        
        aggregator = NewsAggregator()
        summary = aggregator.get_player_summary(player_name)
        
        click.echo(f"\\n📊 PLAYER SUMMARY: {summary['player_name'].upper()}")
        click.echo("=" * 60)
        
        click.echo(f"Total news items: {summary['total_news_items']}")
        click.echo(f"Latest injury status: {summary['latest_injury_status'].upper()}")
        click.echo(f"Injury summary: {summary['injury_summary']}")
        click.echo(f"Last updated: {summary['last_updated']}")
        
        if summary['top_headlines']:
            click.echo("\\n🏆 KEY HEADLINES:")
            click.echo("-" * 30)
            
            for i, headline in enumerate(summary['top_headlines'], 1):
                click.echo(f"\\n{i}. {headline['headline']}")
                click.echo(f"   📅 {headline['date']} | 📰 {headline['source'].upper()}")
                click.echo(f"   🏷️  {headline['type'].upper()} | 🎯 {headline['relevance_score']:.1f}/10")
        
    except Exception as e:
        click.echo(f"Error generating summary: {e}")


@news_cli.command('team')
@click.argument('team_code')
@click.option('--limit', '-l', default=5, help='Number of news items')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.pass_context
def get_team_news(ctx, team_code: str, limit: int, verbose: bool):
    """Get team-specific news (e.g., BAL, SF, KC)"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        from ..news.sources import RotoWireNewsSource
        
        click.echo(f"Fetching news for team {team_code.upper()}...")
        
        rotowire = RotoWireNewsSource()
        team_news = rotowire.fetch_team_news(team_code, limit=limit)
        
        click.echo(f"\\n🏈 {team_code.upper()} TEAM NEWS")
        click.echo("=" * 50)
        
        if not team_news:
            click.echo("No recent news found for this team.")
            return
        
        click.echo(f"Total news items: {len(team_news)}")
        
        click.echo("\\n📰 TEAM HEADLINES:")
        click.echo("-" * 30)
        
        for i, news in enumerate(team_news, 1):
            click.echo(f"\\n{i}. {news.headline}")
            click.echo(f"   📅 {news.published_date.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"   👤 {news.player_name}")
            click.echo(f"   🏷️  {news.news_type.value.upper()}")
            
            if verbose and news.content:
                click.echo(f"   📝 {news.content[:200]}{'...' if len(news.content) > 200 else ''}")
            
            if news.url:
                click.echo(f"   🔗 {news.url}")
        
    except Exception as e:
        click.echo(f"Error fetching team news: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


@news_cli.command('test')
@click.pass_context
def test_news_system(ctx):
    """Test the news system with sample players"""
    # First, let's get current news and test with players actually mentioned
    click.echo("🔍 Finding current NFL news to test with...")
    
    import requests
    try:
        url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news'
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Extract player names from current headlines
        current_players = []
        for article in data.get('articles', [])[:5]:
            headline = article.get('headline', '')
            # Simple name extraction - look for common patterns
            import re
            # Match patterns like "Name Name" in headlines
            names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', headline)
            for name in names:
                if name not in current_players and len(name.split()) == 2:
                    current_players.append(name)
        
        if current_players:
            click.echo(f"Found {len(current_players)} players in current news")
            test_players = current_players[:3]  # Test with first 3
        else:
            # Fallback to common players
            test_players = ["Zack Moss", "Isaiah Likely", "Stephen Jones"]
            
    except Exception:
        # Fallback players known to be in news
        test_players = ["Zack Moss", "Isaiah Likely", "Stephen Jones"]
    
    click.echo("🧪 Testing news system with sample players...")
    click.echo("=" * 50)
    
    aggregator = NewsAggregator()
    
    for player in test_players:
        try:
            click.echo(f"\\nTesting: {player}")
            summary = aggregator.get_player_summary(player)
            
            click.echo(f"  ✅ Found {summary['total_news_items']} news items")
            click.echo(f"  🏥 Status: {summary['latest_injury_status']}")
            
            if summary['top_headlines']:
                latest = summary['top_headlines'][0]
                click.echo(f"  📰 Latest: {latest['headline'][:50]}...")
            
        except Exception as e:
            click.echo(f"  ❌ Error: {e}")
    
    # Test cache stats
    stats = aggregator.get_cache_stats()
    click.echo(f"\\n📊 Cache Statistics:")
    click.echo(f"  Player cache size: {stats['player_cache_size']}")
    click.echo(f"  Injury cache size: {stats['injury_cache_size']}")
    click.echo(f"  Cache duration: {stats['cache_duration_hours']} hours")