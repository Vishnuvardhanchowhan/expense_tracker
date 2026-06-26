"""
build_master.py
Orchestrator: scans data/statements/ for monthly CSVs, parses each one,
applies category rules, and writes data/master_transactions_historical.csv.

Run this manually after dropping a new month's CSV into data/statements/,
or call build_master() directly from the Streamlit app (it's fast enough
to just re-run on every dashboard load, which is what app.py does).
"""

from pathlib import Path
import pandas as pd

from src.parser import parse_all_statements
from src.categorizer import categorize_dataframe

BASE_DIR = Path(__file__).resolve().parent.parent
STATEMENTS_DIR = BASE_DIR / "data" / "statements"
RULES_PATH = BASE_DIR / "data" / "category_rules.json"
MASTER_PATH = BASE_DIR / "data" / "master_transactions.csv"


def build_master() -> pd.DataFrame:
    df = parse_all_statements(STATEMENTS_DIR)

    if df.empty:
        return df

    df = categorize_dataframe(df, RULES_PATH)

    # 'spend' = positive number for money going out, easier for charts later
    df["spend"] = df["amount"].apply(lambda x: -x if x < 0 else 0)
    df["income"] = df["amount"].apply(lambda x: x if x > 0 else 0)

    # Use financial_month (set by parser.py) rather than the raw calendar
    # month. Salary credits get attributed to the month named in the bank's
    # own narration (e.g. "JAN 26 SALARY") instead of the date it actually
    # landed, since salary often arrives a few days before month-end and
    # would otherwise make the wrong month look like it has no income.
    df["month"] = df["financial_month"]

    _check_balance_reconciliation(df)

    df.to_csv(MASTER_PATH, index=False)
    return df


def _check_balance_reconciliation(df: pd.DataFrame) -> None:
    """
    Sanity check: for each source file, verify that previous_balance + amount
    == this row's balance. Flags any row where they don't match, which
    usually means a row got mis-parsed (wrong sign, skipped row, duplicate).
    Only runs if the statement actually had a balance column.
    """
    if "balance" not in df.columns or df["balance"].isna().all():
        return

    mismatches = []
    for source_file, group in df.groupby("source_file", sort=False):
        # Don't re-sort - parser.py already produced rows in correct
        # chronological order (including same-day sequence, which matters
        # since balance only reconciles in the bank's original row order).
        prev_balance = None
        for _, row in group.iterrows():
            if pd.isna(row["balance"]):
                prev_balance = None
                continue
            if prev_balance is not None:
                expected = round(prev_balance + row["amount"], 2)
                actual = round(row["balance"], 2)
                if abs(expected - actual) > 0.5:  # small tolerance for rounding
                    mismatches.append(
                        f"{source_file} on {row['date'].date()}: expected balance "
                        f"{expected}, found {actual} ('{row['description'][:50]}')"
                    )
            prev_balance = row["balance"]

    if mismatches:
        print(f"[build_master warning] {len(mismatches)} balance mismatch(es) detected:")
        for m in mismatches[:10]:
            print(f"  - {m}")
        if len(mismatches) > 10:
            print(f"  ... and {len(mismatches) - 10} more")


if __name__ == "__main__":
    result = build_master()
    print(f"Built master with {len(result)} transactions.")
    if not result.empty:
        print(f"Saved to {MASTER_PATH}")
        print(f"Date range: {result['date'].min()} to {result['date'].max()}")
        print(f"Categories found: {sorted(result['category'].unique())}")
