"""
Base scraper class with common functionality
"""

import requests
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from pathlib import Path

from ...core.config import Config, get_config

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for web scrapers with common functionality"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.session = requests.Session()
        self.setup_session()
    
    def setup_session(self):
        """Setup session with headers and rate limiting"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_with_retry(self, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """GET request with retry logic and rate limiting"""
        for attempt in range(max_retries):
            try:
                # Rate limiting
                delay = random.uniform(1, 3)
                time.sleep(delay)
                
                response = self.session.get(url, **kwargs)
                response.raise_for_status()
                
                logger.debug(f"Successfully fetched {url}")
                return response
                
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def save_data(self, data: List[Dict], filename: str, output_dir: Optional[Path] = None):
        """Save scraped data to CSV"""
        import pandas as pd
        
        if not data:
            logger.warning(f"No data to save for {filename}")
            return
        
        output_path = output_dir or self.config.raw_data_dir
        output_path.mkdir(parents=True, exist_ok=True)
        
        filepath = output_path / filename
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        
        logger.info(f"Saved {len(data)} records to {filepath}")
    
    @abstractmethod
    def scrape(self, year: int, week: int) -> List[Dict]:
        """Scrape data for a specific year and week"""
        pass
    
    def scrape_season(self, year: int, weeks: Optional[List[int]] = None) -> Dict[int, List[Dict]]:
        """Scrape entire season of data"""
        if weeks is None:
            weeks = list(range(1, 18))  # NFL weeks 1-17
        
        season_data = {}
        
        for week in weeks:
            try:
                logger.info(f"Scraping {self.__class__.__name__} data for {year} Week {week}")
                week_data = self.scrape(year, week)
                season_data[week] = week_data
                
                # Save individual week data
                filename = f"{self.get_data_prefix()}_{year}_{week}.csv"
                self.save_data(week_data, filename)
                
            except Exception as e:
                logger.error(f"Failed to scrape {year} Week {week}: {e}")
                season_data[week] = []
        
        return season_data
    
    @abstractmethod
    def get_data_prefix(self) -> str:
        """Return the data file prefix for this scraper"""
        pass