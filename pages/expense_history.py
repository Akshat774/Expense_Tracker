"""
FinAI Expense History — Search, filter, edit, and export real expenses from SQLite.
"""

import streamlit as st
import pandas as pd
import json
import logging

from utils.database import (
    initialize_database, get_all_expenses, filter_expenses,
    update_expense, delete_expense, export_csv, get_database_stats
)
from utils.prompts import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)

st.set_page_config(page_title="History | FinAI", page_icon="📜", layout="wide")
initialize_database()

st.title("📜 Expense History")
st.markdown("Filter, edit, and export your past expenses.")

# ── KPI Cards ────────────────────────────────────────────────────────────────
stats = get_database_stats()
count = stats["count"]
total = stats["total"]
avg = (total / count) if count > 0 else 0.0
date_range = (
    f"{stats['earliest']} – {stats['latest']}"
    if stats["earliest"] and stats["latest"] else "—"
)

kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("Total Transactions", str(count))
with kpi2:
    st.metric("Average Transaction", f"${avg:,.2f}")
with kpi3:
    st.metric("Date Range", date_range)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
all_expenses = get_all_expenses()

# Build dynamic filter options from actual data
all_merchants = sorted(set(e["merchant_name"] for e in all_expenses if e["merchant_name"]))
all_months_raw = sorted(set(
    e["transaction_date"][:7]
    for e in all_expenses
    if e.get("transaction_date") and len(e["transaction_date"]) >= 7
), reverse=True)
all_months = ["All Months"] + all_months_raw

with st.expander("🔍 Search and Filter Options", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("Search Merchant or Category", placeholder="e.g. AWS, Travel...")
        merchant_filter = st.multiselect("Filter by Merchant", options=all_merchants)
    with col2:
        category_filter = st.multiselect("Filter by Category", options=ALLOWED_CATEGORIES)
        month_filter = st.selectbox("Filter by Month", options=all_months)
    with col3:
        sort_by = st.selectbox("Sort By", ["Date", "Amount", "Merchant", "Confidence"])
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

# ── Apply filters ─────────────────────────────────────────────────────────────
month_param = None if month_filter == "All Months" else month_filter

if category_filter or month_param:
    filtered = filter_expenses(
        categories=category_filter if category_filter else None,
        month=month_param,
    )
else:
    filtered = all_expenses

# Search
if search.strip():
    q = search.strip().lower()
    filtered = [
        e for e in filtered
        if q in (e.get("merchant_name") or "").lower()
        or q in (e.get("category") or "").lower()
    ]

# Merchant filter
if merchant_filter:
    filtered = [e for e in filtered if e.get("merchant_name") in merchant_filter]

# Sort
sort_key_map = {
    "Date": "transaction_date",
    "Amount": "total_amount",
    "Merchant": "merchant_name",
    "Confidence": "confidence_score",
}
sort_key = sort_key_map[sort_by]
reverse = sort_order == "Descending"
filtered.sort(key=lambda e: (e.get(sort_key) or ""), reverse=reverse)

# ── Display table ─────────────────────────────────────────────────────────────
st.markdown("### 📊 Transactions Ledger")

if not filtered:
    st.info("No expenses match your current filters.")
else:
    display_df = pd.DataFrame([
        {
            "ID": e["id"],
            "Date": e.get("transaction_date") or "",
            "Merchant": e.get("merchant_name") or "",
            "Category": e.get("category") or "",
            "Amount": e.get("total_amount") or 0.0,
            "Confidence": f"{(e.get('confidence_score') or 0) * 100:.0f}%",
        }
        for e in filtered
    ])

    edited_table = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Amount": st.column_config.NumberColumn("Amount ($)", format="$%.2f"),
        }
    )

    # ── Edit / Delete by ID ───────────────────────────────────────────────────
    act_col1, act_col2, act_col3 = st.columns([2, 1, 1])
    with act_col1:
        st.caption("💡 Enter an expense ID below to edit or delete it.")
    with act_col2:
        edit_id = st.number_input("Edit Expense ID", min_value=1, step=1, key="edit_id_input", label_visibility="collapsed")
    with act_col3:
        delete_id = st.number_input("Delete Expense ID", min_value=1, step=1, key="del_id_input", label_visibility="collapsed")

    edit_col, del_col = st.columns(2)

    with edit_col:
        with st.expander("✏️ Edit Expense"):
            row = next((e for e in filtered if e["id"] == edit_id), None)
            if row:
                new_merchant = st.text_input("Merchant", value=row.get("merchant_name") or "", key="edit_merchant")
                new_date = st.text_input("Date (YYYY-MM-DD)", value=row.get("transaction_date") or "", key="edit_date")
                new_category = st.selectbox(
                    "Category", ALLOWED_CATEGORIES,
                    index=ALLOWED_CATEGORIES.index(row["category"]) if row.get("category") in ALLOWED_CATEGORIES else 0,
                    key="edit_cat"
                )
                new_total = st.number_input("Total Amount", value=float(row.get("total_amount") or 0), step=0.01, key="edit_total")
                if st.button("💾 Save Changes", type="primary"):
                    update_expense(edit_id, {
                        "merchant_name": new_merchant,
                        "transaction_date": new_date,
                        "category": new_category,
                        "total_amount": new_total,
                    })
                    st.success("Updated!")
                    st.rerun()
            else:
                st.caption("Enter a valid expense ID above.")

    with del_col:
        with st.expander("🗑️ Delete Expense"):
            row = next((e for e in filtered if e["id"] == delete_id), None)
            if row:
                st.warning(f"Delete **{row.get('merchant_name')}** on {row.get('transaction_date')}?")
                if st.button("🗑️ Confirm Delete", type="primary"):
                    delete_expense(delete_id)
                    st.success("Deleted!")
                    st.rerun()
            else:
                st.caption("Enter a valid expense ID above.")

st.divider()

# ── Export ────────────────────────────────────────────────────────────────────
st.subheader("📥 Export Data")
exp_col1, exp_col2 = st.columns(2)

csv_data = export_csv()
with exp_col1:
    st.download_button(
        label="📄 Download as CSV",
        data=csv_data or "",
        file_name="finai_expenses.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not bool(csv_data),
    )
with exp_col2:
    if filtered:
        filtered_csv = pd.DataFrame(filtered).to_csv(index=False)
        st.download_button(
            label="📄 Download Filtered as CSV",
            data=filtered_csv,
            file_name="finai_filtered_expenses.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Download Filtered as CSV", use_container_width=True, disabled=True)
