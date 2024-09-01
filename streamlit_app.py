import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# Set page title
st.set_page_config(page_title="Fantasy Football Draft Strategy", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv("data/draft_strategy.csv")
    df['drafted'] = 'False'
    return df


if 'df' not in st.session_state:
    st.session_state.df = load_data()


def filter_dataframe(df, position, round, search_term):
    filtered = df.copy()
    if position != "All":
        filtered = filtered[filtered["Position"] == position]
    if round != "All":
        filtered = filtered[filtered["Round"] == round]
    if search_term:
        filtered = filtered[filtered["Player"].str.contains(
            search_term, case=False)]
    return filtered


st.title("Fantasy Football Draft Strategy Dashboard")


# Display My Team
st.header("My Team")
my_team = st.session_state.df[st.session_state.df['drafted'] == 'My Team'].sort_values('Rank')
st.dataframe(my_team[['Rank', 'Player', 'Position', 'Team', 'Value', 'VBD', 'Tier', 'Rating', 'Rookie', 'Round']])


# Sidebar for filtering
st.sidebar.header("Filters")

positions = ["All"] + sorted(st.session_state.df["Position"].unique().tolist())
selected_position = st.sidebar.selectbox(
    "Select Position", positions, key="position_filter")

rounds = ["All"] + sorted(st.session_state.df["Round"].unique().tolist())
selected_round = st.sidebar.selectbox(
    "Select Round", rounds, key="round_filter")

# Add this at the beginning of your sidebar content
st.sidebar.header("User Guide")
st.sidebar.markdown("""
### Fantasy Football Draft Strategy Dashboard

This tool helps you make informed decisions during your fantasy football draft.

**Key Features:**
1. **My Team**: Shows your drafted players at the top.
2. **Draft Strategy Table**: Main table with all available players.
3. **Player Analysis**: Detailed player info in sidebar when selected.

**How to Use:**
1. **Search & Filter**: Use the search bar and filters to find players.
2. **Sort**: Click column headers to sort by different metrics (e.g., VBD, Tier).
3. **Draft Players**: In the 'Drafted' column, select:
   - 'My Team' for players you draft
   - 'Other Team' for players drafted by others
4. **View Analysis**: Click on a player to see their detailed analysis in the sidebar.

**Tips:**
- Focus on high VBD players for best value.
- Use Tier to identify drop-offs in talent.
- Balance your team across positions.

Good luck with your draft!
""")

# Main content
st.header("Draft Strategy")

search_term = st.text_input("Search Players", "", key="search_filter")

# Apply filters
filtered_df = filter_dataframe(
    st.session_state.df, selected_position, selected_round, search_term)

# Configure AgGrid
gb = GridOptionsBuilder.from_dataframe(filtered_df)
gb.configure_selection('single', use_checkbox=False, pre_selected_rows=[])
gb.configure_default_column(flex=1, min_width=100,
                            resizable=True, sortable=True)

column_config = {
    "Rank": "Rank",
    "Player": "Player Name",
    "Position": "Position",
    "Value": "Value",
    "Tier": "Tier",
    "Rating": "Rating",
    "Rookie": "Rookie",
    "Round": "Round",
    "drafted": "Drafted",
    "Team": "Team",
    "VBD": "VBD"
}

for col, header in column_config.items():
    gb.configure_column(col, header_name=header)

# Hide the 'Analyst Rating' column
gb.configure_column("Analyst Rating", hide=True)

gb.configure_column("drafted",
                    editable=True,
                    cellEditor='agSelectCellEditor',
                    cellEditorParams={
                        'values': ['False', 'My Team', 'Other Team']
                    },
                    cellRenderer=JsCode("""
                        function(params) {
                            return params.value === 'False' ? '' : params.value;
                        }
                    """))

cellstyle_jscode = JsCode("""
function(params) {
    const value = params.value;
    if (value === 5) return {'color': 'white', 'backgroundColor': 'darkgreen'};
    if (value === 4) return {'color': 'black', 'backgroundColor': 'lightgreen'};
    if (value === 2) return {'color': 'black', 'backgroundColor': 'lightcoral'};
    if (value === 1) return {'color': 'white', 'backgroundColor': 'darkred'};
    return {'color': 'black', 'backgroundColor': 'white'};
}
""")

gb.configure_column("Rating", cellStyle=cellstyle_jscode)

gb.configure_grid_options(
    onCellValueChanged=JsCode("""
    function(params) {
        if (params.colDef.field === 'drafted') {
            params.api.refreshCells({force: true});
            params.api.redrawRows();
        }
    }
    """),
    getRowStyle=JsCode("""
    function(params) {
        if (params.data.drafted === 'My Team') return {'backgroundColor': '#90EE90'};
        if (params.data.drafted === 'Other Team') return {'backgroundColor': '#FFA07A'};
        return null;
    }
    """)
)

grid_options = gb.build()

grid_response = AgGrid(
    filtered_df,
    gridOptions=grid_options,
    height=380,
    width='100%',
    data_return_mode='AS_INPUT',
    update_mode='MODEL_CHANGED',
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True,
    theme='streamlit',
    key='player_grid',
    reload_data=False
)

# Player Analysis Section
st.header("Player Analysis")
selected_rows = grid_response['selected_rows']

if not selected_rows.empty:
    selected_player = selected_rows.iloc[0]

    player_name = selected_player.get('Player')
    analyst_rating = selected_player.get('Analyst Rating')

    if player_name is not None:
        st.subheader(f"{player_name}")
        if analyst_rating is not None:
            st.markdown(analyst_rating)
        else:
            st.error(f"No analysis found for player: {player_name}")
    else:
        st.error("Player name not found in selected data")
else:
    st.info("Select a player from the table to view their analysis.")

# Update the dataframe based on user interactions
if grid_response['data'] is not None:
    dataframe_changed = False
    drafted_players_updated = []

    for index, row in grid_response['data'].iterrows():
        original_draft_status = st.session_state.df.loc[st.session_state.df['Player']
                                                        == row['Player'], 'drafted'].iloc[0]
        if original_draft_status != row['drafted']:
            st.session_state.df.loc[st.session_state.df['Player']
                                    == row['Player'], 'drafted'] = row['drafted']
            dataframe_changed = True
            drafted_players_updated.append(row['Player'])

    if dataframe_changed:
        st.rerun()


# Force a rerun if any filter changes
if st.session_state.get('prev_position') != selected_position or \
   st.session_state.get('prev_round') != selected_round or \
   st.session_state.get('prev_search') != search_term:
    st.session_state.prev_position = selected_position
    st.session_state.prev_round = selected_round
    st.session_state.prev_search = search_term
    st.rerun()
