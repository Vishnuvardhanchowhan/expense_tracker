"""
app.py
Mobile-first Streamlit dashboard for the expense tracker.
Run with: streamlit run app.py

All data/calculation logic below is unchanged from the original dashboard.
Only the rendering layer (layout, navigation, styling) has been redesigned
for small screens.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src.build_master import build_master, MASTER_PATH, RULES_PATH
from src.sip_tracker import get_sip_summary

BASE_DIR = Path(__file__).resolve().parent
SIP_HOLDINGS_PATH = BASE_DIR / "data" / "mutual_fund_holdings.csv"

st.set_page_config(
    page_title="Expense Tracker",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =====================================================================
# THEME
# Dark fintech palette. Mint = inflow/gain, coral = spend, indigo =
# invested/SIP, amber = transfers. Tabular figures so amounts align.
# =====================================================================

INK = "#0B0E14"
SURFACE = "#151922"
SURFACE_2 = "#1C212C"
BORDER = "#262C38"
TEXT = "#EDEFF4"
TEXT_DIM = "#8B92A4"
MINT = "#00E5A0"
CORAL = "#FF5C72"
INDIGO = "#6C7CFF"
AMBER = "#FFB02E"

PLOTLY_TEMPLATE = "plotly_dark"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
}}

.stApp {{
    background: {INK};
}}

/* Hide Streamlit chrome */
#MainMenu, header, footer {{ visibility: hidden; }}
.block-container {{
    padding-top: 0.75rem !important;
    padding-bottom: 6.5rem !important;
    max-width: 480px;
}}

/* Hide native tab list + Streamlit's default radio/selectbox chrome where used as nav */
div[data-testid="stTabs"] > div:first-child {{ display: none; }}
div[data-testid="stTabs"] {{ margin-top: -0.5rem; }}

/* ---------- Top app bar ---------- */
.app-bar {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 0.25rem 0.1rem 0.6rem 0.1rem;
}}
.app-bar h1 {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {TEXT};
    margin: 0;
    letter-spacing: -0.02em;
}}
.app-bar .month-chip {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    color: {INDIGO};
    background: rgba(108,124,255,0.12);
    border: 1px solid rgba(108,124,255,0.25);
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
}}

/* ---------- Balance strip (signature element) ---------- */
.balance-strip {{
    background: linear-gradient(135deg, {SURFACE} 0%, {SURFACE_2} 100%);
    border: 1px solid {BORDER};
    border-radius: 18px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.9rem;
    position: relative;
    overflow: hidden;
}}
.balance-strip::before {{
    content: "";
    position: absolute;
    top: -40%;
    right: -20%;
    width: 160px;
    height: 160px;
    background: radial-gradient(circle, rgba(0,229,160,0.10), transparent 70%);
    pointer-events: none;
}}
.bs-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.bs-label {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {TEXT_DIM};
    font-weight: 600;
}}
.bs-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    font-weight: 700;
    color: {TEXT};
}}
.bs-arrow {{
    color: {TEXT_DIM};
    font-size: 0.95rem;
    margin: 0 0.35rem;
}}
.bs-track {{
    height: 6px;
    border-radius: 999px;
    background: {BORDER};
    margin-top: 0.75rem;
    overflow: hidden;
    display: flex;
}}
.bs-fill {{
    height: 100%;
    background: linear-gradient(90deg, {INDIGO}, {MINT});
}}
.bs-delta {{
    text-align: right;
    font-size: 0.72rem;
    font-weight: 700;
    margin-top: 0.4rem;
    font-family: 'JetBrains Mono', monospace;
}}

/* ---------- Metric grid (2-up) ---------- */
.metric-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    margin-bottom: 1rem;
}}
.metric-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 0.8rem 0.85rem;
    min-height: 86px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
.metric-card .icon-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.metric-card .icon-badge {{
    width: 26px;
    height: 26px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
}}
.metric-card .label {{
    font-size: 0.66rem;
    color: {TEXT_DIM};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 0.5rem;
}}
.metric-card .value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.08rem;
    font-weight: 700;
    color: {TEXT};
    margin-top: 0.1rem;
}}
.badge-mint {{ background: rgba(0,229,160,0.14); color: {MINT}; }}
.badge-coral {{ background: rgba(255,92,114,0.14); color: {CORAL}; }}
.badge-indigo {{ background: rgba(108,124,255,0.14); color: {INDIGO}; }}
.badge-amber {{ background: rgba(255,176,46,0.14); color: {AMBER}; }}

/* ---------- Section headers ---------- */
.section-h {{
    font-size: 0.85rem;
    font-weight: 700;
    color: {TEXT};
    margin: 1.1rem 0 0.5rem 0.1rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}
.section-h .dot {{
    width: 6px; height: 6px; border-radius: 50%;
}}

/* ---------- Cards for misc content ---------- */
.info-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 0.9rem 1rem;
    color: {TEXT_DIM};
    font-size: 0.85rem;
    line-height: 1.5;
}}
.info-card.warn {{ border-color: rgba(255,176,46,0.35); }}
.info-card.success {{ border-color: rgba(0,229,160,0.35); color: {MINT}; }}

.pill-row {{ display: flex; gap: 0.5rem; margin-bottom: 0.7rem; }}
.pill {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
}}

/* Dataframes */
div[data-testid="stDataFrame"] {{
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid {BORDER};
}}

/* Selectbox restyle */
div[data-testid="stSelectbox"] > div > div {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    color: {TEXT};
}}

/* ---------- Bottom tab bar ---------- */
.bottom-nav-spacer {{ height: 0; }}
div[data-testid="stHorizontalBlock"]:has(div.navbtn-marker) {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(11,14,20,0.92);
    backdrop-filter: blur(14px);
    border-top: 1px solid {BORDER};
    padding: 0.5rem 0.4rem calc(0.5rem + env(safe-area-inset-bottom)) 0.4rem;
    z-index: 999;
    max-width: 480px;
    margin: 0 auto;
}}
div[data-testid="stHorizontalBlock"]:has(div.navbtn-marker) button {{
    background: transparent !important;
    border: none !important;
    color: {TEXT_DIM} !important;
    font-size: 0.62rem !important;
    font-weight: 600 !important;
    box-shadow: none !important;
    padding: 0.3rem 0 !important;
    line-height: 1.25 !important;
    width: 100%;
}}
div[data-testid="stHorizontalBlock"]:has(div.navbtn-marker) button:hover {{
    color: {TEXT} !important;
}}
div[data-testid="stHorizontalBlock"]:has(div.navbtn-marker) button p {{
    font-size: 0.62rem !important;
    font-weight: 600 !important;
    white-space: pre-line !important;
}}

/* Active tab indicator via a colored top border injected per-button using nth-child */
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str):
    """
    Render raw HTML safely via st.markdown.

    Streamlit's markdown step runs HTML through a markdown parser first.
    Multi-line HTML with leading indentation/blank lines can get
    misread as a code block or split block and printed as literal text
    instead of being rendered. Collapsing to one line side-steps that.
    """
    flat = " ".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(flat, unsafe_allow_html=True)


def style_fig(fig, height=240):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT, size=11),
        margin=dict(l=10, r=10, t=10, b=10),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig


def metric_card_html(icon, badge_class, label, value):
    return (
        '<div class="metric-card">'
        f'<div class="icon-row"><div class="icon-badge {badge_class}">{icon}</div></div>'
        f'<div><div class="label">{label}</div><div class="value">{value}</div></div>'
        '</div>'
    )


def section_header(label, color):
    return (
        f'<div class="section-h"><span class="dot" style="background:{color}"></span>'
        f"{label}</div>"
    )


# =====================================================================
# DATA LOADING — unchanged from original
# =====================================================================

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
    html('<div class="app-bar"><h1>💰 Expense Tracker</h1></div>')
    html(
        '<div class="info-card warn">No statement files found yet. Drop a CSV into '
        '<code>data/statements/</code> named like <code>2026-01.csv</code> and refresh '
        "this page.</div>"
    )
    st.stop()

months = sorted(df["month"].unique())

# =====================================================================
# NAVIGATION STATE — bottom tab bar drives which section renders
# =====================================================================

TABS = [
    ("overview", "📊", "Overview"),
    ("category", "🔍", "Categories"),
    ("family", "👨‍👩‍👧", "Family"),
    ("sip", "📈", "Invest"),
    ("review", "⚠️", "Review"),
]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "overview"

# =====================================================================
# TOP APP BAR
# =====================================================================

active_label = next(t[2] for t in TABS if t[0] == st.session_state.active_tab)
html(
    f'<div class="app-bar"><h1>💰 Expense Tracker</h1>'
    f'<div class="month-chip">{active_label.upper()}</div></div>'
)

# =====================================================================
# TAB 1: OVERVIEW
# =====================================================================

if st.session_state.active_tab == "overview":
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

    # ---- Balance strip (signature element) ----
    delta = leftover - opening_balance
    delta_color = MINT if delta >= 0 else CORAL
    delta_sign = "+" if delta >= 0 else ""
    max_ref = max(abs(opening_balance), abs(leftover), 1)
    fill_pct = max(6, min(100, (leftover / max_ref) * 100)) if max_ref else 50

    html(
        f"""
        <div class="balance-strip">
            <div class="bs-row">
                <div>
                    <div class="bs-label">Start of Month</div>
                    <div class="bs-value">₹{opening_balance:,.0f}</div>
                </div>
                <div class="bs-arrow">→</div>
                <div style="text-align:right">
                    <div class="bs-label">Left Over</div>
                    <div class="bs-value">₹{leftover:,.0f}</div>
                </div>
            </div>
            <div class="bs-track"><div class="bs-fill" style="width:{fill_pct:.0f}%"></div></div>
            <div class="bs-delta" style="color:{delta_color}">{delta_sign}₹{delta:,.0f} this month</div>
        </div>
        """
    )

    # ---- Metric grid, 2 per row ----
    html(
        '<div class="metric-grid">'
        + metric_card_html("↓", "badge-coral", "Total Spend", f"₹{total_spend:,.0f}")
        + metric_card_html("↑", "badge-mint", "Total Income", f"₹{total_income:,.0f}")
        + metric_card_html("🤝", "badge-amber", "Family/Friends", f"₹{total_to_family_friends:,.0f}")
        + metric_card_html("📈", "badge-indigo", "Invested (SIP)", f"₹{total_invested:,.0f}")
        + "</div>"
    )

    html(section_header("Spend trend — last 6 months", INDIGO))
    trend = (
        df.groupby("month")['net_spend']
        .sum()
        .reset_index()
        .tail(6)
    )
    fig = px.line(trend, x="month", y='net_spend', markers=True,
                  color_discrete_sequence=[INDIGO])
    fig.update_traces(line_width=3, marker_size=8)
    fig.update_layout(yaxis_title="", xaxis_title="")
    st.plotly_chart(style_fig(fig), use_container_width=True, config={"displayModeBar": False})

    html(section_header(f"Category breakdown — {selected_month}", MINT))
    cat_breakdown = (
        month_df.groupby("category")['net_spend']
        .sum()
        .reset_index()
    )
    cat_breakdown = cat_breakdown[cat_breakdown['net_spend'] > 0]
    fig2 = px.pie(
        cat_breakdown, names="category", values='net_spend', hole=0.62,
        color_discrete_sequence=[MINT, INDIGO, CORAL, AMBER, "#9B8CFF", "#3DD9D6", "#FF8A65"],
    )
    fig2.update_traces(textposition="outside", textfont_size=10)
    st.plotly_chart(style_fig(fig2, height=300), use_container_width=True, config={"displayModeBar": False})


# =====================================================================
# TAB 2: CATEGORY DEEP DIVE
# =====================================================================

elif st.session_state.active_tab == "category":
    categories = sorted(df["category"].unique())
    selected_cat = st.selectbox("Select category", categories)

    cat_df = df[df["category"] == selected_cat].sort_values("date", ascending=False)

    html(section_header(f"{selected_cat} — trend over time", INDIGO))
    cat_trend = cat_df.groupby("month")['net_spend'].sum().reset_index()
    fig3 = px.bar(cat_trend, x="month", y='net_spend', color_discrete_sequence=[INDIGO])
    fig3.update_layout(yaxis_title="", xaxis_title="")
    fig3.update_traces(marker_cornerradius=6)
    st.plotly_chart(style_fig(fig3), use_container_width=True, config={"displayModeBar": False})

    html(section_header(f"All transactions — {selected_cat}", TEXT_DIM))
    st.dataframe(
        cat_df[["date", "description", 'net_spend', "month"]],
        use_container_width=True,
        hide_index=True,
    )


# =====================================================================
# TAB 3: FAMILY & FRIENDS
# =====================================================================

elif st.session_state.active_tab == "family":
    ff_df = df[df["category"].isin(["Send Money - Family", "Send Money - Friends"])]
    if ff_df.empty:
        html(
            '<div class="info-card">No family/friend transfers found yet. Add the UPI IDs '
            "or names you send money to in <code>data/category_rules.json</code> under the "
            "'people' list for Send Money - Family / Send Money - Friends.</div>"
        )
    else:
        fam_total = ff_df[ff_df['category'] == 'Send Money - Family']['net_spend'].sum()
        friend_total = ff_df[ff_df['category'] == 'Send Money - Friends']['net_spend'].sum()

        html(
            '<div class="metric-grid">'
            + metric_card_html("👪", "badge-amber", "Sent to Family", f"₹{fam_total:,.0f}")
            + metric_card_html("🧑‍🤝‍🧑", "badge-indigo", "Sent to Friends", f"₹{friend_total:,.0f}")
            + "</div>"
        )

        html(section_header("Monthly trend", AMBER))
        trend = ff_df.groupby(["month", "category"])['net_spend'].sum().reset_index()
        fig4 = px.bar(trend, x="month", y='net_spend', color="category", barmode="group",
                      color_discrete_sequence=[AMBER, INDIGO])
        fig4.update_layout(yaxis_title="", xaxis_title="", legend_title="")
        st.plotly_chart(style_fig(fig4), use_container_width=True, config={"displayModeBar": False})

        html(section_header("All transfers", TEXT_DIM))
        st.dataframe(
            ff_df[["date", "description", "category", 'net_spend']].sort_values(
                "date", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )


# =====================================================================
# TAB 4: INVESTMENTS (SIP)
# =====================================================================

elif st.session_state.active_tab == "sip":
    sip_df = load_sip_summary()

    if sip_df.empty:
        html(
            '<div class="info-card">No SIP data yet. Add your funds to '
            "<code>data/sip_holdings.json</code> with scheme codes from mfapi.in and your "
            "monthly units bought.</div>"
        )
    else:
        total_invested = sip_df["total_invested"].sum()
        total_current = sip_df["current_value"].sum(skipna=True)
        total_gain = total_current - total_invested if pd.notna(total_current) else None

        gain_color = MINT if (total_gain is not None and total_gain >= 0) else CORAL
        gain_str = f"₹{total_gain:,.0f}" if total_gain is not None else "N/A"
        gain_badge = "badge-mint" if (total_gain is not None and total_gain >= 0) else "badge-coral"

        html(
            '<div class="metric-grid">'
            + metric_card_html("💸", "badge-indigo", "Total Invested", f"₹{total_invested:,.0f}")
            + metric_card_html(
                "💰", "badge-mint",
                "Current Value",
                f"₹{total_current:,.0f}" if pd.notna(total_current) else "N/A",
              )
            + metric_card_html("📊", gain_badge, "Gain / Loss", gain_str)
            + "</div>"
        )

        html(section_header("Fund-wise breakdown", INDIGO))
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

        html(section_header("Invested vs current", MINT))
        fig5 = px.bar(
            plot_df_melted, x="fund_name", y="amount", color="metric", barmode="group",
            color_discrete_sequence=[INDIGO, MINT],
        )
        fig5.update_layout(yaxis_title="", xaxis_title="", legend_title="")
        fig5.update_xaxes(tickangle=-30)
        st.plotly_chart(style_fig(fig5, height=280), use_container_width=True, config={"displayModeBar": False})


# =====================================================================
# TAB 5: REVIEW UNCATEGORIZED
# =====================================================================

elif st.session_state.active_tab == "review":
    uncategorized = df[df["category"] == "Uncategorized"].sort_values("date", ascending=False)
    local_shops = df[df["category"] == "Local Shops / Unknown Person"].sort_values(
        "date", ascending=False
    )

    html(section_header("Genuinely unrecognized transactions", CORAL))
    if uncategorized.empty:
        html(
            '<div class="info-card success">Nothing to review here — everything is '
            "categorized! 🎉</div>"
        )
    else:
        html(
            f'<div class="info-card warn">{len(uncategorized)} transaction(s) couldn\'t be '
            f"auto-categorized (₹{uncategorized['spend'].sum():,.0f} total). Add keywords or "
            f"names to <code>data/category_rules.json</code> to fix these.</div>"
        )
        st.dataframe(
            uncategorized[["date", "description", "spend", "month"]],
            use_container_width=True,
            hide_index=True,
        )

    html(section_header("Local Shops / Unknown Person", AMBER))
    html(
        '<div class="info-card">Payments to UPI IDs that look like an individual\'s name '
        "rather than a registered business — common for local vendors in India who use "
        "their own name as their UPI ID. Check the recurring names below: if you recognize "
        "one as a regular vendor, friend, or family member, add them to "
        "<code>data/category_rules.json</code> so they get tagged properly going forward.</div>"
    )
    st.write("")

    if local_shops.empty:
        html('<div class="info-card success">Nothing here right now.</div>')
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
            html(section_header("Recurring unknown payees", INDIGO))
            st.dataframe(recurring.head(20), use_container_width=True)

        html(
            f'<div class="pill-row"><span class="pill">{len(local_shops)} txns</span>'
            f'<span class="pill">₹{local_shops["spend"].sum():,.0f} total</span></div>'
        )
        st.dataframe(
            local_shops[["date", "description", "spend", "month"]],
            use_container_width=True,
            hide_index=True,
        )


# =====================================================================
# BOTTOM TAB BAR
# =====================================================================

html('<div class="navbtn-marker" style="display:none"></div>')
nav_cols = st.columns(len(TABS))
for col, (key, icon, label) in zip(nav_cols, TABS):
    with col:
        is_active = st.session_state.active_tab == key
        prefix = "●\n" if is_active else "\n"
        if st.button(f"{icon}\n{label}", key=f"nav_{key}", use_container_width=True):
            st.session_state.active_tab = key
            st.rerun()