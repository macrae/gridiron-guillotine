import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# Set page title
st.set_page_config(page_title="Fantasy Football Player Stats", layout="wide")

@st.cache_data
def load_data():
    return pd.read_csv("data/merged_player_ratings.csv")

df = load_data()

st.title("Fantasy Football Player Stats Dashboard")

# Sidebar for filtering and player rating
st.sidebar.header("Filters")

# Position filter
positions = ["All"] + sorted(df["pos"].unique().tolist())
selected_position = st.sidebar.selectbox("Select Position", positions)

# Team filter
teams = ["All"] + sorted(df["team"].unique().tolist())
selected_team = st.sidebar.selectbox("Select Team", teams)

# Apply filters
filtered_df = df.copy()
if selected_position != "All":
    filtered_df = filtered_df[filtered_df["pos"] == selected_position]
if selected_team != "All":
    filtered_df = filtered_df[filtered_df["team"] == selected_team]

# Main content
st.header("Player Stats")

# Search box
search_term = st.text_input("Search Players", "")
if search_term:
    filtered_df = filtered_df[filtered_df["index"].str.contains(search_term, case=False)]

# Configure AgGrid
gb = GridOptionsBuilder.from_dataframe(filtered_df)
gb.configure_selection('single', use_checkbox=False)
gb.configure_column("index", header_name="Player Name")

# Add color-coding based on rating_label
cellstyle_jscode = JsCode("""
function(params) {
    if (params.value === 'mega bullish') {
        return {
            'color': 'white',
            'backgroundColor': 'darkgreen'
        }
    } else if (params.value === 'bullish') {
        return {
            'color': 'black',
            'backgroundColor': 'lightgreen'
        }
    } else if (params.value === 'bearish') {
        return {
            'color': 'black',
            'backgroundColor': 'lightcoral'
        }
    } else if (params.value === 'mega bearish') {
        return {
            'color': 'white',
            'backgroundColor': 'darkred'
        }
    }
    return {
        'color': 'black',
        'backgroundColor': 'white'
    }
}
""")

gb.configure_column("rating_label", cellStyle=cellstyle_jscode)

grid_options = gb.build()

# Display AgGrid
grid_response = AgGrid(
    filtered_df,
    gridOptions=grid_options,
    height=400,
    width='100%',
    data_return_mode='AS_INPUT',
    update_mode='SELECTION_CHANGED',
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True
)

# Player Rating Section (in sidebar)
st.sidebar.header("Player Rating")
selected_rows = grid_response['selected_rows']

if isinstance(selected_rows, pd.DataFrame) and not selected_rows.empty:
    selected_player = selected_rows.iloc[0]

    if 'index' in selected_player:
        player_name = selected_player['index']
        st.sidebar.markdown(f"**{player_name}**")
        if 'rating' in selected_player:
            st.sidebar.markdown(selected_player['rating'])
        else:
            st.sidebar.error(f"No rating found for player: {player_name}")
    else:
        st.sidebar.error("Player name ('index') not found in selected data")
else:
    st.sidebar.info("Select a player to view their rating.")

# Create two columns for the remaining content
col1, col2 = st.columns([1, 1])

with col1:
    # Display summary stats grouped by position
    st.header("Summary Statistics by Position")
    summary_stats = filtered_df.groupby('pos').agg({
        'weighted_mean': ['mean', 'std', 'min', 'max'],
        'discounted_ci_lower': ['mean', 'min', 'max'],
        'ci_upper': ['mean', 'min', 'max'],
        'vbd': ['mean', 'min', 'max']
    }).round(2)

    # Flatten column names
    summary_stats.columns = ['_'.join(col).strip() for col in summary_stats.columns.values]
    st.write(summary_stats)

with col2:
    # Histogram of fantasy points
    st.header("Distribution of Fantasy Points")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(data=filtered_df, x='weighted_mean', kde=True, ax=ax)
    ax.set_xlabel('Fantasy Points (Weighted Mean)')
    ax.set_ylabel('Frequency')
    st.pyplot(fig)