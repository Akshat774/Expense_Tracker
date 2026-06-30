"""
FinAI - AI Powered Expense Tracker
Main dashboard entry point.
"""

import os
import streamlit as st
from utils.database import initialize_database, get_database_stats

# 1. Page Configuration
st.set_page_config(
    page_title="FinAI | Smart Expense Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Load Custom CSS
def load_css(file_path: str) -> None:
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
                .main .block-container { padding-top: 2rem; }
            </style>
        """, unsafe_allow_html=True)

load_css("assets/styles.css")

# 3. Initialize DB on startup
initialize_database()

# 4. Sidebar
st.sidebar.markdown("# 💼 FinAI Tracker")
st.sidebar.markdown("AI expense tracking powered by **Gemini**.")
st.sidebar.divider()

# 5. Main Dashboard
st.title("🚀 Welcome to FinAI")
st.markdown("Extract, track, and analyze your expenses instantly using AI.")
st.divider()

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

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Spent (All Time)", value=f"${total:,.2f}")
with col2:
    st.metric(label="Receipts Processed", value=str(count))
with col3:
    st.metric(label="Average Transaction", value=f"${avg:,.2f}")
with col4:
    st.metric(label="Date Range", value=date_range if count > 0 else "—")

st.markdown("### ⚡ Quick Actions")
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
