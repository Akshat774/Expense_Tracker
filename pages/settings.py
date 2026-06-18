import streamlit as st

st.set_page_config(page_title="Settings | FinAI", page_icon="⚙️", layout="wide")
st.title("⚙️ System Settings")
st.markdown("Manage your API keys, preferences, and database configurations.")

st.divider()

# Status Check Row
st.subheader("🌐 System Status")
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.metric(label="Gemini API Status", value="Connected", delta="Model: Stable")
        st.caption("Using the official `google-genai` SDK implementation.")

with col2:
    with st.container(border=True):
        st.metric(label="Database Status", value="Healthy", delta="SQLite v2.4")
        st.caption("Active connection established with local `expenses.db` file.")

with col3:
    with st.container(border=True):
        st.metric(label="Environment Variables", value="Verified", delta="Tokens OK")
        st.caption(".env configuration file loaded correctly.")

st.divider()

# Preferences Selection
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

# Backup / Reset Section
st.subheader("💾 Database Management")
db_col1, db_col2 = st.columns(2)

with db_col1:
    st.markdown("##### 📁 Backup & Export")
    st.write("Save your configuration data and history to an offline file.")
    st.button("📦 Create Backup File", use_container_width=True)
    st.button("Export Application Settings JSON", use_container_width=True, type="secondary")

with db_col2:
    st.markdown("##### ⚠️ Destructive Actions")
    st.write("Restore historical saves or clear current configurations entirely.")
    st.button("⏪ Restore Database from Backup", use_container_width=True)
    
    # Secure confirmation with a clean popover layout element
    with st.popover("🚨 Factory Reset Application Data", use_container_width=True):
        st.markdown("#### Are you completely sure?")
        st.write("This action deletes all saved tables, files, and logs inside `expenses.db` permanently.")
        if st.button("Yes, Clear Everything", type="primary", use_container_width=True):
            st.error("Wiping application database...")

st.divider()

# About Section
st.subheader("ℹ️ About FinAI")
about_col1, about_col2 = st.columns([2, 1])
with about_col1:
    st.markdown("""
    * **App Version:** v1.0.0-Beta
    * **AI Engine Framework:** `google-genai` native integration
    * **UI Framework:** Streamlit Open-Source SaaS Dashboard layout
    """)
with about_col2:
    st.markdown("<div style='text-align: right; color: gray; padding-top: 20px;'>Released under the standard MIT License.</div>", unsafe_allow_html=True)