#!/usr/bin/env python3
"""
Demo script to test the Gridiron Guillotine Mock Draft System
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config

def demo_mock_draft():
    """Demonstrate the mock draft system"""
    print("🏈 GRIDIRON GUILLOTINE MOCK DRAFT DEMO")
    print("=" * 50)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        print("📊 Testing system components...")
        
        # Test initialization
        simulator._initialize_draft(6, 12, 5)
        print(f"✅ Draft initialized - {len(simulator.draft_state.teams)} teams, {len(simulator.draft_state.available_players)} players")
        
        # Test recommendations
        recommendations = simulator._get_user_recommendations()
        print(f"✅ Generated {len(recommendations)} strategic recommendations")
        
        # Show top 5 recommendations
        print(f"\n🎯 TOP 5 GRIDIRON GUILLOTINE RECOMMENDATIONS:")
        print("-" * 50)
        for i, (player, reason) in enumerate(recommendations[:5], 1):
            pos_icon = simulator._get_position_icon(player.position)
            print(f"{i}. {pos_icon} {player.name:<25} ({player.position.value}) VBD: {player.vbd:5.1f}")
            print(f"   Reason: {reason}")
        
        # Test AI opponent selection
        print(f"\n🤖 TESTING AI OPPONENT STRATEGIES:")
        print("-" * 30)
        for team in simulator.draft_state.teams[:3]:  # Show first 3 teams
            if not team.is_user:
                ai_pick = simulator._ai_select_player(team)
                if ai_pick:
                    print(f"   {team.team_name} ({team.strategy_type}): {ai_pick.name} ({ai_pick.position.value})")
        
        print(f"\n✅ MOCK DRAFT SYSTEM READY!")
        print(f"   Run: gridiron draft mock --position 6")
        print(f"   This will start a full interactive mock draft session")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_mock_draft()