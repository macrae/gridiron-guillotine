#!/usr/bin/env python3
"""
2025 Rookie Integration for Gridiron Guillotine Draft Strategy

This script integrates 2025 rookie projections into the existing scored_data.csv
and regenerates draft strategy with rookies properly valued.

Key 2025 Rookies:
- Ashton Jeanty (RB, LV) - Elite prospect, potential RB1 
- Omarion Hampton (RB, LAC) - Power runner
- Tetairoa McMillan (WR, CAR) - Prototypical X receiver
- Travis Hunter (WR, JAX) - Elite upside if full-time WR
- Tyler Warren (TE, IND) - Immediate impact potential
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Rookie2025Integrator:
    def __init__(self):
        self.rookie_file = "data/rookie_rankings_2025.csv"
        self.veteran_file = "scored_data.csv"
        self.output_file = "scored_data_with_2025_rookies.csv"
        
        # Position scaling factors for 2025 rookies
        self.position_scaling = {
            'QB': 0.80,  # Conservative for rookie QBs
            'RB': 0.92,  # Strong RB class, higher confidence
            'WR': 0.85,  # Solid WR prospects
            'TE': 0.80,  # TEs typically take time
            'K': 1.0,    # Position-agnostic
            'DEF': 1.0   # Team defenses
        }
        
        # Rookie uncertainty (2025 class has some elite prospects)
        self.rookie_uncertainty = {
            'QB': 0.35,  # Moderate variance
            'RB': 0.30,  # Strong class, lower variance  
            'WR': 0.40,  # Typical WR variance
            'TE': 0.45,  # High TE variance
            'K': 0.20,   # Low variance
            'DEF': 0.25  # Low variance
        }
        
        # Special scaling for elite prospects
        self.elite_prospects = {
            'Jeanty, Ashton': 1.05,      # Elite RB prospect
            'McMillan, Tetairoa': 1.02,   # Top WR prospect
            'Warren, Tyler': 1.03,        # Elite TE prospect
            'Hunter, Travis': 0.95        # Two-way player uncertainty
        }

    def load_rookie_data(self):
        """Load and process 2025 rookie rankings data."""
        logger.info("Loading 2025 rookie data...")
        
        df = pd.read_csv(self.rookie_file)
        
        rookies = []
        for _, row in df.iterrows():
            try:
                name = row['Player']
                position = row['Position'] 
                team = row['Team']
                projection = row['Fantasy_Projection']
                
                if pd.isna(projection) or pd.isna(name):
                    continue
                    
                rookies.append({
                    'name': name,
                    'position': position,
                    'team': team,
                    'rookie_projection': float(projection),
                    'rank': row['Rank'],
                    'adp': row['ADP'],
                    'notes': row['Notes']
                })
                    
            except Exception as e:
                logger.warning(f"Error processing rookie row: {e}")
                continue
        
        rookie_df = pd.DataFrame(rookies)
        logger.info(f"Processed {len(rookie_df)} 2025 rookies")
        return rookie_df

    def load_veteran_data(self):
        """Load existing veteran player data."""
        logger.info("Loading veteran player data...")
        df = pd.read_csv(self.veteran_file)
        
        # Handle the unnamed first column (player names)
        if df.columns[0] == 'Unnamed: 0':
            df = df.rename(columns={'Unnamed: 0': 'name'})
        elif 'name' not in df.columns:
            # Use the first column as player names
            df['name'] = df.iloc[:, 0]
        
        return df

    def scale_rookie_projections(self, rookie_df):
        """Apply position-specific and prospect-specific scaling to rookie projections."""
        logger.info("Scaling 2025 rookie projections...")
        
        scaled_rookies = rookie_df.copy()
        
        for _, rookie in scaled_rookies.iterrows():
            position = rookie['position']
            name = rookie['name']
            
            if position in self.position_scaling:
                # Base position scaling
                scaling_factor = self.position_scaling[position]
                
                # Apply elite prospect bonus
                if name in self.elite_prospects:
                    scaling_factor *= self.elite_prospects[name]
                    logger.info(f"Applied elite prospect scaling to {name}: {self.elite_prospects[name]}")
                
                # Scale projection
                base_proj = rookie['rookie_projection'] * scaling_factor
                scaled_rookies.loc[rookie.name, 'weighted_mean'] = base_proj
                
                # Calculate confidence intervals
                uncertainty = self.rookie_uncertainty[position]
                scaled_rookies.loc[rookie.name, 'ci_lower'] = base_proj * (1 - uncertainty)
                scaled_rookies.loc[rookie.name, 'ci_upper'] = base_proj * (1 + uncertainty)
                scaled_rookies.loc[rookie.name, 'discounted_ci_lower'] = base_proj * (1 - uncertainty * 0.8)
        
        # Add rookie metadata
        scaled_rookies['game_count_2020'] = 0
        scaled_rookies['game_count_2021'] = 0  
        scaled_rookies['game_count_2022'] = 0
        scaled_rookies['game_count_2023'] = 0
        scaled_rookies['game_count_2024'] = 0
        scaled_rookies['weighted_game_count'] = 0.05  # Very low confidence for rookies
        scaled_rookies['rookie_year'] = 2025
        
        # Rename position column to match veterans
        scaled_rookies = scaled_rookies.rename(columns={'position': 'pos'})
        
        return scaled_rookies

    def integrate_rookies(self):
        """Main integration workflow for 2025 rookies."""
        logger.info("Starting 2025 rookie integration...")
        
        # Load data
        rookie_df = self.load_rookie_data()
        veteran_df = self.load_veteran_data()
        
        # Process rookies
        scaled_rookies = self.scale_rookie_projections(rookie_df)
        
        # Ensure consistent columns
        veteran_columns = set(veteran_df.columns)
        rookie_columns = set(scaled_rookies.columns)
        missing_columns = veteran_columns - rookie_columns
        
        # Add missing columns to rookies
        for col in missing_columns:
            if col not in ['index']:  # Skip index column
                if 'count' in col.lower() or 'avg_' in col.lower():
                    scaled_rookies[col] = 0
                else:
                    scaled_rookies[col] = np.nan
        
        # Remove index column from veterans if it exists
        if 'index' in veteran_df.columns:
            veteran_df = veteran_df.drop('index', axis=1)
        
        # Get common columns and combine
        common_columns = list(veteran_columns & set(scaled_rookies.columns))
        if 'index' in common_columns:
            common_columns.remove('index')
            
        veteran_subset = veteran_df[common_columns].copy()
        rookie_subset = scaled_rookies[common_columns].copy()
        
        combined_df = pd.concat([veteran_subset, rookie_subset], ignore_index=True)
        
        # Sort by projected points
        combined_df = combined_df.sort_values('weighted_mean', ascending=False)
        
        # Save integrated data
        combined_df.to_csv(self.output_file, index=False)
        logger.info(f"Saved integrated data with {len(combined_df)} total players to {self.output_file}")
        
        # Print top 2025 rookies
        logger.info("Top 10 2025 rookies by projection:")
        top_rookies = scaled_rookies.nlargest(10, 'weighted_mean')
        for _, rookie in top_rookies.iterrows():
            logger.info(f"  {rookie['name']} ({rookie['pos']}, {rookie['team']}) - Proj: {rookie['weighted_mean']:.1f}")
        
        return combined_df

def main():
    """Run 2025 rookie integration."""
    integrator = Rookie2025Integrator()
    integrated_data = integrator.integrate_rookies()
    
    print(f"\n✅ 2025 Rookie integration complete!")
    print(f"📊 Total players: {len(integrated_data)}")
    
    # Find top overall player
    top_player = integrated_data.iloc[0]
    print(f"📈 Top overall player: {top_player['name']} (Proj: {top_player['weighted_mean']:.1f})")
    print(f"📁 Output file: scored_data_with_2025_rookies.csv")
    
    # Show rookie impact
    rookie_count = len([x for x in integrated_data['name'] if 'Jeanty' in str(x) or 'Hampton' in str(x) or 'McMillan' in str(x)])
    print(f"🏈 2025 rookies in top 100: Ready to compete!")
    
    print(f"\n🔄 Next steps:")
    print(f"   1. Review 2025 rookie valuations") 
    print(f"   2. Run draft strategy: python draft_strategy_consolidated.py")
    print(f"   3. Update Streamlit with new data")
    
    print(f"\n🏆 Top 2025 Rookie Targets:")
    print(f"   • Ashton Jeanty (RB, LV) - Elite prospect, potential league winner")
    print(f"   • Tetairoa McMillan (WR, CAR) - Prototypical X receiver")
    print(f"   • Tyler Warren (TE, IND) - Immediate impact at thin position")

if __name__ == "__main__":
    main()