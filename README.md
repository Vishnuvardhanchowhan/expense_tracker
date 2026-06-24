# Expense Tracker

Personal expense + SIP dashboard. Built on Streamlit, reads bank statement
CSVs you drop into a folder.

## Setup (one-time)

```bash
pip install -r requirements.txt
```

## Monthly workflow

1. Export your bank statement as CSV for the month.
2. Rename it to `YYYY-MM.csv` (e.g. `2026-03.csv`) and drop it into
   `data/statements/`.
3. (If you do SIPs) Add this month's installment to `data/sip_holdings.json`
   under the right fund's `units_log` — date, amount invested, units bought,
   NAV on that date. Your bank/AMC statement or app shows units allotted.
4. Run the dashboard:
   ```bash
   streamlit run app.py
   ```
5. Check the "Review Uncategorized" tab. For anything sitting there, add a
   keyword (or the UPI ID, for people) to `data/category_rules.json` so it
   gets caught automatically next time. Re-run the app and it'll re-categorize
   retroactively across all months too.

## Files you'll actually edit

- `data/category_rules.json` — keyword/people → category mapping. This is
  your main tuning knob. Add specific keywords above generic ones since the
  first match wins. Already pre-loaded with patterns from real Indian bank
  UPI narrations (Swiggy, Blinkit, EMI auto-debits, etc.) - just add your own
  family/friend UPI IDs or names under `Send Money - Family` / `Send Money - Friends`.
- `data/sip_holdings.json` — your SIP funds and monthly installments.
  Scheme codes: search at https://www.mfapi.in/ or hit
  `https://api.mfapi.in/mf/search?q=YOUR_FUND_NAME` in a browser.

## Things this tracker automatically handles

These came up while testing against a real 6-month statement, so they're
built in rather than something you need to fix by hand each time:

- **Salary timing.** If your salary narration mentions the month it's for
  (e.g. "JAN 26 SALARY") even though it lands a few days before month-end,
  the tracker attributes it to the *intended* month, not the calendar date.
  This avoids a false "negative leftover" in the month salary lands and a
  false "no income" in the month it's actually for.
- **Swapped DR/CR columns.** Some bank exports mislabel which column is debit
  vs credit. The parser cross-checks against the statement's own running
  Balance column and auto-corrects if needed, printing a notice when it does.
  This is verified mathematically, not guessed.
- **Local vendors using personal names as UPI ID.** Extremely common in India
  - your sabzi-wala, kirana store, or tea stall might show up as a person's
  name rather than a business name. These get routed to a
  "Local Shops / Unknown Person" bucket (visible in the Review tab, with
  recurring names surfaced first) instead of mixing into either your tagged
  Family/Friends categories or a generic Uncategorized pile.
- **Balance reconciliation check.** Every build verifies previous_balance +
  amount = next balance for every row. Mismatches print a warning - if you
  ever see one, it usually means a new statement format snuck in a column
  layout the parser hasn't seen before.

## Files you (probably) won't touch

- `src/parser.py` — auto-detects bank CSV column names. If a new statement
  fails to parse, the error message tells you which columns it found —
  add your bank's exact header name to `COLUMN_ALIASES` at the top of the file.
- `src/categorizer.py`, `src/sip_tracker.py`, `src/build_master.py` — pipeline
  internals.
- `data/master_transactions.csv` — auto-generated on every run, don't edit
  directly (it'll be overwritten).

## Notes

- SIP returns use live NAV from mfapi.in (free, public, no signup). It fetches
  the latest available NAV each time you load the Investments tab.
- Any credit (money in) is auto-tagged "Income" unless it matches a more
  specific rule, so salary/refunds don't clutter the Uncategorized tab.
- Dashboard auto re-scans `data/statements/` on every load — no manual file
  selection needed, just drop the CSV in and refresh.
