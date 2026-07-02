"""
FinAI Expense History — Browse, search, filter, edit, delete, and export expenses.
Includes per-row JSON viewer for line items and tax breakdown.
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
st.markdown("Filter, edit, export and inspect your past expenses.")

# ── KPI Cards ────────────────────────────────────────────────────────────────
stats = get_database_stats()
count      = stats["count"]
total      = stats["total"]
avg        = (total / count) if count > 0 else 0.0
date_range = (
    f"{stats['earliest']} – {stats['latest']}"
    if stats["earliest"] and stats["latest"] else "—"
)

k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Total Transactions", str(count))
with k2:
    st.metric("Average Transaction", f"₹{avg:,.2f}")
with k3:
    st.metric("Date Range", date_range)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
all_expenses = get_all_expenses()

all_merchants = sorted({e["merchant_name"] for e in all_expenses if e.get("merchant_name")})
all_months_raw = sorted({
    e["transaction_date"][:7]
    for e in all_expenses
    if e.get("transaction_date") and len(e["transaction_date"]) >= 7
}, reverse=True)
month_options = ["All Months"] + all_months_raw

with st.expander("🔍 Search & Filter", expanded=True):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        search          = st.text_input("Search Merchant / Category / Address", placeholder="e.g. Swiggy, Food...")
        merchant_filter = st.multiselect("Filter by Merchant", options=all_merchants)
    with fc2:
        category_filter = st.multiselect("Filter by Category", options=ALLOWED_CATEGORIES)
        month_filter    = st.selectbox("Filter by Month", options=month_options)
    with fc3:
        sort_by    = st.selectbox("Sort By", ["Date", "Amount", "Merchant", "Confidence"])
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

# ── Apply filters ─────────────────────────────────────────────────────────────
month_param = None if month_filter == "All Months" else month_filter

filtered = filter_expenses(
    categories=category_filter if category_filter else None,
    month=month_param,
)

if search.strip():
    q = search.strip().lower()
    filtered = [
        e for e in filtered
        if q in (e.get("merchant_name")    or "").lower()
        or q in (e.get("category")         or "").lower()
        or q in (e.get("merchant_address") or "").lower()
    ]

if merchant_filter:
    filtered = [e for e in filtered if e.get("merchant_name") in merchant_filter]

sort_key_map = {"Date": "transaction_date", "Amount": "total_amount",
                "Merchant": "merchant_name", "Confidence": "confidence_score"}
sort_key = sort_key_map[sort_by]
filtered.sort(key=lambda e: (e.get(sort_key) or ""), reverse=(sort_order == "Descending"))

# ── Main ledger table ─────────────────────────────────────────────────────────
st.markdown("### 📊 Transactions Ledger")

if not filtered:
    st.info("No expenses match your current filters.")
else:
    display_df = pd.DataFrame([
        {
            "ID":           e["id"],
            "Date":         e.get("transaction_date") or "",
            "Time":         e.get("transaction_time") or "",
            "Merchant":     e.get("merchant_name")    or "",
            "Category":     e.get("category")         or "",
            "Currency":     e.get("currency")         or "",
            "Payment":      e.get("payment_method")   or "",
            "Subtotal":     e.get("subtotal")         or 0.0,
            "Discount":     e.get("discount_amount")  or 0.0,
            "Tax":          e.get("tax_amount")       or 0.0,
            "Total":        e.get("total_amount")     or 0.0,
            "Confidence":   f"{(e.get('confidence_score') or 0) * 100:.0f}%",
            "Invoice No.":  e.get("invoice_number")   or "",
            "Address":      e.get("merchant_address") or "",
        }
        for e in filtered
    ])

    st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID":       st.column_config.NumberColumn("ID",       disabled=True, width="small"),
            "Date":     st.column_config.TextColumn("Date",       disabled=True),
            "Time":     st.column_config.TextColumn("Time",       disabled=True, width="small"),
            "Subtotal": st.column_config.NumberColumn("Subtotal", disabled=True, format="₹%.2f"),
            "Discount": st.column_config.NumberColumn("Discount", disabled=True, format="₹%.2f"),
            "Tax":      st.column_config.NumberColumn("Tax",      disabled=True, format="₹%.2f"),
            "Total":    st.column_config.NumberColumn("Total",    disabled=True, format="₹%.2f"),
        }
    )

    st.caption(f"Showing {len(filtered)} of {count} total expenses.")

st.divider()

# ── Per-row JSON viewer ───────────────────────────────────────────────────────
st.markdown("### 🔍 Inspect Expense JSON")
st.caption("Enter an expense ID to view the full raw record including line items and tax breakdown.")

if filtered:
    valid_ids = [e["id"] for e in filtered]
    inspect_id = st.selectbox(
        "Select Expense ID to inspect",
        options=valid_ids,
        format_func=lambda eid: next(
            (f"#{eid} — {e.get('merchant_name','?')} · {e.get('transaction_date','?')} · ₹{e.get('total_amount') or 0:.2f}"
             for e in filtered if e["id"] == eid), str(eid)
        ),
        key="inspect_select"
    )

    row = next((e for e in filtered if e["id"] == inspect_id), None)
    if row:
        # Parse stored JSON strings back to objects for display
        display_row = dict(row)
        for json_field in ("line_items", "tax_breakdown"):
            raw = display_row.get(json_field)
            if raw:
                try:
                    display_row[json_field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        tab_summary, tab_items, tab_tax, tab_full = st.tabs([
            "📋 Summary", "🛒 Line Items", "🧾 Tax Breakdown", "📄 Full JSON"
        ])

        with tab_summary:
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"**Merchant:** {display_row.get('merchant_name') or '—'}")
                st.markdown(f"**Address:** {display_row.get('merchant_address') or '—'}")
                st.markdown(f"**Invoice No.:** {display_row.get('invoice_number') or '—'}")
                st.markdown(f"**Date:** {display_row.get('transaction_date') or '—'}  {display_row.get('transaction_time') or ''}")
                st.markdown(f"**Category:** {display_row.get('category') or '—'}")
            with sc2:
                st.markdown(f"**Currency:** {display_row.get('currency') or '—'}")
                st.markdown(f"**Payment:** {display_row.get('payment_method') or '—'}")
                st.markdown(f"**Subtotal:** ₹{display_row.get('subtotal') or 0:.2f}")
                st.markdown(f"**Discount:** ₹{display_row.get('discount_amount') or 0:.2f}")
                st.markdown(f"**Tax:** ₹{display_row.get('tax_amount') or 0:.2f}")
                st.markdown(f"**Total:** ₹{display_row.get('total_amount') or 0:.2f}")
                st.markdown(f"**Confidence:** {(display_row.get('confidence_score') or 0)*100:.0f}%")

        with tab_items:
            items = display_row.get("line_items") or []
            if items and isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
                items_df = pd.DataFrame(items)
                items_df.columns = [c.replace("_", " ").title() for c in items_df.columns]
                st.dataframe(items_df, use_container_width=True, hide_index=True)
            else:
                st.info("No line items recorded for this expense.")

        with tab_tax:
            tax_data = display_row.get("tax_breakdown") or []
            if tax_data and isinstance(tax_data, list) and len(tax_data) > 0:
                tax_df = pd.DataFrame(tax_data)
                tax_df.columns = [c.replace("_", " ").title() for c in tax_df.columns]
                st.dataframe(tax_df, use_container_width=True, hide_index=True)
            else:
                st.info("No tax breakdown recorded for this expense.")

        with tab_full:
            st.json(display_row)

st.divider()

# ── Edit & Delete ─────────────────────────────────────────────────────────────
st.markdown("### ✏️ Edit / Delete Expense")

if not filtered:
    st.info("No expenses to edit.")
else:
    edit_col, del_col = st.columns(2)

    with edit_col:
        with st.expander("✏️ Edit Expense"):
            edit_id = st.number_input(
                "Expense ID to edit", min_value=1, step=1, key="edit_id"
            )
            row = next((e for e in filtered if e["id"] == edit_id), None)
            if row:
                new_merchant = st.text_input("Merchant",         value=row.get("merchant_name")    or "", key="e_merchant")
                new_date     = st.text_input("Date (YYYY-MM-DD)",value=row.get("transaction_date") or "", key="e_date")
                new_time     = st.text_input("Time",             value=row.get("transaction_time") or "", key="e_time")
                new_cat      = st.selectbox(
                    "Category", ALLOWED_CATEGORIES,
                    index=ALLOWED_CATEGORIES.index(row["category"])
                    if row.get("category") in ALLOWED_CATEGORIES else 0,
                    key="e_cat"
                )
                new_currency = st.text_input("Currency",         value=row.get("currency")         or "", key="e_currency")
                new_payment  = st.text_input("Payment Method",   value=row.get("payment_method")   or "", key="e_payment")
                new_total    = st.number_input("Total Amount",   value=float(row.get("total_amount") or 0), step=0.01, key="e_total")
                new_tax      = st.number_input("Tax",            value=float(row.get("tax_amount")  or 0), step=0.01, key="e_tax")
                new_discount = st.number_input("Discount",       value=float(row.get("discount_amount") or 0), step=0.01, key="e_disc")
                new_conf     = st.slider("Confidence",           0.0, 1.0, float(row.get("confidence_score") or 0), key="e_conf")

                if st.button("💾 Save Changes", type="primary", key="save_edit"):
                    update_expense(edit_id, {
                        "merchant_name":    new_merchant,
                        "transaction_date": new_date,
                        "transaction_time": new_time,
                        "category":         new_cat,
                        "currency":         new_currency,
                        "payment_method":   new_payment,
                        "total_amount":     new_total,
                        "tax_amount":       new_tax,
                        "discount_amount":  new_discount,
                        "confidence_score": new_conf,
                    })
                    st.success(f"✅ Expense #{edit_id} updated!")
                    st.rerun()
            else:
                st.caption("Enter a valid expense ID above.")

    with del_col:
        with st.expander("🗑️ Delete Expense"):
            del_id = st.number_input(
                "Expense ID to delete", min_value=1, step=1, key="del_id"
            )
            row = next((e for e in filtered if e["id"] == del_id), None)
            if row:
                st.warning(
                    f"**#{del_id} — {row.get('merchant_name') or '?'}**  \n"
                    f"{row.get('transaction_date') or '?'} · "
                    f"₹{row.get('total_amount') or 0:.2f}"
                )
                if st.button("🗑️ Confirm Delete", type="primary", key="confirm_del"):
                    delete_expense(del_id)
                    st.success(f"Expense #{del_id} deleted.")
                    st.rerun()
            else:
                st.caption("Enter a valid expense ID above.")

st.divider()

# ── Export ────────────────────────────────────────────────────────────────────
st.subheader("📥 Export Data")
exp1, exp2 = st.columns(2)

with exp1:
    csv_all = export_csv()
    st.download_button(
        label="📄 Download All Expenses (CSV)",
        data=csv_all or "",
        file_name="finai_all_expenses.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not bool(csv_all),
    )

with exp2:
    if filtered:
        # Build a clean filtered CSV (parse JSON fields for readability)
        rows_clean = []
        for e in filtered:
            row_copy = dict(e)
            for jf in ("line_items", "tax_breakdown"):
                try:
                    row_copy[jf] = json.dumps(json.loads(row_copy.get(jf) or "[]"))
                except Exception:
                    pass
            rows_clean.append(row_copy)
        filtered_csv = pd.DataFrame(rows_clean).to_csv(index=False)
        st.download_button(
            label="📄 Download Filtered View (CSV)",
            data=filtered_csv,
            file_name="finai_filtered_expenses.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Download Filtered View (CSV)", use_container_width=True, disabled=True)