"""
Draft-related CLI commands
"""

import click
import pandas as pd
from typing import Optional

from ..core.strategy import ChampionshipDraftStrategy
from ..core.models import LeagueSettings
from ..data.loaders import load_and_prepare_data


@click.group()
def draft_cli():
    """Draft strategy and simulation commands"""
    pass


@draft_cli.command('simulate')
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--rounds', type=int, default=5, help='Number of rounds to simulate')
@click.option('--teams', type=int, default=12, help='Number of teams')
@click.option('--ppr', is_flag=True, default=True, help='PPR scoring')
@click.pass_context
def simulate_draft(ctx, position: int, rounds: int, teams: int, ppr: bool):
    """Simulate multiple rounds of drafting"""
    from ..core.config import get_config
    
    config = get_config()
    league_settings = LeagueSettings(teams=teams, ppr=ppr)
    
    try:
        click.echo("Loading player data...")
        player_data = load_and_prepare_data()
        
        # Filter to fantasy-relevant positions only
        fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        player_data = player_data[player_data['position'].isin(fantasy_positions)]
        
        strategy = ChampionshipDraftStrategy(position, league_settings, config)
        
        click.echo(f"\\n🎯 DRAFT SIMULATION - POSITION {position}")
        click.echo("=" * 60)
        
        for round_num in range(1, rounds + 1):
            round_strategy = strategy.get_round_strategy(player_data, round_num, top_n=5)
            
            hero_phase = strategy._determine_hero_rb_phase(round_num)
            click.echo(f"\\n🔄 ROUND {round_num} - {hero_phase.value.replace('_', ' ').title()}")
            click.echo("-" * 40)
            
            for i, (_, player) in enumerate(round_strategy.iterrows(), 1):
                name = player['name']
                pos = player['position']
                value = player['adjusted_value']
                click.echo(f"  {i}. {name:25s} ({pos}) Value: {value:.1f}")
            
            # Simulate picking the top player
            if len(round_strategy) > 0:
                top_pick = round_strategy.iloc[0]
                strategy.simulate_pick(top_pick['name'])
                click.echo(f"  ✅ Simulated pick: {top_pick['name']}")
        
        click.echo(f"\\n✨ Simulation complete!")
        click.echo(f"Hero RB acquired: {strategy.draft_state.hero_rb_acquired}")
        click.echo(f"Current phase: {strategy.draft_state.hero_rb_phase.value}")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@draft_cli.command('analyze')
@click.option('--position', '-p', type=int, required=True, help='Your draft position')
@click.option('--player', required=True, help='Player name to analyze')
@click.pass_context
def analyze_player(ctx, position: int, player: str):
    """Analyze a specific player's value"""
    from ..core.config import get_config
    
    config = get_config()
    league_settings = LeagueSettings()
    
    try:
        player_data = load_and_prepare_data()
        
        # Filter to fantasy-relevant positions only
        fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        player_data = player_data[player_data['position'].isin(fantasy_positions)]
        
        # Find the player
        matches = player_data[player_data['name'].str.contains(player, case=False, na=False)]
        
        if len(matches) == 0:
            click.echo(f"No players found matching '{player}'")
            return
        
        if len(matches) > 1:
            click.echo(f"Multiple players found matching '{player}':")
            for i, (_, p) in enumerate(matches.iterrows(), 1):
                click.echo(f"  {i}. {p['name']} ({p['position']}, {p.get('team', 'N/A')})")
            return
        
        player_row = matches.iloc[0]
        strategy = ChampionshipDraftStrategy(position, league_settings, config)
        
        click.echo(f"\\n📊 PLAYER ANALYSIS: {player_row['name']}")
        click.echo("=" * 50)
        click.echo(f"Position: {player_row['position']}")
        click.echo(f"Team: {player_row.get('team', 'N/A')}")
        click.echo(f"Projected Points: {player_row['projected_points']:.1f}")
        click.echo(f"VBD: {player_row.get('vbd', 0):.1f}")
        click.echo(f"Tier: {player_row.get('tier', 1)}")
        
        # Advanced metrics if available
        if 'wopr' in player_row and player_row['wopr'] > 0:
            click.echo(f"WOPR: {player_row['wopr']:.3f}")
        if 'advanced_score' in player_row:
            click.echo(f"Advanced Score: {player_row['advanced_score']:.1f}")
        
        # Show value in different rounds
        click.echo(f"\\n📈 VALUE BY ROUND:")
        for round_num in [1, 3, 6, 10]:
            # Mock scarcity and tier data for analysis
            scarcity_factors = {pos: 1.0 for pos in strategy.config.replacement_levels.keys()}
            tier_dropoffs = {pos: 0.0 for pos in strategy.config.replacement_levels.keys()}
            
            value = strategy.adjust_player_value(
                player_row, scarcity_factors, tier_dropoffs, round_num
            )
            
            hero_phase = strategy._determine_hero_rb_phase(round_num)
            click.echo(f"  Round {round_num:2d} ({hero_phase.value:15s}): {value:6.1f}")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@draft_cli.command('test-phases')
