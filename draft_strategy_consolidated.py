"""
Consolidated Draft Strategy Engine
Combines the best features from v1, v1.1, and v2 with additional improvements
Optimized for RB-focused strategy and value-based drafting
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

class DraftStrategy:
    """
    Comprehensive draft strategy engine with dynamic VBD, positional scarcity,
    tier-based valuation, and RB-focused approach
    """
    
    def __init__(self, draft_position: int, total_teams: int = DEFAULT_TOTAL_TEAMS, 
                 position_limits: Dict[str, int] = None):
        self.draft_position = draft_position
        self.total_teams = total_teams
        self.position_limits = position_limits or POSITION_LIMITS.copy()
        self.draft_state = self._initialize_draft_state()
        self.drafted_players = set()
        logger.info(f"Draft strategy initialized for position {draft_position}")
    
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
        
        # Boost RB scarcity (RB-focused strategy)
        if 'RB' in scarcity_factors:
            scarcity_factors['RB'] *= 1.2
        
        logger.debug(f"Scarcity factors: {scarcity_factors}")
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
        
        # Position strategy boost (RB-focused)
        position_boost = 1.0
        if position == 'RB':
            # Heavy RB boost in early-mid rounds
            if current_round <= 8:
                position_boost = 1.4
            elif current_round <= 12:
                position_boost = 1.2
        elif position == 'WR':
            # Moderate WR boost
            if current_round <= 6:
                position_boost = 1.1
        elif position in ['K', 'DEF']:
            # Penalize K/DEF early
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
        
        # Combine all factors
        final_value = (base_value * scarcity_boost * (1 + tier_boost) * 
                      position_boost * roster_need_boost * upside_boost * rookie_boost)
        
        return max(0, final_value)
    
    def get_round_strategy(self, player_df: pd.DataFrame, current_round: int, 
                          top_n: int = 12) -> pd.DataFrame:
        """
        Generate strategy for a specific round with comprehensive player evaluation
        """
        # Update player data
        player_df = self.calculate_dynamic_vbd(player_df)
        player_df = self.initialize_tiers(player_df)
        
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
        
        # Return top players sorted by adjusted value
        result = strategy_players.nlargest(top_n, 'adjusted_value')[
            ['name', 'position', 'team', 'projected_points', 'vbd', 'adjusted_value', 'tier']
        ].reset_index(drop=True)
        
        logger.info(f"Round {current_round} strategy generated with {len(result)} players")
        return result
    
    def simulate_pick(self, player_name: str, team_number: int = None):
        """Simulate a draft pick"""
        if team_number is None:
            team_number = self.draft_position
        
        self.drafted_players.add(player_name)
        logger.debug(f"Player {player_name} drafted by Team{team_number}")
    
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

def load_and_prepare_data(data_path: str = 'scored_data.csv') -> pd.DataFrame:
    """Load and prepare player data for draft strategy"""
    try:
        df = pd.read_csv(data_path, index_col=0)  # First column is row numbers
        
        # Map columns to standard names
        column_mapping = {
            'index': 'name',
            'pos': 'position', 
            'weighted_mean': 'projected_points',
            'ci_lower': 'floor',
            'ci_upper': 'ceiling'
        }
        
        # Check if required columns exist
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
    """Example usage of the consolidated draft strategy"""
    # Load player data
    try:
        player_data = load_and_prepare_data()
    except:
        logger.error("Could not load player data. Please ensure scored_data.csv exists.")
        return
    
    # Initialize draft strategy for position 4
    draft_strategy = DraftStrategy(draft_position=4, total_teams=12)
    
    # Generate strategy for round 1
    round1_strategy = draft_strategy.get_round_strategy(player_data, current_round=1)
    print("Round 1 Strategy (Top 12 picks):")
    print(round1_strategy.to_string(index=False))
    
    # Generate full draft strategy
    logger.info("Generating full draft strategy...")
    full_strategy = draft_strategy.generate_full_draft_strategy(player_data)
    
    # Save strategies to CSV files
    for i, strategy in enumerate(full_strategy, 1):
        filename = f'draft_strategy_round_{i}.csv'
        strategy.to_csv(filename, index=False)
        logger.info(f"Round {i} strategy saved to {filename}")
    
    print(f"\nGenerated strategies for {len(full_strategy)} rounds")
    print("Strategy files saved with prefix 'draft_strategy_round_'")

if __name__ == "__main__":
    main()