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
        strategy = ChampionshipDraftStrategy(draft_position=position, config=config)
        
        # Show position category and basic info
        if position <= 3:
            category = "EARLY"
            strategy_desc = "Elite talent focus, avoid reaches"
        elif position <= 8:
            category = "MIDDLE"
            strategy_desc = "Best player available flexibility"
        else:
            category = "LATE"
            strategy_desc = "Back-to-back picks advantage"
        
        print(f"Position Category: {category}")
        print(f"Strategy: {strategy_desc}")
        
        # Test draft position analyzer
        from gridiron_guillotine.core.models import Player, Position
        mock_player = Player(
            name="Test Player",
            position=Position.RB,
            team="BUF",
            projected_points=15.0
        )
        draft_adj = strategy.position_analyzer.calculate_position_adjustment(
            mock_player, position, 1
        )
        print(f"Position Adjustment: {draft_adj:.2f}")
        
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
        strategy = ChampionshipDraftStrategy(draft_position=position, config=config)
        
        if position <= 3:
            category = "EARLY"
        elif position <= 8:
            category = "MIDDLE"
        else:
            category = "LATE"
            
        print(f"\nDraft Position {position} ({category}):")
        
        for player_name, player_pos in test_players.items():
            # Create mock player for testing
            from gridiron_guillotine.core.models import Player, Position
            mock_player = Player(
                name=player_name,
                position=Position(player_pos),
                team="BUF",
                projected_points=20.0
            )
            
            adjustment = strategy.position_analyzer.calculate_position_adjustment(
                mock_player, position, 1
            )
            
            if adjustment > 0:
                print(f"  {player_name:25s} (+{adjustment:.1f}) ⬆️ BOOSTED")
            elif adjustment < 0:
                print(f"  {player_name:25s} ({adjustment:.1f}) ⬇️ PENALIZED")
            else:
                print(f"  {player_name:25s} (±0.0)  ➡️ NEUTRAL")
    
    # Test round-by-round priority changes
    print(f"\n⏰ ROUND-BY-ROUND PRIORITY TEST (Position 11)")
    print("-" * 50)
    
    late_strategy = ChampionshipDraftStrategy(draft_position=11, config=config)
    
    for round_num in [1, 2, 3, 6, 10]:
        priorities = late_strategy._get_priority_positions(round_num)
        hero_phase = late_strategy._determine_hero_rb_phase(round_num)
        
        print(f"\nRound {round_num}:")
        print(f"  Hero Phase: {hero_phase.value}")
        print(f"  Priority Positions: {[pos.value for pos in priorities[:3]]}")
    
    print(f"\n✅ POSITION STRATEGY TESTING COMPLETE!")
    print("🎯 Hero-RB strategy adapts by draft position:")
    print("  📍 Early (1-3): Aggressive hero RB pursuit")
    print("  📍 Middle (4-8): Balanced hero RB + WR flexibility")  
    print("  📍 Late (9-12): Back-to-back advantage for depth")

if __name__ == "__main__":
    test_position_strategies()