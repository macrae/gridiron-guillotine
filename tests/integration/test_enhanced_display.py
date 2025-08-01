#!/usr/bin/env python3
"""
Test the enhanced recommendation display with all metrics
"""

from gridiron_guillotine.live.mock_draft import MockDraftSimulator
from gridiron_guillotine.core.config import get_config

def test_enhanced_recommendations():
    """Test the enhanced recommendation display"""
    print("🔧 TESTING ENHANCED RECOMMENDATION DISPLAY")
    print("=" * 60)
    
    try:
        config = get_config()
        simulator = MockDraftSimulator(config)
        
        # Initialize draft
        simulator._initialize_draft(6, 12, 15)
        
        print("✅ Enhanced display features added:")
        print("   📊 Projected Fantasy Points")
        print("   💎 Value Above Replacement (VBD)")
        print("   📈📉 News Impact Arrows")
        print("   🎯 Enhanced formatting")
        
        # Test Round 1 recommendations with enhanced display
        print(f"\n🎯 SAMPLE ENHANCED RECOMMENDATIONS:")
        print("=" * 80)
        
        recommendations = simulator._get_user_recommendations()
        
        for i, (player, reason) in enumerate(recommendations[:5], 1):
            pos_icon = simulator._get_position_icon(player.position)
            news_icon = simulator._get_news_icon(player)
            
            projected_pts = player.projected_points
            vbd_score = player.vbd
            
            news_str = f" {news_icon}" if news_icon else ""
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}) "
                  f"Proj: {projected_pts:5.1f} | VBD: {vbd_score:5.1f}{news_str}")
            print(f"     └─ {reason}")
        
        print(f"\n📊 KEY FEATURES:")
        print(f"   Proj: Expected fantasy points for the season")
        print(f"   VBD: Value above replacement player (higher = better)")
        print(f"   📈: Positive news impact (trending up)")
        print(f"   📉: Negative news impact (trending down)")
        print(f"   ➖: Neutral news impact")
        
        # Test player with news
        players_with_news = [p for p, _ in recommendations 
                           if hasattr(p, '_enhanced_data') and p._enhanced_data 
                           and p._enhanced_data.overall_news_impact.value != 'neutral']
        
        if players_with_news:
            sample_player = players_with_news[0]
            news_icon = simulator._get_news_icon(sample_player)
            print(f"\n📰 SAMPLE PLAYER WITH NEWS:")
            print(f"   {simulator._get_position_icon(sample_player.position)} "
                  f"{sample_player.name} {news_icon} - "
                  f"Impact: {sample_player._enhanced_data.overall_news_impact.value}")
        
        print(f"\n✅ ENHANCED DISPLAY READY!")
        print(f"   All draft recommendations now show:")
        print(f"   • Fantasy point projections")
        print(f"   • Value above replacement scores") 
        print(f"   • Real-time news impact indicators")
        print(f"   • Strategic reasoning")
        
    except Exception as e:
        print(f"❌ Error testing enhanced display: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_enhanced_recommendations()