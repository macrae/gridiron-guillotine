#!/usr/bin/env python3
"""
Demo the enhanced recommendation display with mock news data
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config
from gridiron_guillotine.data.database import NewsImpact

def demo_enhanced_display():
    """Demo the enhanced display with different news impacts"""
    print("🏈 ENHANCED RECOMMENDATION DISPLAY DEMO")
    print("=" * 60)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        # Initialize draft
        simulator._initialize_draft(6, 12, 15)
        
        print("🎯 MOCK RECOMMENDATIONS WITH NEWS INDICATORS:")
        print("=" * 85)
        
        # Get sample recommendations
        recommendations = simulator._get_user_recommendations()
        
        # Mock different news impacts for demo
        news_impacts = [NewsImpact.POSITIVE, NewsImpact.NEGATIVE, NewsImpact.NEUTRAL, 
                       NewsImpact.POSITIVE, NewsImpact.NEUTRAL]
        
        for i, (player, reason) in enumerate(recommendations[:5], 1):
            # Mock news impact for demo
            if hasattr(player, '_enhanced_data') and player._enhanced_data:
                player._enhanced_data.overall_news_impact = news_impacts[i-1]
            
            pos_icon = simulator._get_position_icon(player.position)
            news_icon = simulator._get_news_icon(player)
            
            projected_pts = player.projected_points
            vbd_score = player.vbd
            
            news_str = f" {news_icon}" if news_icon else ""
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}) "
                  f"Proj: {projected_pts:5.1f} | VBD: {vbd_score:5.1f}{news_str}")
            print(f"     └─ {reason}")
        
        print(f"\n📊 WHAT THE INDICATORS MEAN:")
        print(f"=" * 40)
        print(f"📈 POSITIVE NEWS: Recent good news (injury recovery, increased role, etc.)")
        print(f"📉 NEGATIVE NEWS: Recent bad news (injury, reduced role, etc.)")
        print(f"➖ NEUTRAL NEWS: No significant recent news impact")
        
        print(f"\n🎯 EXAMPLE USAGE IN LIVE DRAFT:")
        print(f"   1. 🏃 Saquon Barkley (RB) Proj: 18.5 | VBD: 6.2 📈")
        print(f"      └─ 🏆 Hero RB target | ⭐ Tier 2 player")
        print(f"      (📈 = Recent positive news boosts his value)")
        print(f"")
        print(f"   2. 🏈 Stefon Diggs (WR) Proj: 16.8 | VBD: 4.1 📉")
        print(f"      └─ 💎 Strong value | Strategic fit")
        print(f"      (📉 = Recent negative news, consider carefully)")
        
        print(f"\n✅ ENHANCED FEATURES NOW ACTIVE:")
        print(f"   📊 Projected Points: Season-long fantasy point expectations")
        print(f"   💎 VBD Scores: Value above replacement (higher = better pick)")
        print(f"   📰 News Arrows: Real-time player news impact")
        print(f"   🧠 Strategic Reasoning: Why each player is recommended")
        
        print(f"\n🚀 Ready for championship-level drafting!")
        
    except Exception as e:
        print(f"❌ Error in demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_enhanced_display()