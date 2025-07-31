"""
Defensive/special teams data scraping
Modernized version of web_scrape_defense.py
"""

import time
import random
import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base import BaseScraper
from ...core.config import Config, get_config

logger = logging.getLogger(__name__)


class DefenseScraper(BaseScraper):
    """Scraper for team defense and special teams statistics"""
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.base_url = "https://www.footballdb.com/statistics/nfl"
        
    def scrape_season_data(self, year: int, week: int = None) -> Optional[pd.DataFrame]:
        """
        Scrape defensive statistics for a season or specific week
        
        Args:
            year: NFL season year
            week: Specific week (1-17), if None scrapes season totals
            
        Returns:
            DataFrame with defensive statistics
        """
        try:
            logger.info(f"Scraping defense data for {year}" + (f" week {week}" if week else ""))
            
            all_data = []
            
            # Scrape team defense and special teams
            categories = ['defense', 'special-teams']
            
            for category in categories:
                cat_data = self._scrape_defense_category(year, category, week)
                if cat_data:
                    all_data.extend(cat_data)
                
                # Rate limiting
                time.sleep(random.uniform(1.0, 3.0))
            
            if all_data:
                df = pd.DataFrame(all_data)
                logger.info(f"Scraped {len(df)} defensive records")
                return df
            else:
                logger.warning("No defensive data scraped")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping defensive data: {e}")
            return None
    
    def _scrape_defense_category(self, year: int, category: str, week: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape data for specific defensive category"""
        try:
            # Build URL
            if week:
                url = f"{self.base_url}/{category}/{year}/week-{week}"
            else:
                url = f"{self.base_url}/{category}/{year}/season"
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                return []
            
            # Find statistics table
            table = soup.find('table', {'class': 'statistics'})
            if not table:
                logger.warning(f"No statistics table found for {category} {year}")
                return []
            
            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
            
            if not headers:
                logger.warning(f"No headers found for {category} table")
                return []
            
            # Extract data rows
            data = []
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
                                
                                # Clean and convert values
                                value = self._clean_stat_value(value)
                                row_data[header] = value
                        
                        # Add metadata
                        row_data['category'] = category
                        row_data['position'] = 'DEF'  # All defensive stats use DEF position
                        row_data['year'] = year
                        row_data['week'] = week
                        row_data['scraped_at'] = pd.Timestamp.now()
                        
                        data.append(row_data)
            
            logger.debug(f"Scraped {len(data)} {category} records")
            return data
            
        except Exception as e:
            logger.error(f"Error scraping {category} data: {e}")
            return []
    
    def _clean_stat_value(self, value: str) -> Any:
        """Clean and convert statistical values"""
        if not value or value in ['-', '--', 'N/A']:
            return 0
        
        # Remove commas and special characters
        value = value.replace(',', '').replace('%', '')
        
        # Handle negative values (e.g., turnovers)
        is_negative = value.startswith('-')
        if is_negative:
            value = value[1:]
        
        # Try to convert to numeric
        try:
            # Try integer first
            if '.' not in value:
                result = int(value)
            else:
                result = float(value)
            
            return -result if is_negative else result
            
        except ValueError:
            # Return as string if conversion fails
            return value
    
    def scrape_multiple_weeks(self, year: int, weeks: List[int]) -> pd.DataFrame:
        """Scrape data for multiple weeks"""
        all_data = []
        
        for week in weeks:
            logger.info(f"Scraping defensive data for week {week} of {year}")
            
            week_data = self.scrape_season_data(year, week)
            if week_data is not None:
                all_data.append(week_data)
            
            # Rate limiting between weeks
            time.sleep(random.uniform(2.0, 4.0))
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Combined defensive data: {len(combined_df)} total records")
            return combined_df
        else:
            logger.warning("No defensive data scraped from any week")
            return pd.DataFrame()
    
    def scrape_full_season(self, year: int) -> pd.DataFrame:
        """Scrape complete season data (all 17 weeks)"""
        weeks = list(range(1, 18))  # Weeks 1-17
        return self.scrape_multiple_weeks(year, weeks)
    
    def save_data(self, data: pd.DataFrame, filepath: Path) -> bool:
        """Save scraped data to file"""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(filepath, index=False)
            logger.info(f"Saved defensive data to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False
    
    def get_defensive_categories(self) -> Dict[str, str]:
        """Get mapping of defensive categories"""
        return {
            'defense': 'Team Defense',
            'special-teams': 'Special Teams'
        }
    
    def calculate_fantasy_points(self, data: pd.DataFrame, scoring_system: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """Calculate fantasy points for defensive stats"""
        if scoring_system is None:
            scoring_system = self._get_default_defense_scoring()
        
        df = data.copy()
        df['fantasy_points'] = 0.0
        
        # Apply scoring for available stats
        for stat, points_per in scoring_system.items():
            if stat in df.columns:
                df['fantasy_points'] += df[stat].fillna(0) * points_per
        
        return df
    
    def _get_default_defense_scoring(self) -> Dict[str, float]:
        """Get default defensive fantasy scoring"""
        return {
            'sacks': 1.0,
            'interceptions': 2.0,
            'fumble_recoveries': 2.0,
            'defensive_tds': 6.0,
            'safeties': 2.0,
            'blocked_kicks': 2.0,
            'points_allowed_0': 10.0,
            'points_allowed_1_6': 7.0,
            'points_allowed_7_13': 4.0,
            'points_allowed_14_20': 1.0,
            'points_allowed_21_27': 0.0,
            'points_allowed_28_34': -1.0,
            'points_allowed_35_plus': -4.0,
        }
    
    def validate_scraped_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Validate scraped defensive data"""
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
        
        # Check required columns
        required_columns = ['category', 'position', 'year']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            validation_result['errors'].extend([f"Missing column: {col}" for col in missing_columns])
            validation_result['valid'] = False
        
        # Category distribution
        if 'category' in data.columns:
            category_counts = data['category'].value_counts().to_dict()
            validation_result['stats']['category_distribution'] = category_counts
            
            # Check if expected categories are present
            expected_categories = ['defense', 'special-teams']
            missing_categories = [cat for cat in expected_categories if cat not in category_counts]
            
            if missing_categories:
                validation_result['warnings'].append(f"Missing categories: {missing_categories}")
        
        # Data completeness
        total_records = len(data)
        validation_result['stats']['total_records'] = total_records
        
        # Check for reasonable team count (should be around 32 teams per category)
        if 'Team' in data.columns and 'category' in data.columns:
            teams_per_category = data.groupby('category')['Team'].nunique().to_dict()
            validation_result['stats']['teams_per_category'] = teams_per_category
            
            for category, team_count in teams_per_category.items():
                if team_count < 30:  # Allow some flexibility
                    validation_result['warnings'].append(f"Low team count for {category}: {team_count}")
        
        return validation_result
    
    def get_data_prefix(self) -> str:
        """Return the data file prefix for this scraper"""
        return "defense"
    
    def scrape(self, year: int, week: int) -> List[Dict]:
        """
        Scrape data for a specific year and week (required by BaseScraper)
        
        Args:
            year: NFL season year
            week: Week number (1-18)
            
        Returns:
            List of dictionaries containing defensive statistics
        """
        try:
            df = self.scrape_season_data(year, week)
            if df is not None and not df.empty:
                return df.to_dict('records')
            else:
                return []
        except Exception as e:
            logger.error(f"Error in scrape method: {e}")
            return []
    
    def get_page_content(self, url: str):
        """Get page content using BeautifulSoup"""
        try:
            response = self.get_with_retry(url)
            from bs4 import BeautifulSoup
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error getting page content from {url}: {e}")
            return None


# Legacy compatibility functions
def scrape_defense_data(year: int, week: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Legacy compatibility function"""
    scraper = DefenseScraper()
    return scraper.scrape_season_data(year, week)


def scrape_defense_full_season(year: int) -> pd.DataFrame:
    """Legacy compatibility function"""
    scraper = DefenseScraper()
    return scraper.scrape_full_season(year)