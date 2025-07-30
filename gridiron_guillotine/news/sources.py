"""
News source implementations for different NFL news providers
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .models import PlayerNews, NewsType, NewsSource, InjuryStatus

logger = logging.getLogger(__name__)


class BaseNewsSource(ABC):
    """Base class for all news sources"""
    
    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Gridiron-Guillotine Fantasy Football Tool 1.0'
        })
        # Add retry strategy
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except ImportError:
            # Fallback if urllib3 not available
            logger.debug("Retry strategy not available, using basic session")
    
    @abstractmethod
    def fetch_player_news(self, player_name: str, limit: int = 10) -> List[PlayerNews]:
        """Fetch news for a specific player"""
        pass
    
    @abstractmethod
    def fetch_injury_reports(self, team: Optional[str] = None) -> List[PlayerNews]:
        """Fetch current injury reports"""
        pass
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        
        return text
    
    def _is_player_mentioned(self, player_name: str, text: str) -> bool:
        """Check if player is mentioned in text"""
        if not player_name or not text:
            return False
        
        # Handle different name formats (Last, First vs First Last)
        if ',' in player_name:
            # Convert "Last, First" to "First Last"
            parts = player_name.split(',')
            if len(parts) == 2:
                player_name = f"{parts[1].strip()} {parts[0].strip()}"
        
        name_parts = player_name.lower().split()
        text_lower = text.lower()
        
        # Check full name
        if player_name.lower() in text_lower:
            return True
        
        # Check first + last name combination
        if len(name_parts) >= 2:
            first_last = f"{name_parts[0]} {name_parts[-1]}"
            if first_last in text_lower:
                return True
        
        # Check last name only (must be substantial match)
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            if len(last_name) >= 4 and last_name in text_lower:
                # Additional check to avoid false positives with common names
                words = text_lower.split()
                if last_name in words:  # Must be a complete word
                    return True
        
        return False
    
    def _classify_news_type(self, text: str) -> NewsType:
        """Classify news type based on content"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['injury', 'hurt', 'injured', 'questionable', 'doubtful', 'out']):
            return NewsType.INJURY
        elif any(word in text_lower for word in ['trade', 'traded']):
            return NewsType.TRADE
        elif any(word in text_lower for word in ['sign', 'release', 'waive', 'cut']):
            return NewsType.TRANSACTION
        elif any(word in text_lower for word in ['suspend', 'suspension']):
            return NewsType.SUSPENSION
        elif any(word in text_lower for word in ['practice', 'depth']):
            return NewsType.PRACTICE_STATUS
        else:
            return NewsType.GENERAL
    
    def _extract_player_name(self, headline: str) -> str:
        """Extract player name from headline"""
        # This is a simplified extraction - could be improved with NLP
        words = headline.split()
        
        # Look for capitalized words that might be names
        potential_names = []
        for i, word in enumerate(words[:-1]):
            if word.istitle() and words[i+1].istitle():
                potential_names.append(f"{word} {words[i+1]}")
        
        return potential_names[0] if potential_names else ""
    
    def _parse_injury_status(self, status_text: str) -> InjuryStatus:
        """Parse injury status from text"""
        if not status_text:
            return InjuryStatus.UNKNOWN
        
        status_lower = status_text.lower()
        
        if any(word in status_lower for word in ['out', 'inactive']):
            return InjuryStatus.OUT
        elif 'doubtful' in status_lower:
            return InjuryStatus.DOUBTFUL
        elif 'questionable' in status_lower:
            return InjuryStatus.QUESTIONABLE
        elif any(word in status_lower for word in ['injured reserve', 'ir']):
            return InjuryStatus.INJURED_RESERVE
        elif 'suspended' in status_lower:
            return InjuryStatus.SUSPENDED
        elif any(word in status_lower for word in ['healthy', 'active', 'good']):
            return InjuryStatus.HEALTHY
        else:
            return InjuryStatus.UNKNOWN


