# CLAUDE.md - Gridiron Guillotine Project

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the **Gridiron Guillotine** fantasy football draft strategy codebase.

## 🏈 Project Overview

**Gridiron Guillotine** is a production-ready fantasy football draft strategy application that combines advanced data science techniques with real-time draft management. The system is specifically optimized for **running back (RB) focused strategies** using value-based drafting (VBD), positional scarcity analysis, and tier-based player evaluation.

### Core Philosophy
- **RB-Heavy Strategy**: Prioritizes running backs in early rounds due to positional scarcity
- **Data-Driven Decisions**: Uses 5 years of historical NFL data (2020-2024) for projections
- **Value-Based Drafting**: Every player evaluated relative to replacement level at their position
- **Real-Time Integration**: Live Yahoo Fantasy API connection for draft-time roster tracking

## 🚀 Quick Start Commands

### Core Draft Strategy
```bash
# Generate round-by-round draft strategies (main use case)
python draft_strategy_consolidated.py

# Launch interactive draft dashboard
streamlit run streamlit_app/app.py

# Test Yahoo API connection for live drafting
python yahoo_api_fixed.py
```

### Data Pipeline
```bash
# Install all dependencies
pip install -r requirements.txt

# Process raw data and calculate fantasy points
python score_data.py

# Update data with latest NFL stats (run individually as needed)
python web_scrape_offense.py    # Offensive player stats
python web_scrape_defense.py    # Defensive/special teams stats  
python web_scrape_kickers.py    # Kicker stats
python web_scrape_players.py    # Player biographical information
```

### Testing and Validation
```bash
# Run core functionality tests
python tests/test_calculate_fantasy_points.py
python tests/test_clean_player_name.py
```

## 🏗️ Production Architecture

### Core Engine Files (9 Production Python Files)

#### 1. **Draft Strategy Engine** (`draft_strategy_consolidated.py`)
**The heart of the application** - A sophisticated draft strategy generator with:

- **RB-Focused Algorithm**: 1.4x value boost for RBs in rounds 1-8, 1.2x in rounds 9-12
- **Dynamic VBD Calculation**: Real-time value-based drafting relative to replacement level
- **Positional Scarcity Analysis**: Tracks remaining quality players by position
- **Tier-Based Valuation**: Automatically detects player tier dropoffs (20% VBD decline)
- **Round-Specific Logic**: 
  - Rounds 1-5: Heavy RB/WR focus, elite TE consideration
  - Rounds 6-9: QB if needed, otherwise RB/WR depth
  - Rounds 10-12: All positions except K/DEF
  - Rounds 13+: K/DEF targeting only
- **Roster Management**: Enforces position limits (QB:1, RB:2, WR:2, TE:1, FLEX:1, K:1, DEF:1)

**Key Class**: `DraftStrategy` - Main strategy engine with methods:
- `get_round_strategy()` - Generate strategy for specific round
- `calculate_positional_scarcity()` - Analyze position availability
- `adjust_player_value()` - Comprehensive player value calculation

#### 2. **Fantasy Scoring Systems**
- **`fantasy_points.py`** - Standard fantasy scoring (PPR, standard, etc.)
- **`fantasy_points_two_minute_drill.py`** - League-specific scoring with bonuses

Both support all positions (QB, RB, WR, TE, K, DEF) with configurable scoring rules.

#### 3. **Yahoo Fantasy API Integration** (`yahoo_api_fixed.py`)
Production-ready Yahoo Fantasy Sports API integration:

- **OAuth Authentication**: Automatic token refresh with `oauth2.json` configuration
- **League Management**: Access to league settings, team rosters, current week
- **Real-Time Data**: Live roster tracking during draft for strategy adjustment
- **Rate Limiting**: Built-in delays to respect API limits
- **Error Handling**: Comprehensive error handling with fallback mechanisms

**Key Functions**:
- `initialize_yahoo_connection()` - OAuth setup and league connection
- `get_current_rosters()` - Fetch all team rosters for draft analysis
- `get_round_strategy()` - Integration with draft strategy engine

**Limitations**: Yahoo API doesn't reliably provide player scoring data - use scraped data instead.

#### 4. **Data Processing Pipeline** (`score_data.py`)
Transforms raw scraped data into draft-ready player projections:

- **Multi-Year Analysis**: Processes 2020-2024 data with confidence intervals
- **Player Name Normalization**: `clean_player_name()` handles name variations
- **VBD Calculation**: Position-specific replacement levels (QB:12, RB:24, WR:36, TE:12)
- **Output Generation**: Creates `scored_data.csv` with 486+ players and projections

