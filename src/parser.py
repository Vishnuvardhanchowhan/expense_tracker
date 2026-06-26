"""
parser.py
Reads a single monthly bank statement CSV and normalizes it into a standard
DataFrame with columns: date, description, amount, balance, source_file,
financial_month

Built to be flexible across bank export formats. If your bank's columns don't
get picked up automatically, add the column name to the relevant list in
COLUMN_ALIASES below - that's the only place you should need to edit.
"""
import os
from datetime import date, timedelta
import pandas as pd
from pathlib import Path
import accumlator_daily as daily_spend_fetcher


def parse_all_statements(STATEMENTS_DIR: Path) -> pd.DataFrame:
    historical_transactions_file_path = os.path.join(STATEMENTS_DIR, "master_transactions_historical.csv")
    cumm_df = pd.read_csv(historical_transactions_file_path)
    cumm_df['date'] = pd.to_datetime(cumm_df['date'], format='mixed')
    # Only try to fetch daily transactions if token exists (already authenticated)
    token_file = Path(daily_spend_fetcher.TOKEN_FILE)
    if not token_file.exists():
        print("[parser info] Gmail token not found - skipping daily transactions fetch")
        return cumm_df
    curr_date_run = pd.to_datetime(date.today())
    # curr_date_run = pd.to_datetime('2026-06-26', format='%Y-%m-%d')
    prev_day_run = curr_date_run - timedelta(days=1)

    transactions = daily_spend_fetcher.fetch_axis_transactions(
        prev_day_run.strftime("%Y-%m-%d"),
        curr_date_run.strftime("%Y-%m-%d")
    )
    transactions = pd.DataFrame(transactions)
    if not transactions.empty:
        transactions["tran_date"] = pd.to_datetime(transactions["tran_date"], format="mixed", errors="coerce")
        transactions = transactions[transactions["tran_date"] == curr_date_run]
        transactions['financial_month'] = transactions['tran_date'].dt.to_period("M").astype(str)
        transactions['source_file'] = 'daily_transactions'
        last_prev_balance = cumm_df["balance"].iloc[-1] if not cumm_df.empty else 0
        transactions['amount'] = transactions['cr'].fillna(0)-transactions['dr'].fillna(0)
        transactions["balance"] = (last_prev_balance + transactions['amount'].cumsum())
        transactions.rename(columns={'tran_date': 'date', 'particulars': 'description'}, inplace=True)
        transactions.drop(columns=['cr', 'dr', 'bal'], inplace=True)
        final_df = pd.concat([cumm_df, transactions], ignore_index=True)
        final_df['date'] = final_df['date'].dt.strftime("%Y-%m-%d")
        final_df = final_df.drop_duplicates(subset=["date", "description", "amount"], keep="first").reset_index(
            drop=True)
        final_df.to_csv(historical_transactions_file_path, index=False)
        final_df['date'] = pd.to_datetime(final_df['date'], format="%Y-%m-%d", errors="coerce")
        return final_df
    return cumm_df

if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent
    STATEMENTS_DIR = BASE_DIR / "data" / "statements"
    parse_all_statements(STATEMENTS_DIR)