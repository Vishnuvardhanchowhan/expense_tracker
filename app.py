"""
app.py
Streamlit dashboard for the expense tracker.
Run with: streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from build_master import build_master, MASTER_PATH, RULES_PATH
from sip_tracker import get_sip_summary

BASE_DIR = Path(__file__).resolve().parent
SIP_HOLDINGS_PATH = BASE_DIR / "data" / "mutual_fund_holdings.csv"

st.set_page_config(page_title="Expense Tracker", layout="wide")


# ---------- Data loading ----------

def load_transactions():
    df = build_master()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_sip_summary():
    try:
        return get_sip_summary(str(SIP_HOLDINGS_PATH))
    except Exception as e:
        st.warning(f"Could not load SIP data: {e}")
        return pd.DataFrame()


df = load_transactions()
df['net_spend'] = -df[df['category']!='Income']['amount']
if df.empty:
    st.title("Expense Tracker")
    st.info(
        "No statement files found yet. Drop a CSV into `data/statements/` "
        "named like `2026-01.csv` and refresh this page."
    )
    st.stop()
months = sorted(df["month"].unique())

st.title("💰 Expense Tracker")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Monthly Overview", "🔍 Category Deep Dive", "👨‍👩‍👧 Family & Friends",
     "📈 Investments (SIP)", "⚠️ Review Uncategorized"]
)


# ---------- Tab 1: Monthly Overview ----------

with tab1:
    selected_month = st.selectbox("Select month", months, index=len(months) - 1)
    month_df = df[df["month"] == selected_month]

    total_spend = month_df["spend"].sum()
    total_income = month_df["income"].sum()
    # Net spend = gross spend minus refunds/credits
    net_spend = month_df['net_spend'].sum()
    
    total_to_family_friends = month_df[
        month_df["category"].isin(["Send Money - Family", "Send Money - Friends"])]['net_spend'].sum()
    total_invested = month_df[month_df["category"] == "Stock Trading"]['net_spend'].sum()
    
    # Calculate actual leftover (closing bank balance)
    # Using balance data: closing_balance = last transaction's balance in the month
    # Or if no balance data: use opening balance + income - spend
    if not month_df["balance"].isna().all():
        # We have balance data - use the closing balance (last transaction of month)
        closing_balance = month_df.iloc[-1]["balance"] if len(month_df) > 0 else 0
        # Calculate opening balance from first transaction: opening = balance - amount
        first_balance = month_df.iloc[0]["balance"] if len(month_df) > 0 else 0
        first_amount = month_df.iloc[0]["amount"] if len(month_df) > 0 else 0
        opening_balance = first_balance - first_amount
        leftover = closing_balance
    else:
        # No balance data - calculate from opening assumption + net changes
        # Assume we're tracking net position: opening + income - spend
        leftover = total_income - total_spend

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Bank Balance (Start of the Month)", f"₹{opening_balance:,.0f}")
    c2.metric("Total Spend (Debit)", f"₹{total_spend:,.0f}", delta=f"-₹{total_spend:,.0f}")
    c3.metric("Total Income (Credit)", f"₹{total_income:,.0f}", delta=f"+₹{total_income:,.0f}")
    c4.metric("Sent to Family/Friends", f"₹{total_to_family_friends:,.0f}")
    c5.metric("Invested (SIP)", f"₹{total_invested:,.0f}")
    c6.metric("Left Over", f"₹{leftover:,.0f}", delta=f"₹{leftover:,.0f}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Spend trend (last 6 months)")
        trend = (
            df.groupby("month")['net_spend']
            .sum()
            .reset_index()
            .tail(6)
        )
        fig = px.line(trend, x="month", y='net_spend', markers=True)
        fig.update_layout(yaxis_title="Spend (₹)", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"Category breakdown — {selected_month}")
        cat_breakdown = (
            month_df.groupby("category")['net_spend']
            .sum()
            .reset_index()
        )
        cat_breakdown = cat_breakdown[cat_breakdown['net_spend'] > 0]
        fig2 = px.pie(cat_breakdown, names="category", values='net_spend', hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)


# ---------- Tab 2: Category Deep Dive ----------

with tab2:
    categories = sorted(df["category"].unique())
    selected_cat = st.selectbox("Select category", categories)

    cat_df = df[df["category"] == selected_cat].sort_values("date", ascending=False)

    st.subheader(f"{selected_cat} — trend over time")
    cat_trend = cat_df.groupby("month")['net_spend'].sum().reset_index()
    fig3 = px.bar(cat_trend, x="month", y='net_spend')
    fig3.update_layout(yaxis_title="Spend (₹)", xaxis_title="")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader(f"All transactions — {selected_cat}")
    st.dataframe(
        cat_df[["date", "description", 'net_spend', "month"]],
        use_container_width=True,
        hide_index=True,
    )


# ---------- Tab 3: Family & Friends ----------

with tab3:
    ff_df = df[df["category"].isin(["Send Money - Family", "Send Money - Friends"])]
    if ff_df.empty:
        st.info(
            "No family/friend transfers found yet. Add the UPI IDs or names you "
            "send money to in `data/category_rules.json` under the 'people' list "
            "for Send Money - Family / Send Money - Friends."
        )
    else:
        c1, c2 = st.columns(2)
        c1.metric(
            "Total sent to Family (all time)",
            f"₹{ff_df[ff_df['category'] == 'Send Money - Family']['net_spend'].sum():,.0f}",
        )
        c2.metric(
            "Total sent to Friends (all time)",
            f"₹{ff_df[ff_df['category'] == 'Send Money - Friends']['net_spend'].sum():,.0f}",
        )

        st.subheader("Monthly trend")
        trend = ff_df.groupby(["month", "category"])['net_spend'].sum().reset_index()
        fig4 = px.bar(trend, x="month", y='net_spend', color="category", barmode="group")
        st.plotly_chart(fig4, use_container_width=True)

        st.subheader("All transfers")
        st.dataframe(
            ff_df[["date", "description", "category", 'net_spend']].sort_values(
                "date", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )


# ---------- Tab 4: Investments (SIP) ----------

with tab4:
    sip_df = load_sip_summary()

    if sip_df.empty:
        st.info(
            "No SIP data yet. Add your funds to `data/sip_holdings.json` "
            "with scheme codes from mfapi.in and your monthly units bought."
        )
    else:
        total_invested = sip_df["total_invested"].sum()
        total_current = sip_df["current_value"].sum(skipna=True)
        total_gain = total_current - total_invested if pd.notna(total_current) else None

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Invested", f"₹{total_invested:,.0f}")
        c2.metric(
            "Current Value",
            f"₹{total_current:,.0f}" if pd.notna(total_current) else "N/A",
        )
        c3.metric(
            "Gain / Loss",
            f"₹{total_gain:,.0f}" if total_gain is not None else "N/A",
            delta=f"{total_gain:,.0f}" if total_gain is not None else None,
        )

        st.divider()
        st.subheader("Fund-wise breakdown")
        display_df = sip_df.rename(
            columns={
                "fund_name": "Fund",
                "amc": "AMC",
                "category": "Category",
                "sub_category": "Sub-Category",
                "total_invested": "Invested (₹)",
                "current_value": "Current Value (₹)",
                "gain_loss": "Gain/Loss (₹)",
                "gain_loss_pct": "Gain/Loss (%)",
                "xirr": "XIRR",
            }
        )
        st.dataframe(
            display_df[
                ["Fund", "AMC", "Category", "Sub-Category", "Invested (₹)", 
                 "Current Value (₹)", "Gain/Loss (₹)", "Gain/Loss (%)", "XIRR"]
            ],
            use_container_width=True,
            hide_index=True,
        )

        # Convert to long-form for plotting (handles mixed types in current_value)
        plot_df = sip_df[["fund_name", "total_invested", "current_value"]].dropna(subset=["current_value"])
        plot_df_melted = plot_df.melt(
            id_vars="fund_name",
            value_vars=["total_invested", "current_value"],
            var_name="metric",
            value_name="amount"
        )
        plot_df_melted["metric"] = plot_df_melted["metric"].map({
            "total_invested": "Invested",
            "current_value": "Current Value"
        })
        
        fig5 = px.bar(
            plot_df_melted, x="fund_name", y="amount", color="metric", barmode="group"
        )
        fig5.update_layout(yaxis_title="₹", xaxis_title="", legend_title="")
        st.plotly_chart(fig5, use_container_width=True)


# ---------- Tab 5: Review Uncategorized ----------

with tab5:
    uncategorized = df[df["category"] == "Uncategorized"].sort_values("date", ascending=False)
    local_shops = df[df["category"] == "Local Shops / Unknown Person"].sort_values(
        "date", ascending=False
    )

    st.subheader("Genuinely unrecognized transactions")
    if uncategorized.empty:
        st.success("Nothing to review here — everything is categorized! 🎉")
    else:
        st.warning(
            f"{len(uncategorized)} transaction(s) couldn't be auto-categorized "
            f"(₹{uncategorized['spend'].sum():,.0f} total). Add keywords or names to "
            f"`data/category_rules.json` to fix these."
        )
        st.dataframe(
            uncategorized[["date", "description", "spend", "month"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Local Shops / Unknown Person")
    st.caption(
        "Payments to UPI IDs that look like an individual's name rather than a "
        "registered business - common for local vendors in India who use their "
        "own name as their UPI ID. Check the recurring names below: if you "
        "recognize one as a regular vendor, friend, or family member, add them "
        "to `data/category_rules.json` so they get tagged properly going forward."
    )

    if local_shops.empty:
        st.success("Nothing here right now.")
    else:
        def _extract_payee(desc):
            parts = str(desc).split("/")
            if len(parts) >= 4 and parts[0].strip().upper() == "UPI":
                return parts[3].strip()
            return desc[:30]

        local_shops = local_shops.copy()
        local_shops["payee"] = local_shops["description"].apply(_extract_payee)

        recurring = (
            local_shops.groupby("payee")["spend"]
            .agg(["count", "sum"])
            .rename(columns={"count": "Times Paid", "sum": "Total Spend (₹)"})
            .sort_values("Total Spend (₹)", ascending=False)
        )
        recurring = recurring[recurring["Times Paid"] >= 2]  # only show actually-recurring ones

        if not recurring.empty:
            st.markdown("**Recurring unknown payees (worth tagging if you recognize them):**")
            st.dataframe(recurring.head(20), use_container_width=True)

        st.markdown(f"**All {len(local_shops)} transactions** (₹{local_shops['spend'].sum():,.0f} total):")
        st.dataframe(
            local_shops[["date", "description", "spend", "month"]],
            use_container_width=True,
            hide_index=True,
        )
