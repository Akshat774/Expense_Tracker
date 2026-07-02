"""
FinAI - AI Powered Expense Tracker
Main dashboard entry point.
"""

import os
import streamlit as st
from utils.database import initialize_database, get_database_stats
from utils.ui import apply_theme, render_sidebar

# 1. Page Configuration
st.set_page_config(
    page_title="FinAI | Smart Expense Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Load shared UI theme
apply_theme()

# 3. Initialize DB on startup
initialize_database()

# 4. Sidebar
render_sidebar(active_page="app.py")

# 5. Main Dashboard
st.markdown(
    """
    <div class="page-shell">
    <div class="hero-card">
        <div class="hero-kicker">AI expense intelligence</div>
        <h1 class="hero-title">FinAI turns receipts into a clean financial command center.</h1>
        <p class="hero-copy">
            Upload receipts, monitor spend, and review insights in a dark, focused workspace designed
            for faster decisions and less visual noise.
        </p>
    </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 6. Live KPI Metrics
stats = get_database_stats()
count = stats["count"]
total = stats["total"]
date_range = (
    f"{stats['earliest']} – {stats['latest']}"
    if stats["earliest"] and stats["latest"]
    else "No data yet"
)
avg = (total / count) if count > 0 else 0.0

st.markdown('<div class="section-label">Live overview</div>', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Spent (All Time)", value=f"${total:,.2f}")
with col2:
    st.metric(label="Receipts Processed", value=str(count))
with col3:
    st.metric(label="Average Transaction", value=f"${avg:,.2f}")
with col4:
    st.markdown(
        f'''
        <div class="kpi-card">
            <div class="kpi-label">Date Range</div>
            <div class="kpi-value kpi-value-compact">{date_range if count > 0 else "—"}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-label">Quick actions</div>', unsafe_allow_html=True)
action_col1, action_col2, action_col3 = st.columns(3)

with action_col1:
    with st.container(border=True):
        st.markdown("#### 📤 Upload Receipt")
        st.write("Scan a new invoice, bill, or receipt using Gemini AI.")
        st.page_link("pages/upload.py", label="Go to Upload", icon="📤")

with action_col2:
    with st.container(border=True):
        st.markdown("#### 📊 View Analytics")
        st.write("See spending breakdowns, trends, and AI-generated insights.")
        st.page_link("pages/analytics.py", label="Go to Analytics", icon="📊")

with action_col3:
    with st.container(border=True):
        st.markdown("#### 📜 Expense History")
        st.write("View past transactions, edit records, or export data.")
        st.page_link("pages/expense_history.py", label="Go to History", icon="📜")
