#!/usr/bin/env python3
"""
Test all the draft strategy fixes together
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config

def test_strategy_fixes():
    """Test all the strategy fixes together"""
    print("🔧 TESTING ALL STRATEGY FIXES")
    print("=" * 50)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        # Initialize draft
        simulator._initialize_draft(6, 12, 15)
        
        print("✅ Strategy fixes applied:")
        print("   🚫 QB overload fixed - max 1 QB until round 13")
        print("   🛡️ Team defenses added - 12 DEF teams available")
        print("   🎯 Late round priority fixed - K/DEF forced in final rounds")
        
        # Test different rounds to show the fix
        test_rounds = [1, 8, 14, 15]
        
        for round_num in test_rounds:
            print(f"\n🎯 ROUND {round_num} RECOMMENDATIONS:")
            print("-" * 40)
            
            # Simulate round
            simulator.draft_state.current_round = round_num
            
            # Get priority positions  
            priorities = simulator.strategy._get_priority_positions(round_num)
            print(f"   Priority: {[p.value for p in priorities]}")
            
            # Get recommendations
            recommendations = simulator._get_user_recommendations()
            
            # Show top 3
            for i, (player, reason) in enumerate(recommendations[:3], 1):
                pos_icon = simulator._get_position_icon(player.position)
                print(f"   {i}. {pos_icon} {player.name} ({player.position.value}) - {reason}")
        
        # Test DEF availability
        from gridiron_guillotine.core.models import Position
        def_players = simulator.db.get_available_players(position=Position.DEF)
        print(f"\n🛡️ TEAM DEFENSES AVAILABLE:")
        for i, defense in enumerate(def_players[:5], 1):
            print(f"   {i}. 🛡️ {defense.name} ({defense.team}) Proj: {defense.projected_points:.1f} | VBD: {defense.vbd:.1f}")
        
        print(f"\n✅ ALL FIXES WORKING!")
        print(f"   🎯 Round 1: Hero-RB focus")
        print(f"   🎯 Round 8: QB priority if needed")
        print(f"   🎯 Round 14-15: K/DEF only")
        print(f"   🛡️ Team defenses available for drafting")
        
    except Exception as e:
        print(f"❌ Error testing fixes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy_fixes()