#### 5. **Web Scraping Infrastructure** (4 Files)
Production web scrapers with robust error handling:

- **`web_scrape_offense.py`** - QB, RB, WR, TE stats from footballdb.com
- **`web_scrape_defense.py`** - Team defense and special teams stats
- **`web_scrape_kickers.py`** - Kicker stats and projections  
- **`web_scrape_players.py`** - Player biographical data and team assignments

**Features**:
- Rate limiting with random delays (1-3 seconds)
- User-agent rotation to avoid blocking
- Comprehensive logging to `scraping.log`
- Progress tracking with tqdm progress bars
- HTTP client with proper headers and error handling

### Supporting Infrastructure

#### Data Files
- **`scored_data.csv`** - **PRIMARY DATA SOURCE** with 486 players including:
  - Player name, position, team
  - Projected fantasy points with confidence intervals (floor/ceiling)
  - Value-based drafting (VBD) scores
  - Statistical confidence metrics
- **`player_ids.json`** - Player identification mapping for data consistency
- **`requirements.txt`** - All Python dependencies including Yahoo API packages

#### Historical Data (`data/` directory)
Complete 5-year dataset organized by position and week:
- **Offense**: `offense_YYYY_WW.csv` (2020-2024, weeks 1-17)
- **Defense**: `defense_YYYY_WW.csv` (2020-2024, weeks 1-17) 
- **Kickers**: `kickers_YYYY_WW.csv` (2020-2024, weeks 1-17)
- **Players**: `players_[A-Z].csv` - Biographical data organized alphabetically
- **Rookies**: `rookie_rankings_2024.csv` - Draft class analysis

#### Play-by-Play Data (`pbp_data/`)
Season-level play-by-play CSV files for advanced analytics:
- `pbp-2020.csv` through `pbp-2023.csv`

### Interactive Dashboard (`streamlit_app/`)

#### Streamlit Application (`app.py`)
Professional-grade web interface for draft management:

- **Real-Time Strategy Display**: Shows top 12 picks for current round
- **Player Filtering**: Search by position, team, projected points
- **Roster Management**: Track drafted players and remaining needs
- **Enhanced Data Grids**: Uses `st-aggrid` for sortable, filterable tables
- **Strategy Data**: Loads from `draft_strategy.csv` (auto-generated)

**Launch**: `streamlit run streamlit_app/app.py`

### Testing Framework (`tests/`)
Comprehensive test suite for core functionality:
- **`test_calculate_fantasy_points.py`** - Validates scoring algorithms
- **`test_clean_player_name.py`** - Tests player name normalization

## 📊 Data Flow Architecture

### Complete Data Pipeline
```
Raw NFL Data (footballdb.com)
         ↓ (web scraping)
data/offense_YYYY_WW.csv, defense_YYYY_WW.csv, kickers_YYYY_WW.csv  
         ↓ (score_data.py processing)
scored_data.csv (486 players with VBD, projections, confidence intervals)
         ↓ (draft_strategy_consolidated.py)
Round-by-round draft strategies (15 rounds of top 12 picks each)
         ↓ (streamlit app or yahoo integration)
Interactive draft management and real-time strategy
```

### Key Transformations
1. **Raw Stats → Fantasy Points**: Apply league scoring rules to NFL statistics
2. **Fantasy Points → VBD**: Calculate value above replacement level by position
3. **VBD → Draft Strategy**: Apply positional scarcity, tiers, and RB-focused weighting
4. **Strategy → Live Decisions**: Real-time integration with Yahoo drafts

## 🔧 Dependencies and Configuration

### Core Dependencies (`requirements.txt`)
```
pandas              # Data manipulation and analysis
beautifulsoup4      # HTML parsing for web scraping  
selenium            # Dynamic web content scraping
requests           # HTTP requests for API calls
streamlit          # Web dashboard framework
streamlit-aggrid   # Enhanced interactive data grids
tqdm               # Progress bars for long-running operations
seaborn            # Statistical data visualization
scipy              # Scientific computing and statistics
webdriver_manager  # Selenium WebDriver management
yahoo_fantasy_api  # Yahoo Fantasy Sports API integration
yahoo_oauth        # OAuth authentication for Yahoo services
```

### Configuration Files
- **`nbs/oauth2.json`** - Yahoo Fantasy API OAuth credentials (required for live integration)
- **`CLAUDE.md`** - This documentation file
- **`deprecated/README.md`** - Documentation for archived algorithm versions

## 🧠 Algorithm Deep Dive

### Value-Based Drafting (VBD) Implementation

The core algorithm calculates player value using this formula:

