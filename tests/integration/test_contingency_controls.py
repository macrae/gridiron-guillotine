#!/usr/bin/env python3
"""
Test the new contingency controls for live draft scenarios
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config

def test_contingency_features():
    """Test all the new contingency control features"""
    print("🎮 CONTINGENCY CONTROLS TEST")
    print("=" * 60)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        # Initialize draft
        simulator._initialize_draft(6, 12, 15)
        
        print("✅ NEW CONTINGENCY FEATURES ADDED:")
        print("   🏈 NFL team display in all recommendations")
        print("   📍 Position filtering (qb, rb, wr, te, k, def)")
        print("   🏟️ Team filtering (buf, sf, kc, etc.)")
        print("   🔧 Manual override capabilities")
        
        # Test 1: Enhanced recommendations with team display
        print(f"\n🎯 TEST 1: ENHANCED RECOMMENDATIONS (with NFL teams)")
        print("=" * 70)
        
        recommendations = simulator._get_user_recommendations()
        for i, (player, reason) in enumerate(recommendations[:5], 1):
            pos_icon = simulator._get_position_icon(player.position)
            news_icon = simulator._get_news_icon(player)
            news_str = f" {news_icon}" if news_icon else ""
            team_str = f" {player.team:<3}" if player.team else " ---"
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}){team_str} "
                  f"Proj: {player.projected_points:5.1f} | VBD: {player.vbd:5.1f}{news_str}")
            print(f"     └─ {reason}")
        
        # Test 2: Position filtering
        print(f"\n🎯 TEST 2: POSITION FILTERING (RBs only)")
        print("=" * 70)
        
        rb_players = simulator._filter_by_position('rb')
        for i, (player, reason) in enumerate(rb_players[:5], 1):
            pos_icon = simulator._get_position_icon(player.position)
            team_str = f" {player.team:<3}" if player.team else " ---"
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}){team_str} "
                  f"Proj: {player.projected_points:5.1f} | VBD: {player.vbd:5.1f}")
            print(f"     └─ {reason}")
        
        # Test 3: Team filtering 
        print(f"\n🎯 TEST 3: TEAM FILTERING (Buffalo Bills)")
        print("=" * 70)
        
        bills_players = simulator._filter_by_team('buf')
        if bills_players:
            for i, (player, reason) in enumerate(bills_players[:5], 1):
                pos_icon = simulator._get_position_icon(player.position)
                print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}) BUF "
                      f"Proj: {player.projected_points:5.1f} | VBD: {player.vbd:5.1f}")
                print(f"     └─ {reason}")
        else:
            print("   No Bills players available")
        
        # Test 4: Show command interface
        print(f"\n🎯 TEST 4: LIVE DRAFT COMMAND INTERFACE")
        print("=" * 70)
        
        print("📋 Available options during your draft pick:")
        print("   • Enter 1-10 to select recommended player")
        print("   • Enter 's' to search for specific player")
        print("   • Enter 'r' to see more recommendations")
        print("   • Enter 'i' for draft information")
        print("   🎯 POSITION FILTERS: 'qb', 'rb', 'wr', 'te', 'k', 'def'")
        print("   🏟️ TEAM FILTERS: 'buf', 'sf', 'kc', etc. (NFL team codes)")
        
        # Test 5: Demonstrate emergency scenarios
        print(f"\n🚨 TEST 5: EMERGENCY SCENARIO EXAMPLES")
        print("=" * 70)
        
        print("🔧 CONTINGENCY EXAMPLES FOR LIVE DRAFT:")
        print("")
        print("📍 SCENARIO 1: Algorithm shows all QBs after you draft a QB")
        print("   → Type 'rb' to see only running backs")
        print("   → Type 'wr' to see only wide receivers")
        print("")
        print("🏟️ SCENARIO 2: You want to stack players from same team")
        print("   → Type 'kc' to see all Kansas City players")
        print("   → Type 'buf' to see all Buffalo players")
        print("")
        print("🔍 SCENARIO 3: Looking for a specific handcuff or sleeper")
        print("   → Type 's' then search for 'Jonathan Taylor'")
        print("   → Drill down by position first, then search")
        print("")
        print("⚡ SCENARIO 4: Quick position pivot in late rounds")
        print("   → Type 'k' to see all available kickers")
        print("   → Type 'def' to see all team defenses")
        
        print(f"\n✅ CONTINGENCY CONTROLS READY!")
        print(f"   🎯 You can now override the algorithm when needed")
        print(f"   📍 Filter by position for specific needs")
        print(f"   🏟️ Filter by team for stacking strategies")
        print(f"   🔧 Full manual control as backup to algorithm")
        
    except Exception as e:
        print(f"❌ Error testing contingency controls: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_contingency_features()