# Integration Tests & Development Files

This directory contains integration tests and development utilities for the Gridiron Guillotine project.

## 🧪 Strategy Testing Files

### Mock Draft Testing
- `demo_mock_draft.py` - Full mock draft simulation examples
- `test_contingency_controls.py` - Manual override testing for live draft scenarios
- `test_enhanced_display.py` - Enhanced recommendation display testing

### Strategy Validation
- `test_corrected_hero_rb.py` - Hero-RB strategy validation tests
- `test_improved_strategy.py` - Improved strategy logic testing
- `test_all_fixes.py` - Comprehensive strategy fix validation

## 🔧 Development Utilities

### Data & Database
- `fix_defense_data.py` - Database DEF player fixes and manual data additions
- `debug_weighted_calc.py` - Weighted calculation debugging utilities

### Strategy Fixes
- `strategy_fixes.py` - Strategy correction implementations and testing

## 🚀 Usage

Run individual test files to validate specific functionality:

```bash
# Test the corrected Hero-RB strategy
python tests/integration/test_corrected_hero_rb.py

# Test contingency controls for live drafts  
python tests/integration/test_contingency_controls.py

# Run mock draft demonstration
python tests/integration/demo_mock_draft.py
```

## 📋 Integration with Main Package

These files test and validate the main package functionality:
- Core strategy engine (`gridiron_guillotine.core.strategy`)
- Mock draft simulator (`gridiron_guillotine.live.mock_draft`)
- Database operations (`gridiron_guillotine.data.database`)
- CLI commands (`gridiron draft mock`)

All improvements tested here have been integrated into the main package structure.