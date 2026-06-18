import streamlit as st
import os

# 1. Page Configuration
st.set_page_config(
    page_title="FinAI | Smart Expense Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Load Custom CSS
def load_css(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Fallback styles if the CSS file doesn't exist yet
        st.markdown("""
            <style>
                .main .block-container { padding-top: 2rem; }
                .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; }
            </style>
        """, unsafe_allow_html=True)

load_css("assets/styles.css")

# 3. Sidebar
st.sidebar.markdown("# 💼 FinAI Tracker")
st.sidebar.markdown("AI expense tracking powered by **Gemini**.")
st.sidebar.divider()

# 4. Main Dashboard
st.title("🚀 Welcome to FinAI")
st.markdown("Extract, track, and analyze your expenses instantly using AI.")
st.divider()

# KPI Metrics Row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Spent This Month", value="$2,450.80", delta="+12%")
with col2:
    st.metric(label="Receipts Processed", value="42", delta="100% Accuracy")
with col3:
    st.metric(label="Pending Review", value="3", delta="-2", delta_color="inverse")
with col4:
    st.metric(label="Budget Used", value="68%", delta="Good Standing")

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