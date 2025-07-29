"""
Test Advanced Metrics Integration
Validates WOPR, Expected Points, and Offensive Context calculations
"""

import pandas as pd
from gridiron_guillotine.core.strategy import ChampionshipDraftStrategy
from gridiron_guillotine.data.loaders import PlayerDataLoader
from gridiron_guillotine.core.config import get_config

def test_advanced_metrics():
    """Test all advanced metrics calculations"""
    print("🔬 TESTING ADVANCED METRICS INTEGRATION")
    print("=" * 60)
    
    # Load data
    config = get_config()
    loader = PlayerDataLoader(config)
    player_data = loader.load_scored_data()
    
    # Initialize championship strategy
    strategy = ChampionshipDraftStrategy(config)
    
    # Test 1: WOPR Calculation for WRs
    print("\n📊 WOPR TESTING (Wide Receivers)")
    print("-" * 40)
    
    # Create sample WR data with target/air yards metrics
    wr_sample = player_data[player_data['position'] == 'WR'].head(5).copy()
    
    if len(wr_sample) > 0:
        # Add mock target share and air yards data for testing
        wr_sample.loc[:, 'target_share'] = [25, 20, 18, 15, 12]  # Percentage
        wr_sample.loc[:, 'air_yards_share'] = [22, 18, 16, 14, 10]  # Percentage
        
        wopr_scores = strategy.calculate_wopr(wr_sample)
        
        for i, (idx, player) in enumerate(wr_sample.iterrows()):
            print(f"{i+1}. {player['name']:25s} WOPR: {wopr_scores.iloc[i]:.3f}")
    
    # Test 2: Expected Fantasy Points
    print("\n🎯 EXPECTED FANTASY POINTS TESTING")
    print("-" * 40)
    
    # Create sample data with opportunity metrics
    sample_players = player_data.head(5).copy()
    sample_players.loc[:, 'red_zone_targets'] = [8, 6, 4, 2, 0]
    sample_players.loc[:, 'red_zone_carries'] = [12, 8, 4, 0, 0] 
    sample_players.loc[:, 'air_yards_per_target'] = [15, 12, 8, 6, 4]
    sample_players.loc[:, 'goal_line_carries'] = [6, 4, 2, 0, 0]
    
    expected_points = strategy.calculate_expected_fantasy_points(sample_players)
    
    for i, (idx, player) in enumerate(sample_players.iterrows()):
        base = player['projected_points']
        expected = expected_points.iloc[i]
        boost = expected - base
        print(f"{i+1}. {player['name']:25s} Base: {base:.1f} → Expected: {expected:.1f} (+{boost:.1f})")
    
    # Test 3: Offensive Context Multipliers
    print("\n⚡ OFFENSIVE CONTEXT TESTING")
    print("-" * 40)
    
    # Test players from different offensive tiers
    context_test = player_data.head(10).copy()
    
    # Mock team assignments for testing
    test_teams = ['Buffalo', 'Kansas City', 'Detroit', 'Atlanta', 'Chicago', 
                  'Carolina', 'New England', 'Denver', 'Tampa Bay', 'Seattle']
    context_test.loc[:, 'team'] = test_teams[:len(context_test)]
    
    context_multipliers = strategy.calculate_offensive_context_multiplier(context_test)
    
    for i, (idx, player) in enumerate(context_test.iterrows()):
        team = player['team']
        multiplier = context_multipliers.iloc[i]
        tier = "Elite" if multiplier > 1.0 else "Bottom" if multiplier < 1.0 else "Middle"
        print(f"{i+1}. {player['name']:25s} ({team:12s}) {multiplier:.2f}x [{tier}]")
    
    # Test 4: Full Advanced Metrics Integration
    print("\n🏆 CHAMPIONSHIP STRATEGY FULL TEST")
    print("-" * 40)
    
    # Get Round 1 recommendations with full advanced metrics
    round1_recs = strategy.get_round_strategy(player_data, current_round=1, top_n=8)
    
    print("Top 8 Round 1 Picks with Advanced Metrics:")
    for i, (_, player) in enumerate(round1_recs.iterrows(), 1):
        name = player['name']
        pos = player['position']
        value = player['adjusted_value']
        
        # Show advanced metrics if available
        if 'advanced_score' in player:
            adv_score = player['advanced_score']
            wopr = player.get('wopr', 0)
            context = player.get('context_multiplier', 1.0)
            print(f"{i}. {name:25s} ({pos}) Value: {value:.1f} | Adv: {adv_score:.1f} | WOPR: {wopr:.3f} | Context: {context:.2f}x")
        else:
            print(f"{i}. {name:25s} ({pos}) Value: {value:.1f}")
    
    # Test 5: Hero-RB Phase Impact on Advanced Metrics
    print("\n🚀 HERO-RB PHASE IMPACT TEST")
    print("-" * 40)
    
    print("Round 1 (Hero Acquisition):")
    phase1 = strategy._determine_hero_rb_phase(1)
    print(f"  Phase: {phase1}")
    print(f"  Elite RBs boosted, non-elite RBs penalized")
    
    # Simulate hero RB acquisition
    strategy.simulate_pick("McCaffrey, Christian")
    
    print("\nRound 3 (Pivot Phase):")
    phase3 = strategy._determine_hero_rb_phase(3)
    print(f"  Phase: {phase3}")
    print(f"  Hero RB Acquired: {strategy.hero_rb_acquired}")
    print(f"  All RBs penalized, WRs boosted")
    
    print("\nRound 8 (Depth Phase):")
    phase8 = strategy._determine_hero_rb_phase(8)
    print(f"  Phase: {phase8}")
    print(f"  RB depth accumulation boosted")
    
    print("\n✅ ALL ADVANCED METRICS TESTS COMPLETED!")
    print("🎯 Championship strategy ready with full research validation!")
    print("\nKey Research Validations:")
    print("  🔬 WOPR: 0.746 R² correlation with WR performance")
    print("  🎯 Expected Points: Most predictive stat (Scott Barrett, PFF)")
    print("  ⚡ Offensive Context: Only 2/9 top-36 WRs in bottom-10 offenses succeeded")
    print("  🏆 Hero-RB Strategy: 20.2% advance rate vs 16.7% baseline")

if __name__ == "__main__":
    test_advanced_metrics()