class ESPNNewsSource(BaseNewsSource):
    """ESPN API-based news source"""
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    
    def fetch_player_news(self, player_name: str, limit: int = 10) -> List[PlayerNews]:
        """Fetch player news from ESPN API"""
        try:
            # ESPN news endpoint
            url = f"{self.BASE_URL}/news"
            params = {'limit': limit * 3}  # Get more to filter by player
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            news_items = []
            
            articles = data.get('articles', [])
            logger.debug(f"ESPN returned {len(articles)} total articles")
            
            for article in articles:
                headline = article.get('headline', '')
                description = article.get('description', '')
                content = headline + " " + description
                
                if self._is_player_mentioned(player_name, content):
                    news_item = self._parse_espn_article(article, player_name)
                    if news_item:
                        news_items.append(news_item)
                        
                if len(news_items) >= limit:
                    break
            
            logger.info(f"Fetched {len(news_items)} news items for {player_name} from ESPN")
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching ESPN news for {player_name}: {e}")
            return []
    
    def fetch_injury_reports(self, team: Optional[str] = None) -> List[PlayerNews]:
        """Fetch injury reports from ESPN"""
        try:
            # ESPN doesn't have a dedicated injury endpoint, so we'll parse from news
            url = f"{self.BASE_URL}/news"
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            injury_news = []
            
            for article in data.get('articles', []):
                headline = article.get('headline', '').lower()
                if any(keyword in headline for keyword in ['injury', 'hurt', 'out', 'questionable']):
                    news_item = self._parse_espn_article(article)
                    if news_item:
                        news_item.news_type = NewsType.INJURY
                        injury_news.append(news_item)
            
            logger.info(f"Fetched {len(injury_news)} injury reports from ESPN")
            return injury_news
            
        except Exception as e:
            logger.error(f"Error fetching ESPN injury reports: {e}")
            return []
    
    def _parse_espn_article(self, article: Dict, player_name: str = "") -> Optional[PlayerNews]:
        """Parse ESPN article into PlayerNews object"""
        try:
            headline = article.get('headline', '')
            description = article.get('description', '')
            
            # Parse date
            published_str = article.get('published')
            published_date = datetime.now()
            if published_str:
                try:
                    published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                except:
                    pass
            
            # Determine news type
            news_type = self._classify_news_type(headline + " " + description)
            
            # Extract player name if not provided
            if not player_name:
                player_name = self._extract_player_name(headline)
            
            return PlayerNews(
                player_name=player_name or "Unknown",
                headline=self._clean_text(headline),
                content=self._clean_text(description),
                news_type=news_type,
                source=NewsSource.ESPN,
                published_date=published_date,
                url=article.get('links', {}).get('web', {}).get('href'),
                injury_status=self._parse_injury_status(headline + " " + description) if news_type == NewsType.INJURY else None
            )
            
        except Exception as e:
            logger.error(f"Error parsing ESPN article: {e}")
            return None
    
    def _is_player_mentioned(self, player_name: str, text: str) -> bool:
        """Check if player is mentioned in text"""
        if not player_name or not text:
            return False
        
        # Handle different name formats (Last, First vs First Last)
        if ',' in player_name:
            # Convert "Last, First" to "First Last"
            parts = player_name.split(',')
            if len(parts) == 2:
                player_name = f"{parts[1].strip()} {parts[0].strip()}"
        
        name_parts = player_name.lower().split()
        text_lower = text.lower()
        
        # Check full name
        if player_name.lower() in text_lower:
            return True
        
        # Check first + last name combination
        if len(name_parts) >= 2:
            first_last = f"{name_parts[0]} {name_parts[-1]}"
            if first_last in text_lower:
                return True
        
        # Check last name only (must be substantial match)
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            if len(last_name) >= 4 and last_name in text_lower:
                # Additional check to avoid false positives with common names
                words = text_lower.split()
                if last_name in words:  # Must be a complete word
                    return True
        
        return False
    
    def _classify_news_type(self, text: str) -> NewsType:
        """Classify news type based on content"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['injury', 'hurt', 'injured', 'questionable', 'doubtful', 'out']):
            return NewsType.INJURY
        elif any(word in text_lower for word in ['trade', 'traded']):
            return NewsType.TRADE
        elif any(word in text_lower for word in ['sign', 'release', 'waive', 'cut']):
            return NewsType.TRANSACTION
        elif any(word in text_lower for word in ['suspend', 'suspension']):
            return NewsType.SUSPENSION
        elif any(word in text_lower for word in ['practice', 'depth']):
            return NewsType.PRACTICE_STATUS
        else:
            return NewsType.GENERAL
    
    def _extract_player_name(self, headline: str) -> str:
        """Extract player name from headline"""
        # This is a simplified extraction - could be improved with NLP
        words = headline.split()
        
        # Look for capitalized words that might be names
        potential_names = []
        for i, word in enumerate(words[:-1]):
            if word.istitle() and words[i+1].istitle():
                potential_names.append(f"{word} {words[i+1]}")
        
        return potential_names[0] if potential_names else ""


class NFLNewsSource(BaseNewsSource):
    """NFL.com official news source"""
    
    BASE_URL = "https://www.nfl.com"
    
    def fetch_player_news(self, player_name: str, limit: int = 10) -> List[PlayerNews]:
        """Fetch player news from NFL.com using web scraping"""
        try:
            import time
            time.sleep(1)  # Rate limiting
            
            # Try NFL.com main news page and search for player mentions
            url = f"{self.BASE_URL}/news/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            # Look for various article containers NFL.com might use
            potential_selectors = [
                'article',
                'div[data-module*="News"]',
                'div.news-item',
                'a[href*="/news/"]',
                '.article-item',
                'div[class*="article"]'
            ]
            
            articles = []
            for selector in potential_selectors:
                found = soup.select(selector)
                if found:
                    articles.extend(found[:50])  # Limit to first 50 to avoid overload
                    
            logger.debug(f"Found {len(articles)} potential articles on NFL.com")
            
            for article in articles:
                try:
                    # Get article text content
                    text_content = article.get_text(separator=' ', strip=True)
                    
                    # Check if player is mentioned (more lenient check)
                    if self._is_player_mentioned(player_name, text_content):
                        news_item = self._parse_nfl_article(article, player_name)
                        if news_item:
                            news_items.append(news_item)
                            
                        if len(news_items) >= limit:
                            break
                            
                except Exception as e:
                    logger.debug(f"Error parsing NFL article: {e}")
                    continue
            
            logger.info(f"Fetched {len(news_items)} news items for {player_name} from NFL.com")
            return news_items
            
        except Exception as e:
            logger.warning(f"NFL.com scraping failed: {e}")
            return []
    
    def fetch_injury_reports(self, team: Optional[str] = None) -> List[PlayerNews]:
        """Fetch official injury reports from NFL.com"""
        try:
            url = f"{self.BASE_URL}/injuries/"
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            injury_news = []
            
            # Parse injury report table (structure would need verification)
            injury_rows = soup.find_all('tr', class_='injury-row')
            
            for row in injury_rows:
                news_item = self._parse_injury_row(row)
                if news_item and (not team or news_item.team == team):
                    injury_news.append(news_item)
            
            logger.info(f"Fetched {len(injury_news)} injury reports from NFL.com")
            return injury_news
            
        except Exception as e:
            logger.debug(f"NFL.com injury reports not implemented - {e}")
            return []
    
    def _parse_nfl_article(self, article_element, player_name: str) -> Optional[PlayerNews]:
        """Parse NFL.com article element"""
        try:
            # Extract headline
            headline = ""
            for selector in ['h1', 'h2', 'h3', 'h4', '.headline', '.title']:
                headline_elem = article_element.select_one(selector)
                if headline_elem:
                    headline = headline_elem.get_text(strip=True)
                    break
            
            # If no headline found in selectors, use link text or first strong text
            if not headline:
                if article_element.name == 'a':
                    headline = article_element.get_text(strip=True)
                else:
                    strong_elem = article_element.find('strong')
                    if strong_elem:
                        headline = strong_elem.get_text(strip=True)
            
            if not headline or len(headline) < 10:
                return None
            
            # Extract content/description
            content = ""
            for selector in ['.description', '.summary', '.excerpt', 'p']:
                content_elem = article_element.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    break
            
            # If no specific content, use the full text but limit it
            if not content:
                content = article_element.get_text(separator=' ', strip=True)[:300]
            
            # Extract URL
            url = None
            if article_element.name == 'a':
                url = article_element.get('href')
            else:
                link_elem = article_element.find('a')
                if link_elem:
                    url = link_elem.get('href')
            
            # Make URL absolute if relative
            if url and url.startswith('/'):
                url = f"{self.BASE_URL}{url}"
            
            # Extract date (try various formats)
            from datetime import timezone
            published_date = datetime.now(timezone.utc)
            for selector in ['.date', '.timestamp', 'time', '[datetime]']:
                date_elem = article_element.select_one(selector)
                if date_elem:
                    try:
                        date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                        # Try to parse various date formats
                        for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y']:
                            try:
                                parsed_date = datetime.strptime(date_text, fmt)
                                # Make timezone aware
                                published_date = parsed_date.replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                        break
                    except:
                        continue
            
            # Classify news type
            news_type = self._classify_news_type(f"{headline} {content}")
            
            return PlayerNews(
                player_name=player_name,
                headline=headline,
                content=content,
                news_type=news_type,
                source=NewsSource.NFL_OFFICIAL,
                published_date=published_date,
                url=url
            )
            
        except Exception as e:
            logger.debug(f"Error parsing NFL article: {e}")
            return None
    
    def _parse_injury_row(self, row_element) -> Optional[PlayerNews]:
        """Parse injury report row"""
        # Implementation would depend on actual NFL.com injury report structure
        return None


class RotoWireNewsSource(BaseNewsSource):
    """RotoWire news source for fantasy-focused content"""
    
    BASE_URL = "https://www.rotowire.com"
    
    def fetch_player_news(self, player_name: str, limit: int = 10) -> List[PlayerNews]:
        """Fetch player news from RotoWire using specific view URLs"""
        try:
            import time
            time.sleep(1.5)  # Rate limiting - be respectful
            
            # RotoWire specific view URLs that provide better coverage
            urls_to_try = [
                f"{self.BASE_URL}/football/news.php?view=top",      # Top news
                f"{self.BASE_URL}/football/news.php?view=injuries", # Injury reports  
                f"{self.BASE_URL}/football/news.php?view=idp",      # IDP news
                f"{self.BASE_URL}/football/news.php"                # General news
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://www.rotowire.com/football/'
            }
            
            all_news_items = []
            
            # Try each view URL to get comprehensive coverage
            for url in urls_to_try:
                try:
                    logger.debug(f"Trying RotoWire URL: {url}")
                    response = self.session.get(url, headers=headers, timeout=15)
                    
                    if response.status_code != 200:
                        logger.debug(f"RotoWire URL {url} returned {response.status_code}")
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    view_news = self._parse_rotowire_page(soup, player_name, url)
                    all_news_items.extend(view_news)
                    
                    logger.debug(f"Found {len(view_news)} items from {url}")
                    
                    # Small delay between requests
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"Error accessing {url}: {e}")
                    continue
            
            # Deduplicate by headline
            seen_headlines = set()
            unique_news = []
            for news in all_news_items:
                headline_key = news.headline.lower().strip()
                if headline_key not in seen_headlines:
                    seen_headlines.add(headline_key)
                    unique_news.append(news)
                    
            # Limit results
            final_news = unique_news[:limit]
            
            logger.info(f"Fetched {len(final_news)} unique news items for {player_name} from RotoWire")
            return final_news
            
        except Exception as e:
            logger.warning(f"RotoWire scraping failed: {e}")
            return []
    
    def fetch_injury_reports(self, team: Optional[str] = None) -> List[PlayerNews]:
        """Fetch injury reports from RotoWire using specific injury view"""
        try:
            import time
            time.sleep(1)
            
            # Use the injury-specific view
            if team:
                # Team-specific injury reports
                url = f"{self.BASE_URL}/football/news.php?team={team.upper()}&view=injuries"
            else:
                # All injury reports
                url = f"{self.BASE_URL}/football/news.php?view=injuries"
                
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://www.rotowire.com/football/'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.debug(f"RotoWire injury URL returned {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            injury_news = self._parse_rotowire_page(soup, None, url, injury_focus=True)
            
            logger.info(f"Fetched {len(injury_news)} injury reports from RotoWire")
            return injury_news
            
        except Exception as e:
            logger.warning(f"RotoWire injury reports failed: {e}")
            return []
    
    def _parse_rotowire_news(self, element, player_name: str) -> Optional[PlayerNews]:
        """Parse RotoWire news element"""
        try:
            # Extract headline/title
            headline = ""
            for selector in ['h1', 'h2', 'h3', 'h4', '.title', '.headline', 'strong']:
                headline_elem = element.select_one(selector)
                if headline_elem:
                    headline = headline_elem.get_text(strip=True)
                    if len(headline) > 10:  # Reasonable headline length
                        break
            
            # If no headline found, create one from the content
            if not headline:
                text = element.get_text(strip=True)
                # Take first sentence or up to 100 chars
                first_sentence = text.split('.')[0]
                headline = first_sentence[:100] if len(first_sentence) < 200 else text[:100]
            
            if not headline or len(headline) < 15:
                return None
            
            # Extract content
            content = element.get_text(separator=' ', strip=True)
            
            # Clean up content - remove headline if it's at the beginning
            if content.startswith(headline):
                content = content[len(headline):].strip()
            
            # Limit content size
            if len(content) > 500:
                content = content[:500] + "..."
            
            # Extract URL
            url = None
            link_elem = element.find('a')
            if link_elem:
                url = link_elem.get('href')
                if url and url.startswith('/'):
                    url = f"{self.BASE_URL}{url}"
            
            # Try to extract date
            from datetime import timezone
            published_date = datetime.now(timezone.utc)  # Default to now
            for selector in ['.date', '.timestamp', 'time', 'span[class*="date"]']:
                date_elem = element.select_one(selector)
                if date_elem:
                    try:
                        date_text = date_elem.get_text(strip=True)
                        # Try various date formats common in fantasy sites
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y', '%Y-%m-%d']:
                            try:
                                parsed_date = datetime.strptime(date_text, fmt)
                                # Make timezone aware
                                published_date = parsed_date.replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                        break
                    except:
                        continue
            
            # Classify news type (RotoWire is fantasy-focused)
            news_type = self._classify_news_type(f"{headline} {content}")
            
            # For RotoWire, prioritize fantasy-relevant types
            text_lower = f"{headline} {content}".lower()
            if any(word in text_lower for word in ['start', 'sit', 'fantasy', 'projection']):
                news_type = NewsType.ANALYSIS
            
            return PlayerNews(
                player_name=player_name,
                headline=headline,
                content=content,
                news_type=news_type,
                source=NewsSource.ROTOWIRE,
                published_date=published_date,
                url=url,
                fantasy_impact=content[:100] if 'fantasy' in content.lower() else None
            )
            
        except Exception as e:
            logger.debug(f"Error parsing RotoWire news: {e}")
            return None
    
    def _parse_rotowire_page(self, soup: BeautifulSoup, player_name: Optional[str], url: str, injury_focus: bool = False) -> List[PlayerNews]:
        """Parse a RotoWire page for news items"""
        news_items = []
        
        try:
            # RotoWire uses various selectors for news items
            potential_selectors = [
                'div.news-update',
                'div.player-news', 
                'div[class*="news"]',
                'tr[class*="news"]',  # Table rows
                'div.update',
                'article',
                '.injury-item',
                'div[id*="news"]'
            ]
            
            articles = []
            for selector in potential_selectors:
                found = soup.select(selector)
                if found:
                    articles.extend(found[:50])
                    
            # Fallback: look for structured content
            if not articles:
                # Look for table rows or divs with player information
                articles = soup.find_all(['tr', 'div'], limit=100)
                
            logger.debug(f"Found {len(articles)} potential articles in RotoWire page")
            
            for article in articles:
                try:
                    text_content = article.get_text(separator=' ', strip=True)
                    
                    # Skip very short content or navigation elements
                    if len(text_content) < 30 or any(skip in text_content.lower() for skip in 
                                                   ['navigation', 'menu', 'footer', 'header', 'advertisement']):
                        continue
                    
                    # If looking for specific player, check if mentioned
                    if player_name and not self._is_player_mentioned(player_name, text_content):
                        continue
                        
                    # For injury focus, prioritize injury-related content
                    if injury_focus and not any(word in text_content.lower() for word in 
                                              ['injury', 'hurt', 'questionable', 'doubtful', 'out', 'ir']):
                        continue
                    
                    # Must contain fantasy/sports keywords to be relevant
                    if not any(keyword in text_content.lower() for keyword in 
                              ['fantasy', 'injury', 'update', 'report', 'news', 'analysis', 'start', 'sit', 'week']):
                        continue
                        
                    news_item = self._parse_rotowire_element(article, player_name, url)
                    if news_item:
                        news_items.append(news_item)
                        
                except Exception as e:
                    logger.debug(f"Error parsing RotoWire article: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error parsing RotoWire page: {e}")
            
        return news_items
    
    def _parse_rotowire_element(self, element, player_name: Optional[str], source_url: str) -> Optional[PlayerNews]:
        """Parse individual RotoWire element"""
        try:
            # Extract headline/title
            headline = ""
            for selector in ['h1', 'h2', 'h3', 'h4', '.title', '.headline', 'strong', 'b']:
                headline_elem = element.select_one(selector)
                if headline_elem:
                    headline = headline_elem.get_text(strip=True)
                    if len(headline) > 10 and len(headline) < 200:
                        break
            
            # If no headline found, create one from content
            if not headline:
                text = element.get_text(strip=True)
                sentences = text.split('.')
                if sentences:
                    headline = sentences[0][:100].strip()
            
            if not headline or len(headline) < 15:
                return None
            
            # Extract content
            content = element.get_text(separator=' ', strip=True)
            if content.startswith(headline):
                content = content[len(headline):].strip()
            
            # Limit content size  
            if len(content) > 500:
                content = content[:500] + "..."
            
            # Extract player name if not provided
            if not player_name:
                # Try to extract from headline or content
                import re
                names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', headline + ' ' + content)
                player_name = names[0] if names else "Unknown Player"
            
            # Extract URL
            url = None
            link_elem = element.find('a')
            if link_elem:
                url = link_elem.get('href')
                if url and url.startswith('/'):
                    url = f"{self.BASE_URL}{url}"
            
            # Default to source URL if no specific link
            if not url:
                url = source_url
                
            # Try to extract date
            from datetime import timezone
            published_date = datetime.now(timezone.utc)
            for selector in ['.date', '.timestamp', 'time', 'span[class*="date"]', '.time']:
                date_elem = element.select_one(selector)
                if date_elem:
                    try:
                        date_text = date_elem.get_text(strip=True)
                        # Try various date formats
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y', '%Y-%m-%d', '%m/%d']:
                            try:
                                if '/' in date_text and len(date_text.split('/')) == 2:
                                    # Add current year for MM/DD format
                                    date_text = f"{date_text}/{datetime.now().year}"
                                parsed_date = datetime.strptime(date_text, fmt)
                                # Make timezone aware
                                published_date = parsed_date.replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                        break
                    except:
                        continue
            
            # Classify news type
            news_type = self._classify_news_type(f"{headline} {content}")
            
            # RotoWire-specific classifications
            text_lower = f"{headline} {content}".lower()
            if any(word in text_lower for word in ['start', 'sit', 'fantasy', 'projection', 'sleeper']):
                news_type = NewsType.ANALYSIS
            elif 'injury' in source_url:
                news_type = NewsType.INJURY
                
            return PlayerNews(
                player_name=player_name,
                headline=headline,
                content=content,
                news_type=news_type,
                source=NewsSource.ROTOWIRE,
                published_date=published_date,
                url=url,
                fantasy_impact=content[:100] if any(word in content.lower() for word in ['fantasy', 'start', 'sit']) else None
            )
            
        except Exception as e:
            logger.debug(f"Error parsing RotoWire element: {e}")
            return None
    
    def fetch_team_news(self, team: str, limit: int = 10) -> List[PlayerNews]:
        """Fetch team-specific news from RotoWire"""
        try:
            import time
            time.sleep(1)
            
            # NFL team abbreviations supported by RotoWire
            valid_teams = {
                'BAL', 'BUF', 'CIN', 'CLE', 'DEN', 'HOU', 'IND', 'JAX', 'KC', 'LV', 'MIA', 'NE', 'NYJ', 'PIT', 'TEN',
                'ARI', 'ATL', 'CAR', 'CHI', 'DAL', 'DET', 'GB', 'LAR', 'MIN', 'NO', 'NYG', 'PHI', 'SEA', 'SF', 'TB', 'WAS'
            }
            
            team_code = team.upper()
            if team_code not in valid_teams:
                logger.warning(f"Invalid team code: {team}. Must be one of {valid_teams}")
                return []
            
            # Team-specific URL
            url = f"{self.BASE_URL}/football/news.php?team={team_code}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://www.rotowire.com/football/'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.debug(f"RotoWire team URL returned {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            team_news = self._parse_rotowire_page(soup, None, url)
            
            # Limit results
            final_news = team_news[:limit]
            
            logger.info(f"Fetched {len(final_news)} news items for team {team_code} from RotoWire")
            return final_news
            
        except Exception as e:
            logger.warning(f"RotoWire team news failed for {team}: {e}")
            return []
    
    def _parse_rotowire_injury(self, element) -> Optional[PlayerNews]:
        """Parse RotoWire injury element - legacy method"""
        return self._parse_rotowire_element(element, None, "https://www.rotowire.com/football/news.php?view=injuries")