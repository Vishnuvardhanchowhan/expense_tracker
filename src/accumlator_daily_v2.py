"""
Axis Bank Transaction Alert Extractor
--------------------------------------
Fetches "transaction alert for Axis Bank A/c" emails from Gmail between two dates,
parses the debited/credited amount, account number, date/time, and transaction
info (particulars), then writes them to an Excel file with columns:

    Tran Date | PARTICULARS | DR | CR | BAL

SETUP (one-time):
1. Go to https://console.cloud.google.com/ -> create/select a project.
2. Enable the "Gmail API" for that project.
3. Create OAuth Client ID credentials (type: Desktop App).
4. Download the JSON and save it as `credentials.json` next to this script.
5. pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib openpyxl

USAGE:
    python axis_bank_extractor.py --start 2026-06-01 --end 2026-06-24 --out transactions.xlsx

On first run, a browser window will open asking you to log in to your Google
account and grant read-only Gmail access. A `token.json` is saved afterwards
so you won't need to log in again until it expires.
"""

import argparse
import base64
import os
import re
import sys
import json
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
import streamlit as st

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
parent_dir = Path(__file__).resolve().parent
grand_parent_dir = os.path.dirname(parent_dir)
TOKEN_FILE = os.path.join(grand_parent_dir, "token.json")
CREDENTIALS_FILE = os.path.join(grand_parent_dir, "credentials.json")

SENDER_QUERY = "alerts@axis.bank.in"
SUBJECT_QUERY = "transaction alert for Axis Bank"


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds.valid:
                print("[gmail auth] using valid token from TOKEN_FILE")
                return build("gmail", "v1", credentials=creds)
            elif creds.expired and creds.refresh_token:
                print("[gmail auth] refreshing expired token from TOKEN_FILE")
                creds.refresh(Request())
                return build("gmail", "v1", credentials=creds)
            else:
                print(f"[gmail auth] TOKEN_FILE creds unusable: valid={creds.valid}, expired={creds.expired}, has_refresh_token={bool(creds.refresh_token)}")
        except Exception as e:
            print(f"[gmail auth] TOKEN_FILE load failed: {e}")

    try:
        raw = st.secrets["google"]["token_json"]
        print(f"[debug] token_json length: {len(raw)!r}, first 10 chars: {raw[:10]!r}")
        token_data = json.loads(raw)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        if creds.valid:
            print("[gmail auth] using valid token from st.secrets")
            return build("gmail", "v1", credentials=creds)
        elif creds.expired and creds.refresh_token:
            print("[gmail auth] refreshing expired token from st.secrets")
            creds.refresh(Request())
            return build("gmail", "v1", credentials=creds)
        else:
            print(f"[gmail auth] st.secrets creds unusable: valid={creds.valid}, expired={creds.expired}, has_refresh_token={bool(creds.refresh_token)}")
    except (KeyError, FileNotFoundError, TypeError) as e:
        print(f"[gmail auth] st.secrets token read failed: {e}")

    print("[gmail auth] falling through to interactive OAuth flow -- this WILL fail/hang in CI")

    # Load credentials from Streamlit secrets or file for OAuth flow
    credentials_data = None

    try:
        # Try Streamlit secrets first (for cloud deployment)
        credentials_data = json.loads(st.secrets["google"]["credentials_json"])
    except (KeyError, FileNotFoundError, TypeError):
        # Fall back to local credentials.json file
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                credentials_data = json.load(f)
        else:
            st.error(
                "❌ Google credentials not found!\n\n"
                "Please add credentials to Streamlit secrets:\n"
                "1. Go to app settings ⚙️ → Secrets\n"
                "2. Add: `[google]` section with `credentials_json`\n"
                "3. Reboot app"
            )
            st.stop()

    # Write credentials to temp file for flow
    temp_creds_file = Path("/tmp/credentials_temp.json")
    try:
        with open(temp_creds_file, "w") as f:
            json.dump(credentials_data, f)

        flow = InstalledAppFlow.from_client_secrets_file(str(temp_creds_file), SCOPES)

        # Try local server first (for local development)
        try:
            creds = flow.run_local_server(port=0, open_browser=False)
        except Exception:
            # Fall back to console mode for Streamlit Cloud
            creds = flow.run_console()

        # Clean up temp file
        temp_creds_file.unlink(missing_ok=True)

        # Save token for future use
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        st.stop()


