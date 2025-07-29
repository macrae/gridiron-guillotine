"""
Data management CLI commands
"""

import click
from pathlib import Path


@click.group()
def data_cli():
    """Data management and processing commands"""
    pass


@data_cli.command('status')
@click.pass_context
def data_status(ctx):
    """Show status of data files"""
    from ..core.config import get_config
    
    config = get_config()
    
    click.echo("📊 DATA STATUS")
    click.echo("=" * 40)
    
    # Check main data files
    main_files = [
        'scored_data.csv',
        'scored_data_with_2025_rookies.csv',
        'player_ids.json'
    ]
    
    for filename in main_files:
        filepath = config.get_data_file_path(filename)
        if filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            click.echo(f"✅ {filename:35s} ({size_mb:.1f} MB)")
        else:
            click.echo(f"❌ {filename:35s} (missing)")
    
    # Check historical data
    data_dir = config.data_dir
    if data_dir.exists():
        offense_files = list(data_dir.glob("offense_*.csv"))
        defense_files = list(data_dir.glob("defense_*.csv"))
        kicker_files = list(data_dir.glob("kickers_*.csv"))
        
        click.echo(f"\\n📈 HISTORICAL DATA:")
        click.echo(f"   Offense files: {len(offense_files)}")
        click.echo(f"   Defense files: {len(defense_files)}")
        click.echo(f"   Kicker files:  {len(kicker_files)}")
    
    # Check processed data directory
    processed_dir = config.processed_data_dir
    if processed_dir.exists():
        processed_files = list(processed_dir.glob("*.csv"))
        click.echo(f"\\n🔄 PROCESSED DATA: {len(processed_files)} files")
    else:
        click.echo(f"\\n🔄 PROCESSED DATA: directory not found")


@data_cli.command('load')
@click.option('--include-rookies/--no-rookies', default=True, help='Include 2025 rookies')
@click.option('--show-head', type=int, default=5, help='Show first N rows')
@click.pass_context
def load_data(ctx, include_rookies: bool, show_head: int):
    """Load and preview player data"""
    from ..data.loaders import PlayerDataLoader
    from ..core.config import get_config
    
    config = get_config()
    loader = PlayerDataLoader(config)
    
    try:
        click.echo("Loading player data...")
        data = loader.load_scored_data(include_rookies=include_rookies)
        
        click.echo(f"\\n📊 LOADED DATA SUMMARY")
        click.echo("=" * 40)
        click.echo(f"Total players: {len(data)}")
        click.echo(f"Positions: {', '.join(sorted(data['position'].unique()))}")
        
        # Position breakdown
        pos_counts = data['position'].value_counts()
        click.echo(f"\\n📈 BY POSITION:")
        for pos, count in pos_counts.items():
            click.echo(f"   {pos}: {count}")
        
        # Show top players
        if show_head > 0:
            click.echo(f"\\n🏆 TOP {show_head} PLAYERS BY PROJECTED POINTS:")
            click.echo("-" * 60)
            top_players = data.nlargest(show_head, 'projected_points')
            
            for i, (_, player) in enumerate(top_players.iterrows(), 1):
                name = player['name']
                pos = player['position']
                points = player['projected_points']
                vbd = player.get('vbd', 0)
                click.echo(f"{i:2d}. {name:25s} ({pos}) {points:6.1f} pts (VBD: {vbd:5.1f})")
        
    except Exception as e:
        click.echo(f"Error loading data: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@data_cli.command('update')
@click.option('--year', type=int, help='Year to scrape (default: current)')
@click.option('--weeks', help='Weeks to scrape (e.g., 1-17 or 1,2,3)')
@click.option('--positions', multiple=True, default=['offense', 'defense', 'kickers'],
              help='Data types to scrape')
@click.pass_context
def update_data(ctx, year: int, weeks: str, positions: tuple):
    """Update data by scraping latest NFL statistics"""
    click.echo("🔄 DATA UPDATE")
    click.echo("=" * 30)
    
    if not year:
        from datetime import datetime
        year = datetime.now().year
    
    # Parse weeks
    if weeks:
        if '-' in weeks:
            start, end = map(int, weeks.split('-'))
            week_list = list(range(start, end + 1))
        else:
            week_list = [int(w.strip()) for w in weeks.split(',')]
    else:
        week_list = list(range(1, 18))  # All weeks
    
    click.echo(f"Year: {year}")
    click.echo(f"Weeks: {week_list}")
    click.echo(f"Positions: {', '.join(positions)}")
    
    # This would integrate with the actual scrapers
    click.echo("\\n⚠️  Scraping functionality not yet integrated with new package structure")
    click.echo("   Use legacy scripts for now:")
    for pos in positions:
        click.echo(f"   python web_scrape_{pos}.py")


@data_cli.command('process')
@click.option('--input-dir', type=click.Path(exists=True), help='Input directory with raw data')
@click.option('--output-file', help='Output file name')
@click.pass_context
def process_data(ctx, input_dir: str, output_file: str):
    """Process raw data into scored player database"""
    from ..core.config import get_config
    
    config = get_config()
    
    if input_dir:
        input_path = Path(input_dir)
    else:
        input_path = config.data_dir
    
    if not output_file:
        output_file = "scored_data_processed.csv"
    
    click.echo(f"🔄 PROCESSING DATA")
    click.echo("=" * 30)
    click.echo(f"Input directory: {input_path}")
    click.echo(f"Output file: {output_file}")
    
    # This would integrate with the actual processing logic
    click.echo("\\n⚠️  Processing functionality not yet integrated with new package structure")
    click.echo("   Use legacy scripts for now:")
    click.echo("   python score_data.py")
    click.echo("   python aggregate_scored_data.py")


@data_cli.command('validate')
@click.option('--file', help='Specific file to validate')
@click.pass_context
def validate_data(ctx, file: str):
    """Validate data integrity and format"""
    from ..data.validators import DataValidator
    from ..core.config import get_config
    
    config = get_config()
    validator = DataValidator(config)
    
    click.echo("🔍 DATA VALIDATION")
    click.echo("=" * 30)
    
    if file:
        # Validate specific file
        filepath = config.get_data_file_path(file)
        if not filepath.exists():
            click.echo(f"❌ File not found: {file}")
            return
        
        try:
            result = validator.validate_file(filepath)
            if result['valid']:
                click.echo(f"✅ {file}: Valid")
                if result.get('warnings'):
                    for warning in result['warnings']:
                        click.echo(f"   ⚠️  {warning}")
            else:
                click.echo(f"❌ {file}: Invalid")
                for error in result.get('errors', []):
                    click.echo(f"   ❌ {error}")
                    
        except Exception as e:
            click.echo(f"Error validating {file}: {e}")
    
    else:
        # Validate all main data files
        main_files = ['scored_data.csv', 'scored_data_with_2025_rookies.csv']
        
        for filename in main_files:
            filepath = config.get_data_file_path(filename)
            if filepath.exists():
                try:
                    result = validator.validate_file(filepath)
                    status = "✅" if result['valid'] else "❌"
                    click.echo(f"{status} {filename}")
                    
                    if result.get('warnings'):
                        for warning in result['warnings']:
                            click.echo(f"   ⚠️  {warning}")
                    
                    if result.get('errors'):
                        for error in result['errors']:
                            click.echo(f"   ❌ {error}")
                            
                except Exception as e:
                    click.echo(f"❌ {filename}: Error - {e}")
            else:
                click.echo(f"⏭️  {filename}: Not found")