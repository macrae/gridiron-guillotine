# Deprecated Files

This directory contains files that have been superseded by improved versions.

## Directory Structure

### draft_strategies/
Contains the original draft strategy algorithm versions:
- `draft_strategy_v1.py` - Initial implementation
- `draft_strategy_v1_1.py` - Added logging and improvements  
- `draft_strategy_v2.py` - Most advanced version with tiers and dynamic VBD

**Superseded by:** `../draft_strategy_consolidated.py` - Combines best features from all versions

### scrapers/
Contains temporary scraper files used for 2024 data collection:
- `scrape_2024_defense.py` - 2024-only defense scraper
- `scrape_2024_kickers.py` - 2024-only kickers scraper

**Superseded by:** Updated main scraper files (`../web_scrape_defense.py`, `../web_scrape_kickers.py`)

### yahoo_api_tests/
Contains test files used during Yahoo API debugging:
- `debug_yahoo_data.py` - API data structure exploration
- `test_yahoo_week16.py` - Week-specific testing

**Superseded by:** `../yahoo_api_fixed.py` - Production-ready Yahoo API integration

## Note

These files are kept for reference but should not be used in production. 
The consolidated versions provide better functionality and maintainability.
