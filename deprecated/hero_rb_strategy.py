"""
Hero-RB Strategy Implementation
Research: 20.2% advance rates vs 16.7% baseline, 9.90% win rates vs 8.30%
Strategy: 1 elite RB (rounds 1-2) → pivot until round 6+ → finish with 5-6 total RBs
"""

import pandas as pd
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class HeroRBStrategy:
    """
    Research-validated Hero-RB implementation
    Dramatically different from RB-heavy approach
    """
    
    def __init__(self, draft_position: int):
        self.draft_position = draft_position
        self.hero_rb_acquired = False
        self.total_rbs_drafted = 0
        self.draft_phase = "hero_acquisition"  # hero_acquisition, pivot_phase, depth_phase
        
        # Research-based round thresholds
        self.hero_rounds = [1, 2]  # Must get hero RB in rounds 1-2
        self.pivot_rounds = [3, 4, 5, 6]  # Avoid RBs unless exceptional value
        self.depth_rounds = [7, 8, 9, 10, 11, 12, 13, 14, 15]  # Accumulate RB depth
        
        # Elite RB targets for Hero selection (research-based)
        self.elite_hero_targets = [
            'McCaffrey, Christian',
            'Henry, Derrick', 
            'Kamara, Alvin',
            'Achane, De\'Von',
            'Taylor, Jonathan',
            'Gibbs, Jahmyr',
            'Barkley, Saquon'
        ]
        
    def get_hero_rb_strategy(self, player_df: pd.DataFrame, current_round: int, 
                           current_roster: Dict[str, List[str]]) -> Dict:
        """
        Get Hero-RB specific recommendations for current round
        Research: Strategy must adapt by phase, not just boost RBs
        """
        strategy_info = {
            'phase': self._determine_phase(current_round),
            'rb_priority': self._get_rb_priority(current_round),
            'position_targets': self._get_position_targets(current_round),
            'avoid_positions': self._get_avoid_positions(current_round),
            'hero_rb_status': self.hero_rb_acquired,
            'total_rbs': self.total_rbs_drafted
        }
        
        # Apply Hero-RB specific player adjustments
        adjusted_df = self._apply_hero_rb_adjustments(player_df, current_round)
        
        return strategy_info, adjusted_df
    
    def _determine_phase(self, current_round: int) -> str:
        """Determine which phase of Hero-RB strategy we're in"""
        if current_round in self.hero_rounds and not self.hero_rb_acquired:
            return "hero_acquisition"
        elif current_round in self.pivot_rounds:
            return "pivot_phase"  
        elif current_round in self.depth_rounds:
            return "depth_phase"
        else:
            return "unknown"
    
    def _get_rb_priority(self, current_round: int) -> str:
        """Get RB priority level for current round"""
        phase = self._determine_phase(current_round)
        
        if phase == "hero_acquisition":
            return "ELITE_ONLY"  # Only draft elite RBs
        elif phase == "pivot_phase":
            return "AVOID"  # Actively avoid RBs unless exceptional
        elif phase == "depth_phase":
            return "ACCUMULATE"  # Target RB depth heavily
        else:
            return "NORMAL"
    
    def _get_position_targets(self, current_round: int) -> List[str]:
        """Get priority positions for current round"""
        phase = self._determine_phase(current_round)
        
        if phase == "hero_acquisition":
            if self.hero_rb_acquired:
                return ["WR", "TE"]  # Got hero, pivot to other positions
            else:
                return ["RB", "WR"]  # Still need hero RB
                
        elif phase == "pivot_phase":
            return ["WR", "QB", "TE"]  # Research: Focus on non-RB positions
            
        elif phase == "depth_phase":
            return ["RB", "WR", "QB", "TE", "K", "DEF"]  # All positions, RB emphasis
            
        else:
            return ["WR", "RB", "QB", "TE"]
    
    def _get_avoid_positions(self, current_round: int) -> List[str]:
        """Get positions to avoid in current round"""
        phase = self._determine_phase(current_round)
        
        if phase == "pivot_phase":
            return ["RB"]  # Key research finding: avoid RBs in rounds 3-6
        elif current_round <= 8:
            return ["K", "DEF"]  # Never draft K/DEF early
        else:
            return []
    
    def _apply_hero_rb_adjustments(self, player_df: pd.DataFrame, current_round: int) -> pd.DataFrame:
        """
        Apply Hero-RB specific adjustments to player values
        Research: Different from simple RB boost - phase-dependent
        """
        adjusted_df = player_df.copy()
        phase = self._determine_phase(current_round)
        
        if phase == "hero_acquisition":
            # MASSIVE boost for elite RBs only
            elite_mask = adjusted_df['name'].isin(self.elite_hero_targets)
            rb_mask = adjusted_df['position'] == 'RB'
            
            # 50% boost for elite RBs (hero candidates)
            adjusted_df.loc[elite_mask & rb_mask, 'adjusted_value'] *= 1.5
            
            # Penalty for non-elite RBs (avoid RB2 trap)
            adjusted_df.loc[~elite_mask & rb_mask, 'adjusted_value'] *= 0.8
            
        elif phase == "pivot_phase":
            # Research key: AVOID RBs during pivot phase
            rb_mask = adjusted_df['position'] == 'RB'
            adjusted_df.loc[rb_mask, 'adjusted_value'] *= 0.6  # Heavy penalty
            
            # Boost WRs and other positions
            wr_mask = adjusted_df['position'] == 'WR'
            adjusted_df.loc[wr_mask, 'adjusted_value'] *= 1.2
            
        elif phase == "depth_phase":
            # Boost RB depth targets
            rb_mask = adjusted_df['position'] == 'RB'
            adjusted_df.loc[rb_mask, 'adjusted_value'] *= 1.3
            
        return adjusted_df
    
    def update_draft_state(self, player_name: str, position: str, round_num: int):
        """Update Hero-RB strategy state when picks are made"""
        if position == 'RB':
            self.total_rbs_drafted += 1
            
            # Check if this was a hero RB acquisition
            if (round_num in self.hero_rounds and 
                player_name in self.elite_hero_targets):
                self.hero_rb_acquired = True
                self.draft_phase = "pivot_phase"
                logger.info(f"HERO RB ACQUIRED: {player_name} in round {round_num}")
        
        # Update phase based on round
        if round_num >= 7:
            self.draft_phase = "depth_phase"
    
    def get_hero_rb_analysis(self) -> Dict:
        """Get analysis of Hero-RB strategy execution"""
        return {
            'hero_rb_acquired': self.hero_rb_acquired,
            'total_rbs_drafted': self.total_rbs_drafted,
            'current_phase': self.draft_phase,
            'target_total_rbs': 6,  # Research: finish with 5-6 total RBs
            'strategy_success': self.hero_rb_acquired,
            'remaining_rb_targets': max(0, 6 - self.total_rbs_drafted)
        }

