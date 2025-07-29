"""
Championship Draft Strategy Engine
Research-validated Hero-RB strategy with PPR optimization and advanced metrics
Based on championship analysis showing 20.2% advance rates vs 16.7% baseline
Integrates Hero-RB + PPR + WOPR + Expected Fantasy Points + Position Flexibility
"""
import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# Configuration constants
POSITION_LIMITS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1, 'K': 1, 'DEF': 1}
DEFAULT_TOTAL_TEAMS = 12
DEFAULT_NUM_ROUNDS = 15

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChampionshipDraftStrategy:
    """
    Research-validated Championship Draft Strategy Engine
    Implements Hero-RB strategy (20.2% advance rate vs 16.7% baseline)
    Includes PPR optimization, advanced metrics, and position flexibility
    """
    
    def __init__(self, draft_position: int, total_teams: int = DEFAULT_TOTAL_TEAMS, 
                 position_limits: Dict[str, int] = None, league_settings: Dict = None):
        self.draft_position = draft_position
        self.total_teams = total_teams
        self.position_limits = position_limits or POSITION_LIMITS.copy()
        self.league_settings = league_settings or {'ppr': True, 'teams': 12}
        self.draft_state = self._initialize_draft_state()
        self.drafted_players = set()
        
        # Hero-RB Strategy State (Research: 20.2% advance rate)
        self.hero_rb_acquired = False
        self.total_rbs_drafted = 0
        self.hero_rb_phase = "hero_acquisition"  # hero_acquisition, pivot_phase, depth_phase
        
        # Research-validated Elite RB targets for Hero selection
        self.elite_hero_rbs = [
            'McCaffrey, Christian',  # Research: Ultimate pass-catching back
            'Kamara, Alvin',        # Research: PPR specialist
            'Achane, De\'Von',      # Research: Emerging elite talent
            'Taylor, Jonathan',     # Research: Proven workhorse
            'Gibbs, Jahmyr',        # Research: Detroit offensive weapon
            'Barkley, Saquon',      # Research: Elite talent in premier system
            'Henry, Derrick'        # Research: Volume monster (but PPR penalty)
        ]
        
        # PPR-specific player adjustments (Research: 6-8 weekly point advantage)
        self.ppr_pass_catchers = {
            'McCaffrey, Christian': 3.0,   # Research: Massive PPR boost
            'Kamara, Alvin': 3.0,         # Research: Reception specialist  
            'Ekeler, Austin': 2.5,        # Research: PPR value
            'Achane, De\'Von': 2.0,       # Research: Receiving upside
            'Gibbs, Jahmyr': 2.0          # Research: Pass-catching role
        }
        
        self.ppr_pure_rushers = {
            'Henry, Derrick': -1.5,       # Research: Reduced PPR value
            'Chubb, Nick': -1.0,          # Research: Limited receiving
            'Jones, Aaron': -0.5          # Research: Traditional back
        }
        
        # Advanced Metrics Configuration (Research: WOPR = 0.746 R² correlation)
        self.wopr_weights = {
            'target_share': 1.5,     # Primary component  
            'air_yards_share': 0.7   # Secondary component
        }
        
        # Research-based offensive rankings (2025 projections)
        self.elite_offenses = [
            'Buffalo', 'Miami', 'Kansas City', 'Cincinnati', 'Baltimore',
            'San Francisco', 'Detroit', 'Philadelphia', 'Dallas', 'LA Rams',
            'Minnesota', 'Green Bay', 'Houston', 'Atlanta'  # Top 14
        ]
        
        self.bottom_offenses = [
            'Carolina', 'New England', 'Chicago', 'Denver', 'NY Giants',
            'Las Vegas', 'Tennessee', 'Jacksonville', 'Arizona', 'Cleveland'
        ]
        
        # Draft Position Strategy Configuration (Research-based)
        self.position_strategies = {
            'early': [1, 2, 3],         # Positions 1-3: Target elite WRs
            'middle': [4, 5, 6, 7, 8],  # Positions 4-8: Optimal flexibility  
            'late': [9, 10, 11, 12]     # Positions 9-12: Back-to-back advantage
        }
        
        # Research-validated elite targets by draft position
        self.position_targets = {
            'early_rd1': ['Chase, Ja\'Marr', 'Jefferson, Justin', 'Hill, Tyreek'],
            'middle_rd1': ['Gibbs, Jahmyr', 'Thomas Jr., Brian', 'Nacua, Puka'],
            'late_rd1': ['Collins, Nico', 'St. Brown, Amon-Ra', 'Metcalf, DK', 'Cooper, Amari'],
            'late_rd2': ['St. Brown, Amon-Ra', 'Thomas Jr., Brian', 'Wilson, Garrett'],
            'late_rd3': ['Hall, Breece', 'Pollard, Tony', 'Mostert, Raheem']
        }
        
        logger.info(f"Championship strategy initialized for position {draft_position} (Hero-RB + Advanced Metrics + Position Logic enabled)")
    
    def _initialize_draft_state(self) -> Dict:
        """Initialize draft state with empty rosters for all teams"""
        rosters = {}
        for i in range(1, self.total_teams + 1):
            rosters[f'Team{i}'] = {pos: [] for pos in self.position_limits.keys()}
        
        return {
            'rosters': rosters,
            'draft_position': self.draft_position,
            'total_teams': self.total_teams,
            'current_pick': 0,
            'current_round': 1
        }
    
    def calculate_positional_scarcity(self, player_df: pd.DataFrame, vbd_column: str = 'vbd') -> Dict[str, float]:
        """
        Calculate positional scarcity factors based on VBD distribution
        Higher scarcity = more valuable to draft early
        """
        scarcity_factors = {}
        available_players = player_df[~player_df['name'].isin(self.drafted_players)]
        
        for position in self.position_limits.keys():
            pos_players = available_players[available_players['position'] == position]
            
            if len(pos_players) == 0:
                scarcity_factors[position] = 1.0
                continue
            
            # Calculate scarcity based on VBD distribution and remaining draft capital
            total_needed = self.position_limits[position] * self.total_teams
            available_count = len(pos_players)
            
            if available_count == 0:
                scarcity_factors[position] = 2.0  # Maximum scarcity
            else:
                # Higher scarcity when fewer quality players available
                quality_threshold = pos_players[vbd_column].quantile(0.6)
                quality_count = len(pos_players[pos_players[vbd_column] >= quality_threshold])
                scarcity_ratio = total_needed / max(quality_count, 1)
                scarcity_factors[position] = min(2.0, max(0.5, scarcity_ratio))
        
        # Hero-RB scarcity adjustments (Research-based)
        if 'RB' in scarcity_factors:
            if self.hero_rb_phase == "hero_acquisition":
                scarcity_factors['RB'] *= 1.5  # Boost elite RB scarcity
            elif self.hero_rb_phase == "pivot_phase":
                scarcity_factors['RB'] *= 0.6  # Reduce RB scarcity (avoid RB2 trap)
            else:  # depth_phase
                scarcity_factors['RB'] *= 1.3  # Boost RB depth scarcity
        
        logger.debug(f"Hero-RB Phase: {self.hero_rb_phase}, Scarcity factors: {scarcity_factors}")
        return scarcity_factors
    
    def initialize_tiers(self, player_df: pd.DataFrame, tier_dropoff_percentage: float = 0.2) -> pd.DataFrame:
        """Initialize player tiers based on VBD dropoffs within each position"""
        player_df = player_df.copy()
        player_df['tier'] = 1
        
        for position in player_df['position'].unique():
            pos_players = player_df[player_df['position'] == position].sort_values('vbd', ascending=False)
            
            if len(pos_players) < 2:
                continue
            
            current_tier = 1
            for i in range(1, len(pos_players)):
                current_vbd = pos_players.iloc[i]['vbd']
                previous_vbd = pos_players.iloc[i-1]['vbd']
                
                # Check for significant dropoff
                if previous_vbd > 0 and (previous_vbd - current_vbd) / previous_vbd > tier_dropoff_percentage:
                    current_tier += 1
                
                player_df.loc[pos_players.iloc[i].name, 'tier'] = current_tier
        
        return player_df
    
    def calculate_tier_dropoffs(self, player_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate how close we are to tier dropoffs for each position"""
        tier_dropoffs = {}
        available_players = player_df[~player_df['name'].isin(self.drafted_players)]
        
        for position in self.position_limits.keys():
            pos_players = available_players[available_players['position'] == position]
            
            if len(pos_players) == 0:
                tier_dropoffs[position] = 0.0
                continue
            
            # Find the next tier boundary
            current_best_tier = pos_players['tier'].min()
            next_tier_players = pos_players[pos_players['tier'] == current_best_tier + 1]
            
            if len(next_tier_players) > 0:
                # Calculate urgency based on how many top-tier players remain
                top_tier_count = len(pos_players[pos_players['tier'] == current_best_tier])
                tier_dropoffs[position] = max(0.0, 1.0 - top_tier_count / 3.0)  # Urgency increases as fewer remain
            else:
                tier_dropoffs[position] = 0.0
        
        return tier_dropoffs
    
    def calculate_dynamic_vbd(self, player_df: pd.DataFrame) -> pd.DataFrame:
        """Recalculate VBD based on current available players"""
        player_df = player_df.copy()
        available_players = player_df[~player_df['name'].isin(self.drafted_players)]
        
        for position in available_players['position'].unique():
            pos_players = available_players[available_players['position'] == position]
            
            if len(pos_players) == 0:
                continue
            
            # Find replacement level (bottom starter for this position)
            num_starters = self.position_limits.get(position, 1) * self.total_teams
            if len(pos_players) >= num_starters:
                replacement_points = pos_players.nsmallest(num_starters, 'projected_points')['projected_points'].iloc[-1]
            else:
                replacement_points = pos_players['projected_points'].min()
            
            # Update VBD for this position
            mask = (player_df['position'] == position) & (~player_df['name'].isin(self.drafted_players))
            player_df.loc[mask, 'vbd'] = player_df.loc[mask, 'projected_points'] - replacement_points
        
        return player_df
    
    def calculate_wopr(self, player_data: pd.DataFrame) -> pd.Series:
        """
        WOPR = 1.5 × (Target Share) + 0.7 × (Air Yards Share)
        Research: 0.746 R² correlation - most predictive WR metric
        """
        wopr_scores = []
        
        for _, player in player_data.iterrows():
            if player.get('position') == 'WR':
                target_share = player.get('target_share', 0) / 100  # Convert percentage
                air_yards_share = player.get('air_yards_share', 0) / 100
                
                wopr = (self.wopr_weights['target_share'] * target_share + 
                       self.wopr_weights['air_yards_share'] * air_yards_share)
                
                wopr_scores.append(wopr)
            else:
                wopr_scores.append(0)  # Non-WRs get 0 WOPR
                
        return pd.Series(wopr_scores, index=player_data.index)
    
    def calculate_expected_fantasy_points(self, player_data: pd.DataFrame) -> pd.Series:
        """
        Expected Fantasy Points based on opportunity metrics
        Research: "Most predictive stat I've ever seen" - Scott Barrett (PFF)
        """
        expected_points = []
        
        for _, player in player_data.iterrows():
            position = player.get('position')
            base_projection = player.get('projected_points', 0)
            
            # Situational adjustments based on research
            adjustments = 0
            
            # Red zone opportunity boost
            red_zone_targets = player.get('red_zone_targets', 0)
            red_zone_carries = player.get('red_zone_carries', 0)
            adjustments += (red_zone_targets * 0.8) + (red_zone_carries * 1.2)
            
            # Air yards adjustment (deep target value)
            air_yards = player.get('air_yards_per_target', 0)
            if position == 'WR' and air_yards > 12:  # Deep threat bonus
                adjustments += air_yards * 0.1
                
            # Goal line carries (RB specific)
            if position == 'RB':
                goal_line_carries = player.get('goal_line_carries', 0)
                adjustments += goal_line_carries * 2.5  # High TD probability
                
            expected_points.append(base_projection + adjustments)
            
        return pd.Series(expected_points, index=player_data.index)
    
    def calculate_offensive_context_multiplier(self, player_data: pd.DataFrame) -> pd.Series:
        """
        Research: Target players in top-14 NFL offenses regardless of talent
        Only 2 of 9 top-36 WRs in bottom-10 offenses met expectations
        """
        multipliers = []
        
        for _, player in player_data.iterrows():
            team = player.get('team', '')
            
            if team in self.elite_offenses:
                multiplier = 1.15  # 15% boost for elite offense (research-validated)
            elif team in self.bottom_offenses:
                multiplier = 0.85  # 15% penalty for bottom offenses (research shows major underperformance)
            else:
                multiplier = 1.0   # Neutral for middle-tier offenses
                
            multipliers.append(multiplier)
            
        return pd.Series(multipliers, index=player_data.index)
    
    def apply_advanced_metrics(self, player_data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all advanced metrics to player data
        Integrates WOPR, Expected Points, and Offensive Context
        """
        data = player_data.copy()
        
        # Calculate individual advanced metrics
        data['wopr'] = self.calculate_wopr(data)
        data['expected_points'] = self.calculate_expected_fantasy_points(data)
        data['context_multiplier'] = self.calculate_offensive_context_multiplier(data)
        
        # Create composite advanced score
        data['advanced_score'] = (
            data['expected_points'] * 
            data['context_multiplier'] * 
            (1 + data['wopr'] * 0.1)  # WOPR as 10% modifier
        )
        
        logger.debug(f"Applied advanced metrics to {len(data)} players")
        return data
    
    def _determine_hero_rb_phase(self, current_round: int) -> str:
        """
        Determine Hero-RB phase based on research
        Research: Hero-RB strategy phases for optimal execution
        """
        if current_round <= 2 and not self.hero_rb_acquired:
            return "hero_acquisition"  # Must get hero RB in rounds 1-2
        elif current_round <= 6:
            return "pivot_phase"       # Rounds 3-6: avoid RBs, focus other positions
        else:
            return "depth_phase"       # Rounds 7+: accumulate RB depth
    
    def get_draft_position_category(self) -> str:
        """Determine draft position category for strategy application"""
        if self.draft_position in self.position_strategies['early']:
            return 'early'
        elif self.draft_position in self.position_strategies['middle']:
            return 'middle'
        else:
            return 'late'
    
    def get_position_specific_guidance(self, current_round: int) -> Dict:
        """
        Get research-based strategy guidance by draft position
        Research: Different approaches for early/middle/late positions
        """
        position_category = self.get_draft_position_category()
        
        if position_category == 'early':
            return self._early_position_strategy(current_round)
        elif position_category == 'middle':
            return self._middle_position_strategy(current_round)
        else:
            return self._late_position_strategy(current_round)
    
    def _early_position_strategy(self, round_num: int) -> Dict:
        """
        Early positions (1-3): Target elite WRs
        Research: Ja'Marr Chase consensus #1 overall for 2025
        """
        if round_num == 1:
            return {
                'priority': ['Elite WR', 'Elite RB if WR run'],
                'targets': self.position_targets['early_rd1'],
                'avoid': ['Reaching for QB/TE'],
                'strategy': 'Premium position focus - avoid reaches'
            }
        elif round_num == 2:
            return {
                'priority': ['Complement R1 pick', 'Best available skill position'],
                'strategy': 'Hero-RB if took WR R1, elite WR if took RB R1',
                'avoid': ['QB before round 6']
            }
        else:
            return {
                'priority': ['BPA skill positions'], 
                'avoid': ['QB before round 6'],
                'strategy': 'Value-based selections without positional reaches'
            }
    
    def _middle_position_strategy(self, round_num: int) -> Dict:
        """
        Middle positions (4-8): Optimal flexibility
        Research: Allow managers to target BPA without reaching
        """
        if round_num <= 2:
            return {
                'priority': ['True BPA approach'],
                'targets': self.position_targets['middle_rd1'],
                'strategy': 'Take advantage of positional flexibility',
                'advantage': 'Can pivot based on board without reaching'
            }
        else:
            return {
                'priority': ['Value-based selections'], 
                'avoid': ['Positional reaches'],
                'strategy': 'Maintain flexibility throughout draft'
            }
    
    def _late_position_strategy(self, round_num: int) -> Dict:
        """
        Late positions (9-12): Back-to-back picks advantage
        Research: CBS example - Collins (1.12), St. Brown (2.1), Hall (3.12)
        """
        if round_num <= 3:
            target_key = f'late_rd{round_num}'
            targets = self.position_targets.get(target_key, [])
            
            return {
                'priority': ['PPR-focused pairs', 'Complementary skill sets'],
                'example': 'Collins (1.12) + St. Brown (2.1) + Hall (3.12) for target volume',
                'strategy': 'Leverage consecutive picks for strategic pairs',
                'specific_targets': targets,
                'advantage': 'Back-to-back picks allow coordinated selections'
            }
        else:
            return {
                'priority': ['Late-round value'], 
                'focus': 'Lottery tickets with back-to-back advantage',
                'strategy': 'Continue leveraging pick proximity'
            }
    
    def apply_position_specific_adjustments(self, player: pd.Series, current_round: int) -> float:
        """
        Apply draft position specific value adjustments
        Research: Different strategies for early/middle/late positions
        """
        position_category = self.get_draft_position_category()
        player_name = player.get('name', '')
        player_position = player.get('position', '')
        adjustment = 0.0
        
        # Early positions (1-3): Elite WR focus
        if position_category == 'early':
            if current_round <= 2:
                # Boost for research-validated elite WR targets
                if any(target in player_name for target in self.position_targets['early_rd1']):
                    adjustment += 2.0  # Major boost for elite WRs
                # Slight penalty for reaching on QB/TE early
                elif player_position in ['QB', 'TE'] and current_round == 1:
                    adjustment -= 1.0
        
        # Middle positions (4-8): BPA flexibility
        elif position_category == 'middle':
            if current_round <= 2:
                # Boost for middle-round research targets
                if any(target in player_name for target in self.position_targets['middle_rd1']):
                    adjustment += 1.5  # Moderate boost for value targets
                # No penalties - maintain flexibility
        
        # Late positions (9-12): PPR pairs and back-to-back advantage
        else:
            if current_round <= 3:
                target_key = f'late_rd{current_round}'
                targets = self.position_targets.get(target_key, [])
                
                # Major boost for research-validated late position targets
                if any(target in player_name for target in targets):
                    adjustment += 2.5  # Largest boost for strategic pairs
                
                # PPR-specific boost for high-target players in late positions
                if player_position == 'WR' and current_round <= 2:
                    adjustment += 1.0  # PPR advantage with back-to-back picks
        
        return adjustment
    
    def adjust_player_value(self, player: pd.Series, scarcity_factors: Dict[str, float], 
                          tier_dropoffs: Dict[str, float], my_roster: Dict[str, List[str]], 
                          current_round: int) -> float:
        """
        Comprehensive player value adjustment considering multiple factors
        Optimized for RB-focused strategy
        """
        base_value = player.get('vbd', 0)
        position = player['position']
        
        # Scarcity boost
        scarcity_boost = scarcity_factors.get(position, 1.0)
        
        # Tier urgency boost
        tier_urgency = tier_dropoffs.get(position, 0.0)
        tier_boost = tier_urgency * 0.3  # Up to 30% boost for tier urgency
        
        # Hero-RB Strategy Boost (Research: 20.2% advance rate)
        position_boost = 1.0
        hero_phase = self._determine_hero_rb_phase(current_round)
        
        if position == 'RB':
            if hero_phase == "hero_acquisition":
                # Massive boost for elite Hero RBs only
                if player['name'] in self.elite_hero_rbs:
                    position_boost = 1.8  # 80% boost for hero candidates
                else:
                    position_boost = 0.7  # Penalty for non-elite RBs
            elif hero_phase == "pivot_phase":
                # Research key: AVOID RBs in rounds 3-6
                position_boost = 0.4  # Heavy penalty during pivot
            else:  # depth_phase
                position_boost = 1.4  # Boost for RB depth accumulation
                
        elif position == 'WR':
            if hero_phase == "hero_acquisition":
                position_boost = 1.0  # Neutral if no Hero RB yet
            elif hero_phase == "pivot_phase":
                position_boost = 1.3  # Major boost during pivot phase
            else:  # depth_phase
                position_boost = 1.1  # Moderate boost for WR depth
                
        elif position in ['K', 'DEF']:
            # Always penalize K/DEF early (research-validated)
            if current_round < 13:
                position_boost = 0.3
        
        # Roster need boost
        roster_need_boost = 1.0
        position_count = len(my_roster.get(position, []))
        position_limit = self.position_limits.get(position, 1)
        
        if position_count == 0:
            roster_need_boost = 1.5  # High boost for unfilled positions
        elif position_count < position_limit:
            roster_need_boost = 1.2  # Moderate boost for partially filled
        else:
            roster_need_boost = 0.8  # Penalty for filled positions
        
        # Upside/ceiling boost for high-variance players
        upside_boost = 1.0
        if 'ceiling' in player and 'floor' in player:
            ceiling = player.get('ceiling', player.get('projected_points', 0))
            floor = player.get('floor', player.get('projected_points', 0))
            projected_points = player.get('projected_points', 0)
            
            if projected_points > 0:
                variance = (ceiling - floor) / projected_points
                upside_boost = 1 + min(0.2, variance * 0.1)  # Up to 20% boost for high-variance players
        
        # Rookie boost in later rounds
        rookie_boost = 1.0
        if player.get('rookie', False) and current_round > 10:
            rookie_boost = 1.1
        
        # PPR adjustments (Research: 6-8 weekly point advantage)
        ppr_boost = 0
        if self.league_settings.get('ppr', True):
            player_name = player.get('name', '')
            
            # Pass-catching RB bonuses (Research: massive PPR value)
            for name, bonus in self.ppr_pass_catchers.items():
                if name.split(',')[0] in player_name:
                    ppr_boost += bonus
                    break
            
            # Pure rusher penalties (Research: reduced PPR value) 
            for name, penalty in self.ppr_pure_rushers.items():
                if name.split(',')[0] in player_name:
                    ppr_boost += penalty  # penalty is negative
                    break
            
            # General PPR position boosts
            if position == 'WR':
                ppr_boost += 1.0  # Research: WRs gain 6-8 points weekly
        
        # Advanced Metrics Integration (Research: WOPR + Expected Points + Context)
        advanced_boost = 0
        if 'advanced_score' in player:
            advanced_score = player.get('advanced_score', 0)
            projected_points = player.get('projected_points', 0)
            
            if projected_points > 0:
                # Advanced metrics provide up to 20% boost based on research validation
                advanced_ratio = advanced_score / projected_points
                advanced_boost = min(0.2, max(-0.1, (advanced_ratio - 1.0) * 0.5))
        
        # Draft Position Specific Adjustments (Research: Different strategies by position)
        position_adjustment = self.apply_position_specific_adjustments(player, current_round)
        
        # Combine all factors
        final_value = (base_value * scarcity_boost * (1 + tier_boost) * 
                      position_boost * roster_need_boost * upside_boost * rookie_boost * 
                      (1 + advanced_boost)) + ppr_boost + position_adjustment
        
        return max(0, final_value)
    
    def get_round_strategy(self, player_df: pd.DataFrame, current_round: int, 
                          top_n: int = 12) -> pd.DataFrame:
        """
        Generate strategy for a specific round with comprehensive player evaluation
        Integrates Hero-RB + PPR + Advanced Metrics for championship-level analysis
        """
        # Update player data with advanced metrics
        player_df = self.calculate_dynamic_vbd(player_df)
        player_df = self.initialize_tiers(player_df)
        player_df = self.apply_advanced_metrics(player_df)
        
        # Calculate factors
        scarcity_factors = self.calculate_positional_scarcity(player_df)
        tier_dropoffs = self.calculate_tier_dropoffs(player_df)
        
        # Get my current roster
        my_roster = self.draft_state['rosters'][f'Team{self.draft_position}']
        
        # Filter available players
        available_players = player_df[~player_df['name'].isin(self.drafted_players)].copy()
        
        # Calculate adjusted values
        available_players['adjusted_value'] = available_players.apply(
            lambda row: self.adjust_player_value(row, scarcity_factors, tier_dropoffs, my_roster, current_round),
            axis=1
        )
        
        # Apply round-specific filtering
        if current_round <= 5:
            # Early rounds: Focus on RB/WR, elite TE if available
            priority_positions = ['RB', 'WR']
            if any((available_players['position'] == 'TE') & (available_players['tier'] <= 2)):
                priority_positions.append('TE')
        elif current_round <= 9:
            # Middle rounds: Add QB if needed, otherwise RB/WR depth
            priority_positions = ['RB', 'WR']
            if len(my_roster.get('QB', [])) == 0:
                priority_positions.insert(0, 'QB')  # Prioritize QB if none drafted
        elif current_round <= 12:
            # Late-middle: All positions except K/DEF
            priority_positions = ['QB', 'RB', 'WR', 'TE']
        else:
            # Final rounds: K/DEF only
            priority_positions = ['K', 'DEF']
        
        # Filter by priority and roster limits
        strategy_players = available_players[
            (available_players['position'].isin(priority_positions)) &
            (available_players.apply(lambda x: len(my_roster.get(x['position'], [])) < 
                                   self.position_limits.get(x['position'], 1), axis=1))
        ]
        
        # If not enough players, expand criteria
        if len(strategy_players) < top_n:
            remaining = available_players[~available_players.index.isin(strategy_players.index)]
            additional_needed = top_n - len(strategy_players)
            strategy_players = pd.concat([
                strategy_players, 
                remaining.nlargest(additional_needed, 'adjusted_value')
            ])
        
        # Return top players sorted by adjusted value with advanced metrics
        columns = ['name', 'position', 'team', 'projected_points', 'vbd', 'adjusted_value', 'tier']
        
        # Add advanced metrics columns if available
        if 'advanced_score' in strategy_players.columns:
            columns.extend(['advanced_score', 'wopr', 'expected_points', 'context_multiplier'])
        
        result = strategy_players.nlargest(top_n, 'adjusted_value')[columns].reset_index(drop=True)
        
        logger.info(f"Round {current_round} strategy generated with {len(result)} players")
        return result
    
    def simulate_pick(self, player_name: str, team_number: int = None):
        """Simulate a draft pick and update Hero-RB state"""
        if team_number is None:
            team_number = self.draft_position
        
        self.drafted_players.add(player_name)
        
        # Update Hero-RB state tracking
        current_round = (len(self.drafted_players) // self.total_teams) + 1
        
        # Check if this pick affects Hero-RB strategy
        if player_name in self.elite_hero_rbs:
            if current_round <= 2 and not self.hero_rb_acquired:
                self.hero_rb_acquired = True
                self.hero_rb_phase = "pivot_phase"
                logger.info(f"🏆 HERO RB ACQUIRED: {player_name} in Round {current_round}")
            
        # Count RBs drafted
        # Note: Would need player position data to properly track RB count
        
        # Update phase based on round
        if current_round >= 7:
            self.hero_rb_phase = "depth_phase"
        elif current_round >= 3:
            self.hero_rb_phase = "pivot_phase" if self.hero_rb_acquired else "hero_acquisition"
            
        logger.debug(f"Pick: {player_name} (Team{team_number}) - Hero Phase: {self.hero_rb_phase}")
    
    def generate_full_draft_strategy(self, player_df: pd.DataFrame, 
                                   num_rounds: int = DEFAULT_NUM_ROUNDS) -> List[pd.DataFrame]:
        """
        Generate complete draft strategy for all rounds
        """
        strategies = []
        
        for round_num in range(1, num_rounds + 1):
            self.draft_state['current_round'] = round_num
            round_strategy = self.get_round_strategy(player_df, round_num)
            strategies.append(round_strategy)
            
            logger.info(f"Completed strategy for round {round_num}")
        
        return strategies

def load_and_prepare_data(data_path: str = None) -> pd.DataFrame:
    """Load and prepare player data for draft strategy"""
    try:
        # Determine which data file to use (prioritize 2025 rookies)
        if data_path is None:
            import os
            if os.path.exists('scored_data_with_2025_rookies.csv'):
                data_path = 'scored_data_with_2025_rookies.csv'
                logger.info("Loading data with 2025 rookies")
            else:
                data_path = 'scored_data.csv'
                logger.info("Loading standard data (no 2025 rookies)")
        
        df = pd.read_csv(data_path)
        
        # Map columns to standard names (handle both old and new formats)
        if 'name' in df.columns:
            # New format with 2025 rookies
            column_mapping = {
                'pos': 'position', 
                'weighted_mean': 'projected_points',
                'ci_lower': 'floor',
                'ci_upper': 'ceiling'
            }
            required_source_columns = ['name', 'pos', 'weighted_mean']
        else:
            # Old format
            column_mapping = {
                'index': 'name',
                'pos': 'position', 
                'weighted_mean': 'projected_points',
                'ci_lower': 'floor',
                'ci_upper': 'ceiling'
            }
            required_source_columns = ['index', 'pos', 'weighted_mean']
        missing_columns = [col for col in required_source_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Rename columns
        df = df.rename(columns=column_mapping)
        
        # Clean up data
        df = df.dropna(subset=['name', 'position', 'projected_points'])
        df['projected_points'] = pd.to_numeric(df['projected_points'], errors='coerce')
        df = df[df['projected_points'] > 0]  # Filter out zero/negative projections
        
        # Standardize position names
        position_mapping = {
            'WR': 'WR', 'RB': 'RB', 'QB': 'QB', 'TE': 'TE', 
            'K': 'K', 'DEF': 'DEF', 'DST': 'DEF'
        }
        df['position'] = df['position'].map(position_mapping).fillna(df['position'])
        
        # Calculate VBD if not present
        if 'vbd' not in df.columns:
            logger.info("Calculating VBD...")
            df['vbd'] = 0.0
            for position in df['position'].unique():
                pos_players = df[df['position'] == position].sort_values('projected_points', ascending=False)
                if len(pos_players) > 0:
                    # Use position-specific replacement levels
                    replacement_levels = {'QB': 12, 'RB': 24, 'WR': 36, 'TE': 12, 'K': 12, 'DEF': 12}
                    replacement_idx = min(replacement_levels.get(position, 12), len(pos_players)) - 1
                    replacement_points = pos_players.iloc[replacement_idx]['projected_points']
                    df.loc[df['position'] == position, 'vbd'] = df.loc[df['position'] == position, 'projected_points'] - replacement_points
        
        # Add default values for missing optional columns
        if 'tier' not in df.columns:
            df['tier'] = 1
        if 'rookie' not in df.columns:
            df['rookie'] = False
        if 'team' not in df.columns:
            df['team'] = df.get('team', '')
            
        # Ensure floor and ceiling exist
        if 'floor' not in df.columns:
            df['floor'] = df['projected_points'] * 0.8
        if 'ceiling' not in df.columns:
            df['ceiling'] = df['projected_points'] * 1.2
            
        logger.info(f"Loaded {len(df)} players for draft strategy")
        return df
        
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

def main():
    """Demo of live draft strategy capabilities - NO static files generated"""
    logger.info("🎯 Live Draft Strategy Demo - Dynamic Recommendations Only")
    
    # Load player data
    try:
        player_data = load_and_prepare_data()
    except:
        logger.error("Could not load player data. Please ensure scored_data.csv exists.")
        return
    
    logger.info(f"Loaded {len(player_data)} players for live draft strategy")
    
    # Initialize championship draft strategy for position 4 (configurable)
    draft_strategy = ChampionshipDraftStrategy(draft_position=4, total_teams=12)
    
    # Show Round 1 live recommendations 
    print("\n🔴 ROUND 1 LIVE RECOMMENDATIONS (Top 12 available):")
    print("=" * 65)
    
    round1_strategy = draft_strategy.get_round_strategy(player_data, current_round=1)
    for i, (_, player) in enumerate(round1_strategy.head(12).iterrows(), 1):
        print(f"{i:2d}. {player['name']:25s} ({player['position']}, {player['team']:12s}) Value: {player['adjusted_value']:.1f}")
    
    print(f"\n💡 LIVE DRAFT USAGE:")
    print(f"   🚀 Use: python live_draft_monitor.py (for real Yahoo integration)")  
    print(f"   🎬 Use: python quick_demo.py (to see live strategy updates)")
    print(f"   📊 Use: streamlit run streamlit_app/app.py (for dashboard)")
    print(f"\n✅ NO STATIC FILES GENERATED - Live draft system ready!")
    print(f"🏆 Strategy engine optimized for real-time recommendations!")

# Compatibility alias for existing integrations
DraftStrategy = ChampionshipDraftStrategy

if __name__ == "__main__":
    main()