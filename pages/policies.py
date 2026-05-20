# pages/policies.py
import streamlit as st

from auth import require_role
from models import get_db, PolicyDocument

if not st.session_state.get("authenticated"):
    st.switch_page("app.py")


def render():
    st.subheader("📚 University Financial Policies & Documents")
    action = st.radio(
        "Action:",
        ["📂 View & Download", "📤 Upload New Document (Admin Only)"],
        horizontal=True,
    )

    if action == "📂 View & Download":
        with get_db() as db:
            existing_years = sorted(
                {y[0] for y in db.query(PolicyDocument.academic_year).distinct().all()}
                | {"2022/2023", "2025/2026"},
                reverse=True,
            )
            sel_year = st.selectbox("Filter by Academic Year:", existing_years)
            docs = (
                db.query(PolicyDocument)
                .filter_by(academic_year=sel_year)
                .order_by(PolicyDocument.uploaded_at.desc())
                .all()
            )
            if not docs:
                st.warning("⚠️ No documents uploaded for this year yet.")
                return

            for doc in docs:
                c1, c2, c3 = st.columns([5, 1, 1])
                c1.markdown(
                    f"📄 **{doc.title}** <br>"
                    f"<small>Uploaded by {doc.uploaded_by} on "
                    f"{doc.uploaded_at.strftime('%Y-%m-%d')}</small>",
                    unsafe_allow_html=True,
                )

                c2.download_button(
                    "⬇️ Download",
