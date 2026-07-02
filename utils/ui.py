"""
Shared UI helpers for applying the FinAI theme across all Streamlit pages.
"""

from pathlib import Path

import streamlit as st


def apply_theme() -> None:
    """Inject the shared CSS theme into the current Streamlit page."""
    css_path = Path(__file__).resolve().parents[1] / "assets" / "styles.css"

    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <style>
                .main .block-container { padding-top: 2rem; padding-bottom: 2.5rem; max-width: 1220px; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(active_page: str | None = None) -> None:
    """Render the shared branded sidebar for every page."""
    st.sidebar.markdown("## FinAI Tracker")
    st.sidebar.markdown("AI expense tracking powered by **Gemini**.")
    st.sidebar.markdown(
        """
        <div class="section-panel" style="margin:1rem 0 1.1rem 0;">
            <div class="section-label" style="margin-bottom:0.45rem;">Workspace</div>
            <div style="color:var(--text-primary);font-weight:600;line-height:1.55;">
                Track receipts, review spend, and manage your data from one place.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    st.sidebar.markdown("### Navigation")

    nav_items = [
        ("Dashboard", "app.py", "🏠"),
        ("Upload Expense", "pages/upload.py", "📤"),
        ("Analytics", "pages/analytics.py", "📊"),
        ("Expense History", "pages/expense_history.py", "📜"),
        ("Settings", "pages/settings.py", "⚙️"),
    ]

    for label, page_path, icon in nav_items:
        is_active = active_page == page_path
        st.sidebar.page_link(page_path, label=label, icon=icon)
        if is_active:
            st.sidebar.markdown(
                "<div style='height:4px;margin:-8px 0 8px 0;border-radius:999px;background:linear-gradient(90deg,#22c55e,#06b6d4,#8b5cf6);'></div>",
                unsafe_allow_html=True,
            )

    st.sidebar.divider()
    st.sidebar.caption("Fast AI extraction. Clear spending insights. Modern control.")