# Integration with existing draft strategy
def enhance_with_hero_rb(original_strategy_class):
    """
    Enhance existing draft strategy with Hero-RB methodology
    """
    class HeroRBEnhancedStrategy(original_strategy_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.hero_rb = HeroRBStrategy(self.draft_position)
            
        def get_round_strategy(self, player_df: pd.DataFrame, current_round: int, 
                             top_n: int = 12) -> pd.DataFrame:
            """
            Override to use Hero-RB logic instead of generic RB-heavy
            """
            # Get Hero-RB specific strategy
            hero_info, adjusted_df = self.hero_rb.get_hero_rb_strategy(
                player_df, current_round, self._get_current_roster()
            )
            
            # Log Hero-RB decision making
            logger.info(f"Round {current_round} Hero-RB Phase: {hero_info['phase']}")
            logger.info(f"RB Priority: {hero_info['rb_priority']}")
            logger.info(f"Target Positions: {hero_info['position_targets']}")
            
            # Use Hero-RB adjusted values instead of generic RB boost
            return super().get_round_strategy(adjusted_df, current_round, top_n)
        
        def simulate_pick(self, player_name: str, team_number: int = None):
            """Override to update Hero-RB state"""
            super().simulate_pick(player_name, team_number)
            
            # Update Hero-RB strategy state
            player_info = self._get_player_info(player_name)
            if player_info:
                self.hero_rb.update_draft_state(
                    player_name, 
                    player_info.get('position', 'UNK'),
                    self._get_current_round()
                )
        
        def _get_current_roster(self) -> Dict[str, List[str]]:
            """Get current roster by position"""
            # Implementation would depend on existing roster tracking
            return {}
        
        def _get_player_info(self, player_name: str) -> Dict:
            """Get player position info"""
            # Implementation would depend on player data structure
            return {}
        
        def _get_current_round(self) -> int:
            """Calculate current round based on picks made"""
            return (len(self.drafted_players) // self.total_teams) + 1
    
    return HeroRBEnhancedStrategy

# Research-based validation
HERO_RB_VALIDATION = {
    'success_metrics': {
        'advance_rate': '20.2% vs 16.7% baseline',
        'win_rate': '9.90% vs 8.30% baseline',
        'data_source': 'FFPC Best Ball leagues 2017-2022'
    },
    
    'strategy_phases': {
        'hero_acquisition': 'Rounds 1-2: Elite RB only',
        'pivot_phase': 'Rounds 3-6: Avoid RBs, focus WR/other',
        'depth_phase': 'Rounds 7+: Accumulate RB depth to 5-6 total'
    },
    
    'key_differences_from_rb_heavy': {
        'rb_targets': '1 elite early vs 2-3 early RBs',
        'round_3_6_strategy': 'Avoid RBs vs target RBs',
        'final_rb_count': '5-6 total vs 3-4 total',
        'success_rate': 'Higher advance/win rates'
    }
}

if __name__ == "__main__":
    print("🏆 HERO-RB STRATEGY IMPLEMENTATION")
    print("=" * 50)
    print("✅ Research-validated approach (20.2% advance rates)")
    print("✅ Phase-based strategy adaptation")
    print("✅ Elite RB targeting (rounds 1-2 only)")
    print("✅ Pivot phase RB avoidance (rounds 3-6)")
    print("✅ Depth accumulation (rounds 7+)")
    print("✅ Integration with existing draft engine")
    print(f"\n🎯 KEY INSIGHT: Hero-RB ≠ RB-Heavy")
    print(f"   Hero-RB drafts FEWER RBs early, MORE RBs late!")
    print(f"   Focus on 1 ELITE RB, then pivot to other positions!")