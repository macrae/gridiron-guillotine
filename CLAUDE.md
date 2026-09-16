# CLAUDE.md - Gridiron Guillotine v2.3

**Championship-caliber Python package** for fantasy football draft strategy with Hero-RB methodology, real-time NFL news, persistent database, and live Yahoo Fantasy integration.

## 🏈 Core Features
- **🏆 Hero-RB Strategy**: Research-validated (20.2% vs 16.7% baseline)
- **🎯 Enhanced Tier-Based Drafting**: Dynamic boundaries with urgency detection
- **🗄️ Persistent Database**: Pre-computed SQLite scores for instant recommendations
- **📰 Multi-Source NFL News**: ESPN, NFL.com, RotoWire integration
- **🌐 Yahoo Fantasy Integration**: Live mock draft monitoring (NEW v2.3)
- **📈 2026 Season Ready**: Current roster updates and 5-year historical data

## 🚀 Quick Start

```bash
# Install
pip install -e .

# Core Commands
gridiron db precompute --force              # Pre-compute player scores
gridiron db recommend --draft-position 6    # Get Hero-RB recommendations
gridiron strategy --position 6              # Show draft strategy
gridiron draft mock --position 6            # Interactive mock draft

# Live Yahoo Integration (NEW v2.3)
gridiron draft yahoo-live -p 6 -u "12345"   # Monitor live Yahoo mock draft
gridiron draft yahoo-test                   # Test Yahoo setup

# NFL News Integration
gridiron db news bulk-update --limit 50     # Update player news
gridiron news player "Jackson, Lamar"       # Player-specific news

# Database Operations
gridiron db stats                           # Database statistics
gridiron db player "McCaffrey, Christian"   # Player details
gridiron db draft "Player Name" "Team" 1 1  # Mark player drafted
```

## 💻 Python API Usage

```python
# Core imports
from gridiron_guillotine.core.strategy import ChampionshipDraftStrategy
from gridiron_guillotine.data.database import PlayerDatabase
from gridiron_guillotine.live.yahoo_mock_monitor import YahooMockDraftMonitor

# Quick usage
db = PlayerDatabase()
recommendations = db.get_top_players(limit=10)

strategy = ChampionshipDraftStrategy(draft_position=6)
tier_recs = strategy.get_tier_recommendations(available_players)

# Yahoo integration
monitor = YahooMockDraftMonitor()
monitor.connect_to_mock_draft(draft_url, user_position=6)
monitor.start_monitoring(polling_interval=10)
```

## 🏗️ Package Structure

**Core directories**: `core/` (strategy), `data/` (database/news), `live/` (Yahoo), `cli/` (commands)

## 🎯 Core Classes

- **PlayerDatabase**: Pre-computed scores & news (`data/database.py`)
- **ChampionshipDraftStrategy**: Hero-RB engine (`core/strategy.py`)
- **EnhancedTierCalculator**: Dynamic tier boundaries (`core/tiers.py`)
- **YahooMockDraftMonitor**: Live draft monitoring (`live/yahoo_mock_monitor.py`)
- **NewsIntegrationEngine**: Multi-source NFL news (`data/news_integration.py`)

## 🎯 Enhanced Tier System

- **4-level urgency**: CRITICAL/HIGH/MODERATE/LOW
- **Dynamic boundaries**: Position-specific thresholds (RB 25%, WR 20%, QB 15%, TE 30%)
- **Draft flow awareness**: Adjusts based on picks until your turn
- **Value boosts**: Up to 90% for critical tier situations

## 🔄 2025 Roster Updates

**Major moves integrated**:
- Sam Darnold → Seattle, Justin Fields → NYJ, Geno Smith → LV
- DK Metcalf → Pittsburgh, Davante Adams → LA Rams
- All 2026 team contexts updated for accurate projections

## 🌐 Yahoo Fantasy Integration (NEW v2.3)

**Features**:
- Multi-source monitoring (Yahoo API + web scraping)
- Real-time pick detection with deduplication
- Live Hero-RB strategy recommendations
- Snake draft position calculation

**Setup**:
```bash
python setup_yahoo_integration.py  # One-time setup
gridiron draft yahoo-test          # Test connection
gridiron draft yahoo-live -p 6 -u "draft_url"  # Monitor live draft
```

## 📰 NFL News System

**Sources**: ESPN API, NFL.com scraper, RotoWire (fantasy-focused)
**Features**: Smart classification, injury detection, impact scoring
**CLI**: `gridiron news player "Name"`, `gridiron news injuries`

## 🗄️ Database Workflow

**Pre-draft**:
1. `gridiron db precompute --force` (716 players in 0.5s)
2. `gridiron db news bulk-update --limit 50`
3. `gridiron db stats` (verify setup)

**Live draft**:
1. `gridiron db recommend --draft-position 6`
2. `gridiron db draft "Player" "Team" round pick`
3. Repeat for instant updated recommendations

## 🧠 Algorithm Overview

**Hero-RB Strategy**: Research-validated approach prioritizing elite RBs in early rounds
**Enhanced Tiers**: Dynamic tier boundaries with draft flow awareness
**Positional Scarcity**: VBD calculations with replacement level thresholds
**Advanced Metrics**: WOPR, Expected Points, offensive context integration

## 🔧 Installation & Setup

```bash
# Modern installation
pip install -e .

# Legacy compatibility
pip install -r requirements.txt

# Verify installation
python -c "import gridiron_guillotine; print('✅ Success')"
gridiron --help
```

## 📁 Key Files

- **Season notes / activity log**: `NOTES.md` — league IDs, pending waivers/trades, weekly post-mortems, decisions (e.g. "keep Warren"), and things to keep track of. Read it first when asked about the leagues, and append to it after any league activity.

- **Main CLI**: `gridiron_guillotine/cli/main.py`
- **Strategy Engine**: `gridiron_guillotine/core/strategy.py`
- **Database**: `data/enhanced_players.db` (SQLite)
- **Config**: `pyproject.toml` (modern Python setup)
- **Legacy**: `deprecated/` (preserved old files)

## 🎮 Mock Draft Testing

**Interactive features**:
- 12 AI opponents with diverse strategies
- Manual override controls (`qb`, `rb`, `wr`, team codes)
- Real-time tier urgency alerts
- Comprehensive roster analysis

## 📋 Migration Summary

**Before**: 19+ individual Python scripts
**After**: Professional package with CLI commands
**Benefits**: Type safety, proper imports, comprehensive testing, real-time news, Yahoo integration

**Current Status**: 🌐 **Championship-ready v2.3** - Production package with Hero-RB strategy, enhanced tier-based drafting, NFL news integration, 2025 roster updates, and revolutionary Yahoo Fantasy live mock draft monitoring.