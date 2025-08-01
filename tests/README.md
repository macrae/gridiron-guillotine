# Gridiron Guillotine Test Suite

This directory contains comprehensive tests for the Gridiron Guillotine fantasy football draft strategy system.

## 🚀 Quick Start

Run the complete test suite:

```bash
# Using pytest directly
pytest

# Using python module (alternative)
python -m pytest tests/

# With verbose output
pytest -v

# Run specific test categories
pytest -m "strategy"
pytest -m "integration" 
pytest -m "unit"
```

## 📋 Test Categories

### 🧪 Unit Tests (`tests/`)
Core functionality tests for individual components:

- **`test_advanced_metrics.py`** - WOPR calculations, Expected Fantasy Points, Offensive Context
- **`test_calculate_fantasy_points.py`** - Fantasy point calculations and scoring systems
- **`test_clean_player_name.py`** - Player name standardization and cleaning
- **`test_hero_rb_phases.py`** - Hero-RB strategy phase transitions (Acquisition → Pivot → Depth)
- **`test_position_strategy.py`** - Draft position-specific strategy adaptations

### 🔧 Integration Tests (`tests/integration/`)
End-to-end workflow and system integration tests:

- **`test_all_fixes.py`** - Comprehensive strategy fix validation
- **`test_contingency_controls.py`** - Manual override and filtering capabilities
- **`test_corrected_hero_rb.py`** - Complete Hero-RB strategy validation
- **`test_enhanced_display.py`** - Enhanced recommendation display with NFL teams and news
- **`test_improved_strategy.py`** - Overall strategy improvement validation

## 🏷️ Test Markers

Use pytest markers to run specific test categories:

```bash
# Strategy-related tests
pytest -m "strategy"

# Integration tests only
pytest -m "integration"

# Unit tests only  
pytest -m "unit"

# Mock draft functionality
pytest -m "mock_draft"

# Database operations
pytest -m "database"

# Exclude slow tests
pytest -m "not slow"
```

## 📊 Test Coverage

The test suite covers:

### ✅ Core Strategy Components
- **Hero-RB Phase Logic** - Acquisition, Pivot, and Depth phases
- **Advanced Metrics Integration** - WOPR, Expected Points, Context multipliers
- **Positional Scarcity Analysis** - Dynamic replacement level calculations
- **Value-Based Drafting (VBD)** - Player value calculations
- **Draft Position Optimization** - Early/Middle/Late position strategies

### ✅ Mock Draft System
- **AI Opponent Strategies** - rb_heavy, wr_heavy, zero_rb, late_qb variants
- **Interactive Controls** - Position filtering, team filtering, manual overrides
- **Enhanced Display** - NFL team information, news impact arrows
- **Draft State Management** - Round progression, roster tracking

### ✅ Data Processing
- **Player Name Cleaning** - Standardization across data sources
- **Fantasy Point Calculations** - PPR, standard, and half-PPR scoring
- **Database Integration** - SQLite operations and data persistence

### ✅ Strategy Fixes
- **QB Trap Prevention** - Early QB penalty system (0.7x multiplier until round 8)
- **RB Depth Accumulation** - Enhanced depth phase boost (1.6x multiplier)
- **Position Limits** - Realistic roster construction (QB:2, RB:4, WR:5, TE:2)
- **Value Thresholds** - Negative VBD player filtering

## 🎯 Expected Results

All tests should pass with output like:

```
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-8.4.1, pluggy-1.6.0
rootdir: /Users/smacrae/gridiron-guillotine
configfile: pyproject.toml
collected 10 items

tests/integration/test_all_fixes.py .                    [ 10%]
tests/integration/test_contingency_controls.py .         [ 20%]
tests/integration/test_corrected_hero_rb.py .            [ 30%]
tests/integration/test_enhanced_display.py .             [ 40%]
tests/integration/test_improved_strategy.py .            [ 50%]
tests/test_advanced_metrics.py .                         [ 60%]
tests/test_calculate_fantasy_points.py .                 [ 70%]
tests/test_clean_player_name.py .                        [ 80%]
tests/test_hero_rb_phases.py .                           [ 90%]
tests/test_position_strategy.py .                        [100%]

============================== 10 passed in 2.18s ==============================
```

## 🔧 Configuration

Test configuration is managed in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests", 
    "unit: marks tests as unit tests",
    "strategy: marks tests related to draft strategy",
    "database: marks tests related to database operations",
    "mock_draft: marks tests related to mock draft functionality",
]
```

## 🐛 Troubleshooting

### Module Import Errors
If you see `ModuleNotFoundError: No module named 'gridiron_guillotine'`:

1. **Preferred Solution**: Install in development mode
   ```bash
   pip install -e .
   ```

2. **Alternative**: Use python module execution
   ```bash
   python -m pytest tests/
   ```

### Slow Tests
Some integration tests may take longer. To skip them:
```bash
pytest -m "not slow"
```

### Database Tests
Database tests require the SQLite database to be initialized:
```bash
gridiron db precompute --force
```

## 📈 Adding New Tests

When adding new tests:

1. **Use descriptive names**: `test_hero_rb_depth_phase_boost()`
2. **Add appropriate markers**: `@pytest.mark.strategy`, `@pytest.mark.integration`
3. **Include docstrings**: Explain what the test validates
4. **Follow naming conventions**: `test_*.py` files, `test_*()` functions
5. **Use proper assertions**: Assert expected behavior clearly

### Example Test Template

```python
import pytest
from gridiron_guillotine.core.strategy import ChampionshipDraftStrategy
from gridiron_guillotine.core.config import get_config

@pytest.mark.strategy
@pytest.mark.unit
def test_new_feature():
    """Test description of what this validates"""
    # Arrange
    config = get_config()
    strategy = ChampionshipDraftStrategy(draft_position=6, config=config)
    
    # Act
    result = strategy.some_method()
    
    # Assert
    assert result == expected_value
    assert len(result) > 0
```

## 🏆 Test Success Criteria

The test suite ensures:

- ✅ **All 10 tests pass** without errors or failures
- ✅ **Strategy correctness** - Hero-RB phases work as designed
- ✅ **Data integrity** - Player data processing is accurate
- ✅ **Mock draft functionality** - Interactive system works properly
- ✅ **API compatibility** - All methods work with current codebase
- ✅ **Error handling** - Graceful handling of edge cases

Your Gridiron Guillotine system is now fully tested and ready for championship-level fantasy football drafting! 🏈