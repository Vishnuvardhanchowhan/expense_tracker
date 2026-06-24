"""
parser.py
Reads a single monthly bank statement CSV and normalizes it into a standard
DataFrame with columns: date, description, amount, balance, source_file,
financial_month

Built to be flexible across bank export formats. If your bank's columns don't
get picked up automatically, add the column name to the relevant list in
COLUMN_ALIASES below - that's the only place you should need to edit.
"""
from datetime import date, timedelta

import pandas as pd
from pathlib import Path
import os
import re
import sys
import accumlator_daily as daily_spend_fetcher

# Add your bank's exact column header here if auto-detection fails for it.
COLUMN_ALIASES = {
    "date": ["date", "txn date", "tran date", "transaction date", "value date", "posting date"],
    "description": ["description", "narration", "particulars", "transaction details",
                     "remarks", "details"],
    "debit": ["debit", "withdrawal", "debit amount", "withdrawal amt", "cr"],
    "credit": ["credit", "deposit", "credit amount", "deposit amt", "dr"],
    "amount": ["amount", "transaction amount", "txn amount"],
    "balance": ["balance", "bal", "closing balance", "running balance"],
}

# Maps month abbreviations as they appear in salary narrations
# (e.g. "JAN 26 SALARY", "DEC 25 SALARY") to month numbers.
_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Matches narrations like "JAN 26 SALARY", "DEC 25 SALARY" to pull out which
# month the salary is actually FOR, since salary often credits in the
# preceding calendar month (e.g. "JAN 26 SALARY" lands on 29-Dec-2025).
_SALARY_MONTH_RE = re.compile(
    r"\b(" + "|".join(_MONTH_ABBR.keys()) + r")\s*[' ]?(\d{2,4})\s*SALARY\b",
    re.IGNORECASE,
)


def _find_column(df_columns, aliases):
    """Match a real column name to one of our known aliases, case/space-insensitive."""
    normalized = {re.sub(r"[^a-z]", "", c.lower()): c for c in df_columns}
    for alias in aliases:
        key = re.sub(r"[^a-z]", "", alias.lower())
        if key in normalized:
            return normalized[key]
    return None





def _extract_salary_financial_month(description: str, txn_date: pd.Timestamp):
    """
    If the narration mentions a salary month explicitly (e.g. "JAN 26 SALARY",
    "DEC 25 SALARY"), return the corresponding period ('YYYY-MM') that the
    salary is actually FOR - not the calendar date it was credited.

    Many companies pay salary a few days before month-end, so "JAN 26 SALARY"
    can land on 29-Dec-2025. Without this, expense tracking shows the wrong
    month as having no income and a false negative "leftover".

    Returns None if the description doesn't match a salary pattern, in which
    case the caller should just use the transaction's actual calendar month.
    """
    if pd.isna(txn_date):
        return None

    match = _SALARY_MONTH_RE.search(str(description))
    if not match:
        return None

    month_abbr = match.group(1).upper()
    year_part = match.group(2)
    month_num = _MONTH_ABBR[month_abbr]

    # Year might be 2-digit ("26") or 4-digit ("2026")
    year_num = int(year_part)
    if year_num < 100:
        year_num += 2000
    return f"{year_num:04d}-{month_num:02d}"