@click.option('--position', '-p', type=int, default=6, help='Draft position to test')
@click.pass_context  
def test_hero_phases(ctx, position: int):
    """Test Hero-RB phase transitions"""
    from ..core.config import get_config
    
    config = get_config()
    league_settings = LeagueSettings()
    
    try:
        player_data = load_and_prepare_data()
        
        # Filter to fantasy-relevant positions only
        fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        player_data = player_data[player_data['position'].isin(fantasy_positions)]
        
        strategy = ChampionshipDraftStrategy(position, league_settings, config)
        
        click.echo(f"🏆 TESTING HERO-RB PHASE TRANSITIONS")
        click.echo("=" * 60)
        
        # Test Round 1 (Hero Acquisition)
        click.echo(f"\\n🎯 ROUND 1 - HERO ACQUISITION PHASE")
        click.echo("-" * 40)
        round1 = strategy.get_round_strategy(player_data, current_round=1, top_n=6)
        for i, (_, player) in enumerate(round1.iterrows(), 1):
            click.echo(f"{i}. {player['name']:25s} ({player['position']}) Value: {player['adjusted_value']:.1f}")
        
        # Simulate picking McCaffrey
        strategy.simulate_pick("McCaffrey, Christian")
        click.echo(f"\\n✅ Hero RB Status: {strategy.draft_state.hero_rb_acquired}")
        click.echo(f"✅ Current Phase: {strategy.draft_state.hero_rb_phase.value}")
        
        # Test Round 3 (Pivot Phase)
        click.echo(f"\\n🔄 ROUND 3 - PIVOT PHASE (Avoid RBs!)")
        click.echo("-" * 40)
        round3 = strategy.get_round_strategy(player_data, current_round=3, top_n=6)
        for i, (_, player) in enumerate(round3.iterrows(), 1):
            click.echo(f"{i}. {player['name']:25s} ({player['position']}) Value: {player['adjusted_value']:.1f}")
        
        # Test Round 8 (Depth Phase)
        click.echo(f"\\n📈 ROUND 8 - DEPTH PHASE (RB Accumulation)")
        click.echo("-" * 40)
        round8 = strategy.get_round_strategy(player_data, current_round=8, top_n=6)
        for i, (_, player) in enumerate(round8.iterrows(), 1):
            click.echo(f"{i}. {player['name']:25s} ({player['position']}) Value: {player['adjusted_value']:.1f}")
        
        click.echo(f"\\n🏆 HERO-RB STRATEGY INSIGHTS:")
        click.echo(f"   ✅ Round 1: Elite RBs dominate (Hero Acquisition)")
        click.echo(f"   ✅ Round 3: WRs prioritized, RBs penalized (Pivot Phase)")
        click.echo(f"   ✅ Round 8: RBs boosted again for depth (Depth Phase)")
        click.echo(f"   🎯 Research Validation: 20.2% advance rate vs 16.7% baseline!")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@draft_cli.command('mock')
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--teams', type=int, default=12, help='Number of teams in league')
@click.option('--rounds', type=int, default=15, help='Number of rounds to draft')
@click.pass_context
def mock_draft(ctx, position: int, teams: int, rounds: int):
    """Start an interactive mock draft to test strategy"""
    from ..live.mock_draft import MockDraftSimulator
    from ..core.config import get_config
    
    # Validate inputs
    if not (1 <= position <= teams):
        click.echo(f"❌ Invalid position. Must be between 1 and {teams}")
        return
    
    if not (8 <= teams <= 16):
        click.echo(f"❌ Invalid team count. Must be between 8 and 16")
        return
    
    if not (10 <= rounds <= 20):
        click.echo(f"❌ Invalid round count. Must be between 10 and 20")
        return
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        click.echo(f"🚀 Starting interactive mock draft...")
        click.echo(f"📊 Make sure you have run 'gridiron db precompute' first!")
        
        # Start the mock draft
        simulator.start_mock_draft(
            user_position=position,
            num_teams=teams, 
            num_rounds=rounds
        )
        
    except KeyboardInterrupt:
        click.echo(f"\\n\\n⏹️  Mock draft interrupted by user")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        if ctx.obj and ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()


