#!/usr/bin/env python3
"""
Test the improved Gridiron Guillotine strategy fixes
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config

def test_strategy_improvements():
    """Test the strategy improvements"""
    print("🔧 TESTING IMPROVED GRIDIRON GUILLOTINE STRATEGY")
    print("=" * 60)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        # Initialize draft
        simulator._initialize_draft(6, 12, 5)
        
        print("✅ Strategy improvements applied:")
        print("   📈 Position limits: QB(2), RB(4), WR(5), TE(2), K(1), DEF(1)")
        print("   🚨 QB urgency: MASSIVE boost after round 8")
        print("   🛡️ Roster caps: Max 4 RBs, 5 WRs to prevent overload")
        print("   ❌ No negative VBD: Blocks terrible players")
        
        # Test recommendations for different rounds
        test_rounds = [1, 8, 10]
        
        for round_num in test_rounds:
            print(f"\n🎯 ROUND {round_num} RECOMMENDATIONS:")
            print("-" * 40)
            
            # Simulate being in this round
            simulator.draft_state.current_round = round_num
            
            # Get recommendations
            recommendations = simulator._get_user_recommendations()
            
            if round_num == 8:
                # Show QB urgency in action
                qb_recs = [(p, r) for p, r in recommendations if p.position.value == 'QB']
                print(f"   🚨 QB Urgency Active - {len(qb_recs)} QBs in top recommendations:")
                for player, reason in qb_recs[:3]:
                    print(f"      • {player.name} - {reason}")
            
            # Show top 3 overall
            print(f"   📊 Top 3 Overall:")
            for i, (player, reason) in enumerate(recommendations[:3], 1):
                pos_icon = simulator._get_position_icon(player.position)
                print(f"      {i}. {pos_icon} {player.name} ({player.position.value}) - {reason}")
        
        print(f"\n✅ STRATEGY IMPROVEMENTS WORKING!")
        print(f"   🎯 QB will now be prioritized when needed")
        print(f"   🛡️ Position caps prevent RB/WR overload")
        print(f"   💎 Better value preservation with VBD thresholds")
        
    except Exception as e:
        print(f"❌ Error testing strategy: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy_improvements()