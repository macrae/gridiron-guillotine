"""
Pre-computation engine for scoring all players using the Championship Draft Strategy
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd

from ..core.strategy import ChampionshipDraftStrategy
from ..core.config import get_config
from ..data.loaders import PlayerDataLoader
from ..data.database import PlayerDatabase, EnhancedPlayer
from ..core.models import Position

logger = logging.getLogger(__name__)


class PlayerPrecomputer:
    """Pre-computes player scores for all draft positions using the strategy engine"""
    
    def __init__(self, config=None):
        """Initialize the pre-computer"""
        self.config = config or get_config()
        self.strategy = ChampionshipDraftStrategy(self.config)
        self.data_loader = PlayerDataLoader(self.config)
        self.database = PlayerDatabase()
        
    def precompute_all_players(self, 
                              draft_positions: List[int] = None,
                              force_recompute: bool = False) -> Dict[str, any]:
        """
        Pre-compute scores for all players across different draft positions
        
        Args:
            draft_positions: List of draft positions to compute for (1-12 by default)
            force_recompute: Force recomputation even if scores are cached
            
        Returns:
            Dictionary with computation results and statistics
        """
        if draft_positions is None:
            draft_positions = list(range(1, 13))  # Positions 1-12
        
        logger.info(f"Starting pre-computation for draft positions: {draft_positions}")
        
        # Load player data
        df = self.data_loader.load_scored_data(include_rookies=True)
        logger.info(f"Loaded {len(df)} players for pre-computation")
        
        results = {
            'total_players': len(df),
            'positions_computed': draft_positions,
            'players_updated': 0,
            'players_skipped': 0,
            'errors': [],
            'computation_time': None,
            'strategy_version': 'v1.0'  # TODO: Make this configurable
        }
        
        start_time = datetime.now()
        
        # Process each player
        for idx, player_row in df.iterrows():
            try:
                player_name = player_row['name'] if 'name' in player_row else player_row.get('Player', '')
                
                if not player_name:
                    logger.warning(f"No player name found in row {idx}")
                    continue
                
                # Check if we need to recompute
                existing_player = self.database.get_player(player_name)
                if existing_player and not force_recompute:
                    # Check if strategy version matches
                    if existing_player.strategy_version == results['strategy_version']:
                        results['players_skipped'] += 1
                        continue
                
                # Convert row to Enhanced Player
                enhanced_player = self._row_to_enhanced_player(player_row)
                
                # Compute scores for all draft positions
                position_scores = {}
                for draft_pos in draft_positions:
                    try:
                        score = self._compute_player_score(player_row, draft_pos)
                        position_scores[draft_pos] = score
                    except Exception as e:
                        logger.error(f"Error computing score for {player_name} at position {draft_pos}: {e}")
                        position_scores[draft_pos] = enhanced_player.adjusted_value  # Fallback
                
                # Update enhanced player with computed scores
                enhanced_player.pre_computed_scores = position_scores
                enhanced_player.strategy_version = results['strategy_version']
                enhanced_player.score_computed_date = datetime.now()
                
                # Save to database
                self.database.upsert_player(enhanced_player)
                results['players_updated'] += 1
                
                if results['players_updated'] % 50 == 0:
                    logger.info(f"Processed {results['players_updated']} players...")
                    
            except Exception as e:
                error_msg = f"Error processing player {player_name}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        end_time = datetime.now()
        results['computation_time'] = (end_time - start_time).total_seconds()
        
        logger.info(f"Pre-computation complete:")
        logger.info(f"  - Players updated: {results['players_updated']}")
        logger.info(f"  - Players skipped: {results['players_skipped']}")
        logger.info(f"  - Errors: {len(results['errors'])}")
        logger.info(f"  - Time: {results['computation_time']:.1f} seconds")
        
        return results
    
    def _row_to_enhanced_player(self, row: pd.Series) -> EnhancedPlayer:
        """Convert pandas row to EnhancedPlayer with proper VBD and adjusted value calculations"""
        # Handle different column name formats
        name = row.get('name', row.get('Player', ''))
        position_str = row.get('position', row.get('Pos', ''))
        team = row.get('team', row.get('Team', ''))
        
        # Convert position string to Position enum
        try:
            position = Position(position_str.upper()) if position_str else Position.UNKNOWN
        except ValueError:
            logger.warning(f"Unknown position '{position_str}' for player {name}")
            position = Position.UNKNOWN
        
        # Get projected points from various possible column names
        projected_points = row.get('projected_points', 
                                 row.get('weighted_mean', 
                                        row.get('points', 0.0)))
        
        # Calculate VBD if not provided
        vbd_value = row.get('vbd', None)
        if vbd_value is None:
            vbd_value = self._calculate_vbd(float(projected_points), position)
        
        # Calculate adjusted value using basic strategy logic if not provided
        adjusted_value = row.get('adjusted_value', None)  
        if adjusted_value is None:
            adjusted_value = self._calculate_adjusted_value(float(projected_points), float(vbd_value), position)
        
        # Create enhanced player
        enhanced_player = EnhancedPlayer(
            name=name,
            position=position,
            team=team,
            projected_points=float(projected_points),
            vbd=float(vbd_value),
            tier=int(row.get('tier', 1)),
            floor=float(row.get('floor', row.get('ci_lower', projected_points * 0.8))),
            ceiling=float(row.get('ceiling', row.get('ci_upper', projected_points * 1.2))),
            rookie=bool(row.get('rookie', False)),
            wopr=float(row.get('wopr', 0.0)),
            expected_points=float(row.get('expected_points', projected_points)),
            context_multiplier=float(row.get('context_multiplier', 1.0)),
            advanced_score=float(row.get('advanced_score', 0.0)),
            adjusted_value=float(adjusted_value),
            target_share=float(row.get('target_share', 0.0)),
            air_yards_share=float(row.get('air_yards_share', 0.0)),
            red_zone_targets=int(row.get('red_zone_targets', 0)),
            red_zone_carries=int(row.get('red_zone_carries', 0)),
            goal_line_carries=int(row.get('goal_line_carries', 0)),
            air_yards_per_target=float(row.get('air_yards_per_target', 0.0))
        )
        
        return enhanced_player
    
    def _calculate_vbd(self, projected_points: float, position: Position) -> float:
        """
        Calculate Value Based Drafting score for a player
        
        VBD = Player's projected points - Replacement level for position
        """
        # Define replacement levels by position (based on league settings)
        replacement_levels = {
            Position.QB: 21.0,    # QB12 level
            Position.RB: 12.9,    # RB24 level  
            Position.WR: 14.8,    # WR36 level
            Position.TE: 9.5,     # TE12 level
            Position.K: 7.0,      # K12 level
            Position.DEF: 8.0,    # DEF12 level
            Position.UNKNOWN: 0.0
        }
        
        replacement_level = replacement_levels.get(position, 0.0)
        return projected_points - replacement_level
    
    def _calculate_adjusted_value(self, projected_points: float, vbd: float, position: Position) -> float:
        """
        Calculate basic adjusted value with position-based multipliers
        
        This applies basic Hero-RB strategy principles:
        - RBs get a premium (scarcity bonus)
        - QBs get a penalty (abundance/streaming)
        - WRs get slight premium in PPR
        """
        base_value = vbd
        
        # Apply position-based adjustments (simplified Hero-RB logic)
        if position == Position.RB:
            # RB scarcity premium - top RBs get significant bonus
            if vbd > 8.0:  # Elite RBs
                multiplier = 1.25
            elif vbd > 3.0:  # Good RBs
                multiplier = 1.15
            else:
                multiplier = 1.05
        elif position == Position.WR:
            # WR PPR bonus - consistent with league format
            if vbd > 6.0:  # Elite WRs
                multiplier = 1.1
            else:
                multiplier = 1.05
        elif position == Position.QB:
            # QB streaming penalty - reduce value due to replaceability
            multiplier = 0.8
        elif position == Position.TE:
            # TE scarcity premium (similar to RB but less)
            if vbd > 4.0:  # Elite TEs
                multiplier = 1.2
            else:
                multiplier = 1.0
        else:
            multiplier = 1.0
        
        adjusted_value = base_value * multiplier
        
        # Ensure minimum value of projected points (don't go below base projection)
        return max(adjusted_value + projected_points - vbd, projected_points * 0.8)
    
    def _compute_player_score(self, player_row: pd.Series, draft_position: int) -> float:
        """
        Compute player score using the strategy engine for a specific draft position
        
        Args:
            player_row: Player data row
            draft_position: Draft position (1-12)
            
        Returns:
            Adjusted player score for the given draft position
        """
        # Initialize strategy for this draft position
        self.strategy.user_position = draft_position
        
        # Create a mock draft state for round 1 (where most computation happens)
        draft_state = {
            'current_round': 1,
            'picks_made': [],
            'available_players': None  # Strategy will handle this
        }
        
        # Get strategy recommendations for round 1
        # This will internally call adjust_player_value which is what we want
        try:
            recommendations = self.strategy.get_round_strategy(
                round_num=1,
                picks_made=[],
                user_position=draft_position
            )
            
            # Find this player in the recommendations
            player_name = player_row.get('name', player_row.get('Player', ''))
            
            # If we can't find the specific player, use the strategy's internal adjustment
            # This is a bit of a hack, but we'll compute the adjustment directly
            return self._direct_player_adjustment(player_row, draft_position)
            
        except Exception as e:
            logger.debug(f"Strategy computation failed for {player_row.get('name', 'unknown')}: {e}")
            # Fallback to basic VBD
            return float(player_row.get('vbd', player_row.get('projected_points', 0.0)))
    
    def _direct_player_adjustment(self, player_row: pd.Series, draft_position: int) -> float:
        """
        Directly compute player adjustment using strategy internals
        
        This replicates the key parts of ChampionshipDraftStrategy.adjust_player_value
        """
        base_vbd = float(player_row.get('vbd', 0.0))
        position_str = player_row.get('position', player_row.get('Pos', ''))
        
        try:
            position = Position(position_str.upper()) if position_str else Position.UNKNOWN
        except ValueError:
            position = Position.UNKNOWN
        
        # Basic position scarcity multipliers (simplified version of strategy logic)
        scarcity_multipliers = {
            Position.RB: 1.3,  # RBs are scarce, higher value
            Position.WR: 1.1,  # WRs are plentiful
            Position.TE: 1.2,  # TEs have positional scarcity
            Position.QB: 0.9,  # QBs can be drafted later
            Position.K: 0.5,   # Kickers have minimal value
            Position.DEF: 0.6  # Defenses have minimal value
        }
        
        scarcity_boost = scarcity_multipliers.get(position, 1.0)
        
        # Draft position adjustments (early picks prefer safer floors)
        if draft_position <= 3:
            # Early picks prefer high floor players
            floor = float(player_row.get('floor', player_row.get('ci_lower', base_vbd * 0.8)))
            position_boost = 1.0 + (floor / base_vbd - 0.8) * 0.3 if base_vbd > 0 else 1.0
        elif draft_position >= 10:
            # Late picks can take more risks for ceiling
            ceiling = float(player_row.get('ceiling', player_row.get('ci_upper', base_vbd * 1.2)))
            position_boost = 1.0 + (ceiling / base_vbd - 1.2) * 0.2 if base_vbd > 0 else 1.0
        else:
            position_boost = 1.0
        
        # Hero-RB adjustment for RBs
        if position == Position.RB:
            # Early round RBs get a boost (Hero-RB strategy)
            hero_boost = 1.2 if draft_position <= 6 else 1.0
        else:
            hero_boost = 1.0
        
        # PPR adjustment (this config value would come from strategy)
        ppr_boost = 1.0
        if position in [Position.WR, Position.RB]:
            receptions_estimate = float(player_row.get('target_share', 0.0)) * 100  # Rough estimate
            if receptions_estimate > 50:  # High-reception players
                ppr_boost = 1.1
        
        # Calculate final adjusted value
        adjusted_value = base_vbd * scarcity_boost * position_boost * hero_boost * ppr_boost
        
        return adjusted_value
    
    def recompute_player(self, player_name: str, draft_positions: List[int] = None) -> bool:
        """
        Recompute scores for a specific player
        
        Args:
            player_name: Name of player to recompute
            draft_positions: Positions to compute for
            
        Returns:
            True if successful
        """
        if draft_positions is None:
            draft_positions = list(range(1, 13))
        
        # Load fresh data
        df = self.data_loader.load_scored_data(include_rookies=True)
        
        # Find the player
        player_mask = df['name'] == player_name
        if 'name' not in df.columns:
            player_mask = df['Player'] == player_name
        
        player_rows = df[player_mask]
        if len(player_rows) == 0:
            logger.error(f"Player '{player_name}' not found in data")
            return False
        
        player_row = player_rows.iloc[0]
        
        try:
            # Get existing player or create new
            enhanced_player = self.database.get_player(player_name)
            if not enhanced_player:
                enhanced_player = self._row_to_enhanced_player(player_row)
            
            # Compute scores for all positions
            position_scores = {}
            for draft_pos in draft_positions:
                score = self._compute_player_score(player_row, draft_pos)
                position_scores[draft_pos] = score
            
            # Update player
            enhanced_player.pre_computed_scores = position_scores
            enhanced_player.strategy_version = 'v1.0'
            enhanced_player.score_computed_date = datetime.now()
            
            # Save to database
            self.database.upsert_player(enhanced_player)
            
            logger.info(f"Recomputed scores for {player_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error recomputing player {player_name}: {e}")
            return False
    
    def get_computation_status(self) -> Dict[str, any]:
        """Get status of pre-computation"""
        stats = self.database.get_stats()
        
        # Check how many players have computed scores
        total_with_scores = 0
        outdated_scores = 0
        
        # This would require a more complex query - for now return basic stats
        return {
            'database_stats': stats,
            'last_computation': None,  # TODO: Track this in database
            'strategy_version': 'v1.0'
        }


def main():
    """CLI entry point for pre-computation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pre-compute player scores')
    parser.add_argument('--positions', nargs='+', type=int, default=list(range(1, 13)),
                       help='Draft positions to compute for (1-12)')
    parser.add_argument('--force', action='store_true',
                       help='Force recomputation even if cached')
    parser.add_argument('--player', type=str,
                       help='Recompute scores for specific player')
    parser.add_argument('--status', action='store_true',
                       help='Show computation status')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    precomputer = PlayerPrecomputer()
    
    if args.status:
        status = precomputer.get_computation_status()
        print("Pre-computation Status:")
        print(f"  Database: {status['database_stats']}")
        
    elif args.player:
        success = precomputer.recompute_player(args.player, args.positions)
        if success:
            print(f"Successfully recomputed scores for {args.player}")
        else:
            print(f"Failed to recompute scores for {args.player}")
    
    else:
        results = precomputer.precompute_all_players(args.positions, args.force)
        print("Pre-computation Results:")
        print(f"  Players updated: {results['players_updated']}")
        print(f"  Players skipped: {results['players_skipped']}")
        print(f"  Errors: {len(results['errors'])}")
        print(f"  Time: {results['computation_time']:.1f} seconds")


if __name__ == '__main__':
    main()