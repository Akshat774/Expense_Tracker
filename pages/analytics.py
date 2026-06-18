import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Analytics | FinAI", page_icon="📊", layout="wide")
st.title("📊 Spending Analytics")
st.markdown("Visualize your spending habits, trends, and monthly breakdowns.")

# KPI Row
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("Total Monthly Spend", "$5,294.15", "+$412.10 MoM")
with kpi2:
    st.metric("Top Category", "Software / SaaS", "45% of total")
with kpi3:
    st.metric("Average Daily Spend", "$88.23", "-3.1% vs last week")
with kpi4:
    st.metric("Flagged Anomalies", "1 Item", "Requires Review")

st.divider()

# Charts Grid Layout
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 🏢 Spending by Category")
    cat_data = pd.DataFrame(
        {"Amount ($)": [2400, 1200, 600, 800, 294]},
        index=["Software / SaaS", "Travel & Transit", "Office Utilities", "Meals", "Misc"]
    )
    st.bar_chart(cat_data, y="Amount ($)", color="#1f77b4")

    st.markdown("#### 📅 Monthly Trend")
    monthly_data = pd.DataFrame(
        {"Spend ($)": [4100, 4800, 3900, 5100, 4600, 5294]},
        index=["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    )
    st.line_chart(monthly_data)

with col_right:
    st.markdown("#### 📈 Weekly Trend")
    weekly_data = pd.DataFrame(
        {"Cumulative Spend ($)": np.random.randn(20).cumsum() + 500},
        columns=["Cumulative Spend ($)"]
    )
    st.area_chart(weekly_data)

    st.markdown("#### 🏆 Top Merchants")
    merchant_data = pd.DataFrame({
        "Merchant": ["AWS", "Acme Corp", "Uber", "GitHub", "Staples"],
        "Total Spent ($)": [1850.00, 1200.00, 640.50, 400.00, 312.40]
    }).set_index("Merchant")
    st.bar_chart(merchant_data, horizontal=True, color="#2ca02c")

st.divider()

# --- AI INSIGHTS ---
st.subheader("🧠 Gemini Financial Insights")
with st.container(border=True):
    st.markdown("""
    * **🚀 Software SaaS Alert:** Software subscriptions make up **45%** of your total budget. Look out for duplicate user licenses between *GitHub* and *Acme Corp*.
    * **⚠️ Travel Spike:** Travel expenses rose by **18%** in week 3 due to last-minute flights.
    * **💡 Savings Tip:** Switching a few background server infrastructure pieces to lower tiers could save roughly $300 next month.
    """)
    st.caption("Insights generated automatically by analyzing your transaction history with Gemini.")

st.divider()
if st.button("📥 Download Full Analytics Report", use_container_width=True):
    st.toast("Generating report...")