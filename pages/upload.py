"""
FinAI Upload Page — Extract expenses from images, PDFs, text files, or pasted text.
Powered by Google Gemini 2.5 Flash via Google AI Studio.
"""

import streamlit as st
import pandas as pd
import datetime
import logging
from io import BytesIO

from utils.database import initialize_database, insert_expense
from utils.image_utils import (
    auto_orient, rotate_image, resize_if_needed,
    compress_image, image_to_buffer
)
from utils.pdf_utils import process_pdf
from utils.text_utils import extract_text_from_txt
from utils import gemini_client
from utils.prompts import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Upload Expense | FinAI", page_icon="📤", layout="wide")
initialize_database()

st.title("📤 Upload New Expense")
st.markdown("Upload a receipt or invoice and let **Gemini 2.5 Flash** extract the data instantly.")

# ── Ingestion Tabs ──────────────────────────────────────────────────────────
tab_upload, tab_camera, tab_paste = st.tabs([
    "📂 Upload File",
    "📸 Camera Capture",
    "✍️ Paste Text"
])

uploaded_file = None
camera_file   = None
pasted_text   = ""

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload a receipt or invoice",
        type=["png", "jpg", "jpeg", "webp", "pdf", "txt"],
        help="Supports images, PDFs, and plain text files."
    )

with tab_camera:
    camera_file = st.camera_input("Take a photo of the receipt")

with tab_paste:
    pasted_text = st.text_area("Paste receipt text here...", height=150)

active_file = uploaded_file or camera_file
has_input   = bool(active_file or pasted_text.strip())

st.divider()

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("extraction", None),
    ("raw_json", None),
    ("preview_image", None),      # PIL Image after auto-orient
    ("last_file_id", None),       # track file identity to reset on new upload
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Detect new file upload and auto-orient immediately ────────────────────────
if active_file:
    mime = getattr(active_file, "type", "image/jpeg")
    is_image = mime in ["image/png", "image/jpeg", "image/jpg", "image/webp"]

    # Use file name + size as a stable identity key
    file_id = f"{getattr(active_file, 'name', 'camera')}_{getattr(active_file, 'size', 0)}"

    if is_image and st.session_state.last_file_id != file_id:
        # New image uploaded — run auto-orient and cache the result
        active_file.seek(0)
        st.session_state.preview_image = auto_orient(active_file)
        st.session_state.last_file_id  = file_id
        active_file.seek(0)


