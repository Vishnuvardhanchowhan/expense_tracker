"""
categorizer.py
Applies data/category_rules.json to a parsed transactions DataFrame.
Adds a 'category' column. Anything that matches nothing becomes 'Uncategorized',
EXCEPT unrecognized payee names that look like a person's name - those go to
'Local Shops / Unknown Person' instead, since in India a huge number of small
vendors (sabzi-wala, kirana store, tailor, etc.) use their own personal name
as their UPI ID rather than a registered business name. This keeps them out
of both your tagged Family/Friends categories AND the generic Uncategorized
bucket, so the Review tab stays useful for genuinely new/odd transactions.
"""

import json
import re
import pandas as pd
from pathlib import Path

# Common UPI narration tokens to strip before judging whether what's left
# looks like a person's name vs a business name.
_UPI_NOISE_TOKENS = re.compile(
    r"\b(UPI|P2M|P2A|SENT|TO|U|VIA|PAY|NA|INT|INTL|MANDATE|STATIC|TXN)\b",
    re.IGNORECASE,
)

# If the cleaned payee name has no digits, is mostly alphabetic, and has 2+
# words, AND doesn't contain common business-indicating tokens, we guess
# it's a person. This is deliberately conservative - false negatives (a
# person misclassified as unknown business) are fine, they just land in
# Uncategorized for manual review.
_BUSINESS_HINTS = re.compile(
    r"(PRIVATE|PVT|LTD|LIMITED|LLP|ENTERPRISE|TRADERS|STORES?|MART|FOODS?|"
    r"FOODCOURT|RESTAURANT|HOTEL|CAFE|PHARMA|PHARMACY|ELECTRONICS|MOBILES?|"
    r"TECH|VENTURES|DEVELOPERS|MOTORS|SERVICES|SOLUTIONS|BANK|FINANCE|"
    r"COMMERCE|RETAIL|FILLING|STATION|TOLL|GOVT|GOVERNMENT|DEPARTMENT|"
    r"CLINIC|HOSPITAL|DIAGNOSTIC|OPTICS|TOYS|BAGS|COFFEE|TEA|JUICE|SHAKES|"
    r"WINES|KULFI)",
    re.IGNORECASE,
)


def load_rules(rules_path: str) -> list:
    with open(rules_path, "r") as f:
        config = json.load(f)
    return config["categories"]


def _looks_like_person_name(payee_raw: str) -> bool:
    """Heuristic: does this UPI payee look like an individual's name rather
    than a registered business? Used to route local-vendor payments (sabzi
    wala, kirana store using own name as UPI ID, etc.) to their own bucket."""
    cleaned = _UPI_NOISE_TOKENS.sub("", payee_raw).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if not cleaned or len(cleaned) < 3:
        return False
    if any(ch.isdigit() for ch in cleaned):
        return False
    if _BUSINESS_HINTS.search(cleaned):
        return False

    words = cleaned.split()
    word_count = len(words)
    if word_count > 5:
        return False
    if word_count == 1:
        # Single-word payees are riskier to call a "person" (could be an
        # abbreviation like 'HSC'). Require reasonable length so we don't
        # misfire on short acronyms.
        return len(words[0]) >= 4
    return True


def _extract_upi_payee(description: str) -> str:
    """
    Pulls the payee name out of a UPI narration like:
    'UPI/P2M/535513023966/BURUGU JYOTHI/Sent u/YES BANK LIMITED YBS'
    -> 'BURUGU JYOTHI'
    Returns '' if the description doesn't look like a UPI transaction.
    """
    parts = str(description).split("/")
    if len(parts) >= 4 and parts[0].strip().upper() == "UPI":
        return parts[3].strip()
    return ""


def categorize_transaction(description: str, rules: list, amount: float = None) -> str:
    desc_upper = str(description).upper()

    # Any credit (money coming in) that isn't a specifically known inflow
    # (e.g. refund) gets bucketed as Income rather than cluttering Uncategorized.

    # Match known people first (exact-ish substring match on UPI ID or name)
    for rule in rules:
        for person in rule.get("people", []):
            if person.upper() in desc_upper:
                return rule["name"]

    # Match keyword rules (merchants, EMI, bills, etc.)
    for rule in rules:
        for keyword in rule.get("keywords", []):
            if keyword.upper() in desc_upper:
                return rule["name"]

    # Nothing matched - check if this looks like a payment to an unrecognized
    # individual (local vendor using their own name as UPI ID) before giving
    # up and calling it fully Uncategorized.
    payee = _extract_upi_payee(description)
    if payee and _looks_like_person_name(payee):
        return "Local Shops / Unknown Person"
    if amount is not None and 'INVESCO INDIA PRIVATE' in desc_upper:
        return "Income"
    return "Uncategorized"


def categorize_dataframe(df: pd.DataFrame, rules_path: str) -> pd.DataFrame:
    """Adds a 'category' column to df based on the description field."""
    rules = load_rules(rules_path)
    df = df.copy()
    df["category"] = df.apply(
        lambda row: categorize_transaction(row["description"], rules, row["amount"]), axis=1
    )
    return df


def get_uncategorized(df: pd.DataFrame) -> pd.DataFrame:
    """Helper for the dashboard's review tab - everything still tagged
    Uncategorized, plus Local Shops/Unknown Person entries (since some of
    those might actually be a friend/family member you haven't tagged yet)."""
    return df[df["category"].isin(["Uncategorized", "Local Shops / Unknown Person"])].copy()
