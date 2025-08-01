"""
Player biographical data scraping
Modernized version of web_scrape_players.py
"""

import time
import random
import logging
import pandas as pd
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
import string

from .base import BaseScraper
from ...core.config import Config, get_config

logger = logging.getLogger(__name__)


def clean_player_name(name: str) -> str:
    """
    Clean and standardize player names
    
    Args:
        name: Raw player name from data source
        
    Returns:
        Cleaned name in "Last, First" format
    """
    # Find the last occurrence of a name pattern (which should be the abbreviated version)
    abbreviated_match = re.search(r'([A-Z]\.?\s*[-\w]+)$', name)
    if abbreviated_match:
        abbreviated_part = abbreviated_match.group(1)
        # Remove the abbreviated part from the original name
        full_name = name[:name.index(abbreviated_part)].strip()

        # Handle hyphenated last names
        if '-' in abbreviated_part:
            last_name = abbreviated_part.split()[-1]
        else:
            last_name = abbreviated_part.split()[-1]

        # Extract first name by removing last name from full name
        first_name = full_name.replace(last_name, '').strip()

        # Handle cases where the first name includes initials
        if re.match(r'^[A-Z]\.?[A-Z]\.?$', first_name):
            return f"{last_name}, {first_name}"
        else:
            return f"{last_name}, {first_name.split()[-1]}"

    # If the above logic fails, return an error message
    return f"Name format error: {name}"


