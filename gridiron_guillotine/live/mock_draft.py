"""
Interactive Mock Draft Simulator for testing draft strategy
"""

import random
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from copy import deepcopy

from ..core.strategy import ChampionshipDraftStrategy
from ..core.models import DraftPick, DraftState, LeagueSettings, Position, Player
from ..core.config import Config, get_config
from ..data.loaders import PlayerDataLoader
from ..data.database import PlayerDatabase

logger = logging.getLogger(__name__)


@dataclass
class MockTeam:
    """Represents a team in the mock draft"""
    team_id: int
    team_name: str
    drafted_players: List[Player] = field(default_factory=list)
    strategy_type: str = "balanced"
    is_user: bool = False
    
    def get_roster_needs(self) -> Dict[str, int]:
        """Calculate what positions this team still needs"""
        current_positions = {}
        for player in self.drafted_players:
            pos = player.position.value
            current_positions[pos] = current_positions.get(pos, 0) + 1
        
        # Standard roster needs
        needs = {
            'QB': max(0, 2 - current_positions.get('QB', 0)),
            'RB': max(0, 4 - current_positions.get('RB', 0)), 
            'WR': max(0, 5 - current_positions.get('WR', 0)),
            'TE': max(0, 2 - current_positions.get('TE', 0)),
            'K': max(0, 1 - current_positions.get('K', 0)),
            'DEF': max(0, 1 - current_positions.get('DEF', 0))
        }
        
        return needs


@dataclass  
class MockDraftState:
    """Tracks the current state of the mock draft"""
    current_round: int = 1
    current_pick_in_round: int = 1
    current_team_idx: int = 0
    total_picks_made: int = 0
    teams: List[MockTeam] = field(default_factory=list)
    all_picks: List[DraftPick] = field(default_factory=list)
    available_players: List[Player] = field(default_factory=list)
    user_position: int = 1
    
    @property
    def current_team(self) -> MockTeam:
        """Get the team currently on the clock"""
        return self.teams[self.current_team_idx]
    
    @property
    def is_user_turn(self) -> bool:
        """Check if it's the user's turn to pick"""
        return self.current_team.is_user