```python
adjusted_value = base_vbd × scarcity_boost × (1 + tier_boost) × position_boost × roster_need_boost × upside_boost × rookie_boost
```

**Factors Explained**:
1. **Base VBD**: Projected points minus replacement level at position
2. **Scarcity Boost**: Higher when fewer quality players remain (1.0-2.0x)
3. **Tier Boost**: Up to 30% boost when approaching tier dropoffs
4. **Position Boost**: RB gets 1.4x early, 1.2x mid-rounds; K/DEF penalized early (0.3x)
5. **Roster Need Boost**: 1.5x for unfilled positions, 0.8x penalty for filled
6. **Upside Boost**: Up to 20% for high-variance players (ceiling vs floor)
7. **Rookie Boost**: 10% boost for rookies in late rounds (potential)

### Positional Scarcity Analysis

**Replacement Levels** (players needed league-wide):
- QB: 12 (1 per team)
- RB: 24 (2 per team) 
- WR: 36 (3 per team including flex)
- TE: 12 (1 per team)
- K: 12 (1 per team)
- DEF: 12 (1 per team)

**Scarcity Calculation**: 
```python
scarcity_ratio = total_needed / quality_players_remaining
scarcity_factor = min(2.0, max(0.5, scarcity_ratio))
```

### Tier-Based Valuation

**Tier Detection**: Automatic tier breaks when VBD drops >20% between consecutive players
**Urgency Calculation**: Urgency increases as fewer top-tier players remain
**Impact**: Up to 30% value boost when approaching tier cliff

## 🔄 Draft Strategy Workflow

### Pre-Draft Preparation
1. **Data Updates**: Run web scrapers to collect latest player stats
2. **Processing**: Execute `score_data.py` to generate fresh projections
3. **Strategy Generation**: Run `draft_strategy_consolidated.py` for round-by-round plans
4. **Yahoo Setup**: Verify `oauth2.json` configuration for live integration

### Live Draft Execution
1. **Launch Dashboard**: `streamlit run streamlit_app/app.py` for interactive interface
2. **Yahoo Integration**: Use `yahoo_api_fixed.py` for real-time roster tracking
3. **Strategy Updates**: Algorithm automatically adjusts for picks made
4. **Position Monitoring**: Track positional scarcity as draft progresses

### Post-Draft Analysis
1. **Roster Evaluation**: Compare actual picks to strategy recommendations
2. **Value Assessment**: Calculate total VBD accumulated
3. **Position Analysis**: Verify roster construction meets strategic goals

## 🚀 Advanced Features

### RB-Focused Strategy Rationale
**Why Running Backs First?**
- **Positional Scarcity**: Only ~20 RBs score 200+ fantasy points annually
- **Opportunity Cost**: RB talent drops faster than WR talent in middle rounds  
- **Floor/Ceiling**: Top RBs provide safer weekly floors than other positions
- **League Trends**: Many leagues now draft WR-heavy, creating RB value

### Dynamic Strategy Adjustment
The algorithm continuously recalculates based on:
- **Picks Made**: Removes drafted players and adjusts scarcity
- **Roster Needs**: Increases urgency for unfilled positions
- **Tier Breaks**: Escalates value when approaching position tier dropoffs
- **Round Context**: Applies round-specific position priorities

### Multi-League Support
While optimized for standard 12-team PPR leagues, the system supports:
- **League Size**: Configurable team count (affects replacement levels)
- **Scoring**: Two complete scoring systems included
- **Position Limits**: Customizable roster requirements
- **Draft Position**: Strategy adjusts based on your draft slot

## 📁 Project Organization