def parse_statement(filepath: str) -> pd.DataFrame:
    """
    Parse one bank statement CSV into standard columns:
    date (datetime), description (str), amount (float, negative = spend, positive = credit),
    balance (float or NaN), source_file (str), financial_month (str 'YYYY-MM')
    
    Amount = credit - debit (positive for money in, negative for money out)
    Salary transactions are attributed to the month in their narration, not the date credited.
    """
    filepath = Path(filepath)
    raw = pd.read_csv(filepath)
    raw.columns = [str(c).strip() for c in raw.columns]

    # Detect columns by alias
    date_col = _find_column(raw.columns, COLUMN_ALIASES["date"])
    desc_col = _find_column(raw.columns, COLUMN_ALIASES["description"])
    debit_col = _find_column(raw.columns, COLUMN_ALIASES["debit"])
    credit_col = _find_column(raw.columns, COLUMN_ALIASES["credit"])
    amount_col = _find_column(raw.columns, COLUMN_ALIASES["amount"])
    balance_col = _find_column(raw.columns, COLUMN_ALIASES["balance"])

    if date_col is None or desc_col is None:
        raise ValueError(
            f"Could not detect date/description columns in {filepath.name}. "
            f"Found columns: {list(raw.columns)}. "
            f"Add your bank's exact header names to COLUMN_ALIASES in parser.py."
        )

    df = pd.DataFrame()
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce", dayfirst=True)
    df["description"] = (
        raw[desc_col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    )

    # Compute amount: credit - debit, or use amount column directly
    if debit_col is not None and credit_col is not None:
        debit = pd.to_numeric(raw[debit_col], errors="coerce").fillna(0)
        credit = pd.to_numeric(raw[credit_col], errors="coerce").fillna(0)
        df["amount"] = credit - debit
    elif amount_col is not None:
        df["amount"] = pd.to_numeric(raw[amount_col], errors="coerce")
    else:
        raise ValueError(
            f"Could not detect debit/credit or amount columns in {filepath.name}. "
            f"Found columns: {list(raw.columns)}. "
            f"Add your bank's exact header names to COLUMN_ALIASES in parser.py."
        )

    if balance_col is not None:
        df["balance"] = pd.to_numeric(raw[balance_col], errors="coerce")
    else:
        df["balance"] = pd.NA

    df = df.dropna(subset=["date", "amount"])

    # Set financial_month: salary narrations shift to next month
    df["financial_month"] = df.apply(
        lambda row: _extract_salary_financial_month(row["description"], row["date"]),
        axis=1,
    )
    df["financial_month"] = df["financial_month"].fillna(df["date"].dt.to_period("M").astype(str))

    df["source_file"] = filepath.name
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    return df


def parse_all_statements(folder: str) -> pd.DataFrame:
    """Parse every CSV in the statements folder and concatenate into one DataFrame."""
    folder = Path(folder)
    files = sorted(folder.glob("*.csv"))
    empty_cols = ["date", "description", "amount", "balance", "source_file", "financial_month"]
    if not files:
        return pd.DataFrame(columns=empty_cols)

    frames = []
    errors = []
    for f in files:
        try:
            frames.append(parse_statement(str(f)))
        except ValueError as e:
            errors.append(str(e))

    if errors:
        # Surface parse errors but don't crash the whole pipeline over one bad file
        for e in errors:
            print(f"[parser warning] {e}")

    if not frames:
        return pd.DataFrame(columns=empty_cols)
    cumm_df = pd.concat(frames, ignore_index=True)
    
    # Only try to fetch daily transactions if token exists (already authenticated)
    token_file = Path(daily_spend_fetcher.TOKEN_FILE)
    if not token_file.exists():
        print("[parser info] Gmail token not found - skipping daily transactions fetch")
        return cumm_df
    
    try:
        curr_date_run = date.today()
        prev_day_run = curr_date_run - timedelta(days=1)
        
        transactions = daily_spend_fetcher.fetch_axis_transactions(
            prev_day_run.strftime("%Y-%m-%d"), 
            curr_date_run.strftime("%Y-%m-%d")
        )
        
        if transactions:
            curr_day_df = pd.DataFrame(transactions)
            curr_day_df["tran_date"] = pd.to_datetime(curr_day_df["tran_date"], format="%d-%m-%Y", errors="coerce")
            curr_day_df = curr_day_df[curr_day_df["tran_date"].dt.date == curr_date_run]
            
            if not curr_day_df.empty:
                last_prev_balance = cumm_df["balance"].iloc[-1] if not cumm_df.empty else 0
                curr_day_df["balance"] = (last_prev_balance +
                                          (curr_day_df["cr"].fillna(0) - curr_day_df["dr"].fillna(0)).cumsum())
                
                final_df = pd.concat([cumm_df, curr_day_df], ignore_index=True)
                final_df = final_df.drop_duplicates(subset=["tran_date", "particulars", "dr", "cr"], keep="first").reset_index(drop=True)
                return final_df
    except Exception as e:
        print(f"[parser warning] Failed to fetch daily transactions: {e}")
    
    return cumm_df
