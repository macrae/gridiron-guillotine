from gridiron_guillotine.data.scrapers.players import clean_player_name
import os
import pandas as pd
import pytest

# Path to the directory containing player files
DATA_DIRECTORY = './data/'


def test_clean_player_name():
    # Iterate over all files in the player data directory
    for filename in os.listdir(DATA_DIRECTORY):
        if filename.startswith('offense_') and filename.endswith('.csv'):
            filepath = os.path.join(DATA_DIRECTORY, filename)
            df = pd.read_csv(filepath)

            # Assuming 'Player' column exists
            assert 'Player' in df.columns, f"'Player' column not found in {filename}"

            # Apply the cleaning function to each name
            df['Cleaned_Name'] = df['Player'].apply(clean_player_name)

            # Check that all cleaned names are non-empty strings with length > 1
            for cleaned_name, name in zip(df['Cleaned_Name'], df['Player']):
                assert isinstance(cleaned_name, str) and len(
                    cleaned_name) > 1, f"Invalid cleaned name found: {name}"
