"""
Offensive player data scraping (QB, RB, WR, TE)
Modernized version of web_scrape_offense.py
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


class OffenseScraper(BaseScraper):
    """Scraper for offensive player statistics"""
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.base_url = "https://www.footballdb.com/statistics/nfl"
        
    def scrape_season_data(self, year: int, week: int = None) -> Optional[pd.DataFrame]:
        """
        Scrape offensive statistics for a season or specific week
        
        Args:
            year: NFL season year
            week: Specific week (1-17), if None scrapes season totals
            
        Returns:
            DataFrame with offensive player statistics
        """
        try:
            # Determine URL pattern based on week
            if week:
                url_suffix = f"{year}/week-{week}"
            else:
                url_suffix = f"{year}/season"
            
            all_data = []
            
            # Scrape each position
            positions = ['qb', 'rb', 'wr', 'te']
            
            for position in positions:
                logger.info(f"Scraping {position.upper()} data for {year}" + (f" week {week}" if week else ""))
                
                pos_data = self._scrape_position_data(year, position, week)
                if pos_data:
                    all_data.extend(pos_data)
                
                # Rate limiting
                time.sleep(random.uniform(1.0, 3.0))
            
            if all_data:
                df = pd.DataFrame(all_data)
                logger.info(f"Scraped {len(df)} offensive player records")
                return df
            else:
                logger.warning("No offensive data scraped")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping offensive data: {e}")
            return None
    
    def _scrape_position_data(self, year: int, position: str, week: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape data for specific position"""
        try:
            # Build URL
            if week:
                url = f"{self.base_url}/{position}/{year}/week-{week}"
            else:
                url = f"{self.base_url}/{position}/{year}/season"
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                return []
            
            # Find statistics table
            table = soup.find('table', {'class': 'statistics'})
            if not table:
                logger.warning(f"No statistics table found for {position} {year}")
                return []
            
            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
            
            if not headers:
                logger.warning(f"No headers found for {position} table")
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
                        row_data['position'] = position.upper()
                        row_data['year'] = year
                        row_data['week'] = week
                        row_data['scraped_at'] = pd.Timestamp.now()
                        
                        data.append(row_data)
            
            logger.debug(f"Scraped {len(data)} {position} records")
            return data
            
        except Exception as e:
            logger.error(f"Error scraping {position} data: {e}")
            return []
    
    def _clean_stat_value(self, value: str) -> Any:
        """Clean and convert statistical values"""
        if not value or value in ['-', '--', 'N/A']:
            return 0
        
        # Remove commas
        value = value.replace(',', '')
        
        # Try to convert to numeric
        try:
            # Try integer first
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            # Return as string if conversion fails
            return value
    
    def scrape_multiple_weeks(self, year: int, weeks: List[int]) -> pd.DataFrame:
        """Scrape data for multiple weeks"""
        all_data = []
        
        for week in weeks:
            logger.info(f"Scraping week {week} of {year}")
            
            week_data = self.scrape_season_data(year, week)
            if week_data is not None:
                all_data.append(week_data)
            
            # Rate limiting between weeks
            time.sleep(random.uniform(2.0, 4.0))
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Combined data: {len(combined_df)} total records")
            return combined_df
        else:
            logger.warning("No data scraped from any week")
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
            logger.info(f"Saved offensive data to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False
    
    def get_position_mapping(self) -> Dict[str, str]:
        """Get mapping of position codes to full names"""
        return {
            'qb': 'Quarterback',
            'rb': 'Running Back', 
            'wr': 'Wide Receiver',
            'te': 'Tight End'
        }
    
    def validate_scraped_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Validate scraped offensive data"""
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
        required_columns = ['position', 'year']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            validation_result['errors'].extend([f"Missing column: {col}" for col in missing_columns])
            validation_result['valid'] = False
        
        # Position distribution
        if 'position' in data.columns:
            position_counts = data['position'].value_counts().to_dict()
            validation_result['stats']['position_distribution'] = position_counts
            
            # Check if all expected positions are present
            expected_positions = ['QB', 'RB', 'WR', 'TE']
            missing_positions = [pos for pos in expected_positions if pos not in position_counts]
            
            if missing_positions:
                validation_result['warnings'].append(f"Missing positions: {missing_positions}")
        
        # Data completeness
        total_records = len(data)
        validation_result['stats']['total_records'] = total_records
        
        # Check for duplicates
        if 'Player' in data.columns:
            duplicates = data.duplicated(subset=['Player', 'position', 'year', 'week'], keep=False)
            duplicate_count = duplicates.sum()
            
            if duplicate_count > 0:
                validation_result['warnings'].append(f"Found {duplicate_count} duplicate records")
                validation_result['stats']['duplicates'] = duplicate_count
        
        return validation_result


# Legacy compatibility functions
def scrape_offense_data(year: int, week: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Legacy compatibility function"""
    scraper = OffenseScraper()
    return scraper.scrape_season_data(year, week)


def scrape_offense_full_season(year: int) -> pd.DataFrame:
    """Legacy compatibility function"""
    scraper = OffenseScraper()
    return scraper.scrape_full_season(year)