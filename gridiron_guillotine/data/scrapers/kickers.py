"""
Kicker data scraping
Modernized version of web_scrape_kickers.py
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


class KickerScraper(BaseScraper):
    """Scraper for kicker statistics"""
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.base_url = "https://www.footballdb.com/statistics/nfl"
        
    def scrape_season_data(self, year: int, week: int = None) -> Optional[pd.DataFrame]:
        """
        Scrape kicker statistics for a season or specific week
        
        Args:
            year: NFL season year
            week: Specific week (1-17), if None scrapes season totals
            
        Returns:
            DataFrame with kicker statistics
        """
        try:
            logger.info(f"Scraping kicker data for {year}" + (f" week {week}" if week else ""))
            
            # Build URL
            if week:
                url = f"{self.base_url}/kicking/{year}/week-{week}"
            else:
                url = f"{self.base_url}/kicking/{year}/season"
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Find statistics table
            table = soup.find('table', {'class': 'statistics'})
            if not table:
                logger.warning(f"No kicking statistics table found for {year}")
                return None
            
            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
            
            if not headers:
                logger.warning("No headers found for kicking table")
                return None
            
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
                                value = self._clean_stat_value(value, header)
                                row_data[header] = value
                        
                        # Add metadata
                        row_data['position'] = 'K'
                        row_data['year'] = year
                        row_data['week'] = week
                        row_data['scraped_at'] = pd.Timestamp.now()
                        
                        data.append(row_data)
            
            if data:
                df = pd.DataFrame(data)
                logger.info(f"Scraped {len(df)} kicker records")
                return df
            else:
                logger.warning("No kicker data scraped")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping kicker data: {e}")
            return None
    
    def _clean_stat_value(self, value: str, header: str) -> Any:
        """Clean and convert kicker statistical values"""
        if not value or value in ['-', '--', 'N/A']:
            return 0
        
        # Handle percentage fields
        if '%' in value or header.lower().endswith('pct'):
            try:
                # Remove % and convert to decimal
                numeric_value = float(value.replace('%', ''))
                return numeric_value / 100.0
            except ValueError:
                return 0.0
        
        # Handle fraction fields (e.g., "15/18" for field goals made/attempted)
        if '/' in value:
            try:
                parts = value.split('/')
                if len(parts) == 2:
                    made = int(parts[0])
                    attempted = int(parts[1])
                    
                    # For some stats, we want both made and attempted
                    # For now, return made (could be enhanced to return both)
                    return made
            except ValueError:
                pass
        
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
            logger.info(f"Scraping kicker data for week {week} of {year}")
            
            week_data = self.scrape_season_data(year, week)
            if week_data is not None:
                all_data.append(week_data)
            
            # Rate limiting between weeks
            time.sleep(random.uniform(2.0, 4.0))
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Combined kicker data: {len(combined_df)} total records")
            return combined_df
        else:
            logger.warning("No kicker data scraped from any week")
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
            logger.info(f"Saved kicker data to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False
    
    def calculate_fantasy_points(self, data: pd.DataFrame, scoring_system: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """Calculate fantasy points for kicker stats"""
        if scoring_system is None:
            scoring_system = self._get_default_kicker_scoring()
        
        df = data.copy()
        df['fantasy_points'] = 0.0
        
        # Apply scoring for available stats
        for stat, points_per in scoring_system.items():
            if stat in df.columns:
                df['fantasy_points'] += df[stat].fillna(0) * points_per
        
        return df
    
    def _get_default_kicker_scoring(self) -> Dict[str, float]:
        """Get default kicker fantasy scoring"""
        return {
            'field_goals_made': 3.0,
            'extra_points_made': 1.0,
            'field_goals_0_19': 3.0,
            'field_goals_20_29': 3.0,
            'field_goals_30_39': 3.0,
            'field_goals_40_49': 4.0,
            'field_goals_50_plus': 5.0,
            'field_goals_missed': -1.0,  # Some leagues penalize misses
        }
    
    def analyze_kicker_performance(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze kicker performance metrics"""
        if data.empty:
            return {}
        
        analysis = {}
        
        # Overall stats
        analysis['total_kickers'] = len(data)
        
        # Field goal analysis
        if 'field_goals_made' in data.columns and 'field_goals_attempted' in data.columns:
            total_made = data['field_goals_made'].sum()
            total_attempted = data['field_goals_attempted'].sum()
            
            if total_attempted > 0:
                analysis['overall_fg_percentage'] = (total_made / total_attempted) * 100
        
        # Top performers
        if 'fantasy_points' in data.columns:
            top_kickers = data.nlargest(10, 'fantasy_points')[['Player', 'Team', 'fantasy_points']]
            analysis['top_kickers'] = top_kickers.to_dict('records')
        
        # Distance analysis (if available)
        distance_fields = ['field_goals_0_19', 'field_goals_20_29', 'field_goals_30_39', 
                          'field_goals_40_49', 'field_goals_50_plus']
        
        distance_analysis = {}
        for field in distance_fields:
            if field in data.columns:
                distance_analysis[field] = data[field].sum()
        
        if distance_analysis:
            analysis['distance_breakdown'] = distance_analysis
        
        return analysis
    
    def validate_scraped_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Validate scraped kicker data"""
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
        
        # Check position consistency
        if 'position' in data.columns:
            positions = data['position'].unique()
            if len(positions) > 1 or (len(positions) == 1 and positions[0] != 'K'):
                validation_result['warnings'].append(f"Unexpected positions in kicker data: {positions}")
        
        # Data completeness
        total_records = len(data)
        validation_result['stats']['total_records'] = total_records
        
        # Check for reasonable kicker count (should be around 32-40 kickers)
        if 'Player' in data.columns:
            unique_kickers = data['Player'].nunique()
            validation_result['stats']['unique_kickers'] = unique_kickers
            
            if unique_kickers < 25:
                validation_result['warnings'].append(f"Low kicker count: {unique_kickers}")
            elif unique_kickers > 50:
                validation_result['warnings'].append(f"High kicker count: {unique_kickers}")
        
        # Check for duplicates
        if 'Player' in data.columns:
            duplicates = data.duplicated(subset=['Player', 'year', 'week'], keep=False)
            duplicate_count = duplicates.sum()
            
            if duplicate_count > 0:
                validation_result['warnings'].append(f"Found {duplicate_count} duplicate records")
                validation_result['stats']['duplicates'] = duplicate_count
        
        return validation_result


# Legacy compatibility functions
def scrape_kicker_data(year: int, week: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Legacy compatibility function"""
    scraper = KickerScraper()
    return scraper.scrape_season_data(year, week)


def scrape_kickers_full_season(year: int) -> pd.DataFrame:
    """Legacy compatibility function"""
    scraper = KickerScraper()
    return scraper.scrape_full_season(year)