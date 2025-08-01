"""
Database management CLI commands
"""

import click
import json
from typing import List, Optional

from ..data.database import PlayerDatabase, DraftStatus
from ..data.precompute import PlayerPrecomputer
from ..data.news_integration import NewsIntegrationEngine
from ..core.models import Position


@click.group()
def database_cli():
    """Database management commands"""
    pass


@database_cli.command()
@click.option('--positions', '-p', multiple=True, type=int, help='Draft positions to compute (1-12)')
@click.option('--force', '-f', is_flag=True, help='Force recomputation of existing scores')
@click.option('--player', type=str, help='Compute scores for specific player only')
@click.pass_context
def precompute(ctx, positions: tuple, force: bool, player: Optional[str]):
    """Pre-compute player scores for all draft positions"""
    
    if not positions:
        positions = list(range(1, 13))  # Default to all positions
    else:
        positions = list(positions)
    
    # Validate positions
    invalid_positions = [p for p in positions if not (1 <= p <= 12)]
    if invalid_positions:
        click.echo(f"Error: Invalid draft positions: {invalid_positions}")
        return
    
    click.echo(f"🔄 Pre-computing player scores...")
    click.echo(f"   Positions: {positions}")
    click.echo(f"   Force recompute: {force}")
    
    if player:
        click.echo(f"   Single player: {player}")
    
    try:
        precomputer = PlayerPrecomputer()
        
        if player:
            # Compute single player
            success = precomputer.recompute_player(player, positions)
            if success:
                click.echo(f"✅ Successfully computed scores for {player}")
            else:
                click.echo(f"❌ Failed to compute scores for {player}")
        else:
            # Compute all players
            with click.progressbar(length=100, label='Computing scores') as bar:
                results = precomputer.precompute_all_players(positions, force)
                bar.update(100)
            
            click.echo(f"\\n✅ Pre-computation complete!")
            click.echo(f"   Players updated: {results['players_updated']}")
            click.echo(f"   Players skipped: {results['players_skipped']}")
            click.echo(f"   Errors: {len(results['errors'])}")
            click.echo(f"   Time: {results['computation_time']:.1f} seconds")
            
            if results['errors'] and ctx.obj.get('verbose'):
                click.echo("\\nErrors:")
                for error in results['errors'][:5]:  # Show first 5 errors
                    click.echo(f"   - {error}")
    
    except Exception as e:
        click.echo(f"❌ Error during pre-computation: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@database_cli.command()
@click.option('--position', type=click.Choice(['QB', 'RB', 'WR', 'TE', 'K', 'DEF']), help='Filter by position')
@click.option('--limit', '-n', type=int, default=50, help='Number of players to show (default: 50)')
@click.option('--available-only', is_flag=True, help='Show only available players')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table', help='Output format')
def players(position: Optional[str], limit: int, available_only: bool, output_format: str):
    """List players in database"""
    
    try:
        db = PlayerDatabase()
        
        # Get players
        if available_only:
            if position:
                players = db.get_available_players(Position(position))
            else:
                players = db.get_available_players()
        else:
            if position:
                players = db.get_top_players(limit * 2, Position(position))  # Get more then filter
            else:
                players = db.get_top_players(limit * 2)
        
        # Limit results
        players = players[:limit]
        
        if not players:
            click.echo("No players found.")
            return
        
        if output_format == 'json':
            # JSON output
            player_data = []
            for p in players:
                player_data.append({
                    'name': p.name,
                    'position': p.position.value,
                    'team': p.team,
                    'projected_points': p.projected_points,
                    'vbd': p.vbd,
                    'adjusted_value': p.adjusted_value,
                    'draft_status': p.draft_status.value,
                    'drafted_by': p.drafted_by,
                    'llm_rating': p.llm_analysis.rating if p.llm_analysis else None
                })
            click.echo(json.dumps(player_data, indent=2))
        
        else:
            # Table output
            status_str = "Available" if available_only else "All"
            pos_str = f" {position}" if position else ""
            click.echo(f"\\n🏈 Top {len(players)}{pos_str} Players ({status_str})")
            click.echo("=" * 80)
            
            # Header
            click.echo(f"{'#':<3} {'Name':<22} {'Pos':<4} {'Team':<6} {'Proj':<6} {'VBD':<6} {'AdjVal':<7} {'Status':<8} {'LLM':<4}")
            click.echo("-" * 80)
            
            for i, player in enumerate(players, 1):
                status = "DRAFT" if player.draft_status == DraftStatus.DRAFTED else "AVAIL"
                llm_rating = f"{player.llm_analysis.rating:.1f}" if player.llm_analysis else "---"
                
                click.echo(f"{i:<3} {player.name[:21]:<22} {player.position.value:<4} "
                          f"{player.team[:5]:<6} {player.projected_points:<6.1f} "
                          f"{player.vbd:<6.1f} {player.adjusted_value:<7.1f} "
                          f"{status:<8} {llm_rating:<4}")
    
    except Exception as e:
        click.echo(f"❌ Error listing players: {e}")


@database_cli.command()
def stats():
    """Show database statistics"""
    
    try:
        db = PlayerDatabase()
        stats = db.get_stats()
        
        click.echo("\\n📊 Database Statistics")
        click.echo("=" * 40)
        click.echo(f"Total players: {stats['total_players']}")
        click.echo(f"Available players: {stats['available_players']}")
        click.echo(f"Drafted players: {stats['drafted_players']}")
        click.echo(f"With LLM analysis: {stats['with_llm_analysis']}")
        click.echo(f"With recent news: {stats['with_recent_news']}")
        
        click.echo("\\n📍 Available by Position:")
        for pos, count in stats['available_by_position'].items():
            click.echo(f"   {pos}: {count}")
    
    except Exception as e:
        click.echo(f"❌ Error getting stats: {e}")


@database_cli.command()
@click.argument('player_name')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table', help='Output format')
def player(player_name: str, output_format: str):
    """Show detailed information for a specific player"""
    
    try:
        db = PlayerDatabase()
        player = db.get_player(player_name)
        
        if not player:
            click.echo(f"❌ Player '{player_name}' not found in database")
            return
        
        if output_format == 'json':
            # JSON output with all details
            player_data = {
                'name': player.name,
                'position': player.position.value,
                'team': player.team,
                'projected_points': player.projected_points,
                'vbd': player.vbd,
                'tier': player.tier,
                'floor': player.floor,
                'ceiling': player.ceiling,
                'rookie': player.rookie,
                'adjusted_value': player.adjusted_value,
                'pre_computed_scores': player.pre_computed_scores,
                'draft_status': player.draft_status.value,
                'drafted_by': player.drafted_by,
                'drafted_round': player.drafted_round,
                'drafted_pick': player.drafted_pick,
                'user_notes': player.user_notes,
                'latest_news': [n.to_dict() for n in player.latest_news],
                'overall_news_impact': player.overall_news_impact.value,
                'llm_analysis': player.llm_analysis.to_dict() if player.llm_analysis else None,
                'last_updated': player.last_updated.isoformat()
            }
            click.echo(json.dumps(player_data, indent=2))
        
        else:
            # Table output
            click.echo(f"\\n🏈 {player.name}")
            click.echo("=" * 50)
            click.echo(f"Position: {player.position.value}")
            click.echo(f"Team: {player.team}")
            click.echo(f"Projected Points: {player.projected_points:.1f}")
            click.echo(f"VBD: {player.vbd:.1f}")
            click.echo(f"Adjusted Value: {player.adjusted_value:.1f}")
            click.echo(f"Floor/Ceiling: {player.floor:.1f} / {player.ceiling:.1f}")
            click.echo(f"Rookie: {'Yes' if player.rookie else 'No'}")
            
            # Draft status
            click.echo(f"\\n📋 Draft Status: {player.draft_status.value.title()}")
            if player.draft_status == DraftStatus.DRAFTED:
                click.echo(f"   Drafted by: {player.drafted_by}")
                click.echo(f"   Round {player.drafted_round}, Pick {player.drafted_pick}")
            
            # Pre-computed scores
            if player.pre_computed_scores:
                click.echo(f"\\n🎯 Position Scores:")
                for pos, score in sorted(player.pre_computed_scores.items()):
                    click.echo(f"   Position {pos}: {score:.1f}")
            
            # LLM Analysis
            if player.llm_analysis:
                click.echo(f"\\n🤖 LLM Analysis:")
                click.echo(f"   Rating: {player.llm_analysis.rating:.1f}/5.0")
                click.echo(f"   Confidence: {player.llm_analysis.confidence:.1f}")
                click.echo(f"   Model: {player.llm_analysis.model_used}")
                click.echo(f"   Reasoning: {player.llm_analysis.reasoning}")
            
            # News
            if player.latest_news:
                click.echo(f"\\n📰 Latest News ({len(player.latest_news)} items):")
                for i, news in enumerate(player.latest_news[:3], 1):  # Show top 3
                    impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➖", "unknown": "❓"}
                    icon = impact_icon.get(news.impact.value, "❓")
                    click.echo(f"   {i}. {icon} {news.headline} ({news.source})")
            
            if player.user_notes:
                click.echo(f"\\n📝 Notes: {player.user_notes}")
            
            click.echo(f"\\n🕒 Last Updated: {player.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    
    except Exception as e:
        click.echo(f"❌ Error getting player details: {e}")


@database_cli.command()
@click.argument('player_name')
@click.argument('team_name')
@click.argument('round_num', type=int)
@click.argument('pick_num', type=int)
def draft(player_name: str, team_name: str, round_num: int, pick_num: int):
    """Mark a player as drafted"""
    
    try:
        db = PlayerDatabase()
        success = db.mark_player_drafted(player_name, team_name, round_num, pick_num)
        
        if success:
            click.echo(f"✅ Marked {player_name} as drafted by {team_name} (R{round_num}, P{pick_num})")
        else:
            click.echo(f"❌ Player '{player_name}' not found or already drafted")
    
    except Exception as e:
        click.echo(f"❌ Error marking player as drafted: {e}")


@database_cli.command()
@click.option('--position', type=click.Choice(['QB', 'RB', 'WR', 'TE', 'K', 'DEF']), help='Filter by position')
@click.option('--draft-position', '-p', type=int, help='Your draft position (1-12)')
@click.option('--current-round', '-r', type=int, default=1, help='Current draft round')
@click.option('--user-picks', type=str, help='Comma-separated list of players you have drafted')
@click.option('--limit', '-n', type=int, default=20, help='Number of recommendations')
@click.option('--no-strategy', is_flag=True, help='Disable Hero-RB strategy (use raw scores)')
def recommend(position: Optional[str], draft_position: Optional[int], current_round: int, 
             user_picks: Optional[str], limit: int, no_strategy: bool):
    """Get draft recommendations from database (uses Hero-RB strategy by default)"""
    
    try:
        db = PlayerDatabase()
        
        # Use Hero-RB strategy by default when draft position is provided (unless disabled)
        use_strategy = draft_position is not None and not no_strategy
        
        if use_strategy:
            # Use Hero-RB strategy logic
            recommendations = _get_strategic_recommendations(
                db, draft_position, current_round, user_picks, position, limit
            )
        else:
            # Simple filtering and sorting
            recommendations = _get_basic_recommendations(
                db, position, draft_position, limit
            )
        
        if not recommendations:
            click.echo("No available players found.")
            return
        
        # Display recommendations
        _display_recommendations(recommendations, position, draft_position, use_strategy)
    
    except Exception as e:
        click.echo(f"❌ Error getting recommendations: {e}")


def _get_strategic_recommendations(db, draft_position, current_round, user_picks, position_filter, limit):
    """Get recommendations using Hero-RB strategy logic with original data format"""
    from ..core.strategy import ChampionshipDraftStrategy
    from ..core.models import LeagueSettings
    from ..core.config import get_config
    from ..data.loaders import PlayerDataLoader
    
    # Parse user picks
    user_pick_names = []
    if user_picks:
        user_pick_names = [name.strip() for name in user_picks.split(',')]
    
    # Load original data format (same as CLI strategy command)
    loader = PlayerDataLoader()
    df = loader.load_scored_data(include_rookies=True)
    
    # Filter to fantasy-relevant positions
    fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
    df = df[df['position'].isin(fantasy_positions)]
    
    # Remove drafted players by querying database directly
    # Use SQL to efficiently get drafted player names
    import sqlite3
    drafted_names = set()
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.execute("SELECT name FROM players WHERE draft_status = 'drafted'")
        drafted_names = {row[0] for row in cursor.fetchall()}
    
    if drafted_names:
        click.echo(f"🚫 Excluding {len(drafted_names)} drafted players: {', '.join(list(drafted_names)[:3])}{'...' if len(drafted_names) > 3 else ''}")
        df = df[~df['name'].isin(drafted_names)]
    
    # Remove user picks from this round
    if user_pick_names:
        df = df[~df['name'].isin(user_pick_names)]
    
    if len(df) == 0:
        return []
    
    # Initialize strategy
    config = get_config()
    league_settings = LeagueSettings()
    strategy = ChampionshipDraftStrategy(draft_position, league_settings, config)
    
    # Get strategic recommendations for this round
    try:
        round_recs = strategy.get_round_strategy(
            df, 
            current_round=current_round, 
            top_n=limit * 2  # Get more then filter
        )
        
        # Convert to EnhancedPlayer objects (or create simple ones)
        strategic_players = []
        for _, row in round_recs.iterrows():
            # Try to get from database first
            player = db.get_player(row['name'])
            if player and player.is_available():
                strategic_players.append(player)
            else:
                # Create a temporary enhanced player from the strategy result
                from ..data.database import EnhancedPlayer
                from ..core.models import Position
                
                try:
                    position = Position(row['position'])
                except ValueError:
                    position = Position.UNKNOWN
                
                temp_player = EnhancedPlayer(
                    name=row['name'],
                    position=position,
                    team=row.get('team', ''),
                    projected_points=row.get('projected_points', 0.0),
                    vbd=row.get('vbd', 0.0),
                    adjusted_value=row.get('adjusted_value', 0.0),
                    floor=row.get('floor', 0.0),
                    ceiling=row.get('ceiling', 0.0),
                    tier=row.get('tier', 1),
                    rookie=row.get('rookie', False)
                )
                strategic_players.append(temp_player)
        
        # Apply position filter if specified
        if position_filter:
            strategic_players = [p for p in strategic_players if p.position.value == position_filter]
        
        return strategic_players[:limit]
        
    except Exception as e:
        click.echo(f"⚠️  Strategy engine error: {e}, falling back to basic recommendations")
        import traceback
        traceback.print_exc()
        return _get_basic_recommendations(db, position_filter, draft_position, limit)


def _get_basic_recommendations(db, position_filter, draft_position, limit):
    """Get basic recommendations without strategy logic"""
    # Get available players
    if position_filter:
        players = db.get_available_players(Position(position_filter))
    else:
        players = db.get_available_players()
    
    if not players:
        return []
    
    # Sort by appropriate score
    if draft_position:
        players.sort(key=lambda p: p.get_position_score(draft_position), reverse=True)
    else:
        players.sort(key=lambda p: p.adjusted_value, reverse=True)
    
    return players[:limit]


def _display_recommendations(players, position_filter, draft_position, strategy_used):
    """Display recommendations in formatted table"""
    if strategy_used and draft_position:
        title_suffix = f" (Hero-RB Strategy - Position {draft_position})"
        score_title = "Strategic Score"
    elif draft_position:
        title_suffix = f" for Draft Position {draft_position}"
        score_title = f"Position {draft_position} Score"
    else:
        title_suffix = ""
        score_title = "Adjusted Value"
    
    pos_str = f" {position_filter}" if position_filter else ""
    
    click.echo(f"\\n🎯 Top {len(players)}{pos_str} Recommendations{title_suffix}")
    click.echo("=" * 80)
    
    # Header
    click.echo(f"{'#':<3} {'Name':<22} {'Pos':<4} {'Team':<6} {score_title:<14} {'LLM':<4} {'News':<4}")
    click.echo("-" * 80)
    
    for i, player in enumerate(players, 1):
        if draft_position and not strategy_used:
            score = player.get_position_score(draft_position)
        else:
            score = player.adjusted_value
        
        llm_rating = f"{player.llm_analysis.rating:.1f}" if player.llm_analysis else "---"
        news_icon = {"positive": "📈", "negative": "📉", "neutral": "➖"}.get(player.overall_news_impact.value, "❓")
        
        click.echo(f"{i:<3} {player.name[:21]:<22} {player.position.value:<4} "
                  f"{player.team[:5]:<6} {score:<14.1f} {llm_rating:<4} {news_icon:<4}")


@database_cli.command()
@click.confirmation_option(prompt='Are you sure you want to clear all draft picks? This cannot be undone.')
def reset_draft():
    """Reset all players to available status (clear all draft picks)"""
    
    try:
        db = PlayerDatabase()
        
        # This would require a custom method in PlayerDatabase
        # For now, we'll implement it directly with SQL
        import sqlite3
        from datetime import datetime
        
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute("""
                UPDATE players 
                SET draft_status = 'available', 
                    drafted_by = NULL, 
                    drafted_round = NULL, 
                    drafted_pick = NULL,
                    last_updated = ?
                WHERE draft_status = 'drafted'
            """, (datetime.now().isoformat(),))
            
            players_reset = cursor.rowcount
        
        click.echo(f"✅ Reset {players_reset} players to available status")
    
    except Exception as e:
        click.echo(f"❌ Error resetting draft: {e}")


# News Integration Commands
@database_cli.group()
def news():
    """NFL news integration commands"""
    pass


@news.command()
@click.argument('player_name')
@click.option('--limit', '-n', type=int, default=10, help='Number of news items to fetch')
def update_player(player_name: str, limit: int):
    """Update news for a specific player"""
    
    try:
        engine = NewsIntegrationEngine()
        
        click.echo(f"🔄 Updating news for {player_name}...")
        success = engine.update_player_news(player_name, limit=limit)
        
        if success:
            click.echo(f"✅ Successfully updated news for {player_name}")
            
            # Show updated player info
            db = PlayerDatabase()
            player = db.get_player(player_name)
            if player and player.latest_news:
                click.echo(f"\n📰 Latest news ({len(player.latest_news)} items):")
                for i, news in enumerate(player.latest_news[:3], 1):
                    impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➖"}.get(news.impact.value, "❓")
                    click.echo(f"  {i}. {impact_icon} {news.headline}")
                    click.echo(f"     {news.source} - {news.published_date.strftime('%Y-%m-%d')}")
        else:
            click.echo(f"❌ Failed to update news for {player_name}")
    
    except Exception as e:
        click.echo(f"❌ Error updating player news: {e}")


@news.command()
@click.option('--limit', '-n', type=int, default=50, help='Number of players to update')
@click.option('--workers', type=int, default=5, help='Concurrent update threads')
@click.option('--news-per-player', type=int, default=5, help='News items per player')
def bulk_update(limit: int, workers: int, news_per_player: int):
    """Update news for top fantasy players"""
    
    try:
        engine = NewsIntegrationEngine()
        
        click.echo(f"🔄 Starting bulk news update for top {limit} players...")
        click.echo(f"   Using {workers} workers, {news_per_player} news items per player")
        
        with click.progressbar(length=100, label='Updating news') as bar:
            results = engine.bulk_update_news(
                max_players=limit,
                max_workers=workers,
                limit_per_player=news_per_player
            )
            bar.update(100)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        click.echo(f"\n✅ Bulk update complete!")
        click.echo(f"   Successful: {successful}")
        click.echo(f"   Failed: {failed}")
        
        if failed > 0:
            failed_players = [name for name, success in results.items() if not success]
            click.echo(f"   Failed players: {', '.join(failed_players[:5])}{'...' if len(failed_players) > 5 else ''}")
    
    except Exception as e:
        click.echo(f"❌ Error during bulk update: {e}")


@news.command()
def injuries():
    """Update injury reports for all players"""
    
    try:
        engine = NewsIntegrationEngine()
        
        click.echo("🏥 Updating injury reports...")
        updated_players = engine.update_injury_reports()
        
        click.echo(f"✅ Updated injury information for {len(updated_players)} players")
        
        if updated_players:
            click.echo("\n🏥 Players with injury updates:")
            for player in updated_players[:10]:  # Show first 10
                impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➖"}.get(player.overall_news_impact.value, "❓")
                click.echo(f"   {impact_icon} {player.name} ({player.position.value}) - {player.team}")
    
    except Exception as e:
        click.echo(f"❌ Error updating injury reports: {e}")


@news.command()
@click.option('--days', type=int, default=7, help='Days to look back')
def summary(days: int):
    """Show news activity summary"""
    
    try:
        engine = NewsIntegrationEngine()
        stats = engine.get_news_summary(days_back=days)
        
        if not stats:
            click.echo("❌ No news data available")
            return
        
        click.echo(f"\n📊 News Summary (last {days} days)")
        click.echo("=" * 40)
        click.echo(f"Total players with news: {stats.get('total_players_with_news', 0)}")
        click.echo(f"Positive news: {stats.get('players_with_positive_news', 0)} players")
        click.echo(f"Negative news: {stats.get('players_with_negative_news', 0)} players")
        click.echo(f"Neutral news: {stats.get('players_with_neutral_news', 0)} players")
        
        if stats.get('most_recent_update'):
            click.echo(f"Most recent update: {stats['most_recent_update'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    except Exception as e:
        click.echo(f"❌ Error getting news summary: {e}")


@news.command()
@click.option('--days', type=int, default=30, help='Days of news to keep')
@click.confirmation_option(prompt='This will delete old news items. Continue?')
def cleanup(days: int):
    """Clean up old news items"""
    
    try:
        engine = NewsIntegrationEngine()
        
        click.echo(f"🧹 Cleaning up news older than {days} days...")
        updated_count = engine.cleanup_old_news(days_to_keep=days)
        
        click.echo(f"✅ Cleaned up old news for {updated_count} players")
    
    except Exception as e:
        click.echo(f"❌ Error cleaning up news: {e}")


@database_cli.command()
@click.option('--force', '-f', is_flag=True, help='Force regeneration of weighted projections')
def update_weighted(force: bool):
    """Update database with weighted multi-year projections"""
    from ..core.config import get_config
    
    try:
        click.echo("🔄 Updating database with weighted multi-year projections...")
        
        from ..data.weighted_calculator import run_weighted_calculation
        from ..data.database import PlayerDatabase
        import pandas as pd
        from pathlib import Path
        
        # Run weighted calculation
        if force:
            click.echo("   Recalculating weighted projections...")
            success = run_weighted_calculation()
            if not success:
                click.echo("❌ Failed to generate weighted projections")
                return
        
        # Load weighted projections
        config = get_config()
        weighted_file = config.data_dir / "weighted_projections_2026.csv"
        
        if not weighted_file.exists():
            click.echo("   No weighted projections found, generating...")
            success = run_weighted_calculation()
            if not success:
                click.echo("❌ Failed to generate weighted projections")
                return
        
        # Load projections
        projections = pd.read_csv(weighted_file)
        click.echo(f"   Loaded {len(projections)} weighted projections")
        
        # Update database by regenerating with precomputed scores
        click.echo("   Updating database with new scores...")
        
        # Use precompute to recalculate with updated data
        precomputer = PlayerPrecomputer()
        results = precomputer.precompute_all_players([1, 6, 12], force_recompute=True)
        
        click.echo(f"✅ Updated database with weighted projections")
        click.echo(f"   Players updated: {results['players_updated']}")
        click.echo(f"   Players skipped: {results['players_skipped']}")
        
        # Show sample results
        db = PlayerDatabase()
        top_players = db.get_top_players(limit=5)
        if top_players:
            click.echo("\n🏆 Top 5 Players (Updated Projections):")
            click.echo("-" * 50)
            for i, player in enumerate(top_players, 1):
                click.echo(f"{i}. {player.name} ({player.position.value}) - {player.adjusted_value:.1f} score")
        
    except Exception as e:
        click.echo(f"❌ Error updating weighted projections: {e}")


if __name__ == '__main__':
    database_cli()