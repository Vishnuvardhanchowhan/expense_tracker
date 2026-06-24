# Mutual Fund Holdings CSV Integration

## Overview
The expense tracker now reads mutual fund holdings from a CSV file (`data/mutual_fund_holdings.csv`) instead of a JSON configuration file.

## CSV Format

The CSV file should have the following columns:

| Column | Type | Description |
|--------|------|-------------|
| Scheme Name | Text | Name of the mutual fund scheme |
| AMC | Text | Asset Management Company (e.g., SBI Mutual Fund, HDFC Mutual Fund) |
| Category | Text | Fund category (e.g., Equity, Commodities) |
| Sub-category | Text | Specific category type (e.g., Thematic, Mid Cap, Gold) |
| Folio No. | Number | Folio number from your investment platform |
| Source | Text | Where you hold the investment (e.g., Groww, Kuvera) |
| Units | Number | Number of units held |
| Invested Value | Number | Total amount invested (₹) |
| Current Value | Number | Current portfolio value (₹) |
| Returns | Number | Total returns in rupees |
| XIRR | Text | Annualized return percentage (e.g., '7.19%') |

## Example Entry

```
SBI PSU Direct Plan Growth,SBI Mutual Fund,Equity,Thematic,42210024,Groww,56.765,1999.9,2236.09,236.187812,7.19%
```

## How to Update Your Holdings

1. Export your mutual fund portfolio from your investment platform (Groww, Kuvera, etc.)
2. Copy the relevant columns into `data/mutual_fund_holdings.csv`
3. The app will automatically refresh the data on next load (with Streamlit cache TTL of 300 seconds)

## Changes Made

### Files Modified

1. **src/sip_tracker.py**
   - Removed: NAV fetching from mfapi.in API
   - Removed: JSON-based configuration reading
   - Added: CSV file reading with `load_mutual_fund_holdings()`
   - Added: Percentage parsing with `clean_percentage()`
   - Simplified: Direct data loading from user-maintained CSV

2. **app.py**
   - Updated: `SIP_HOLDINGS_PATH` to point to CSV file
   - Updated: Display columns to show AMC, Category, Sub-Category
   - Maintained: All existing functionality (metrics, charts, summaries)

3. **New File: data/mutual_fund_holdings.csv**
   - Pre-populated with sample data from your holdings
   - Can be updated manually or programmatically

## Benefits

✅ No need to maintain complex JSON with scheme codes  
✅ Uses data directly from your investment platform export  
✅ Includes AMC and category information for better tracking  
✅ XIRR values directly from source, no calculations needed  
✅ Easier to update - just export CSV from your investment app  

## Troubleshooting

**Error: "No columns to parse from file"**
- The CSV file is empty or not created. Create it with the sample data.

**Error: Column not found**
- Ensure column names exactly match those in the table above (case-sensitive).

**Data not updating**
- Streamlit caches data for 300 seconds. Refresh the browser or wait.
- Verify file is saved in `data/mutual_fund_holdings.csv`