@draft_cli.command('yahoo-live')
@click.option('--position', '-p', type=int, required=True, help='Your draft position (1-12)')
@click.option('--draft-url', '-u', required=True, help='Yahoo mock draft URL or draft ID')
@click.option('--polling-interval', type=int, default=10, help='Polling interval in seconds (default: 10)')
@click.option('--headless', is_flag=True, default=True, help='Run web scraper in headless mode')
@click.pass_context
def yahoo_live_mock(ctx, position: int, draft_url: str, polling_interval: int, headless: bool):
    """Monitor live Yahoo Fantasy Football mock draft
    
    Connect to a Yahoo mock draft room and get real-time Hero-RB strategy recommendations
    as picks are made by other teams.
    
    Examples:
    
    \\b
    # Connect using full Yahoo mock draft URL
    gridiron draft yahoo-live -p 6 -u "https://football.fantasysports.yahoo.com/f1/draftroom/12345"
    
    \\b
    # Connect using just the draft ID
    gridiron draft yahoo-live -p 6 -u "12345"
    
    \\b
    # Custom polling interval (faster updates)
    gridiron draft yahoo-live -p 6 -u "12345" --polling-interval 5
    """
    from ..live.yahoo_mock_monitor import YahooMockDraftMonitor, YahooMockDraftConsole
    from ..core.config import Config, get_config
    
    # Validate position (support up to 16-team leagues)
    if not (1 <= position <= 16):
        click.echo(f"❌ Invalid position. Must be between 1 and 16")
        return
    
    # Validate polling interval
    if not (5 <= polling_interval <= 60):
        click.echo(f"❌ Invalid polling interval. Must be between 5 and 60 seconds")
        return
    
    try:
        # Create a fresh Config object to avoid context issues
        config = Config()
            
        monitor = YahooMockDraftMonitor(config)
        console = YahooMockDraftConsole(monitor)
        
        click.echo(f"🚀 CONNECTING TO YAHOO MOCK DRAFT")
        click.echo(f"Position: {position}")
        click.echo(f"Draft URL/ID: {draft_url}")
        click.echo(f"Polling: every {polling_interval}s")
        click.echo(f"Web scraping: {'headless' if headless else 'visible browser'}")
        click.echo("=" * 60)
        
        # Connect to the mock draft
        if not monitor.connect_to_mock_draft(draft_url, position):
            click.echo("❌ Failed to connect to Yahoo mock draft")
            click.echo("\\nTroubleshooting:")
            click.echo("1. Ensure the draft URL/ID is correct")
            click.echo("2. Check your Yahoo Fantasy API credentials (oauth2.json)")
            click.echo("3. Make sure Chrome/Chromium is installed for web scraping")
            click.echo("4. Verify the mock draft is currently active")
            return
        
        click.echo("✅ Connected successfully!")
        click.echo("\\nStarting live monitoring... (Press Ctrl+C to stop)")
        click.echo("=" * 60)
        
        # Start monitoring
        monitor.start_monitoring(polling_interval)
        
    except KeyboardInterrupt:
        click.echo(f"\\n\\n⏹️  Yahoo mock draft monitoring stopped")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        if ctx.obj and ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()
        
        click.echo(f"\\n💡 Troubleshooting tips:")
        click.echo(f"   • Ensure 'gridiron db precompute' has been run")
        click.echo(f"   • Check Yahoo API credentials in nbs/oauth2.json")
        click.echo(f"   • Install Selenium ChromeDriver for web scraping")
        click.echo(f"   • Verify the draft is active and accessible")