class MockDraftSimulator:
    """Interactive mock draft simulator"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.strategy = None
        self.db = PlayerDatabase()
        self.draft_state = None
        
    def start_mock_draft(self, user_position: int, num_teams: int = 12, 
                        num_rounds: int = 15) -> None:
        """Start an interactive mock draft"""
        print(f"\n🏈 GRIDIRON GUILLOTINE MOCK DRAFT")
        print("=" * 50)
        print(f"Teams: {num_teams} | Rounds: {num_rounds} | Your Position: {user_position}")
        print(f"Strategy: Hero-RB + Enhanced Tier Analysis")
        print("=" * 50)
        
        # Initialize draft
        self._initialize_draft(user_position, num_teams, num_rounds)
        
        # Run the draft
        self._run_interactive_draft()
        
        # Show final results
        self._show_final_results()
    
    def _initialize_draft(self, user_position: int, num_teams: int, num_rounds: int):
        """Initialize the mock draft"""
        print("\n📊 Initializing draft...")
        
        # Create teams
        teams = []
        for i in range(num_teams):
            is_user = (i + 1) == user_position
            team = MockTeam(
                team_id=i + 1,
                team_name=f"You" if is_user else f"Team {i + 1}",
                strategy_type="hero_rb" if is_user else self._get_random_strategy(),
                is_user=is_user
            )
            teams.append(team)
        
        # Load available players from database
        print("📈 Loading player data from database...")
        available_players = self._load_players_from_db()
        
        if not available_players:
            raise Exception("Failed to load player data")
        
        print(f"✅ Loaded {len(available_players)} players")
        
        # Initialize draft state
        self.draft_state = MockDraftState(
            teams=teams,
            available_players=available_players,
            user_position=user_position
        )
        
        # Initialize strategy for user
        league_settings = LeagueSettings(
            teams=num_teams,
            rounds=num_rounds,
            ppr=True
        )
        
        draft_state = DraftState(
            current_round=1,
            current_pick=1
        )
        
        self.strategy = ChampionshipDraftStrategy(user_position, league_settings, self.config)
        
        print("🚀 Draft initialization complete!")
    
    def _load_players_from_db(self) -> List[Player]:
        """Load players from the database with enhanced data"""
        try:
            # Get ALL available players to ensure K/DEF are included
            enhanced_players = self.db.get_available_players()  # Get all players
            
            players = []
            for ep in enhanced_players:
                player = Player(
                    name=ep.name,
                    position=Position(ep.position),
                    team=ep.team or "",
                    projected_points=ep.projected_points or 0.0,
                    vbd=ep.vbd or 0.0,
                    floor=ep.floor or 0.0,
                    ceiling=ep.ceiling or 0.0
                )
                # Store enhanced data for display
                player._enhanced_data = ep  # Store reference to enhanced player
                players.append(player)
            
            return players
            
        except Exception as e:
            logger.error(f"Failed to load players from database: {e}")
            return []
    
    def _get_random_strategy(self) -> str:
        """Get random strategy for opponent teams"""
        strategies = ["balanced", "rb_heavy", "wr_heavy", "late_qb", "early_te", "zero_rb"]
        weights = [0.3, 0.15, 0.15, 0.15, 0.1, 0.15]
        return random.choices(strategies, weights=weights)[0]
    
    def _run_interactive_draft(self):
        """Run the interactive draft"""
        while self.draft_state.current_round <= 15:  # Standard 15 rounds
            self._execute_round()
            if self._check_draft_complete():
                break
    
    def _execute_round(self):
        """Execute a complete round of drafting"""
        round_num = self.draft_state.current_round
        
        print(f"\n🔄 ROUND {round_num}")
        print("-" * 30)
        
        # Determine pick order (snake draft)
        if round_num % 2 == 1:  # Odd rounds - normal order
            pick_order = list(range(len(self.draft_state.teams)))
        else:  # Even rounds - reverse order
            pick_order = list(reversed(range(len(self.draft_state.teams))))
        
        for pick_in_round, team_idx in enumerate(pick_order, 1):
            self.draft_state.current_team_idx = team_idx
            self.draft_state.current_pick_in_round = pick_in_round
            
            current_team = self.draft_state.current_team
            
            print(f"\nPick {self.draft_state.total_picks_made + 1} - {current_team.team_name}")
            
            if current_team.is_user:
                # User's turn - show recommendations and get choice
                selected_player = self._handle_user_pick()
            else:
                # AI opponent pick
                selected_player = self._handle_ai_pick(current_team)
                
            if selected_player:
                self._process_pick(selected_player, current_team)
            
            # Brief pause for readability
            if not current_team.is_user:
                time.sleep(0.5)
        
        # Advance to next round
        self.draft_state.current_round += 1
    
    def _handle_user_pick(self) -> Optional[Player]:
        """Handle the user's draft pick"""
        # Get strategic recommendations
        recommendations = self._get_user_recommendations()
        
        # Show recommendations with enhanced data
        print(f"\n🎯 GRIDIRON GUILLOTINE RECOMMENDATIONS:")
        print("=" * 80)
        
        for i, (player, reason) in enumerate(recommendations[:10], 1):
            pos_icon = self._get_position_icon(player.position)
            news_icon = self._get_news_icon(player)
            
            # Get enhanced stats if available
            projected_pts = player.projected_points
            vbd_score = player.vbd
            
            # Format the display with all key metrics including NFL team
            news_str = f" {news_icon}" if news_icon else ""
            team_str = f" {player.team:<3}" if player.team else " ---"
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}){team_str} "
                  f"Proj: {projected_pts:5.1f} | VBD: {vbd_score:5.1f}{news_str}")
            print(f"     └─ {reason}")
        
        # Show additional context
        self._show_draft_context()
        
        # Get user input with enhanced controls
        while True:
            try:
                print(f"\n📋 Available options:")
                print(f"   • Enter 1-10 to select recommended player")
                print(f"   • Enter 's' to search for specific player")
                print(f"   • Enter 'r' to see more recommendations")
                print(f"   • Enter 'i' for draft information")
                print(f"   🎯 POSITION FILTERS: 'qb', 'rb', 'wr', 'te', 'k', 'def'")
                print(f"   🏟️ TEAM FILTERS: 'buf', 'sf', 'kc', etc. (NFL team codes)")
                
                choice = input(f"\nYour choice: ").strip().lower()
                
                if choice in ['i', 'info']:
                    self._show_detailed_info()
                    continue
                elif choice in ['r', 'more']:
                    self._show_extended_recommendations()
                    continue
                elif choice in ['s', 'search']:
                    return self._handle_player_search()
                elif choice in ['qb', 'rb', 'wr', 'te', 'k', 'def']:
                    # Position filter
                    filtered = self._filter_by_position(choice)
                    self._show_filtered_recommendations(filtered, "position", choice)
                    
                    # Allow selection from filtered results
                    try:
                        filter_choice = input(f"\nSelect from {choice.upper()} players (number) or press Enter to return: ").strip()
                        if filter_choice.isdigit():
                            filter_idx = int(filter_choice) - 1
                            if 0 <= filter_idx < len(filtered):
                                return filtered[filter_idx][0]
                    except (ValueError, IndexError):
                        pass
                    continue
                elif len(choice) in [2, 3] and choice.isalpha():
                    # Possible team filter (2-3 letter team codes)
                    team_codes = ['ari', 'atl', 'bal', 'buf', 'car', 'chi', 'cin', 'cle', 'dal', 
                                 'den', 'det', 'gb', 'hou', 'ind', 'jax', 'kc', 'lv', 'lac', 
                                 'lar', 'mia', 'min', 'ne', 'no', 'nyg', 'nyj', 'phi', 'pit', 
                                 'sf', 'sea', 'tb', 'ten', 'was']
                    
                    if choice in team_codes:
                        # Team filter
                        filtered = self._filter_by_team(choice)
                        self._show_filtered_recommendations(filtered, "team", choice)
                        
                        # Allow selection from filtered results
                        try:
                            filter_choice = input(f"\nSelect from {choice.upper()} players (number) or press Enter to return: ").strip()
                            if filter_choice.isdigit():
                                filter_idx = int(filter_choice) - 1
                                if 0 <= filter_idx < len(filtered):
                                    return filtered[filter_idx][0]
                        except (ValueError, IndexError):
                            pass
                        continue
                    else:
                        print("❌ Invalid team code. Use 3-letter codes like 'buf', 'sf', 'kc'")
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(recommendations):
                        return recommendations[idx][0]
                    else:
                        print("❌ Invalid selection. Please try again.")
                else:
                    print("❌ Invalid input. Please try again.")
                    
            except (ValueError, KeyboardInterrupt):
                print("❌ Invalid input. Please try again.")
    
    def _handle_ai_pick(self, team: MockTeam) -> Optional[Player]:
        """Handle AI team draft pick"""
        if not self.draft_state.available_players:
            return None
        
        # Simple AI strategy based on team type
        selected = self._ai_select_player(team)
        
        if selected:
            print(f"🤖 {team.team_name} selects: {selected.name} ({selected.position.value})")
        
        return selected
    
    def _ai_select_player(self, team: MockTeam) -> Optional[Player]:
        """AI player selection logic"""
        available = self.draft_state.available_players
        if not available:
            return None
        
        round_num = self.draft_state.current_round
        roster_needs = team.get_roster_needs()
        
        # Filter available players by position needs
        needed_players = []
        for player in available:
            pos = player.position.value
            if roster_needs.get(pos, 0) > 0:
                needed_players.append(player)
        
        if not needed_players:
            needed_players = available  # Fallback to all available
        
        # Apply strategy-specific logic
        if team.strategy_type == "rb_heavy":
            # Prioritize RBs heavily
            rbs = [p for p in needed_players if p.position == Position.RB]
            if rbs and round_num <= 8:
                return max(rbs, key=lambda p: p.vbd)
        
        elif team.strategy_type == "wr_heavy":
            # Prioritize WRs
            wrs = [p for p in needed_players if p.position == Position.WR]
            if wrs and round_num <= 8:
                return max(wrs, key=lambda p: p.vbd)
        
        elif team.strategy_type == "zero_rb":
            # Avoid RBs until late
            if round_num <= 6:
                non_rbs = [p for p in needed_players if p.position != Position.RB]
                if non_rbs:
                    return max(non_rbs, key=lambda p: p.vbd)
        
        elif team.strategy_type == "late_qb":
            # Avoid QB until late
            if round_num <= 8:
                non_qbs = [p for p in needed_players if p.position != Position.QB]
                if non_qbs:
                    return max(non_qbs, key=lambda p: p.vbd)
            else:
                qbs = [p for p in needed_players if p.position == Position.QB]
                if qbs and roster_needs.get('QB', 0) > 0:
                    return max(qbs, key=lambda p: p.vbd)
        
        elif team.strategy_type == "early_te":
            # Take TE early if needed
            if round_num <= 5 and roster_needs.get('TE', 0) > 0:
                tes = [p for p in needed_players if p.position == Position.TE]
                if tes:
                    return max(tes, key=lambda p: p.vbd)
        
        # Default: best available by VBD
        return max(needed_players, key=lambda p: p.vbd)
    
    def _get_user_recommendations(self) -> List[Tuple[Player, str]]:
        """Get strategic recommendations for the user"""
        try:
            # Convert current state to what strategy expects
            available_df = self._convert_to_dataframe()
            
            round_num = self.draft_state.current_round
            
            # Get recommendations using championship strategy
            recommendations = self.strategy.get_round_strategy(
                available_df, round_num, top_n=15
            )
            
            results = []
            for _, row in recommendations.iterrows():
                # Find the corresponding Player object
                player_name = row['name']
                player = next((p for p in self.draft_state.available_players 
                             if p.name == player_name), None)
                
                if player:
                    # Generate reason based on strategy
                    reason = self._generate_pick_reason(player, row, round_num)
                    results.append((player, reason))
            
            return results[:15]  # Top 15 recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            # Fallback: sort by VBD
            sorted_players = sorted(self.draft_state.available_players, 
                                  key=lambda p: p.vbd, reverse=True)
            return [(p, "Best available by VBD") for p in sorted_players[:15]]
    
    def _generate_pick_reason(self, player: Player, row: Any, round_num: int) -> str:
        """Generate a reason for recommending this pick"""
        pos = player.position.value
        hero_phase = self.strategy._determine_hero_rb_phase(round_num)
        
        reasons = []
        
        # Hero-RB specific reasons
        if pos == "RB":
            if hero_phase.value == "hero_acquisition" and round_num <= 2:
                reasons.append("🏆 Hero RB target")
            elif hero_phase.value == "depth_phase" and round_num >= 8:
                reasons.append("📈 RB depth building")
            elif hero_phase.value == "pivot_phase":
                reasons.append("⚠️ Pivot phase - consider WR instead")
        
        # Tier-based reasons
        if hasattr(row, 'tier') and row.get('tier', 0) <= 2:
            reasons.append(f"⭐ Tier {int(row.get('tier', 1))} player")
        
        # Value-based reasons
        vbd = player.vbd
        if vbd > 50:
            reasons.append("🔥 Elite value")
        elif vbd > 20:
            reasons.append("💎 Strong value")
        
        # Position scarcity
        pos_count = len([p for p in self.draft_state.available_players 
                        if p.position == player.position])
        if pos_count <= 5:
            reasons.append(f"⏰ {pos} scarcity")
        
        return " | ".join(reasons) if reasons else "Strategic fit"
    
    def _convert_to_dataframe(self):
        """Convert available players to DataFrame for strategy"""
        import pandas as pd
        
        data = []
        for player in self.draft_state.available_players:
            data.append({
                'name': player.name,
                'position': player.position.value,
                'team': player.team,
                'projected_points': player.projected_points,
                'vbd': player.vbd,
                'floor': player.floor,
                'ceiling': player.ceiling
            })
        
        return pd.DataFrame(data)
    
    def _show_draft_context(self):
        """Show additional draft context"""
        round_num = self.draft_state.current_round
        hero_phase = self.strategy._determine_hero_rb_phase(round_num)
        
        print(f"\n📋 DRAFT CONTEXT:")
        print(f"   🔄 Round {round_num} | Phase: {hero_phase.value.replace('_', ' ').title()}")
        
        # Show your current roster
        user_team = next(t for t in self.draft_state.teams if t.is_user)
        if user_team.drafted_players:
            print(f"   👥 Your Roster ({len(user_team.drafted_players)}):")
            for player in user_team.drafted_players:
                pos_icon = self._get_position_icon(player.position)
                print(f"      {pos_icon} {player.name} ({player.position.value})")
        else:
            print(f"   👥 Your Roster: Empty")
        
        # Show positional availability
        pos_counts = {}
        for player in self.draft_state.available_players:
            pos = player.position.value
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        
        print(f"   📊 Available: ", end="")
        pos_strs = []
        for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
            count = pos_counts.get(pos, 0)
            if count > 0:
                pos_strs.append(f"{pos}({count})")
        print(" | ".join(pos_strs))
    
    def _get_position_icon(self, position: Position) -> str:
        """Get emoji icon for position"""
        icons = {
            Position.QB: "🎯",
            Position.RB: "🏃",
            Position.WR: "🏈", 
            Position.TE: "🤲",
            Position.K: "🦵",
            Position.DEF: "🛡️"
        }
        return icons.get(position, "⚪")
    
    def _filter_by_position(self, position_code: str) -> List[Tuple[Player, str]]:
        """Filter available players by position"""
        position_map = {
            'qb': Position.QB,
            'rb': Position.RB, 
            'wr': Position.WR,
            'te': Position.TE,
            'k': Position.K,
            'def': Position.DEF
        }
        
        if position_code.lower() not in position_map:
            return []
        
        target_position = position_map[position_code.lower()]
        filtered_players = [p for p in self.draft_state.available_players 
                          if p.position == target_position]
        
        # Sort by VBD and generate reasons
        filtered_players.sort(key=lambda p: p.vbd, reverse=True)
        
        results = []
        for player in filtered_players[:20]:  # Top 20 for that position
            reason = f"Best available {position_code.upper()}"
            if player.vbd > 5.0:
                reason += " | 🔥 Elite value"
            elif player.vbd > 2.0:
                reason += " | 💎 Strong value"
            results.append((player, reason))
        
        return results
    
    def _filter_by_team(self, team_code: str) -> List[Tuple[Player, str]]:
        """Filter available players by NFL team"""
        team_map = {
            'ari': 'ARI', 'atl': 'ATL', 'bal': 'BAL', 'buf': 'BUF', 'car': 'CAR', 'chi': 'CHI',
            'cin': 'CIN', 'cle': 'CLE', 'dal': 'DAL', 'den': 'DEN', 'det': 'DET', 'gb': 'GB',
            'hou': 'HOU', 'ind': 'IND', 'jax': 'JAX', 'kc': 'KC', 'lv': 'LV', 'lac': 'LAC',
            'lar': 'LAR', 'mia': 'MIA', 'min': 'MIN', 'ne': 'NE', 'no': 'NO', 'nyg': 'NYG',
            'nyj': 'NYJ', 'phi': 'PHI', 'pit': 'PIT', 'sf': 'SF', 'sea': 'SEA', 'tb': 'TB',
            'ten': 'TEN', 'was': 'WAS'
        }
        
        target_team = team_map.get(team_code.lower(), team_code.upper())
        filtered_players = [p for p in self.draft_state.available_players 
                          if p.team and p.team.upper() == target_team]
        
        # Sort by VBD
        filtered_players.sort(key=lambda p: p.vbd, reverse=True)
        
        results = []
        for player in filtered_players[:15]:  # Top 15 for that team
            reason = f"{target_team} player"
            if player.vbd > 5.0:
                reason += " | 🔥 Elite value"
            elif player.vbd > 2.0:
                reason += " | 💎 Strong value"
            results.append((player, reason))
        
        return results
    
    def _show_filtered_recommendations(self, filtered_players: List[Tuple[Player, str]], 
                                     filter_type: str, filter_value: str):
        """Show filtered recommendations"""
        if not filtered_players:
            print(f"❌ No available players found for {filter_type}: {filter_value}")
            return
        
        print(f"\n🎯 {filter_type.upper()} FILTER: {filter_value.upper()}")
        print("=" * 80)
        
        for i, (player, reason) in enumerate(filtered_players, 1):
            pos_icon = self._get_position_icon(player.position)
            news_icon = self._get_news_icon(player)
            news_str = f" {news_icon}" if news_icon else ""
            team_str = f" {player.team:<3}" if player.team else " ---"
            
            projected_pts = player.projected_points
            vbd_score = player.vbd
            
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}){team_str} "
                  f"Proj: {projected_pts:5.1f} | VBD: {vbd_score:5.1f}{news_str}")
            print(f"     └─ {reason}")
    
    def _get_news_icon(self, player: Player) -> str:
        """Get news impact icon for player"""
        if not hasattr(player, '_enhanced_data') or not player._enhanced_data:
            return ""
        
        from ..data.database import NewsImpact
        impact = player._enhanced_data.overall_news_impact
        
        if impact == NewsImpact.POSITIVE:
            return "📈"  # Up arrow for positive news
        elif impact == NewsImpact.NEGATIVE:
            return "📉"  # Down arrow for negative news
        elif impact == NewsImpact.NEUTRAL:
            return "➖"  # Neutral for neutral news
        else:
            return ""   # No icon for unknown
    
    def _show_detailed_info(self):
        """Show detailed draft information"""
        print(f"\n📊 DETAILED DRAFT INFORMATION")
        print("=" * 40)
        
        # League overview
        total_picks = len(self.draft_state.all_picks)
        total_possible = len(self.draft_state.teams) * 15
        print(f"Draft Progress: {total_picks}/{total_possible} picks made")
        print(f"Available Players: {len(self.draft_state.available_players)}")
        
        # Team strategies
        print(f"\n🤖 Opponent Strategies:")
        for team in self.draft_state.teams:
            if not team.is_user:
                print(f"   {team.team_name}: {team.strategy_type}")
        
        # Recent picks
        if len(self.draft_state.all_picks) > 0:
            print(f"\n📝 Recent Picks:")
            recent = self.draft_state.all_picks[-5:]
            for pick in recent:
                print(f"   R{pick.round_num}.{pick.pick_num}: {pick.player_name} "
                      f"({pick.position.value}) to {pick.team_name}")
    
    def _show_extended_recommendations(self):
        """Show extended recommendations with enhanced data"""
        recommendations = self._get_user_recommendations()
        
        print(f"\n🎯 EXTENDED RECOMMENDATIONS (Top 20):")
        print("=" * 85)
        
        for i, (player, reason) in enumerate(recommendations[:20], 1):
            pos_icon = self._get_position_icon(player.position)
            news_icon = self._get_news_icon(player)
            
            projected_pts = player.projected_points
            vbd_score = player.vbd
            
            team_str = f" {player.team:<3}" if player.team else " ---"
            news_str = f" {news_icon}" if news_icon else ""
            print(f"{i:2d}. {pos_icon} {player.name:<22} ({player.position.value}){team_str} "
                  f"Proj: {projected_pts:5.1f} | VBD: {vbd_score:5.1f}{news_str} | {reason}")
    
    def _handle_player_search(self) -> Optional[Player]:
        """Handle player search functionality"""
        search_term = input("Enter player name to search: ").strip()
        
        if not search_term:
            return None
        
        # Search available players
        matches = [p for p in self.draft_state.available_players 
                  if search_term.lower() in p.name.lower()]
        
        if not matches:
            print(f"❌ No players found matching '{search_term}'")
            return None
        
        if len(matches) == 1:
            player = matches[0]
            news_icon = self._get_news_icon(player)
            news_str = f" {news_icon}" if news_icon else ""
            team_str = f" {player.team}" if player.team else ""
            print(f"✅ Found: {player.name} ({player.position.value}){team_str} "
                  f"Proj: {player.projected_points:.1f} | VBD: {player.vbd:.1f}{news_str}")
            confirm = input("Select this player? (y/n): ").strip().lower()
            return player if confirm in ['y', 'yes'] else None
        
        # Multiple matches - show options
        print(f"\n🔍 Found {len(matches)} matches:")
        for i, player in enumerate(matches[:10], 1):
            pos_icon = self._get_position_icon(player.position)
            news_icon = self._get_news_icon(player)
            news_str = f" {news_icon}" if news_icon else ""
            team_str = f" {player.team}" if player.team else ""
            print(f"{i}. {pos_icon} {player.name} ({player.position.value}){team_str} "
                  f"Proj: {player.projected_points:.1f} | VBD: {player.vbd:.1f}{news_str}")
        
        try:
            choice = int(input("Select player (number): ")) - 1
            if 0 <= choice < len(matches):
                return matches[choice]
        except ValueError:
            pass
        
        print("❌ Invalid selection")
        return None
    
    def _process_pick(self, player: Player, team: MockTeam):
        """Process a draft pick"""
        # Create draft pick record
        pick = DraftPick(
            player_name=player.name,
            team_name=team.team_name,
            position=player.position,
            round_num=self.draft_state.current_round,
            pick_num=self.draft_state.total_picks_made + 1
        )
        
        # Add to records
        team.drafted_players.append(player)
        self.draft_state.all_picks.append(pick)
        self.draft_state.available_players.remove(player)
        self.draft_state.total_picks_made += 1
        
        # Update strategy state if user pick
        if team.is_user:
            self.strategy.simulate_pick(player.name)
        
        # Show pick confirmation
        pos_icon = self._get_position_icon(player.position)
        print(f"✅ {pos_icon} {team.team_name} drafts {player.name} ({player.position.value})")
    
    def _check_draft_complete(self) -> bool:
        """Check if draft is complete"""
        return (self.draft_state.current_round > 15 or 
                len(self.draft_state.available_players) == 0)
    
    def _show_final_results(self):
        """Show final draft results"""
        print(f"\n🏆 MOCK DRAFT COMPLETE!")
        print("=" * 50)
        
        # Show user's final roster
        user_team = next(t for t in self.draft_state.teams if t.is_user)
        
        print(f"\n👥 YOUR FINAL ROSTER:")
        print("-" * 30)
        
        # Group by position
        roster_by_pos = {}
        for player in user_team.drafted_players:
            pos = player.position.value
            if pos not in roster_by_pos:
                roster_by_pos[pos] = []
            roster_by_pos[pos].append(player)
        
        # Display roster with enhanced information
        total_vbd = 0
        total_projected = 0
        for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
            if pos in roster_by_pos:
                print(f"\n{pos}:")
                for player in roster_by_pos[pos]:
                    pos_icon = self._get_position_icon(player.position)
                    news_icon = self._get_news_icon(player)
                    news_str = f" {news_icon}" if news_icon else ""
                    print(f"  {pos_icon} {player.name:<22} "
                          f"Proj: {player.projected_points:5.1f} | VBD: {player.vbd:5.1f}{news_str}")
                    total_vbd += player.vbd
                    total_projected += player.projected_points
        
        print(f"\n📊 ROSTER ANALYSIS:")
        print(f"   Total Projected Points: {total_projected:.1f}")
        print(f"   Total VBD: {total_vbd:.1f}")
        print(f"   Players Drafted: {len(user_team.drafted_players)}")
        print(f"   Hero RB Strategy: {'✅ Success' if self.strategy.draft_state.hero_rb_acquired else '❌ Failed'}")
        
        # Position breakdown
        pos_counts = {}
        for player in user_team.drafted_players:
            pos = player.position.value
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        
        print(f"   Position Mix: ", end="")
        pos_strs = []
        for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
            count = pos_counts.get(pos, 0) 
            if count > 0:
                pos_strs.append(f"{pos}({count})")
        print(" | ".join(pos_strs))
        
        print(f"\n🎯 Ready to test this strategy in a real draft!")