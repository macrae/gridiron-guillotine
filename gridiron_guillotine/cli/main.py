"""
Main CLI entry point for Gridiron Guillotine
"""

import click
import logging
from pathlib import Path

from ..core.config import get_config
from .draft import draft_cli
from .data import data_cli
from .news import news_cli
from .database import database_cli


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config-dir', type=click.Path(exists=True), help='Configuration directory')
@click.pass_context
def main(ctx, verbose: bool, config_dir: str):
    """
    Gridiron Guillotine: Championship Fantasy Football Draft Strategy
    
    Research-validated Hero-RB strategy with advanced metrics and live draft monitoring.
    """
    setup_logging(verbose)
    
    # Store config in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = get_config()
    
    if config_dir:
        ctx.obj['config'].data_dir = Path(config_dir)


@main.command()
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--teams', '-t', type=int, default=12, help='Number of teams in league')
@click.option('--rounds', '-r', type=int, default=15, help='Number of draft rounds')
@click.option('--ppr', is_flag=True, default=True, help='PPR scoring (default: True)')
@click.pass_context
def strategy(ctx, position: int, teams: int, rounds: int, ppr: bool):
    """Show draft strategy for your position"""
    from ..core.strategy import ChampionshipDraftStrategy
    from ..core.models import LeagueSettings
    from ..data.loaders import load_and_prepare_data
    
    if not (1 <= position <= teams):
        click.echo(f"Error: Draft position must be between 1 and {teams}")
        return
    
    league_settings = LeagueSettings(teams=teams, rounds=rounds, ppr=ppr)
    
    try:
        # Load player data
        click.echo("Loading player data...")
        player_data = load_and_prepare_data()
        
        # Filter to fantasy-relevant positions only
        fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        player_data = player_data[player_data['position'].isin(fantasy_positions)]
        
        # Initialize strategy
        strategy = ChampionshipDraftStrategy(position, league_settings, ctx.obj['config'])
        
        # Show Round 1 strategy
        click.echo(f"\\n🏆 CHAMPIONSHIP STRATEGY - POSITION {position}")
        click.echo("=" * 60)
        click.echo(f"League: {teams} teams, {rounds} rounds, PPR: {ppr}")
        
        round1 = strategy.get_round_strategy(player_data, current_round=1, top_n=12)
        
        click.echo("\\n🎯 ROUND 1 RECOMMENDATIONS:")
        click.echo("-" * 40)
        
        for i, (_, player) in enumerate(round1.iterrows(), 1):
            name = player['name']
            pos = str(player['position'])
            team = str(player.get('team', ''))
            if team == 'nan':
                team = 'TBD'
            value = player['adjusted_value']
            click.echo(f"{i:2d}. {name:25s} ({pos}, {team:12s}) Value: {value:.1f}")
        
        # Show strategy guidance
        hero_phase = strategy._determine_hero_rb_phase(1)
        click.echo(f"\\n💡 STRATEGY PHASE: {hero_phase.value.replace('_', ' ').title()}")
        
        position_category = strategy.position_analyzer.get_position_category(position)
        click.echo(f"📍 POSITION CATEGORY: {position_category.title()}")
        
        if position_category == 'early':
            click.echo("   → Focus: Elite WRs, avoid QB/TE reaches")
        elif position_category == 'middle':
            click.echo("   → Focus: BPA flexibility, optimal value")
        else:  # late
            click.echo("   → Focus: PPR pairs, back-to-back advantage")
        
        click.echo(f"\\n🎯 Research Validation: Hero-RB achieves 20.2% advance rate vs 16.7% baseline!")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()


@main.command()
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--port', type=int, default=8501, help='Streamlit port (default: 8501)')
@click.pass_context
def dashboard(ctx, position: int, port: int):
    """Launch interactive draft dashboard"""
    import subprocess
    import sys
    
    click.echo(f"🚀 Launching draft dashboard for position {position}...")
    click.echo(f"   Dashboard will open at http://localhost:{port}")
    
    # Set environment variable for position
    import os
    os.environ['GRIDIRON_DRAFT_POSITION'] = str(position)
    
    try:
        # Launch streamlit app
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "gridiron_guillotine/web/streamlit_app.py",
            "--server.port", str(port)
        ])
    except KeyboardInterrupt:
        click.echo("\\n🛑 Dashboard stopped")


@main.command()
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--polling-interval', type=int, default=20, help='Polling interval in seconds')
@click.pass_context
def live(ctx, position: int, polling_interval: int):
    """Start live draft monitoring"""
    from ..live.monitor import LiveDraftMonitor
    from ..core.models import LeagueSettings
    
    click.echo(f"🔴 STARTING LIVE DRAFT MONITORING")
    click.echo(f"Position: {position}, Polling: every {polling_interval}s")
    click.echo("=" * 50)
    
    try:
        league_settings = LeagueSettings()
        monitor = LiveDraftMonitor(
            draft_position=position,
            league_settings=league_settings,
            polling_interval=polling_interval,
            config=ctx.obj['config']
        )
        
        monitor.start_monitoring()
        
    except KeyboardInterrupt:
        click.echo("\\n🛑 Live monitoring stopped")
    except Exception as e:
        click.echo(f"Error: {e}")
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()


# Add subcommand groups
main.add_command(draft_cli, name='draft')
main.add_command(data_cli, name='data')
main.add_command(news_cli, name='news')
main.add_command(database_cli, name='db')


@main.command()
def version():
    """Show version information"""
    from .. import __version__
    click.echo(f"Gridiron Guillotine v{__version__}")
    click.echo("Championship Fantasy Football Draft Strategy")
    click.echo("Research-validated Hero-RB with Advanced Metrics")


if __name__ == '__main__':
    main()