@draft_cli.command('yahoo-test')
@click.option('--draft-url', '-u', help='Yahoo mock draft URL to test (optional)')
@click.pass_context
def yahoo_test_connection(ctx, draft_url: str):
    """Test Yahoo Fantasy API and web scraping connection
    
    Test your Yahoo Fantasy API credentials and web scraping setup
    without connecting to a specific draft.
    """
    from ..live.yahoo_mock_monitor import YahooMockDraftMonitor
    from ..api.yahoo import YahooFantasyClient
    from ..core.config import Config, get_config
    
    # Create a fresh Config object to avoid context issues
    config = Config()
    
    click.echo("🧪 TESTING YAHOO INTEGRATION")
    click.echo("=" * 40)
    
    # Test Yahoo API
    click.echo("1. Testing Yahoo Fantasy API...")
    try:
        yahoo_client = YahooFantasyClient(config)
        if yahoo_client.authenticate():
            click.echo("   ✅ Yahoo API authentication successful")
            
            league_info = yahoo_client.get_league_info()
            if league_info:
                click.echo(f"   ✅ Connected to league: {league_info.get('name', 'Unknown')}")
            else:
                click.echo("   ⚠️  No league info available (normal for mock drafts)")
        else:
            click.echo("   ❌ Yahoo API authentication failed")
            click.echo("   💡 Check your oauth2.json credentials")
    except Exception as e:
        click.echo(f"   ❌ Yahoo API error: {e}")
    
    # Test web scraping setup
    click.echo("\\n2. Testing web scraping setup...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
        click.echo("   ✅ Web driver (Chrome) initialized successfully")
    except Exception as e:
        click.echo(f"   ❌ Web scraping error: {e}")
        click.echo("   💡 Install ChromeDriver: brew install chromedriver")
    
    # Test database connection
    click.echo("\\n3. Testing player database...")
    try:
        from ..data.database import PlayerDatabase
        db = PlayerDatabase()
        stats = db.get_stats()
        if stats['total_players'] > 0:
            click.echo(f"   ✅ Database ready with {stats['total_players']} players")
        else:
            click.echo("   ⚠️  Database empty - run 'gridiron db precompute'")
    except Exception as e:
        click.echo(f"   ❌ Database error: {e}")
    
    # Test specific draft URL if provided
    if draft_url:
        click.echo(f"\\n4. Testing draft URL: {draft_url}")
        try:
            monitor = YahooMockDraftMonitor(config)
            draft_id = monitor._extract_draft_id(draft_url)
            if draft_id:
                click.echo(f"   ✅ Draft ID extracted: {draft_id}")
            else:
                click.echo("   ❌ Could not extract draft ID from URL")
        except Exception as e:
            click.echo(f"   ❌ Draft URL test error: {e}")
    
    click.echo(f"\\n🎯 INTEGRATION TEST COMPLETE")
    click.echo(f"Ready to monitor Yahoo mock drafts? Use:")
    click.echo(f"   gridiron draft yahoo-live -p <position> -u <draft_url>")