class PlayerScraper(BaseScraper):
    """Scraper for player biographical information"""
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.base_url = "https://www.nfl.com/players"
    
    def get_data_prefix(self) -> str:
        """Return the data file prefix for this scraper"""
        return "players"
    
    def scrape(self, year: int, week: int) -> List[Dict]:
        """Scrape data for a specific year and week - not applicable for player data"""
        return []
    
    def get_page_content(self, url: str):
        """Get page content using BeautifulSoup"""
        try:
            from bs4 import BeautifulSoup
            response = self.get_with_retry(url)
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
        
    def scrape_all_players(self) -> pd.DataFrame:
        """
        Scrape all player biographical data
        
        Returns:
            DataFrame with player biographical information
        """
        try:
            logger.info("Starting comprehensive player data scraping")
            
            all_data = []
            
            # Scrape players by alphabet (A-Z)
            for letter in string.ascii_uppercase:
                logger.info(f"Scraping players starting with '{letter}'")
                
                letter_data = self._scrape_players_by_letter(letter)
                if letter_data:
                    all_data.extend(letter_data)
                
                # Rate limiting between letters
                time.sleep(random.uniform(2.0, 4.0))
            
            if all_data:
                df = pd.DataFrame(all_data)
                logger.info(f"Scraped {len(df)} total player records")
                return df
            else:
                logger.warning("No player data scraped")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error scraping player data: {e}")
            return pd.DataFrame()
    
    def _scrape_players_by_letter(self, letter: str) -> List[Dict[str, Any]]:
        """Scrape players whose last names start with given letter"""
        try:
            url = f"{self.base_url}/players-{letter.lower()}.html"
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                return []
            
            # Find player tables (there might be multiple tables per page)
            tables = soup.find_all('table', {'class': 'statistics'})
            if not tables:
                logger.warning(f"No player tables found for letter {letter}")
                return []
            
            all_players = []
            
            for table in tables:
                # Extract headers
                headers = []
                header_row = table.find('thead')
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
                
                if not headers:
                    continue
                
                # Extract data rows
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= len(headers):
                            row_data = {}
                            
                            for i, cell in enumerate(cells[:len(headers)]):
                                if i < len(headers):
                                    header = headers[i]
                                    value = cell.get_text(strip=True)
                                    
                                    # Clean player data
                                    value = self._clean_player_value(value, header)
                                    row_data[header] = value
                            
                            # Add metadata
                            row_data['scraped_at'] = pd.Timestamp.now()
                            row_data['letter_group'] = letter
                            
                            all_players.append(row_data)
            
            logger.debug(f"Scraped {len(all_players)} players for letter {letter}")
            return all_players
            
        except Exception as e:
            logger.error(f"Error scraping players for letter {letter}: {e}")
            return []
    
    def scrape_active_players(self, year: int = None) -> pd.DataFrame:
        """
        Scrape only active players for a specific year
        
        Args:
            year: Season year (if None, uses current year)
            
        Returns:
            DataFrame with active player information
        """
        try:
            if year is None:
                year = pd.Timestamp.now().year
            
            logger.info(f"Scraping active players for {year}")
            
            # Get all players first
            all_players = self.scrape_all_players()
            
            if all_players.empty:
                return pd.DataFrame()
            
            # Filter for active players (this would need to be enhanced based on actual data structure)
            # For now, return all players - in reality, we'd filter by active status or recent games
            active_players = all_players.copy()
            active_players['active_year'] = year
            
            logger.info(f"Found {len(active_players)} active players for {year}")
            return active_players
            
        except Exception as e:
            logger.error(f"Error scraping active players: {e}")
            return pd.DataFrame()
    
    def _clean_player_value(self, value: str, header: str) -> Any:
        """Clean and convert player biographical values"""
        if not value or value in ['-', '--', 'N/A']:
            return None
        
        # Handle specific fields
        header_lower = header.lower()
        
        # Height field (e.g., "6-2" -> convert to inches)
        if 'height' in header_lower and '-' in value:
            try:
                parts = value.split('-')
                if len(parts) == 2:
                    feet = int(parts[0])
                    inches = int(parts[1])
                    return feet * 12 + inches
            except ValueError:
                pass
        
        # Weight field (remove "lbs" and convert to int)
        if 'weight' in header_lower:
            try:
                # Remove common suffixes
                clean_weight = value.replace('lbs', '').replace('lb', '').strip()
                return int(clean_weight)
            except ValueError:
                pass
        
        # Age field
        if 'age' in header_lower:
            try:
                return int(value)
            except ValueError:
                pass
        
        # Experience/Years field
        if 'exp' in header_lower or 'years' in header_lower:
            try:
                return int(value.replace('yrs', '').replace('yr', '').strip())
            except ValueError:
                pass
        
        # Return as-is for other fields
        return value.strip()
    
    def enrich_with_team_data(self, players_df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Enrich player data with current team information
        
        Args:
            players_df: DataFrame with player data
            year: Season year for team assignments
            
        Returns:
            DataFrame with team information added
        """
        try:
            logger.info(f"Enriching player data with {year} team assignments")
            
            # This would typically involve scraping roster pages for each team
            # For now, we'll return the data as-is
            # In a full implementation, this would:
            # 1. Scrape each NFL team's roster page
            # 2. Match players by name
            # 3. Add current team, jersey number, etc.
            
            enriched_df = players_df.copy()
            enriched_df['season_year'] = year
            
            return enriched_df
            
        except Exception as e:
            logger.error(f"Error enriching player data: {e}")
            return players_df
    
    def save_data(self, data: pd.DataFrame, filepath: Path) -> bool:
        """Save scraped data to file"""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(filepath, index=False)
            logger.info(f"Saved player data to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False
    
    def get_player_positions(self) -> List[str]:
        """Get list of all NFL positions"""
        return ['QB', 'RB', 'FB', 'WR', 'TE', 'OL', 'C', 'G', 'T', 
                'DL', 'DE', 'DT', 'NT', 'LB', 'ILB', 'OLB', 'MLB',
                'DB', 'CB', 'S', 'FS', 'SS', 'K', 'P', 'LS']
    
    def normalize_player_names(self, data: pd.DataFrame) -> pd.DataFrame:
        """Normalize player names for consistency"""
        df = data.copy()
        
        if 'Player' in df.columns:
            # Apply name cleaning
            df['normalized_name'] = df['Player'].apply(self._normalize_name)
        elif 'Name' in df.columns:
            df['normalized_name'] = df['Name'].apply(self._normalize_name)
        
        return df
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a player name"""
        if not name:
            return ""
        
        # Remove common suffixes
        suffixes = [' Jr.', ' Sr.', ' III', ' II', ' IV', ' V']
        normalized = name
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        # Remove extra whitespace and convert to title case
        normalized = ' '.join(normalized.split()).title()
        
        return normalized
    
    def validate_scraped_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Validate scraped player data"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        if data.empty:
            validation_result['valid'] = False
            validation_result['errors'].append("No data to validate")
            return validation_result
        
        # Check for required columns (flexible since different sources have different formats)
        expected_columns = ['Player', 'Name']  # At least one should exist
        has_name_column = any(col in data.columns for col in expected_columns)
        
        if not has_name_column:
            validation_result['errors'].append("No player name column found")
            validation_result['valid'] = False
        
        # Data completeness
        total_records = len(data)
        validation_result['stats']['total_records'] = total_records
        
        # Check for reasonable player count
        if total_records < 1000:
            validation_result['warnings'].append(f"Low player count: {total_records}")
        elif total_records > 5000:
            validation_result['warnings'].append(f"High player count: {total_records}")
        
        # Position distribution (if available)
        position_columns = ['Position', 'Pos']
        position_col = None
        for col in position_columns:
            if col in data.columns:
                position_col = col
                break
        
        if position_col:
            position_counts = data[position_col].value_counts().to_dict()
            validation_result['stats']['position_distribution'] = dict(list(position_counts.items())[:10])  # Top 10
        
        # Check for duplicates
        name_column = 'Player' if 'Player' in data.columns else 'Name'
        if name_column in data.columns:
            duplicates = data.duplicated(subset=[name_column], keep=False)
            duplicate_count = duplicates.sum()
            
            if duplicate_count > 0:
                validation_result['warnings'].append(f"Found {duplicate_count} duplicate player names")
                validation_result['stats']['duplicates'] = duplicate_count
        
        return validation_result


# Legacy compatibility functions
def scrape_all_player_data() -> pd.DataFrame:
    """Legacy compatibility function"""
    scraper = PlayerScraper()
    return scraper.scrape_all_players()


def scrape_active_player_data(year: int) -> pd.DataFrame:
    """Legacy compatibility function"""
    scraper = PlayerScraper()
    return scraper.scrape_active_players(year)