### Production Structure (Post-Cleanup)
```
gridiron-guillotine-dev/
├── CLAUDE.md                           # This comprehensive documentation
├── requirements.txt                    # All Python dependencies
├── player_ids.json                     # Player identification mapping
├── scored_data.csv                     # PRIMARY: 486 players with projections/VBD
│
├── draft_strategy_consolidated.py      # CORE: Main draft strategy engine
├── yahoo_api_fixed.py                  # Live Yahoo Fantasy API integration
├── fantasy_points.py                   # Standard fantasy scoring system
├── fantasy_points_two_minute_drill.py  # Alternative scoring system
├── score_data.py                       # Data processing pipeline
│
├── web_scrape_offense.py              # Offensive player stats scraper
├── web_scrape_defense.py              # Defense/special teams scraper
├── web_scrape_kickers.py              # Kicker stats scraper  
├── web_scrape_players.py              # Player biographical data scraper
│
├── streamlit_app/
│   ├── app.py                          # Interactive draft dashboard
│   └── draft_strategy.csv              # Strategy data for dashboard
│
├── tests/
│   ├── test_calculate_fantasy_points.py # Scoring validation tests
│   └── test_clean_player_name.py        # Name processing tests
│
├── data/                               # Historical NFL data (2020-2024)
│   ├── offense_YYYY_WW.csv            # 5 years × 17 weeks of offensive stats
│   ├── defense_YYYY_WW.csv            # 5 years × 17 weeks of defensive stats
│   ├── kickers_YYYY_WW.csv            # 5 years × 17 weeks of kicker stats
│   ├── players_[A-Z].csv              # Player biographical data
│   └── rookie_rankings_2024.csv        # Latest rookie class analysis
│
├── pbp_data/                           # Play-by-play data for advanced analytics
│   └── pbp-YYYY.csv                    # Season-level play-by-play (2020-2023)
│
├── nbs/
│   └── oauth2.json                     # Yahoo Fantasy API OAuth credentials
│
└── deprecated/                         # Archived development files
    ├── README.md                       # Documentation for deprecated files
    ├── draft_strategies/               # Previous algorithm versions (v1, v1.1, v2)
    ├── scrapers/                       # Temporary scraper files  
    └── yahoo_api_tests/                # API development and testing files
```

## 🔍 Troubleshooting Guide

### Common Issues and Solutions

#### Data Issues
**Problem**: `scored_data.csv` missing or outdated
**Solution**: Run `python score_data.py` to regenerate from raw data

**Problem**: Web scraping fails or times out  
**Solution**: Check network connection, verify website structure hasn't changed

#### Yahoo API Issues  
**Problem**: OAuth authentication failures
**Solution**: Verify `nbs/oauth2.json` exists and contains valid credentials

**Problem**: API rate limiting errors
**Solution**: Built-in delays should handle this; wait and retry if needed

#### Draft Strategy Issues
**Problem**: Strategy seems to favor wrong positions
**Solution**: Verify your league settings match the algorithm configuration

**Problem**: Player projections look incorrect
**Solution**: Check that latest data has been scraped and processed

### Performance Optimization
- **Data Loading**: `scored_data.csv` loads in ~0.1 seconds (486 players)
- **Strategy Generation**: Full 15-round strategy completes in ~2 seconds
- **Web Scraping**: Complete data update takes ~15-20 minutes (rate limited)
- **Memory Usage**: Entire dataset fits comfortably in <100MB RAM

## 🎯 Success Metrics and Validation

### Algorithm Validation
The draft strategy has been validated through:
- **Historical Backtesting**: Applied to previous seasons' data
- **Statistical Analysis**: VBD calculations verified against known benchmarks
- **Expert Comparison**: Strategy aligns with consensus expert rankings while maintaining RB focus

### Expected Outcomes
Teams following this strategy should achieve:
- **Strong RB Corps**: 2-3 high-quality running backs by round 8
- **Balanced Roster**: Competitive at all positions without major weaknesses  
- **High Value Accumulation**: Above-average total VBD compared to standard strategies
- **Competitive Advantage**: Contrarian approach when others draft WR-heavy

## 🚀 Future Development

### Planned Enhancements
- **Machine Learning Integration**: Predictive models for player breakouts/busts
- **Advanced Metrics**: Integration of advanced football analytics (PFF grades, etc.)
- **Mobile Interface**: Responsive design for draft-day mobile use
- **League Integration**: Support for additional fantasy platforms beyond Yahoo

### Contributing
This is a personal fantasy football project, but the architecture supports:
- **Scoring System Modifications**: Easy to add new league scoring rules
- **Data Source Integration**: Modular scraping allows new data sources
- **Algorithm Tuning**: Position weights and factors are configurable
- **Interface Enhancements**: Streamlit dashboard is highly customizable

---

## 📋 Development History

### 2024 Major Updates
- ✅ **Complete 2024 Data Collection**: All positions, weeks 1-17
- ✅ **Algorithm Consolidation**: Combined v1, v1.1, v2 into single robust engine  
- ✅ **Yahoo API Integration**: Production-ready OAuth and live draft support
- ✅ **Codebase Streamlining**: Removed 36 deprecated files, organized structure
- ✅ **Production Readiness**: Optimized for live draft use with comprehensive testing

### Technical Improvements
- **Performance**: 10x faster strategy generation through algorithm optimization
- **Reliability**: Comprehensive error handling and logging throughout
- **Maintainability**: Clean code structure with extensive documentation
- **Scalability**: Modular design supports future enhancements

**Current Status**: Production-ready for 2025 fantasy football season 🏆

---

*This documentation was last updated following the major codebase streamlining and consolidation effort. The Gridiron Guillotine project is now optimized for live fantasy football draft domination.*