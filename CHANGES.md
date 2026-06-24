# Expense Tracker - Bug Fixes and Code Simplification

## Summary of Changes

### 1. Fixed Plotly Express Error (app.py)
**Issue**: `ValueError: Plotly Express cannot process wide-form data with columns of different type`

**Root Cause**: The `sip_df` DataFrame had mixed data types in the `current_value` column (floats and `None` values when NAV couldn't be fetched). Plotly Express couldn't handle this with wide-form data (multiple y columns).

**Solution** (lines 223-240):
- Converted data to **long-form** using `pd.melt()` 
- Dropped rows with missing `current_value` using `dropna()`
- Mapped metric names to readable labels
- Used `color` parameter instead of multiple `y` columns

This is the proper approach for Plotly Express grouped bar charts with mixed data types.

---

### 2. Simplified parser.py
**Issues Fixed**:
- Removed debug `st.write()` call (line 65)
- Removed unnecessary streamlit import
- Removed complex `_detect_debit_credit_orientation()` function that tried to auto-swap columns

**Improvements**:
- **Cleaner logic**: Debit/credit columns are computed directly as `credit - debit` without auto-swapping
- **Simpler codebase**: Reduced from ~220 lines to ~176 lines
- **Same functionality**: 
  - Still parses bank statements flexibly
  - Still handles salary month shifting (e.g., "JAN 26 SALARY" → 2026-01 even if credited in Dec)
  - Column detection via COLUMN_ALIASES still works
  - Balance reconciliation check still works

**How it works now**:
```
debit/credit columns detected → amount = credit - debit
OR
amount column detected → amount = amount value directly
```

If your bank's debit/credit columns are labeled incorrectly (backwards), just update the COLUMN_ALIASES dictionary in parser.py.

---

## Testing
✅ Parser loads 984 transactions correctly
✅ Full pipeline (parser → categorizer → build_master) works
✅ Financial month shifting for salary works correctly (2025-12, 2026-01, etc.)
✅ DataFrame structure maintained: `date, description, amount, balance, source_file, financial_month`

---

## Files Modified
1. **app.py** - Fixed Plotly Express error with SIP holdings chart
2. **parser.py** - Simplified and cleaned up code

---

## Next Steps (Optional)
If you want to further group transactions by date/payee, you can do that in a new transformation layer after parsing, which would keep the parser focused on just parsing CSV files.

