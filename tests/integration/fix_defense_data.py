#!/usr/bin/env python3
"""
Add team defenses to the database manually
"""

from gridiron_guillotine.data.database import PlayerDatabase, EnhancedPlayer
from gridiron_guillotine.core.models import Position
from datetime import datetime

def add_team_defenses():
    """Add NFL team defenses to the database"""
    print("🛡️ ADDING NFL TEAM DEFENSES TO DATABASE")
    print("=" * 50)
    
    # Top 12 NFL team defenses with estimated stats
    team_defenses = [
        {"name": "49ers", "team": "SF", "proj": 10.5, "vbd": 3.2},
        {"name": "Bills", "team": "BUF", "proj": 10.2, "vbd": 2.9},
        {"name": "Cowboys", "team": "DAL", "proj": 9.8, "vbd": 2.5},
        {"name": "Eagles", "team": "PHI", "proj": 9.5, "vbd": 2.2},
        {"name": "Ravens", "team": "BAL", "proj": 9.3, "vbd": 2.0},
        {"name": "Steelers", "team": "PIT", "proj": 9.0, "vbd": 1.7},
        {"name": "Jets", "team": "NYJ", "proj": 8.8, "vbd": 1.5},
        {"name": "Browns", "team": "CLE", "proj": 8.5, "vbd": 1.2},
        {"name": "Saints", "team": "NO", "proj": 8.2, "vbd": 0.9},
        {"name": "Chargers", "team": "LAC", "proj": 8.0, "vbd": 0.7},
        {"name": "Rams", "team": "LAR", "proj": 7.8, "vbd": 0.5},
        {"name": "Dolphins", "team": "MIA", "proj": 7.5, "vbd": 0.2}
    ]
    
    try:
        db = PlayerDatabase()
        
        added_count = 0
        for defense in team_defenses:
            # Check if already exists
            existing = db.get_player(defense["name"])
            if existing:
                print(f"   ⚠️  {defense['name']} already exists, skipping")
                continue
            
            # Create enhanced player for team defense
            enhanced_player = EnhancedPlayer(
                name=defense["name"],
                position=Position.DEF,
                team=defense["team"],
                projected_points=defense["proj"],
                vbd=defense["vbd"],
                tier=1 if defense["vbd"] > 2.0 else 2,
                floor=defense["proj"] * 0.7,
                ceiling=defense["proj"] * 1.4,
                rookie=False,
                
                # Set other required fields
                wopr=0.0,
                expected_points=defense["proj"],
                context_multiplier=1.0,
                advanced_score=defense["vbd"],
                adjusted_value=defense["vbd"],
                target_share=0.0,
                air_yards_share=0.0,
                red_zone_targets=0,
                red_zone_carries=0,
                goal_line_carries=0,
                air_yards_per_target=0.0,
                
                created_date=datetime.now(),
                last_updated=datetime.now()
            )
            
            # Add to database
            db.upsert_player(enhanced_player)
            print(f"   ✅ Added {defense['name']} DEF (Proj: {defense['proj']}, VBD: {defense['vbd']})")
            added_count += 1
        
        print(f"\n✅ TEAM DEFENSES ADDED: {added_count}")
        
        # Verify they're in the database
        print(f"\n📊 Updated Database Stats:")
        stats = db.get_stats()
        print(f"   Total players: {stats['total_players']}")
        
        # Check DEF count
        def_players = db.get_available_players(position=Position.DEF)
        print(f"   DEF players: {len(def_players)}")
        
        if def_players:
            print(f"\n🛡️ Team Defenses in Database:")
            for defense in def_players[:5]:
                print(f"   • {defense.name} ({defense.team}) - Proj: {defense.projected_points}, VBD: {defense.vbd}")
        
        print(f"\n🎯 Team defenses ready for draft!")
        
    except Exception as e:
        print(f"❌ Error adding team defenses: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_team_defenses()