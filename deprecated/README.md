# Deprecated Files

This directory contains files that have been superseded by the new `gridiron_guillotine` package structure (v2.0).

## Recently Moved Files (Package Refactoring - v2.0)

### Core Strategy Files
- `draft_strategy_consolidated.py` → `gridiron_guillotine/core/strategy.py`
- `hero_rb_strategy.py` → Integrated into `gridiron_guillotine/core/strategy.py`
- `advanced_metrics.py` → `gridiron_guillotine/core/metrics.py`
- `championship_strategy_integration.py` → Integrated into strategy system

### Data Processing Files
- `score_data.py` → `gridiron_guillotine/data/processors.py`
- `aggregate_scored_data.py` → Integrated into processors

### Web Scraping Files
- `web_scrape_offense.py` → `gridiron_guillotine/data/scrapers/offense.py`
- `web_scrape_defense.py` → `gridiron_guillotine/data/scrapers/defense.py`
- `web_scrape_kickers.py` → `gridiron_guillotine/data/scrapers/kickers.py`
- `web_scrape_players.py` → `gridiron_guillotine/data/scrapers/players.py`

### API and Live Monitoring
- `yahoo_api_fixed.py` → `gridiron_guillotine/api/yahoo.py`
- `live_draft_monitor.py` → `gridiron_guillotine/live/monitor.py`

### Fantasy Scoring Systems
- `fantasy_points.py` → Integrated into `gridiron_guillotine/data/processors.py`
- `fantasy_points_two_minute_drill.py` → Integrated into processors

### Strategy Components
- `ppr_optimization.py` → Integrated into `gridiron_guillotine/core/strategy.py`
- `sleeper_identification.py` → Integrated into strategy system

### Web Interface
- `streamlit_app/app.py` → `gridiron_guillotine/web/streamlit_app.py`

### Utility Files
- `integrate_rookies_2025.py` → Functionality available via CLI

## Legacy Directory Structure

### draft_strategies/
Contains the original draft strategy algorithm versions:
- `draft_strategy_v1.py` - Initial implementation
- `draft_strategy_v1_1.py` - Added logging and improvements  
- `draft_strategy_v2.py` - Most advanced version with tiers and dynamic VBD

### scrapers/
Contains temporary scraper files used for 2024 data collection:
- `scrape_2024_defense.py` - 2024-only defense scraper
- `scrape_2024_kickers.py` - 2024-only kickers scraper

### yahoo_api_tests/
Contains test files used during Yahoo API debugging:
- `debug_yahoo_data.py` - API data structure exploration
- `test_yahoo_week16.py` - Week-specific testing

## Note

**All files in this directory have been superseded by the new v2.0 package structure.**

- **New CLI Usage**: `gridiron --help`
- **New Package Import**: `from gridiron_guillotine.core import ChampionshipDraftStrategy`
- **Modern Architecture**: Professional Python package with proper namespacing

These files are kept for reference only and should not be used in production. 
The new package provides better functionality, maintainability, and professional structure.
