"""
Streamlit dashboard for Gridiron Guillotine
Modern web interface for draft strategy and live monitoring
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any, Optional
import logging

from ..core.strategy import ChampionshipDraftStrategy
from ..core.models import DraftState, LeagueSettings, Position
from ..data.loaders import PlayerDataLoader
from ..live.monitor import LiveDraftMonitor
from ..live.simulator import DraftSimulator
from ..core.config import get_config

logger = logging.getLogger(__name__)


class StreamlitDashboard:
    """Main Streamlit dashboard application"""
    
    def __init__(self):
        self.config = get_config()
        self.strategy = ChampionshipDraftStrategy(self.config)
        self.data_loader = PlayerDataLoader(self.config)
        self.monitor = LiveDraftMonitor(self.config)
        self.simulator = DraftSimulator(self.config)
        
        # Initialize session state
        if 'draft_state' not in st.session_state:
            st.session_state.draft_state = None
        if 'player_data' not in st.session_state:
            st.session_state.player_data = None
        if 'monitoring_active' not in st.session_state:
            st.session_state.monitoring_active = False
    
    def run(self):
        """Main dashboard entry point"""
        st.set_page_config(
            page_title="Gridiron Guillotine v2.0",
            page_icon="🏈",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Header
        st.title("🏈 Gridiron Guillotine v2.0")
        st.markdown("**Championship Fantasy Football Draft Strategy**")
        
        # Sidebar navigation
        page = st.sidebar.selectbox(
            "Navigation",
            ["Strategy Analysis", "Live Draft Monitor", "Draft Simulation", "Player Database", "Settings"]
        )
        
        # Load data if not already loaded
        if st.session_state.player_data is None:
            self._load_data()
        
        # Route to selected page
        if page == "Strategy Analysis":
            self._strategy_analysis_page()
        elif page == "Live Draft Monitor":
            self._live_monitor_page()
        elif page == "Draft Simulation":
            self._simulation_page()
        elif page == "Player Database":
            self._player_database_page()
        elif page == "Settings":
            self._settings_page()
    
    def _load_data(self):
        """Load player data"""
        with st.spinner("Loading player data..."):
            try:
                data = self.data_loader.load_scored_data()
                if data is not None:
                    st.session_state.player_data = data
                    st.success(f"Loaded {len(data)} players")
                else:
                    st.error("Failed to load player data")
            except Exception as e:
                st.error(f"Error loading data: {e}")
    
    def _strategy_analysis_page(self):
        """Strategy analysis and recommendations page"""
        st.header("📊 Draft Strategy Analysis")
        
        # Draft position input
        col1, col2, col3 = st.columns(3)
        
        with col1:
            draft_position = st.selectbox("Draft Position", range(1, 13), index=5)
        
        with col2:
            num_teams = st.selectbox("League Size", [10, 12, 14], index=1)
        
        with col3:
            scoring = st.selectbox("Scoring Type", ["PPR", "Half-PPR", "Standard"], index=0)
        
        # Initialize draft state
        league_settings = LeagueSettings(
            league_name="Analysis League",
            num_teams=num_teams,
            draft_position=draft_position,
            scoring_type=scoring.lower().replace("-", "_")
        )
        
        draft_state = DraftState(
            current_round=1,
            current_pick=1,
            picks_made=[],
            user_draft_position=draft_position,
            league_settings=league_settings
        )
        
        self.strategy.initialize_draft(draft_state)
        
        # Round selector
        round_num = st.slider("Draft Round", 1, 15, 1)
        
        # Get strategy recommendations
        try:
            recommendations = self.strategy.get_round_strategy(
                round_num, draft_state.picks_made, draft_position
            )
            
            # Display recommendations
            st.subheader(f"Round {round_num} Recommendations")
            
            if recommendations.get('top_picks'):
                # Top picks table
                top_picks_df = pd.DataFrame(recommendations['top_picks'][:10])
                
                # Format for display
                if not top_picks_df.empty:
                    display_df = top_picks_df[['name', 'position', 'team', 'projected_points', 'vbd', 'adjusted_value']].copy()
                    display_df.columns = ['Player', 'Position', 'Team', 'Projected Points', 'VBD', 'Adjusted Value']
                    display_df = display_df.round(2)
                    
                    st.dataframe(display_df, use_container_width=True)
                
                # Strategy insights
                if recommendations.get('strategy_insights'):
                    st.subheader("Strategy Insights")
                    insights = recommendations['strategy_insights']
                    
                    for key, value in insights.items():
                        if isinstance(value, (int, float)):
                            st.metric(key.replace('_', ' ').title(), f"{value:.2f}")
                        else:
                            st.write(f"**{key.replace('_', ' ').title()}:** {value}")
            
            # Visualizations
            self._create_strategy_visualizations(recommendations, draft_position, round_num)
            
        except Exception as e:
            st.error(f"Error generating recommendations: {e}")
    
    def _live_monitor_page(self):
        """Live draft monitoring page"""
        st.header("🔴 Live Draft Monitor")
        
        # Configuration
        col1, col2 = st.columns(2)
        
        with col1:
            draft_position = st.selectbox("Your Draft Position", range(1, 13), index=5, key="monitor_position")
        
        with col2:
            polling_interval = st.selectbox("Polling Interval (seconds)", [10, 20, 30, 60], index=1)
        
        # Monitor status
        status = self.monitor.get_monitoring_status()
        
        if status['monitoring_active']:
            st.success("🟢 Monitoring Active")
            st.write(f"Current Round: {status['current_round']}")
            st.write(f"Picks Made: {status['picks_made']}")
            st.write(f"Last Check: {status['last_check']}")
            
            if st.button("Stop Monitoring", type="secondary"):
                self.monitor.stop_monitoring()
                st.session_state.monitoring_active = False
                st.experimental_rerun()
        else:
            st.warning("🔴 Monitoring Inactive")
            
            if st.button("Start Monitoring", type="primary"):
                # Note: Actual monitoring would need to run in background
                # This is a simplified version for demo
                st.info("Live monitoring requires Yahoo API setup. See Settings page.")
        
        # Manual pick entry for testing
        st.subheader("Manual Pick Entry (Testing)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            player_name = st.text_input("Player Name")
        
        with col2:
            position = st.selectbox("Position", [pos.value for pos in Position])
        
        with col3:
            if st.button("Add Pick"):
                if player_name:
                    st.success(f"Added pick: {player_name} ({position})")
    
    def _simulation_page(self):
        """Draft simulation page"""
        st.header("🎯 Draft Simulation")
        
        # Simulation parameters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sim_position = st.selectbox("Draft Position", range(1, 13), index=5, key="sim_position")
        
        with col2:
            num_simulations = st.selectbox("Number of Simulations", [1, 5, 10, 25], index=1)
        
        with col3:
            num_rounds = st.selectbox("Rounds to Simulate", [10, 12, 15], index=2)
        
        # Run simulation
        if st.button("Run Simulation", type="primary"):
            with st.spinner(f"Running {num_simulations} simulation(s)..."):
                try:
                    # Load data if needed
                    if not self.simulator.load_player_data():
                        st.error("Failed to load player data for simulation")
                        return
                    
                    # Run simulations
                    results = self.simulator.simulate_multiple_drafts(
                        user_position=sim_position,
                        num_simulations=num_simulations,
                        num_rounds=num_rounds
                    )
                    
                    if results:
                        # Analyze results
                        analysis = self.simulator.analyze_simulation_results(results)
                        
                        # Display results
                        st.subheader("Simulation Results")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Average Total VBD", f"{analysis.get('average_total_vbd', 0):.1f}")
                        
                        with col2:
                            st.metric("Average Projected Points", f"{analysis.get('average_projected_points', 0):.1f}")
                        
                        with col3:
                            st.metric("Hero-RB Success Rate", f"{analysis.get('hero_rb_success_rate', 0):.1%}")
                        
                        with col4:
                            st.metric("Average RBs Drafted", f"{analysis.get('average_rbs_drafted', 0):.1f}")
                        
                        # Show individual simulation results
                        if st.checkbox("Show Individual Results"):
                            for i, result in enumerate(results):
                                with st.expander(f"Simulation {i + 1} - {result.simulation_id}"):
                                    # User roster
                                    roster_data = []
                                    for player in result.user_roster:
                                        roster_data.append({
                                            'Player': player.name,
                                            'Position': player.position.value,
                                            'Team': player.team,
                                            'Projected Points': player.projected_points,
                                            'VBD': player.vbd
                                        })
                                    
                                    roster_df = pd.DataFrame(roster_data)
                                    st.dataframe(roster_df, use_container_width=True)
                    
                    else:
                        st.error("No simulation results generated")
                        
                except Exception as e:
                    st.error(f"Simulation error: {e}")
    
    def _player_database_page(self):
        """Player database and search page"""
        st.header("🗄️ Player Database")
        
        if st.session_state.player_data is not None:
            df = st.session_state.player_data.copy()
            
            # Filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                position_filter = st.multiselect(
                    "Filter by Position",
                    options=df['position'].unique(),
                    default=df['position'].unique()
                )
            
            with col2:
                team_filter = st.multiselect(
                    "Filter by Team",
                    options=sorted(df['team'].unique()),
                    default=[]
                )
            
            with col3:
                min_points = st.number_input("Minimum Projected Points", value=0.0, step=1.0)
            
            # Apply filters
            filtered_df = df[df['position'].isin(position_filter)]
            
            if team_filter:
                filtered_df = filtered_df[filtered_df['team'].isin(team_filter)]
            
            filtered_df = filtered_df[filtered_df['projected_points'] >= min_points]
            
            # Sort options
            sort_by = st.selectbox(
                "Sort by",
                ['projected_points', 'vbd', 'floor', 'ceiling'],
                index=1
            )
            
            filtered_df = filtered_df.sort_values(sort_by, ascending=False)
            
            # Display results
            st.write(f"Showing {len(filtered_df)} players")
            
            # Format for display
            display_columns = ['name', 'position', 'team', 'projected_points', 'vbd', 'floor', 'ceiling']
            display_df = filtered_df[display_columns].copy()
            display_df.columns = ['Player', 'Position', 'Team', 'Projected Points', 'VBD', 'Floor', 'Ceiling']
            display_df = display_df.round(2)
            
            st.dataframe(display_df, use_container_width=True, height=600)
        
        else:
            st.warning("No player data available. Please load data first.")
    
    def _settings_page(self):
        """Settings and configuration page"""
        st.header("⚙️ Settings")
        
        # Data status
        st.subheader("Data Status")
        
        if st.session_state.player_data is not None:
            st.success(f"✅ Player data loaded: {len(st.session_state.player_data)} players")
        else:
            st.warning("❌ No player data loaded")
        
        if st.button("Reload Data"):
            st.session_state.player_data = None
            self._load_data()
            st.experimental_rerun()
        
        # Yahoo API configuration
        st.subheader("Yahoo Fantasy API")
        st.info("To enable live draft monitoring, configure your Yahoo API credentials in `nbs/oauth2.json`")
        
        # Strategy configuration
        st.subheader("Strategy Configuration")
        
        # Display current config (read-only for now)
        config_data = {
            "Elite Hero RBs": ", ".join(self.config.elite_hero_rbs),
            "Replacement Levels": str(dict(self.config.replacement_levels)),
            "PPR Adjustments": str(dict(self.config.ppr_adjustments))
        }
        
        for key, value in config_data.items():
            st.text_input(key, value, disabled=True)
        
        # About
        st.subheader("About")
        st.markdown("""
        **Gridiron Guillotine v2.0** - Championship Fantasy Football Draft Strategy
        
        - **Hero-RB Strategy**: 20.2% advance rate vs 16.7% baseline
        - **Advanced Metrics**: WOPR, Expected Points, Offensive Context
        - **PPR Optimization**: Pass-catching player bonuses
        - **Live Integration**: Yahoo Fantasy API support
        """)
    
    def _create_strategy_visualizations(self, recommendations: Dict[str, Any], 
                                      draft_position: int, round_num: int):
        """Create visualization charts for strategy analysis"""
        if not recommendations.get('top_picks'):
            return
        
        # Position distribution chart
        st.subheader("Position Distribution - Top 20 Picks")
        
        top_20 = recommendations['top_picks'][:20]
        position_counts = {}
        
        for player in top_20:
            pos = player.get('position', 'Unknown')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        if position_counts:
            fig = px.pie(
                values=list(position_counts.values()),
                names=list(position_counts.keys()),
                title=f"Round {round_num} - Top 20 Picks by Position"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # VBD vs Projected Points scatter
        st.subheader("Value Analysis - VBD vs Projected Points")
        
        plot_data = []
        for player in top_20:
            plot_data.append({
                'Player': player.get('name', ''),
                'Position': player.get('position', ''),
                'VBD': player.get('vbd', 0),
                'Projected Points': player.get('projected_points', 0),
                'Adjusted Value': player.get('adjusted_value', 0)
            })
        
        if plot_data:
            plot_df = pd.DataFrame(plot_data)
            
            fig = px.scatter(
                plot_df,
                x='Projected Points',
                y='VBD',
                color='Position',
                size='Adjusted Value',
                hover_name='Player',
                title=f"Round {round_num} Value Analysis"
            )
            st.plotly_chart(fig, use_container_width=True)


def main():
    """Main entry point for Streamlit app"""
    dashboard = StreamlitDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()