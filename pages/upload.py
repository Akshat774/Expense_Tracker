import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Upload Expense | FinAI", page_icon="📤", layout="wide")
st.title("📤 Upload New Expense")
st.markdown("Choose a method below to add your receipt.")

# Ingestion Tabs
tab_upload, tab_camera, tab_paste = st.tabs([
    "📂 Upload File", 
    "📸 Camera Capture", 
    "✍️ Paste Text"
])

uploaded_file = None
pasted_text = ""

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload a receipt or invoice", 
        type=["png", "jpg", "jpeg", "webp", "pdf", "txt"],
        help="Supports images, PDFs, and plain text files."
    )

with tab_camera:
    uploaded_file = st.camera_input("Take a photo of the receipt")

with tab_paste:
    pasted_text = st.text_area("Paste receipt text here...", height=150)

st.divider()

# Side-by-Side Layout
if uploaded_file or pasted_text:
    col_left, col_right = st.columns([1, 1], gap="large")
    
    # --- LEFT COLUMN: PREVIEW ---
    with col_left:
        st.subheader("🖼️ File Preview")
        with st.container(border=True):
            if uploaded_file:
                if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg", "image/webp"]:
                    st.image(uploaded_file, use_container_width=True, caption="Uploaded Image")
                elif uploaded_file.type == "application/pdf":
                    st.info(f"📄 PDF Loaded: **{uploaded_file.name}**")
                    st.caption("PDF preview is ready for AI extraction.")
                else:
                    st.text_area("File Content", value=uploaded_file.read().decode("utf-8"), height=300, disabled=True)
            elif pasted_text:
                st.info("✍️ Manually Pasted Text")
                st.text(pasted_text)
                
        st.button("✨ Extract with Gemini", type="primary", use_container_width=True)

    # --- RIGHT COLUMN: AI EXTRACTION ---
    with col_right:
        st.subheader("🤖 AI Extraction Results")
        
        # Status & Confidence Badge
        status_col, confidence_col = st.columns(2)
        with status_col:
            st.markdown("**Status:** 🟢 Extraction Complete")
        with confidence_col:
            st.markdown("**Confidence:** :green[94.2%]")
            
        # Editable Form Fields
        with st.container(border=True):
            merchant = st.text_input("Merchant Name", value="Acme Cloud Solutions")
            
            meta_col1, meta_col2 = st.columns(2)
            with meta_col1:
                date_val = st.date_input("Transaction Date", datetime.date(2026, 6, 15))
            with meta_col2:
                category = st.selectbox("Category", [
                    "Software / SaaS", "Travel & Transit", "Meals & Entertainment", "Office Utilities"
                ], index=0)
                
            # Editable Itemized Table
            st.markdown("**Itemized Items**")
            mock_items = pd.DataFrame([
                {"Description": "API Core Subscription", "Quantity": 1, "Unit Price": 120.00, "Total": 120.00},
                {"Description": "Cloud Storage Addon", "Quantity": 5, "Unit Price": 15.00, "Total": 75.00}
            ])
            edited_items = st.data_editor(mock_items, num_rows="dynamic", use_container_width=True)
            
            # Totals
            tax_col, total_col = st.columns(2)
            with tax_col:
                tax = st.number_input("Tax / Fees", value=15.60, step=0.01)
            with total_col:
                total = st.number_input("Total Amount", value=210.60, step=0.01)

        # Raw JSON Expander
        with st.expander("🛠️ View Raw JSON Response"):
            st.json({
                "merchant": "Acme Cloud Solutions",
                "date": "2026-06-15",
                "confidence_score": 0.942,
                "model_used": "gemini-2.5-flash"
            })

        # Action Buttons
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            st.button("💾 Save Expense", type="primary", use_container_width=True)
        with btn_col2:
            st.button("🔄 Reset", type="secondary", use_container_width=True)
        with btn_col3:
            st.button("❌ Cancel", type="secondary", use_container_width=True)
else:
    st.info("💡 Please upload a file, take a picture, or paste text to begin extraction.")