"""
Yahoo Mock Draft Live Monitoring System

Real-time monitoring of Yahoo Fantasy Football mock drafts with multi-source integration:
- Yahoo Fantasy API (authenticated)
- Web scraping fallback for draft room
- Hybrid approach for maximum reliability
"""

import time
import logging
import requests
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import re
import json

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..api.yahoo import YahooFantasyClient
from ..core.models import DraftPick, Position, DraftState, LeagueSettings
from ..core.strategy import ChampionshipDraftStrategy
from ..data.database import PlayerDatabase
from ..core.config import Config, get_config

logger = logging.getLogger(__name__)


@dataclass
class YahooMockDraftInfo:
    """Yahoo mock draft information"""
    draft_id: str
    league_name: str
    num_teams: int
    current_round: int
    current_pick: int
    user_team_id: Optional[str] = None
    user_position: Optional[int] = None
    draft_url: Optional[str] = None
    scoring_type: str = "ppr"


@dataclass
class YahooMockPickDetection:
    """Detected pick from Yahoo mock draft"""
    player_name: str
    player_position: str
    team_name: str
    team_id: str
    pick_number: int
    round_number: int
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "yahoo_api"  # yahoo_api, web_scraper, hybrid


class YahooMockDraftMonitor:
    """
    Advanced Yahoo Mock Draft monitoring with multiple detection methods
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.yahoo_client = YahooFantasyClient(self.config)
        self.strategy = None  # Will be initialized when we know draft position
        self.db = PlayerDatabase()
        
        # Monitoring state
        self.draft_info: Optional[YahooMockDraftInfo] = None
        self.monitoring_active = False
        self.last_pick_count = 0
        self.detected_picks: List[YahooMockPickDetection] = []
        
        # Web driver for scraping (optional)
        self.driver: Optional[webdriver.Chrome] = None
        
        # Event callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'draft_started': [],
            'pick_detected': [],
            'user_turn': [],
            'recommendation_update': [],
            'draft_completed': []
        }
    
    def add_callback(self, event: str, callback: Callable):
        """Add event callback"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def setup_web_driver(self, headless: bool = True) -> bool:
        """Setup Selenium web driver for scraping"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Web driver initialized successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Could not initialize web driver: {e}")
            return False
    
    def connect_to_mock_draft(self, draft_url: str, user_position: int) -> bool:
        """
        Connect to Yahoo mock draft by URL - WEB SCRAPING ONLY
        
        Args:
            draft_url: Yahoo mock draft URL 
            user_position: User's draft position (1-based)
        """
        try:
            # Extract draft ID from URL if needed
            draft_id = self._extract_draft_id(draft_url)
            if not draft_id:
                logger.warning(f"Could not extract draft ID from: {draft_url}")
                draft_id = "unknown"
            
            logger.info(f"🚀 CONNECTING TO YAHOO DRAFT (WEB SCRAPING ONLY)")
            logger.info(f"   URL: {draft_url}")
            logger.info(f"   Position: {user_position}")
            logger.info(f"   Draft ID: {draft_id}")
            
            # ONLY use web scraping - skip Yahoo API completely
            web_connected = self._connect_via_web_scraper(draft_url)
            
            if not web_connected:
                logger.error("❌ Failed to connect via web scraping")
                return False
            
            # Initialize strategy with user's draft position
            # Skip this for now to avoid dependency issues
            # from ..core.strategy import ChampionshipDraftStrategy
            # self.strategy = ChampionshipDraftStrategy(draft_position=user_position)
            self.strategy = None  # Will work without strategy for testing
            
            logger.info(f"✅ Connected to mock draft via web scraping")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to mock draft: {e}")
            return False
    
    def _extract_draft_id(self, draft_input: str) -> Optional[str]:
        """Extract draft ID from URL or return if already an ID"""
        if 'yahoo.com' in draft_input:
            # Pattern 1: Old format /draftroom/abc123
            match = re.search(r'/draftroom/(\w+)', draft_input)
            if match:
                return match.group(1)
            
            # Pattern 2: New format /draftclient/f1/8945977/13
            match = re.search(r'/draftclient/f1/(\d+)/\d+', draft_input)
            if match:
                return match.group(1)
            
            # Pattern 3: Just the draft ID in path /f1/8945977/
            match = re.search(r'/f1/(\d+)/?', draft_input)
            if match:
                return match.group(1)
            
            # Try alternative patterns in query parameters
            parsed = urlparse(draft_input)
            if 'draft_id' in parsed.query:
                query_params = parse_qs(parsed.query)
                return query_params.get('draft_id', [None])[0]
        else:
            # Assume it's already a draft ID
            return draft_input.strip()
        
        return None
    
    def _connect_via_api(self, draft_id: str, user_position: int) -> bool:
        """Connect to mock draft via Yahoo API"""
        try:
            # Authenticate with Yahoo API
            if not self.yahoo_client.authenticate():
                logger.warning("Yahoo API authentication failed")
                return False
            
            # Get league/draft information
            league_info = self.yahoo_client.get_league_info()
            if not league_info:
                logger.warning("Could not get league info from API")
                return False
            
            self.draft_info = YahooMockDraftInfo(
                draft_id=draft_id,
                league_name=league_info.get('name', 'Mock Draft'),
                num_teams=league_info.get('num_teams', 12),
                current_round=1,
                current_pick=1,
                user_position=user_position,
                scoring_type=league_info.get('scoring_type', 'ppr')
            )
            
            logger.info("Successfully connected via Yahoo API")
            return True
            
        except Exception as e:
            logger.warning(f"API connection failed: {e}")
            return False
    
    def _connect_via_web_scraper(self, draft_url: str) -> bool:
        """Connect to mock draft via web scraping"""
        try:
            if not self.setup_web_driver():
                return False
            
            # Navigate to draft room
            logger.info(f"Navigating to draft URL: {draft_url}")
            self.driver.get(draft_url)
            
            # Wait for page to load
            wait = WebDriverWait(self.driver, 15)
            
            # Look for the main draft application container
            selectors_to_try = [
                "#app",                      # Main React app container
                "[data-reactroot]",          # React root element
                ".draftboard",               # Legacy selector
                ".draft-board",              # Alternative
                ".draft-content",            # Content area
                "body"                       # Fallback - just ensure page loads
            ]
            
            loaded = False
            for selector in selectors_to_try:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    logger.info(f"Found draft page with selector: {selector}")
                    loaded = True
                    break
                except TimeoutException:
                    logger.debug(f"Selector {selector} not found, trying next...")
                    continue
            
            if not loaded:
                logger.warning("Could not find any draft page elements")
                return False
            
            # Wait for content to load
            time.sleep(3)
            
            # DEBUG: Log page information
            logger.info(f"🔍 PAGE DEBUG INFO:")
            logger.info(f"   Page title: {self.driver.title}")
            logger.info(f"   Current URL: {self.driver.current_url}")
            
            # Check if this is actually a draft page
            page_source_sample = self.driver.page_source[:1000]
            logger.info(f"   Page content sample: {page_source_sample}")
            
            # Look for draft-specific content
            draft_keywords = ["draft", "pick", "round", "selection"]
            found_keywords = [kw for kw in draft_keywords if kw.lower() in self.driver.page_source.lower()]
            logger.info(f"   Found draft keywords: {found_keywords}")
            
            # Try to find ANY elements that might contain draft data
            all_elements_with_text = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Round') or contains(text(), 'Pick') or contains(text(), 'Draft')]")
            logger.info(f"   Elements containing draft text: {len(all_elements_with_text)}")
            
            for i, elem in enumerate(all_elements_with_text[:5]):  # Show first 5
                try:
                    logger.info(f"     Element {i+1}: {elem.tag_name} - '{elem.text[:100]}'")
                except:
                    logger.info(f"     Element {i+1}: Could not read text")
            
            # Extract draft info from page - use more generic approach
            draft_info = self._scrape_draft_info()
            if draft_info:
                self.draft_info = draft_info
                self.draft_info.draft_url = draft_url
                logger.info("Successfully connected via web scraping")
                return True
            else:
                # Still return True if we can load the page, even without draft info
                logger.info("Page loaded but could not extract draft info - continuing anyway")
                self.draft_info = YahooMockDraftInfo(
                    draft_id="web_scraped",
                    league_name="Yahoo Mock Draft",
                    num_teams=12,  # Default
                    current_round=1,
                    current_pick=1
                )
                self.draft_info.draft_url = draft_url
                return True
            
        except Exception as e:
            logger.warning(f"Web scraping connection failed: {e}")
            return False
    
    def _scrape_draft_info(self) -> Optional[YahooMockDraftInfo]:
        """Scrape draft information from Yahoo draft room"""
        try:
            # Extract league name
            league_name_element = self.driver.find_element(By.CLASS_NAME, "league-name")
            league_name = league_name_element.text if league_name_element else "Mock Draft"
            
            # Count teams from draft board
            team_elements = self.driver.find_elements(By.CLASS_NAME, "team")
            num_teams = len(team_elements) if team_elements else 12
            
            # Extract current pick info
            current_pick_element = self.driver.find_element(By.CLASS_NAME, "current-pick")
            pick_text = current_pick_element.text if current_pick_element else "Round 1, Pick 1"
            
            # Parse round and pick from text like "Round 3, Pick 5"
            round_match = re.search(r'Round (\d+)', pick_text)
            pick_match = re.search(r'Pick (\d+)', pick_text)
            
            current_round = int(round_match.group(1)) if round_match else 1
            current_pick = int(pick_match.group(1)) if pick_match else 1
            
            return YahooMockDraftInfo(
                draft_id="web_scraped",
                league_name=league_name,
                num_teams=num_teams,
                current_round=current_round,
                current_pick=current_pick
            )
            
        except Exception as e:
            logger.error(f"Error scraping draft info: {e}")
            return None
    
    def start_monitoring(self, polling_interval: int = 10) -> bool:
        """
        Start monitoring the Yahoo mock draft
        
        Args:
            polling_interval: Seconds between checks
        """
        if not self.draft_info:
            logger.error("No draft connection established")
            return False
        
        self.monitoring_active = True
        
        # Fire draft started callbacks
        for callback in self.callbacks['draft_started']:
            try:
                callback(self.draft_info)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        logger.info(f"Starting Yahoo mock draft monitoring (polling every {polling_interval}s)")
        
        try:
            while self.monitoring_active:
                # Multi-source pick detection
                new_picks = self._detect_new_picks()
                
                if new_picks:
                    self._process_new_picks(new_picks)
                
                # Check if it's user's turn
                self._check_user_turn()
                
                # Update recommendations
                self._update_recommendations()
                
                time.sleep(polling_interval)
                
        except KeyboardInterrupt:
            logger.info("Mock draft monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
        finally:
            self.stop_monitoring()
        
        return True
    
    def stop_monitoring(self):
        """Stop monitoring and cleanup"""
        self.monitoring_active = False
        
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        
        logger.info("Mock draft monitoring stopped")
    
    def _detect_new_picks(self) -> List[YahooMockPickDetection]:
        """Detect new picks using WEB SCRAPING ONLY"""
        new_picks = []
        
        # SKIP API detection completely - only use web scraping
        logger.debug("Skipping Yahoo API - using web scraping only")
        
        # Try web scraping detection
        try:
            web_picks = self._detect_picks_via_web_scraping()
            new_picks.extend(web_picks)
            logger.debug(f"Web scraping found {len(web_picks)} picks")
        except Exception as e:
            logger.debug(f"Web scraping pick detection failed: {e}")
        
        # No need to deduplicate since we're only using one source
        return new_picks
    
    def _detect_picks_via_api(self) -> List[YahooMockPickDetection]:
        """Detect new picks via Yahoo API"""
        if not self.yahoo_client:
            return []
        
        try:
            current_rosters = self.yahoo_client.get_current_rosters()
            if not current_rosters:
                logger.debug("No roster data from Yahoo API")
                return []
            
            # Handle the case where API returns strings instead of player dictionaries
            # This happens with mock drafts
            total_picks = 0
            for team_name, roster in current_rosters.items():
                if isinstance(roster, list):
                    # Filter out non-dict entries (API bug returns strings for mock drafts)
                    valid_players = [player for player in roster if isinstance(player, dict)]
                    total_picks += len(valid_players)
                    
                    if len(valid_players) != len(roster):
                        logger.debug(f"Team {team_name}: {len(roster)} total entries, {len(valid_players)} valid players")
            
            if total_picks > self.last_pick_count:
                # New picks detected - find the new ones
                new_count = total_picks - self.last_pick_count
                logger.info(f"API detected {new_count} new picks")
                
                picks = []
                for team_name, roster in current_rosters.items():
                    if isinstance(roster, list):
                        # Only process dictionary entries (valid player data)
                        valid_players = [player for player in roster if isinstance(player, dict)]
                        
                        # Get the last N players from this team
                        for player in valid_players[-new_count:]:
                            try:
                                # Extract player info safely
                                player_name = self.yahoo_client._extract_player_name(player)
                                player_position = player.get('position', 'UNKNOWN')
                                
                                if player_name and player_name != "Unknown":
                                    pick = YahooMockPickDetection(
                                        player_name=player_name,
                                        player_position=player_position,
                                        team_name=team_name,
                                        team_id=team_name,
                                        pick_number=total_picks,
                                        round_number=(total_picks - 1) // self.draft_info.num_teams + 1,
                                        source="yahoo_api"
                                    )
                                    picks.append(pick)
                                    logger.debug(f"API parsed pick: {player_name} ({player_position}) -> {team_name}")
                            except Exception as player_error:
                                logger.debug(f"Error parsing player data: {player_error}")
                                continue
                
                self.last_pick_count = total_picks
                return picks
            
        except Exception as e:
            logger.debug(f"API pick detection error: {e}")
            # Don't log full traceback at DEBUG level
            import traceback
            logger.debug(f"API traceback: {traceback.format_exc()}")
        
        return []
    
    def _detect_picks_via_web_scraping(self) -> List[YahooMockPickDetection]:
        """Detect new picks via web scraping - COMPREHENSIVE APPROACH"""
        if not self.driver:
            return []
        
        try:
            logger.debug("🔍 COMPREHENSIVE DRAFT CONTENT SCAN")
            
            # STRATEGY 1: Look for ANY elements that might contain draft data
            all_potential_elements = []
            
            # Cast a wide net - look for ANY content that might be draft-related
            broad_selectors = [
                # Tables and rows (most common for draft boards)
                "table", "tbody", "tr", "td",
                # Divs with any draft-related classes or IDs
                "div[class*='draft']", "div[id*='draft']",
                "div[class*='pick']", "div[id*='pick']", 
                "div[class*='player']", "div[id*='player']",
                "div[class*='team']", "div[id*='team']",
                "div[class*='round']", "div[id*='round']",
                # Data attributes
                "[data-testid]", "[data-*='draft']", "[data-*='pick']",
                # Lists and items
                "ul", "li", "ol",
                # Spans and text elements
                "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
                # Any element with draft-related text
                "//*[contains(text(), 'Round')]",
                "//*[contains(text(), 'Pick')]", 
                "//*[contains(text(), 'Draft')]",
                "//*[contains(text(), 'Player')]",
                "//*[contains(text(), 'Team')]"
            ]
            
            for selector in broad_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        logger.debug(f"Found {len(elements)} elements with selector: {selector}")
                        for elem in elements:
                            try:
                                text = elem.text.strip()
                                # Only include elements with meaningful text
                                if text and len(text) > 3:
                                    all_potential_elements.append((elem, text, selector))
                            except:
                                pass
                except Exception as e:
                    continue
            
            logger.info(f"📊 Found {len(all_potential_elements)} potential draft elements")
            
            # STRATEGY 2: Filter elements that look like draft picks
            draft_picks = []
            pick_patterns = [
                # Look for patterns that might indicate draft picks
                r'Round\s+\d+',
                r'Pick\s+\d+',
                r'R\d+P\d+',
                r'\d+\.\s+[A-Z][a-z]+.*[A-Z][a-z]+',  # "1. Player Name"
                r'[A-Z][a-z]+,\s[A-Z][a-z]+',         # "Last, First"
                r'(QB|RB|WR|TE|K|DEF)',               # Position indicators
            ]
            
            import re
            for elem, text, selector in all_potential_elements:
                # Check if text matches any draft pick patterns
                for pattern in pick_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        draft_picks.append((elem, text, selector, pattern))
                        logger.debug(f"DRAFT PICK CANDIDATE: '{text[:50]}...' (matched: {pattern})")
                        break
            
            logger.info(f"🎯 Found {len(draft_picks)} potential draft pick elements")
            
            # STRATEGY 3: Try to extract meaningful picks
            new_picks = []
            current_pick_count = len(draft_picks)
            
            if current_pick_count > self.last_pick_count:
                logger.info(f"🆕 Detected {current_pick_count - self.last_pick_count} new potential picks")
                
                # Process new elements
                for i in range(self.last_pick_count, current_pick_count):
                    if i < len(draft_picks):
                        elem, text, selector, pattern = draft_picks[i]
                        pick_data = self._parse_pick_element_smart(elem, text, i + 1)
                        if pick_data:
                            new_picks.append(pick_data)
                            logger.info(f"✅ PARSED PICK: {pick_data.player_name} ({pick_data.player_position})")
                
                self.last_pick_count = current_pick_count
            
            # STRATEGY 4: Log current page state for debugging
            if len(new_picks) == 0:
                logger.info(f"🤔 No picks found. Logging page state for debugging...")
                logger.info(f"   Page title: {self.driver.title}")
                logger.info(f"   Current URL: {self.driver.current_url}")
                
                # Look for ANY text containing draft keywords
                draft_text_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Round') or contains(text(), 'Pick') or contains(text(), 'Draft')]")
                logger.info(f"   Elements with draft text: {len(draft_text_elements)}")
                
                for i, elem in enumerate(draft_text_elements[:5]):
                    try:
                        logger.info(f"     {i+1}. {elem.tag_name}: '{elem.text[:100]}...'")
                    except:
                        pass
            
            return new_picks
            
        except Exception as e:
            logger.error(f"Web scraping pick detection error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _parse_pick_element(self, pick_element, pick_number: int) -> Optional[YahooMockPickDetection]:
        """Parse a pick element from the draft board - flexible parsing for Yahoo structure"""
        try:
            # Get all text from the element to analyze
            element_text = pick_element.text.strip()
            
            # Skip empty elements
            if not element_text:
                return None
            
            # Try multiple strategies to extract player information
            player_name = None
            player_position = None
            team_name = "Unknown Team"
            
            # Strategy 1: Look for specific selectors within the element
            name_selectors = [
                ".player-name", 
                "[data-testid*='name']",
                "[class*='name']",
                "span", 
                "div",
                "td"
            ]
            
            for selector in name_selectors:
                try:
                    name_element = pick_element.find_element(By.CSS_SELECTOR, selector)
                    if name_element and name_element.text.strip():
                        potential_name = name_element.text.strip()
                        # Basic validation - names should be 2+ words and contain letters
                        if len(potential_name.split()) >= 2 and any(c.isalpha() for c in potential_name):
                            player_name = potential_name
                            logger.debug(f"Found player name with {selector}: {player_name}")
                            break
                except:
                    continue
            
            # Strategy 2: Parse from element text if no specific selectors worked
            if not player_name and element_text:
                # Look for patterns like "Player Name (Position)" or "Player Name Position"
                import re
                
                # Pattern 1: "Player Name (QB)" 
                match = re.search(r'([A-Za-z\s\.]+)\s*\(([A-Z]{1,3})\)', element_text)
                if match:
                    player_name = match.group(1).strip()
                    player_position = match.group(2).strip()
                else:
                    # Pattern 2: Just use the text if it looks like a name
                    words = element_text.split()
                    if len(words) >= 2 and all(word.replace('.', '').isalpha() for word in words[:2]):
                        player_name = ' '.join(words[:2])
                        # Look for position in remaining words
                        for word in words[2:]:
                            if word.upper() in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DST']:
                                player_position = word.upper()
                                break
            
            # Strategy 3: Look for position separately if not found
            if not player_position:
                position_selectors = [
                    ".position", 
                    ".player-position",
                    "[data-testid*='position']",
                    "[class*='position']"
                ]
                
                for selector in position_selectors:
                    try:
                        pos_element = pick_element.find_element(By.CSS_SELECTOR, selector)
                        if pos_element and pos_element.text.strip():
                            player_position = pos_element.text.strip().upper()
                            break
                    except:
                        continue
            
            # Strategy 4: Extract team name
            team_selectors = [
                ".team-name",
                ".team",
                "[data-testid*='team']",
                "[class*='team']"
            ]
            
            for selector in team_selectors:
                try:
                    team_element = pick_element.find_element(By.CSS_SELECTOR, selector)
                    if team_element and team_element.text.strip():
                        team_name = team_element.text.strip()
                        break
                except:
                    continue
            
            # Validate we found essential information
            if not player_name:
                logger.debug(f"Could not extract player name from element: {element_text[:100]}")
                return None
            
            # Default position if not found
            if not player_position:
                player_position = "UNKNOWN"
            
            # Calculate round based on pick number
            round_number = (pick_number - 1) // self.draft_info.num_teams + 1
            
            pick_data = YahooMockPickDetection(
                player_name=player_name,
                player_position=player_position,
                team_name=team_name,
                team_id=team_name,
                pick_number=pick_number,
                round_number=round_number,
                source="web_scraper"
            )
            
            logger.debug(f"Parsed pick: {player_name} ({player_position}) -> {team_name}")
            return pick_data
            
        except Exception as e:
            logger.debug(f"Error parsing pick element: {e}")
            logger.debug(f"Element text: {getattr(pick_element, 'text', 'NO_TEXT')[:100]}")
            return None
    
    def _parse_pick_element_smart(self, element, text: str, pick_number: int) -> Optional[YahooMockPickDetection]:
        """Smart parsing of potential draft pick elements"""
        try:
            import re
            
            # Initialize default values
            player_name = None
            player_position = "UNKNOWN"
            team_name = "Unknown Team"
            
            # STRATEGY 1: Look for common draft pick text patterns
            
            # Pattern: "1. Player Name (Position)"
            match = re.search(r'\d+\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([A-Z]{1,3})\)', text)
            if match:
                player_name = match.group(1).strip()
                player_position = match.group(2).strip()
                logger.debug(f"Pattern 1 match: {player_name} ({player_position})")
            
            # Pattern: "Last, First (Position)"
            if not player_name:
                match = re.search(r'([A-Z][a-z]+),\s+([A-Z][a-z]+)\s*\(([A-Z]{1,3})\)', text)
                if match:
                    player_name = f"{match.group(2)} {match.group(1)}"
                    player_position = match.group(3).strip()
                    logger.debug(f"Pattern 2 match: {player_name} ({player_position})")
            
            # Pattern: "Player Name - Position"
            if not player_name:
                match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*-\s*(QB|RB|WR|TE|K|DEF)', text, re.IGNORECASE)
                if match:
                    player_name = match.group(1).strip()
                    player_position = match.group(2).strip().upper()
                    logger.debug(f"Pattern 3 match: {player_name} ({player_position})")
            
            # Pattern: Just position indicator in text
            if not player_name:
                position_match = re.search(r'(QB|RB|WR|TE|K|DEF)', text, re.IGNORECASE)
                if position_match:
                    player_position = position_match.group(1).upper()
                    # Try to extract name (everything before position)
                    name_part = text[:position_match.start()].strip()
                    if len(name_part.split()) >= 2:
                        player_name = name_part
                        logger.debug(f"Pattern 4 match: {player_name} ({player_position})")
            
            # Pattern: Generic name extraction (2+ words with letters)
            if not player_name:
                words = text.split()
                name_words = []
                for word in words:
                    if re.match(r'^[A-Za-z]+$', word) and len(word) > 1:
                        name_words.append(word)
                    if len(name_words) >= 2:
                        break
                
                if len(name_words) >= 2:
                    player_name = ' '.join(name_words)
                    logger.debug(f"Pattern 5 match: {player_name}")
            
            # STRATEGY 2: Try to extract team name from nearby elements
            try:
                # Look for parent or sibling elements that might contain team info
                parent = element.find_element(By.XPATH, "..")
                if parent:
                    team_text = parent.text
                    team_match = re.search(r'(Team\s+\w+|\w+\s+Team)', team_text, re.IGNORECASE)
                    if team_match:
                        team_name = team_match.group(1)
            except:
                pass
            
            # Validate we found essential information
            if not player_name or len(player_name.split()) < 2:
                logger.debug(f"Could not extract valid player name from: '{text}'")
                return None
            
            # Calculate round based on pick number
            round_number = (pick_number - 1) // self.draft_info.num_teams + 1 if self.draft_info else 1
            
            pick_data = YahooMockPickDetection(
                player_name=player_name,
                player_position=player_position,
                team_name=team_name,
                team_id=team_name,
                pick_number=pick_number,
                round_number=round_number,
                source="web_scraper_smart"
            )
            
            logger.debug(f"Smart parsed pick: {player_name} ({player_position}) -> {team_name}")
            return pick_data
            
        except Exception as e:
            logger.debug(f"Error in smart pick parsing: {e}")
            logger.debug(f"Element text: '{text}'")
            return None
    
    def _deduplicate_picks(self, picks: List[YahooMockPickDetection]) -> List[YahooMockPickDetection]:
        """Remove duplicate picks from multiple sources"""
        seen = set()
        unique_picks = []
        
        for pick in picks:
            # Create a unique key for this pick
            key = (pick.player_name, pick.pick_number, pick.round_number)
            
            if key not in seen:
                seen.add(key)
                unique_picks.append(pick)
        
        return unique_picks
    
    def _process_new_picks(self, new_picks: List[YahooMockPickDetection]):
        """Process newly detected picks"""
        for pick in new_picks:
            # Add to detected picks
            self.detected_picks.append(pick)
            
            # Update draft info
            self.draft_info.current_round = pick.round_number
            self.draft_info.current_pick = pick.pick_number + 1
            
            logger.info(f"PICK DETECTED: {pick.player_name} ({pick.player_position}) → {pick.team_name}")
            
            # Fire pick detected callbacks
            for callback in self.callbacks['pick_detected']:
                try:
                    callback(pick)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def _check_user_turn(self):
        """Check if it's approaching the user's turn"""
        if not self.draft_info or not self.draft_info.user_position:
            return
        
        current_pick_in_round = (self.draft_info.current_pick - 1) % self.draft_info.num_teams + 1
        
        # Calculate user's pick in current round (snake draft)
        if self.draft_info.current_round % 2 == 1:  # Odd round
            user_pick_in_round = self.draft_info.user_position
        else:  # Even round (snake)
            user_pick_in_round = self.draft_info.num_teams - self.draft_info.user_position + 1
        
        picks_until_user = user_pick_in_round - current_pick_in_round
        
        # Notify if user's turn is approaching (within 2 picks)
        if 0 < picks_until_user <= 2:
            for callback in self.callbacks['user_turn']:
                try:
                    callback(picks_until_user, self.draft_info)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def _update_recommendations(self):
        """Update strategy recommendations based on current draft state"""
        try:
            # Convert detected picks to DraftPick objects
            draft_picks = []
            for pick in self.detected_picks:
                try:
                    position = Position(pick.player_position.upper())
                except ValueError:
                    position = Position.UNKNOWN
                
                draft_pick = DraftPick(
                    player_name=pick.player_name,
                    team_name=pick.team_name,
                    position=position,
                    round_num=pick.round_number,
                    pick_num=pick.pick_number
                )
                draft_picks.append(draft_pick)
            
            # Get recommendations from database with debug info
            logger.debug("Getting top players from database...")
            available_players = self.db.get_top_players(limit=20)
            logger.debug(f"Database returned {len(available_players)} players")
            
            if available_players:
                logger.debug(f"First player: {available_players[0].name}, Score: {getattr(available_players[0], 'hero_rb_score', 'NO_SCORE')}")
            
            # Filter out already drafted players
            drafted_names = {pick.player_name for pick in self.detected_picks}
            available = [p for p in available_players if p.name not in drafted_names]
            logger.debug(f"After filtering drafted players: {len(available)} available")
            
            # Fire recommendation callbacks
            for callback in self.callbacks['recommendation_update']:
                try:
                    callback(available[:10], self.draft_info)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating recommendations: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'monitoring_active': self.monitoring_active,
            'draft_connected': self.draft_info is not None,
            'draft_info': {
                'draft_id': self.draft_info.draft_id if self.draft_info else None,
                'league_name': self.draft_info.league_name if self.draft_info else None,
                'current_round': self.draft_info.current_round if self.draft_info else None,
                'current_pick': self.draft_info.current_pick if self.draft_info else None,
                'user_position': self.draft_info.user_position if self.draft_info else None,
            },
            'picks_detected': len(self.detected_picks),
            'api_connected': self.yahoo_client is not None,
            'web_driver_active': self.driver is not None,
            'callbacks_registered': {
                event: len(callbacks) 
                for event, callbacks in self.callbacks.items()
            }
        }


class YahooMockDraftConsole:
    """Console interface for Yahoo mock draft monitoring"""
    
    def __init__(self, monitor: YahooMockDraftMonitor):
        self.monitor = monitor
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup console display callbacks"""
        self.monitor.add_callback('draft_started', self._on_draft_started)
        self.monitor.add_callback('pick_detected', self._on_pick_detected)
        self.monitor.add_callback('user_turn', self._on_user_turn)
        self.monitor.add_callback('recommendation_update', self._on_recommendations_updated)
    
    def _on_draft_started(self, draft_info: YahooMockDraftInfo):
        """Handle draft started event"""
        print(f"\n🚀 YAHOO MOCK DRAFT CONNECTED")
        print(f"League: {draft_info.league_name}")
        print(f"Teams: {draft_info.num_teams}")
        print(f"Your Position: {draft_info.user_position}")
        print(f"Scoring: {draft_info.scoring_type.upper()}")
        print("=" * 60)
    
    def _on_pick_detected(self, pick: YahooMockPickDetection):
        """Handle pick detected event"""
        source_icon = "🔵" if pick.source == "yahoo_api" else "🟢" if pick.source == "web_scraper" else "🟡"
        print(f"{source_icon} R{pick.round_number}P{pick.pick_number}: {pick.player_name} ({pick.player_position}) → {pick.team_name}")
    
    def _on_user_turn(self, picks_until_user: int, draft_info: YahooMockDraftInfo):
        """Handle user turn approaching event"""
        print(f"\n🔔 YOUR TURN IN {picks_until_user} PICK{'S' if picks_until_user > 1 else ''}!")
        print("Get ready to draft!")
    
    def _on_recommendations_updated(self, recommendations: List[Any], draft_info: YahooMockDraftInfo):
        """Handle recommendations updated event"""
        print(f"\n📊 TOP RECOMMENDATIONS (Round {draft_info.current_round}):")
        for i, player in enumerate(recommendations[:5], 1):
            name = getattr(player, 'name', 'Unknown')
            position = getattr(player, 'position', 'Unknown')
            score = getattr(player, 'hero_rb_score', 0)
            print(f"  {i}. {name:25s} ({position}) Score: {score:.1f}")