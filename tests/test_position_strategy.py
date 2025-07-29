"""
Test Draft Position-Specific Strategy Logic
Shows how strategy changes based on draft position
"""

import pandas as pd
from gridiron_guillotine.core.strategy import ChampionshipDraftStrategy
from gridiron_guillotine.data.loaders import PlayerDataLoader
from gridiron_guillotine.core.config import get_config

def test_position_strategies():
    """Test draft position-specific strategies"""
    print("📍 TESTING DRAFT POSITION-SPECIFIC STRATEGIES")
    print("=" * 70)
    
    # Load data
    config = get_config()
    loader = PlayerDataLoader(config)
    player_data = loader.load_scored_data()
    
    # Test different draft positions
    test_positions = [2, 6, 11]  # Early, Middle, Late
    
    for position in test_positions:
        print(f"\n🎯 DRAFT POSITION {position} ANALYSIS")
        print("-" * 50)
        
        # Initialize strategy for this position  
        strategy = ChampionshipDraftStrategy(config)
        
        # Show position category and guidance
        category = strategy.get_draft_position_category()
        guidance = strategy.get_position_specific_guidance(current_round=1)
        
        print(f"Position Category: {category.upper()}")
        print(f"Priority: {guidance['priority']}")
        print(f"Strategy: {guidance['strategy']}")
        
        if 'targets' in guidance:
            print(f"Research Targets: {guidance['targets']}")
        if 'avoid' in guidance:
            print(f"Avoid: {guidance['avoid']}")
        if 'advantage' in guidance:
            print(f"Advantage: {guidance['advantage']}")
        
        # Get Round 1 recommendations
        print(f"\nRound 1 Top 8 Recommendations:")
        round1_recs = strategy.get_round_strategy(player_data, current_round=1, top_n=8)
        
        for i, (_, player) in enumerate(round1_recs.iterrows(), 1):
            name = player['name']
            pos = player['position']
            value = player['adjusted_value']
            print(f"  {i}. {name:25s} ({pos}) Value: {value:.1f}")
    
    # Test position-specific adjustments for key players
    print(f"\n🔬 POSITION-SPECIFIC ADJUSTMENT TESTING")
    print("-" * 50)
    
    # Test key research targets
    test_players = {
        'Chase, Ja\'Marr': 'WR',      # Elite WR for early positions
        'Gibbs, Jahmyr': 'RB',        # Middle position target  
        'Collins, Nico': 'WR',        # Late position target
        'St. Brown, Amon-Ra': 'WR',   # Late position PPR target
        'Allen, Josh': 'QB'           # QB reach test
    }
    
    for position in [2, 6, 11]:
        strategy = ChampionshipDraftStrategy(draft_position=position, total_teams=12)
        print(f"\nDraft Position {position} ({strategy.get_draft_position_category().upper()}):")
        
        for player_name, player_pos in test_players.items():
            # Create mock player for testing
            mock_player = pd.Series({
                'name': player_name,
                'position': player_pos,
                'projected_points': 20.0
            })
            
            adjustment = strategy.apply_position_specific_adjustments(mock_player, current_round=1)
            
            if adjustment > 0:
                print(f"  {player_name:25s} (+{adjustment:.1f}) ⬆️ BOOSTED")
            elif adjustment < 0:
                print(f"  {player_name:25s} ({adjustment:.1f}) ⬇️ PENALIZED")
            else:
                print(f"  {player_name:25s} (±0.0)  ➡️ NEUTRAL")
    
    # Test round-by-round guidance changes
    print(f"\n⏰ ROUND-BY-ROUND GUIDANCE TEST (Position 11)")
    print("-" * 50)
    
    late_strategy = ChampionshipDraftStrategy(draft_position=11, total_teams=12)
    
    for round_num in [1, 2, 3, 6, 10]:
        guidance = late_strategy.get_position_specific_guidance(round_num)
        print(f"\nRound {round_num}:")
        print(f"  Priority: {guidance.get('priority', 'N/A')}")
        print(f"  Strategy: {guidance.get('strategy', 'N/A')}")
        
        if 'specific_targets' in guidance:
            print(f"  Targets: {guidance['specific_targets']}")
        if 'example' in guidance:
            print(f"  Example: {guidance['example']}")
    
    print(f"\n✅ POSITION STRATEGY TESTING COMPLETE!")
    print("🎯 Research-validated strategies by draft position:")
    print("  📍 Early (1-3): Elite WR focus, avoid reaches")
    print("  📍 Middle (4-8): BPA flexibility, optimal value")  
    print("  📍 Late (9-12): PPR pairs, back-to-back advantage")

if __name__ == "__main__":
    test_position_strategies()