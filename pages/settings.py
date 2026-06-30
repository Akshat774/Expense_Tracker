"""
FinAI Settings — API health checks, database management, backup/restore, and preferences.
"""

import streamlit as st
import os
import shutil
import sqlite3
import logging
from datetime import datetime

from utils.database import (
    initialize_database, get_database_stats,
    reset_database, export_csv
)

logger = logging.getLogger(__name__)

DB_PATH = "expenses.db"
BACKUP_PATH = "expenses_backup.db"

st.set_page_config(page_title="Settings | FinAI", page_icon="⚙️", layout="wide")
initialize_database()

st.title("⚙️ System Settings")
st.markdown("Manage your API keys, preferences, and database configurations.")

st.divider()

# ── System Status ─────────────────────────────────────────────────────────────
st.subheader("🌐 System Status")
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        if st.button("🔄 Check Gemini API", use_container_width=True):
            with st.spinner("Pinging Gemini..."):
                try:
                    from utils.hf_client import health_check
                    result = health_check()
                    if result["ok"]:
                        st.session_state["ai_status"] = ("🟢 Connected", result["message"])
                    else:
                        st.session_state["ai_status"] = ("🔴 Disconnected", result["message"])
                except Exception as e:
                    st.session_state["ai_status"] = ("🔴 Error", str(e))

        ai_val, ai_msg = st.session_state.get("ai_status", ("⬜ Not Checked", ""))
        st.metric(label="AI Model Status", value=ai_val)
        if ai_msg:
            st.caption(ai_msg)
        else:
            st.caption("Model: Qwen/Qwen2.5-VL-7B-Instruct · Provider: auto (deepinfra/together) · HuggingFace Inference API.")

with col2:
    with st.container(border=True):
        db_ok = os.path.exists(DB_PATH)
        db_status = "🟢 Healthy" if db_ok else "🔴 Missing"
        stats = get_database_stats()
        try:
            sqlite_ver = sqlite3.sqlite_version
        except Exception:
            sqlite_ver = "?"
        st.metric(label="Database Status", value=db_status, delta=f"SQLite v{sqlite_ver}")
        st.caption(f"{stats['count']} records · ${stats['total']:,.2f} total")

with col3:
    with st.container(border=True):
        api_key = os.getenv("GOOGLE_API_KEY", "")
        env_status = "🟢 Verified" if api_key else "🔴 Missing"
        st.metric(label="Environment Variables", value=env_status)
        if api_key:
            masked = api_key[:6] + "…" + api_key[-4:]
            st.caption(f"GOOGLE_API_KEY loaded: `{masked}`")
        else:
            st.caption("⚠️ Set GOOGLE_API_KEY in your .env file.")

st.divider()

# ── App Preferences ───────────────────────────────────────────────────────────
st.subheader("⚙️ App Preferences")
pref_col1, pref_col2 = st.columns(2)

with pref_col1:
    currency = st.selectbox("Base Currency Symbol", ["USD ($)", "EUR (€)", "GBP (£)", "INR (₹)"])
    rows_per_page = st.slider("Rows per page in history view", min_value=10, max_value=100, value=25)

with pref_col2:
    ai_mode = st.radio("Gemini Accuracy Mode", [
        "Gemini Flash (Faster response times)",
        "Gemini Pro (Deep, high-accuracy processing)"
    ])
    st.toggle("Automatically split items matching single line invoices", value=True)

st.divider()

# ── Database Management ───────────────────────────────────────────────────────
st.subheader("💾 Database Management")
db_col1, db_col2 = st.columns(2)

with db_col1:
    st.markdown("##### 📁 Backup & Export")
    st.write("Save your expense history and database to offline files.")

    if st.button("📦 Create Database Backup", use_container_width=True):
        try:
            shutil.copy2(DB_PATH, BACKUP_PATH)
            st.success(f"Backup created: `{BACKUP_PATH}`")
        except Exception as e:
            st.error(f"Backup failed: {e}")

    csv_data = export_csv()
    st.download_button(
        label="📥 Export All Expenses (CSV)",
        data=csv_data or "",
        file_name=f"finai_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not bool(csv_data),
    )

    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            db_bytes = f.read()
        st.download_button(
            label="💾 Download Database File",
            data=db_bytes,
            file_name="expenses.db",
            mime="application/octet-stream",
            use_container_width=True,
        )

with db_col2:
    st.markdown("##### ⚠️ Destructive Actions")
    st.write("Restore from backup or clear all data.")

    uploaded_backup = st.file_uploader(
        "Restore from backup (.db file)", type=["db"], key="restore_upload"
    )
    if uploaded_backup:
        if st.button("⏪ Restore Database", use_container_width=True):
            try:
                with open(DB_PATH, "wb") as f:
                    f.write(uploaded_backup.read())
                st.success("Database restored successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Restore failed: {e}")

    with st.popover("🚨 Factory Reset Application Data", use_container_width=True):
        st.markdown("#### Are you completely sure?")
        st.write("This deletes **all** saved expenses from `expenses.db` permanently.")
        if st.button("Yes, Clear Everything", type="primary", use_container_width=True):
            try:
                reset_database()
                st.success("Database reset complete. All expenses deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

st.divider()

# ── About ─────────────────────────────────────────────────────────────────────
st.subheader("ℹ️ About FinAI")
about_col1, about_col2 = st.columns([2, 1])
with about_col1:
    st.markdown("""
    * **App Version:** v1.0.0
    * **AI Engine:** `Qwen/Qwen2.5-VL-7B-Instruct` via HuggingFace Inference API (provider: auto)
    * **UI Framework:** Streamlit
    * **Database:** SQLite via Python `sqlite3`
    """)
with about_col2:
    st.markdown(
        "<div style='text-align: right; color: gray; padding-top: 20px;'>Released under the MIT License.</div>",
        unsafe_allow_html=True
    )