def build_gmail_query(start_date: str, end_date: str) -> str:
    """
    Gmail search query. Filters by sender and date range only — NOT subject,
    since Axis Bank uses several different subject lines for transaction
    alerts (e.g. "transaction alert for Axis Bank A/c", plain "Alert", etc.).
    Subject-agnostic filtering happens later via parse_transaction(), which
    only keeps emails whose body actually contains a debit/credit pattern.

    Gmail's `before:` is exclusive of that day, so we bump end_date by one
    day to make the range inclusive.
    start_date / end_date format: YYYY-MM-DD
    """
    from datetime import timedelta

    start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y/%m/%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    end_fmt_exclusive = (end_dt + timedelta(days=1)).strftime("%Y/%m/%d")

    query = f"from:({SENDER_QUERY}) after:{start_fmt} before:{end_fmt_exclusive}"
    return query


def list_message_ids(service, query: str):
    """Return all Gmail message IDs matching the query, handling pagination."""
    message_ids = []
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=500)
            .execute()
        )
        message_ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return message_ids


def get_message_body_text(service, msg_id: str) -> str:
    """Fetch a message and return its plain-text (or stripped HTML) body."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )
    payload = msg.get("payload", {})
    text_parts = []

    def walk_parts(part):
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            if mime_type == "text/plain":
                text_parts.append(("plain", decoded))
            elif mime_type == "text/html":
                text_parts.append(("html", decoded))
        for sub in part.get("parts", []) or []:
            walk_parts(sub)

    walk_parts(payload)

    # Prefer plain text; fall back to stripped HTML
    plain = next((t for kind, t in text_parts if kind == "plain"), None)
    if plain:
        return plain

    html = next((t for kind, t in text_parts if kind == "html"), None)
    if html:
        return re.sub(r"<[^>]+>", " ", html)

    return ""

def parse_transaction(body: str):
    """
    Extract Tran Date, amount, DR/CR, and particulars from the email body.
    Returns a dict or None if the body doesn't match any expected pattern.
    """
    text = re.sub(r"[ \t]+", " ", body)
    text = re.sub(r"\r\n|\r", "\n", text)

    # ---------- Amount + direction ----------
    amount_match = re.search(
        r"Amount\s+(Credited|Debited)\s*:?\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE
    )
    if amount_match:
        direction, amount_str = amount_match.group(1), amount_match.group(2)
    else:
        amount_match = re.search(
            r"INR\s*([\d,]+\.\d{2})\s*was\s*(credited|debited)", text, re.IGNORECASE
        )
        if amount_match:
            amount_str, direction = amount_match.group(1), amount_match.group(2)
        else:
            # "has been credited/debited with INR 6847.88"
            amount_match = re.search(
                r"(credited|debited)\s+with\s+INR\s*([\d,]+\.\d{2})",
                text,
                re.IGNORECASE,
            )
            if amount_match:
                direction, amount_str = amount_match.group(1), amount_match.group(2)
            else:
                return None

    amount = float(amount_str.replace(",", ""))
    direction = direction.lower()

    # ---------- Date ----------
    date_match = re.search(
        r"Date\s*&\s*Time\s*:?\s*([\d]{2}-[\d]{2}-[\d]{2,4}),?\s*([\d:]{5,8})\s*IST",
        text,
        re.IGNORECASE,
    )
    if date_match:
        tran_date = date_match.group(1)
    else:
        # "on 25-06-2026 at 08:32:17 IST"
        date_match2 = re.search(
            r"\bon\s+([\d]{2}-[\d]{2}-[\d]{2,4})\s+at\s+([\d:]{5,8})\s*IST",
            text,
            re.IGNORECASE,
        )
        tran_date = date_match2.group(1) if date_match2 else ""

    # ---------- Particulars ----------
    info_match = re.search(
        r"Transaction\s+Info\s*:?\s*([^\n]+)", text, re.IGNORECASE
    )
    if info_match:
        particulars = info_match.group(1).strip()
    else:
        # "by NEFT/CMS1762611394246/MOTI" — strip trailing punctuation like a sentence-ending "."
        info_match2 = re.search(r"\bby\s+([A-Z0-9/_\-\.]+)", text)
        particulars = info_match2.group(1).strip().rstrip(".") if info_match2 else ""

    # ---------- Balance ----------
    bal_match = re.search(
        r"(?:Available\s+Balance|Avl\s*Bal|Balance)\s*:?\s*INR?\s*([\d,]+\.\d{2})",
        text,
        re.IGNORECASE,
    )
    balance = bal_match.group(1) if bal_match else ""

    # ---------- Account ----------
    acct_match = re.search(r"A/c\s*(?:no\.?)?\s*[:\-]?\s*(XX\d+)", text, re.IGNORECASE)
    if not acct_match:
        acct_match = re.search(r"Account\s*Number\s*:?\s*(XX\d+)", text, re.IGNORECASE)
    account = acct_match.group(1) if acct_match else ""

    return {
        "tran_date": tran_date,
        "particulars": particulars or account,
        "dr": amount if direction == "debited" else None,
        "cr": amount if direction == "credited" else None,
        "bal": balance,
    }


def parse_email_date(internal_date_ms: str) -> str:
    """
    Convert Gmail's internalDate (ms since epoch, UTC) to DD-MM-YYYY for
    sorting fallback.

    FIX: previously used datetime.fromtimestamp() with no timezone, which
    converts using the *local timezone of the machine running the script*.
    That gave a different (and silently wrong) result locally (IST) vs. on
    a GitHub Actions runner (UTC) -- a 5.5 hour difference, enough to flip
    a transaction near midnight onto the wrong calendar day. internalDate
    is now explicitly treated as UTC, then converted to IST, so the result
    is identical no matter where this script runs.
    """
    dt_utc = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
    dt_ist = dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return dt_ist.strftime("%d-%m-%Y")


def fetch_axis_transactions(start_date: str, end_date: str):
    """
    Main extraction routine.
    start_date / end_date: 'YYYY-MM-DD' strings.
    Returns a list of transaction dicts.
    """
    service = get_gmail_service()
    query = build_gmail_query(start_date, end_date)
    print(f"Gmail search query: {query}")

    msg_ids = list_message_ids(service, query)
    print(f"Found {len(msg_ids)} matching emails.")

    transactions = []
    for mid in msg_ids:
        try:
            msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
            body = get_message_body_text(service, mid)
            parsed = parse_transaction(body)
            if parsed is None:
                continue
            if not parsed["tran_date"]:
                parsed["tran_date"] = parse_email_date(msg.get("internalDate", "0"))
            transactions.append(parsed)
        except HttpError as e:
            print(f"Skipping message {mid} due to API error: {e}")

    def sort_key(t):
        for fmt in ("%d-%m-%y", "%d-%m-%Y"):
            try:
                return datetime.strptime(t["tran_date"], fmt)
            except ValueError:
                continue
        return datetime.min

    transactions.sort(key=sort_key)
    return transactions


if __name__ == "__main__":
    curr_date_run = pd.to_datetime(date.today())
    prev_day_run = curr_date_run - timedelta(days=1)
    transactions = fetch_axis_transactions(prev_day_run, curr_date_run)
    print(transactions)