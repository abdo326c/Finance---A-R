# pages/policies.py
import base64
import streamlit as st

from auth import require_role
from models import get_db, PolicyDocument

if not st.session_state.get('authenticated'):
    st.switch_page("app.py")
    
def render():
    st.subheader("📚 University Financial Policies & Documents")
    action = st.radio("Action:", ["📂 View & Download", "📤 Upload New Document (Admin Only)"], horizontal=True)

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
                c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
                c1.markdown(
                    f"📄 **{doc.title}** <br>"
                    f"<small>Uploaded by {doc.uploaded_by} on "
                    f"{doc.uploaded_at.strftime('%Y-%m-%d')}</small>",
                    unsafe_allow_html=True,
                )
                if c2.button("👁️ View", key=f"view_{doc.id}"):
                    st.session_state["view_doc_id"] = doc.id
                c3.download_button("⬇️ Download", data=doc.file_data,
                                   file_name=doc.file_name, mime="application/pdf",
                                   key=f"dl_{doc.id}")
                if st.session_state.get("user_role") == "Admin":
                    if c4.button("🗑️ Delete", key=f"del_{doc.id}"):
                        if st.session_state.get(f"confirm_del_{doc.id}"):
                            db.delete(doc)
                            db.commit()
                            st.rerun()
                        else:
                            st.session_state[f"confirm_del_{doc.id}"] = True
                            st.warning(f"Click Delete again to confirm removing '{doc.title}'.")

            if st.session_state.get("view_doc_id"):
                doc_v = db.get(PolicyDocument, st.session_state["view_doc_id"])
                if doc_v:
                    st.markdown(f"---\n### 👀 Viewing: {doc_v.title}")
                    if st.button("❌ Close"):
                        st.session_state["view_doc_id"] = None
                        st.rerun()
                    b64 = base64.b64encode(doc_v.file_data).decode()
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64}" '
                        f'width="100%" height="800" type="application/pdf"></iframe>',
                        unsafe_allow_html=True,
                    )

    else:
        require_role("Admin")
        with st.form("upload_doc_form", clear_on_submit=True):
            title    = st.text_input("Document Title *")
            doc_year = st.selectbox("Academic Year *",
                                    [f"{y}/{y+1}" for y in range(2020, 2030)], index=5)
            pdf_file = st.file_uploader("Select PDF *", type=["pdf"])
            if st.form_submit_button("📤 Upload"):
                if not title or not pdf_file:
                    st.error("Title and PDF file are required.")
                else:
                    with get_db() as db:
                        try:
                            db.add(PolicyDocument(
                                title=title, academic_year=doc_year,
                                file_name=pdf_file.name, file_data=pdf_file.read(),
                                uploaded_by=st.session_state.get("logged_in_user"),
                            ))
                            db.commit()
                            st.session_state["flash_msg"] = "Document uploaded successfully!"
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error("Upload failed. Please try again.")
                            st.exception(e)
