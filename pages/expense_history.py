import streamlit as st
import pandas as pd

st.set_page_config(page_title="History | FinAI", page_icon="📜", layout="wide")
st.title("📜 Expense History")
st.markdown("Filter, edit, and export your past expenses.")

# KPI Cards
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("Total Transactions", "148")
with kpi2:
    st.metric("Average Transaction", "$85.40")
with kpi3:
    st.metric("Date Range", "Jan 2026 - Jun 2026")

st.divider()

# Filters and Sorting
with st.expander("🔍 Search and Filter Options", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("Search Merchant or Description", placeholder="e.g. AWS, Uber...")
        merchant_filter = st.multiselect("Filter by Merchant", ["AWS", "Uber", "GitHub", "Staples"])
    with col2:
        category_filter = st.multiselect("Filter by Category", ["Software / SaaS", "Travel", "Office Utilities"])
        month_filter = st.selectbox("Filter by Month", ["All Months", "June 2026", "May 2026", "April 2026"])
    with col3:
        sort_by = st.selectbox("Sort By", ["Date", "Amount", "Merchant", "Confidence"])
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

# Mock Data Table
mock_db = pd.DataFrame([
    {"ID": 101, "Date": "2026-06-14", "Merchant": "AWS Cloud Services", "Category": "Software / SaaS", "Amount": 450.23, "Confidence": "98%"},
    {"ID": 102, "Date": "2026-06-12", "Merchant": "Uber Transport", "Category": "Travel & Transit", "Amount": 24.50, "Confidence": "91%"},
    {"ID": 103, "Date": "2026-06-10", "Merchant": "GitHub Premium", "Category": "Software / SaaS", "Amount": 100.00, "Confidence": "100%"},
    {"ID": 104, "Date": "2026-06-05", "Merchant": "Whole Foods", "Category": "Meals & Entertainment", "Amount": 87.12, "Confidence": "89%"},
    {"ID": 105, "Date": "2026-05-28", "Merchant": "Staples Supplies", "Category": "Office Utilities", "Amount": 112.40, "Confidence": "95%"},
])

st.markdown("### 📊 Transactions Ledger")
# Editable history table
edited_table = st.data_editor(mock_db, use_container_width=True, hide_index=True)

# Placeholders for Edit / Delete
act_col1, act_col2, act_col3 = st.columns([2, 1, 1])
with act_col1:
    st.caption("💡 Tip: You can double-click cells in the table above to edit them directly.")
with act_col2:
    st.button("✏️ Edit Selected Row", use_container_width=True, disabled=True)
with act_col3:
    st.button("🗑️ Delete Selected Row", use_container_width=True, disabled=True)

st.divider()

# Export Buttons
st.subheader("📥 Export Data")
exp_col1, exp_col2 = st.columns(2)
with exp_col1:
    st.download_button(
        label="Download as CSV",
        data=mock_db.to_csv(index=False),
        file_name="finai_expenses.csv",
        mime="text/csv",
        use_container_width=True
    )
with exp_col2:
    st.button("Export as PDF Report", use_container_width=True)