# ── Layout ────────────────────────────────────────────────────────────────────
if has_input:
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── LEFT: Preview ─────────────────────────────────────────────────────────
    with col_left:
        st.subheader("🖼️ File Preview")
        with st.container(border=True):
            if active_file:
                mime = getattr(active_file, "type", "image/jpeg")
                is_image = mime in ["image/png", "image/jpeg", "image/jpg", "image/webp"]

                if is_image and st.session_state.preview_image is not None:
                    img = st.session_state.preview_image
                    w, h = img.size

                    # Display the preview image
                    st.image(
                        img,
                        use_container_width=True,
                        caption=f"Preview — {w}×{h}px  |  Use buttons below to rotate if needed",
                    )

                    # Manual rotation controls
                    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                    with r_col1:
                        if st.button("↺ 90° CCW", use_container_width=True, key="rot_ccw"):
                            st.session_state.preview_image = rotate_image(
                                st.session_state.preview_image, 90
                            )
                            st.rerun()
                    with r_col2:
                        if st.button("↻ 90° CW", use_container_width=True, key="rot_cw"):
                            st.session_state.preview_image = rotate_image(
                                st.session_state.preview_image, -90
                            )
                            st.rerun()
                    with r_col3:
                        if st.button("↕ Flip 180°", use_container_width=True, key="rot_180"):
                            st.session_state.preview_image = rotate_image(
                                st.session_state.preview_image, 180
                            )
                            st.rerun()
                    with r_col4:
                        if st.button("⟳ Reset", use_container_width=True, key="rot_reset"):
                            active_file.seek(0)
                            st.session_state.preview_image = auto_orient(active_file)
                            active_file.seek(0)
                            st.rerun()

                elif mime == "application/pdf":
                    st.info(f"📄 PDF Loaded: **{active_file.name}**")
                    st.caption("PDF ready for AI extraction.")
                else:
                    active_file.seek(0)
                    st.text_area(
                        "File Content",
                        value=active_file.read().decode("utf-8", errors="replace"),
                        height=300,
                        disabled=True,
                    )
            elif pasted_text:
                st.info("✍️ Manually Pasted Text")
                st.text(pasted_text[:2000])

        # Extract button
        if st.button("✨ Extract with Gemini", type="primary", use_container_width=True):
            with st.spinner("Analyzing with Gemini 2.5 Flash..."):
                try:
                    result = None

                    if active_file:
                        mime = getattr(active_file, "type", "")
                        is_image = mime in ["image/png", "image/jpeg", "image/jpg", "image/webp"]

                        if is_image:
                            # Use the session-state image (with user rotations applied)
                            img = st.session_state.preview_image
                            if img is None:
                                active_file.seek(0)
                                img = auto_orient(active_file)

                            img_resized = resize_if_needed(img)
                            compressed  = compress_image(img_resized)
                            result = gemini_client.extract_from_image(compressed)

                        elif mime == "application/pdf":
                            active_file.seek(0)
                            text, image_buffers = process_pdf(active_file)
                            if text:
                                result = gemini_client.extract_from_text(text)
                            elif image_buffers:
                                result = gemini_client.extract_from_image(image_buffers[0])
                            else:
                                st.error("Could not extract content from this PDF.")

                        elif mime == "text/plain":
                            active_file.seek(0)
                            text = extract_text_from_txt(active_file)
                            result = gemini_client.extract_from_text(text)

                    elif pasted_text.strip():
                        result = gemini_client.extract_from_text(pasted_text)

                    if result:
                        st.session_state.extraction = result
                        st.session_state.raw_json   = result.model_dump()
                        st.success("✅ Extraction complete!")

                except EnvironmentError:
                    st.error(
                        "🔑 **GOOGLE_API_KEY not found.**\n\n"
                        "Add this to your `.env` file:\n"
                        "```\nGOOGLE_API_KEY=your_key_here\n```\n"
                        "Get a free key at: https://aistudio.google.com/apikey"
                    )
                except Exception as e:
                    err = str(e)
                    if any(k in err.lower() for k in ["api_key", "invalid", "401", "403"]):
                        st.error(f"🔑 **API key invalid or expired.**\n\nError: {err}")
                    elif "429" in err or "quota" in err.lower():
                        st.error("⚠️ **Rate limit hit.** Wait a moment and try again.")
                    elif "500" in err or "503" in err:
                        st.error("🔄 **Gemini temporarily unavailable.** Try again in a few seconds.")
                    else:
                        st.error(f"Extraction failed: {err}")
                    logger.exception("Gemini extraction error")

    # ── RIGHT: Results / Edit Form ────────────────────────────────────────────
    with col_right:
        st.subheader("🤖 AI Extraction Results")
        ext = st.session_state.extraction

        if ext is None:
            st.info("Click **✨ Extract with Gemini** on the left to begin.")
        else:
            conf     = ext.confidence_score or 0.0
            conf_pct = f"{conf * 100:.1f}%"
            status_col, confidence_col = st.columns(2)
            with status_col:
                st.markdown("**Status:** 🟢 Extraction Complete")
            with confidence_col:
                color = "green" if conf >= 0.85 else "orange" if conf >= 0.60 else "red"
                st.markdown(f"**Confidence:** :{color}[{conf_pct}]")

            with st.container(border=True):
                merchant = st.text_input("Merchant Name", value=ext.merchant_name or "")

                meta_col1, meta_col2 = st.columns(2)
                with meta_col1:
                    try:
                        date_default = (
                            datetime.date.fromisoformat(ext.transaction_date)
                            if ext.transaction_date else datetime.date.today()
                        )
                    except ValueError:
                        date_default = datetime.date.today()
                    date_val = st.date_input("Transaction Date", value=date_default)
                    if ext.transaction_time:
                        st.caption(f"🕐 Time: {ext.transaction_time}")

                with meta_col2:
                    cat_options = ALLOWED_CATEGORIES
                    cat_idx = (
                        cat_options.index(ext.category)
                        if ext.category in cat_options else 0
                    )
                    category = st.selectbox("Category", cat_options, index=cat_idx)

                currency       = st.text_input("Currency", value=ext.currency or "")
                payment_method = st.text_input(
                    "Payment Method",
                    value="" if (ext.payment_method or "").lower() == "null"
                    else (ext.payment_method or "")
                )

                st.markdown("**Itemized Items**")
                items_data = [
                    {
                        "Description": li.description or "",
                        "Quantity":    li.quantity or 1,
                        "Unit Price":  li.unit_price or 0.0,
                        "Total":       li.line_total or 0.0,
                    }
                    for li in ext.line_items
                ] if ext.line_items else []
                items_df = (
                    pd.DataFrame(items_data) if items_data
                    else pd.DataFrame(columns=["Description", "Quantity", "Unit Price", "Total"])
                )
                edited_items = st.data_editor(
                    items_df, num_rows="dynamic", use_container_width=True
                )

                if ext.tax_breakdown:
                    st.markdown("**Tax Breakdown**")
                    for tb in ext.tax_breakdown:
                        label = tb.tax_name or "Tax"
                        rate  = f" ({tb.rate_percent}%)" if tb.rate_percent else ""
                        amt   = tb.amount or 0.0
                        st.caption(f"• {label}{rate}: {ext.currency or ''} {amt:.2f}")

                tax_col, total_col = st.columns(2)
                with tax_col:
                    tax   = st.number_input("Tax / Fees",    value=float(ext.tax_amount   or 0.0), step=0.01)
                with total_col:
                    total = st.number_input("Total Amount",  value=float(ext.total_amount  or 0.0), step=0.01)

                disc_col, sub_col = st.columns(2)
                with disc_col:
                    discount = st.number_input("Discount",   value=float(ext.discount_amount or 0.0), step=0.01)
                with sub_col:
                    subtotal = st.number_input("Subtotal",   value=float(ext.subtotal       or 0.0), step=0.01, disabled=True)

            with st.expander("🛠️ View Raw JSON Response"):
                st.json(st.session_state.raw_json or {})

            btn_col1, btn_col2, btn_col3 = st.columns(3)

            with btn_col1:
                if st.button("💾 Save Expense", type="primary", use_container_width=True):
                    line_items_list = [
                        {
                            "description": row.get("Description", ""),
                            "quantity":    row.get("Quantity", 1),
                            "unit_price":  row.get("Unit Price", 0.0),
                            "line_total":  row.get("Total", 0.0),
                        }
                        for _, row in edited_items.iterrows()
                    ]
                    expense_data = {
                        "merchant_name":    merchant,
                        "transaction_date": str(date_val),
                        "transaction_time": ext.transaction_time,
                        "category":         category,
                        "currency":         currency,
                        "payment_method":   payment_method,
                        "subtotal":         subtotal,
                        "discount_amount":  discount,
                        "tax_amount":       tax,
                        "total_amount":     total,
                        "confidence_score": conf,
                        "line_items":       line_items_list,
                        "tax_breakdown":    [
                            tb.model_dump() for tb in (ext.tax_breakdown or [])
                        ],
                        "merchant_address": ext.merchant_address,
                        "invoice_number":   ext.invoice_number,
                    }
                    try:
                        new_id = insert_expense(expense_data)
                        st.success(f"✅ Expense saved! (ID: {new_id})")
                        st.session_state.extraction    = None
                        st.session_state.raw_json      = None
                        st.session_state.preview_image = None
                        st.session_state.last_file_id  = None
                    except Exception as e:
                        st.error(f"Failed to save: {e}")

            with btn_col2:
                if st.button("🔄 Reset", type="secondary", use_container_width=True):
                    st.session_state.extraction    = None
                    st.session_state.raw_json      = None
                    st.session_state.preview_image = None
                    st.session_state.last_file_id  = None
                    st.rerun()

            with btn_col3:
                if st.button("❌ Cancel", type="secondary", use_container_width=True):
                    st.session_state.extraction = None
                    st.rerun()

else:
    st.info("💡 Please upload a file, take a picture, or paste text to begin extraction.")