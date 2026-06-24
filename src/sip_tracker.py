"""
sip_tracker.py
Reads mutual fund holdings from data/mutual_fund_holdings.csv 
and computes portfolio metrics (gain/loss, XIRR, etc.)
"""

import pandas as pd


def load_mutual_fund_holdings(holdings_path: str) -> pd.DataFrame:
    """Load mutual fund holdings from CSV file."""
    df = pd.read_csv(holdings_path)
    return df


def clean_percentage(value: str) -> float | None:
    """Convert percentage string (e.g., '7.19%', 'N/A') to float."""
    if pd.isna(value) or value == 'N/A' or str(value).strip() == 'N/A':
        return None
    try:
        return float(str(value).strip().rstrip('%'))
    except:
        return None


def get_sip_summary(holdings_path: str) -> pd.DataFrame:
    """
    Returns a DataFrame with mutual fund holdings.
    Columns: fund_name, amc, category, sub_category, folio_no, units, 
             total_invested, current_value, gain_loss, gain_loss_pct, xirr
    """
    df = load_mutual_fund_holdings(holdings_path)
    
    # Rename columns to match app.py expectations
    df = df.rename(columns={
        'Scheme Name': 'fund_name',
        'AMC': 'amc',
        'Category': 'category',
        'Sub-category': 'sub_category',
        'Folio No.': 'folio_no',
        'Source': 'source',
        'Units': 'units',
        'Invested Value': 'total_invested',
        'Current Value': 'current_value',
        'Returns': 'gain_loss',
        'XIRR': 'xirr',
    })
    
    # Convert numeric columns
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df['total_invested'] = pd.to_numeric(df['total_invested'], errors='coerce')
    df['current_value'] = pd.to_numeric(df['current_value'], errors='coerce')
    df['gain_loss'] = pd.to_numeric(df['gain_loss'], errors='coerce')
    df['gain_loss_pct'] = df['xirr'].apply(clean_percentage)
    
    # Add computed NAV columns for compatibility with app.py
    df['current_nav'] = None  # Not available from CSV
    df['nav_date'] = None  # Not available from CSV
    df['total_units'] = df['units']  # Alias for compatibility
    
    # Select and order columns for app.py
    return df[['fund_name', 'amc', 'category', 'sub_category', 'folio_no', 'source',
               'units', 'total_units', 'total_invested', 'current_value', 
               'gain_loss', 'gain_loss_pct', 'current_nav', 'nav_date', 'xirr']]
