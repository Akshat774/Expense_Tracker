"""
FinAI Analytics — Real spending analytics powered by Pandas, Plotly, and Gemini 2.5 Flash.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import logging
import json

from utils.database import initialize_database, get_all_expenses, get_database_stats

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Analytics | FinAI", page_icon="📊", layout="wide")
initialize_database()

st.title("📊 Spending Analytics")
st.markdown("Visualize your spending habits, trends, and monthly breakdowns.")

# ── Load data ─────────────────────────────────────────────────────────────────
expenses = get_all_expenses()

if not expenses:
    st.info("📭 No expense data yet. Upload some receipts to see analytics!")
    st.stop()

df = pd.DataFrame(expenses)
df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)
df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
df = df.dropna(subset=["transaction_date"])
df["month"] = df["transaction_date"].dt.to_period("M").astype(str)
df["week"] = df["transaction_date"].dt.to_period("W").astype(str)
df["day"] = df["transaction_date"].dt.date

# ── KPI Row ───────────────────────────────────────────────────────────────────
stats = get_database_stats()
total = stats["total"] or 0.0
count = stats["count"] or 0
avg_daily = (
    df.groupby("day")["total_amount"].sum().mean()
    if not df.empty else 0.0
)
top_cat = (
    df.groupby("category")["total_amount"].sum().idxmax()
    if not df.empty else "—"
)
top_cat_pct = (
    df.groupby("category")["total_amount"].sum().max() / total * 100
    if total > 0 else 0
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    with st.container(border=True):
        st.metric("Total Spent (All Time)", f"₹{total:,.2f}")
with kpi2:
    with st.container(border=True):
        st.metric("Top Category", top_cat, f"{top_cat_pct:.0f}% of total")
with kpi3:
    with st.container(border=True):
        st.metric("Average Daily Spend", f"₹{avg_daily:,.2f}")
with kpi4:
    with st.container(border=True):
        st.metric("Total Receipts", str(count))

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 🏢 Spending by Category")
    cat_df = df.groupby("category")["total_amount"].sum().reset_index()
    cat_df.columns = ["Category", "Amount"]
    cat_df = cat_df.sort_values("Amount", ascending=False)
    fig_cat = px.bar(
        cat_df, x="Category", y="Amount",
        color="Amount", color_continuous_scale="Blues",
        labels={"Amount": "Amount (₹)"},
    )
    fig_cat.update_layout(showlegend=False, coloraxis_showscale=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#94a3b8")
    st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("#### 📅 Monthly Trend")
    monthly_df = df.groupby("month")["total_amount"].sum().reset_index()
    monthly_df.columns = ["Month", "Spend"]
    monthly_df = monthly_df.sort_values("Month")
    fig_monthly = px.line(
        monthly_df, x="Month", y="Spend",
        markers=True, labels={"Spend": "Spend (₹)"}
    )
    fig_monthly.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#94a3b8")
    fig_monthly.update_traces(line_color="#6366f1", marker_color="#818cf8")
    st.plotly_chart(fig_monthly, use_container_width=True)

with col_right:
    st.markdown("#### 📈 Weekly Cumulative Spend")
    weekly_df = df.groupby("week")["total_amount"].sum().reset_index()
    weekly_df.columns = ["Week", "Spend"]
    weekly_df = weekly_df.sort_values("Week")
    weekly_df["Cumulative"] = weekly_df["Spend"].cumsum()
    fig_weekly = px.area(
        weekly_df, x="Week", y="Cumulative",
        labels={"Cumulative": "Cumulative Spend (₹)"}
    )
    fig_weekly.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#94a3b8")
    fig_weekly.update_traces(line_color="#10b981", fillcolor="rgba(16,185,129,0.15)")
    st.plotly_chart(fig_weekly, use_container_width=True)

    st.markdown("#### 🏆 Top Merchants")
    merchant_df = (
        df.groupby("merchant_name")["total_amount"].sum()
        .reset_index()
        .sort_values("total_amount", ascending=True)
        .tail(10)
    )
    merchant_df.columns = ["Merchant", "Total"]
    fig_merch = px.bar(
        merchant_df, x="Total", y="Merchant",
        orientation="h", labels={"Total": "Total (₹)"},
        color="Total", color_continuous_scale="Greens",
    )
    fig_merch.update_layout(showlegend=False, coloraxis_showscale=False,
                             paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             font_color="#94a3b8")
    st.plotly_chart(fig_merch, use_container_width=True)

st.divider()

# ── Gemini AI Insights ────────────────────────────────────────────────────────
st.subheader("🧠 Gemini Financial Insights")

if st.button("✨ Generate AI Insights", type="primary"):
    with st.spinner("Analyzing your spending with Gemini 2.5 Flash..."):
        try:
            from utils.gemini_client import generate_insights

            summary_rows = df[["transaction_date", "merchant_name", "category", "total_amount"]].copy()
            summary_rows["transaction_date"] = summary_rows["transaction_date"].astype(str)
            summary_json = summary_rows.tail(50).to_dict(orient="records")

            reply = generate_insights(summary_json)

            with st.container(border=True):
                st.markdown(reply)
                st.caption("Insights generated by Gemini 2.5 Flash based on your transaction history.")

        except EnvironmentError as e:
            st.error(
                "🔑 **GOOGLE_API_KEY not found.**\n\n"
                "Add it to your `.env` file:\n```\nGOOGLE_API_KEY=your_key_here\n```"
            )
        except Exception as e:
            st.error(f"Could not generate insights: {e}")
else:
    with st.container(border=True):
        st.caption("Click the button above to generate AI-powered insights from your transaction history.")

st.divider()

# ── Download Report ───────────────────────────────────────────────────────────
report_df = df[["transaction_date", "merchant_name", "category", "total_amount", "confidence_score"]].copy()
report_df.columns = ["Date", "Merchant", "Category", "Amount", "Confidence"]
csv_report = report_df.to_csv(index=False)

st.download_button(
    label="📥 Download Full Analytics Report (CSV)",
    data=csv_report,
    file_name="finai_analytics_report.csv",
    mime="text/csv",
    use_container_width=True,
)