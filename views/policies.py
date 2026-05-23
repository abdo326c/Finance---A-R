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
                c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
                c1.markdown(
                    f"📄 **{doc.title}** <br>"
                    f"<small>Uploaded by {doc.uploaded_by} on "
                    f"{doc.uploaded_at.strftime('%Y-%m-%d')}</small>",
                    unsafe_allow_html=True,
                )

                if c2.button("👁️ View", key=f"view_{doc.id}", use_container_width=True):
                    st.session_state["viewing_pdf_id"] = doc.id
                    st.rerun()

                c3.download_button(
                    "⬇️ Download",
                    data=doc.file_data,
                    file_name=doc.file_name,
                    mime="application/pdf",
                    key=f"dl_{doc.id}",
                    use_container_width=True,
                )

                if st.session_state.get("user_role") == "Admin":
                    if c4.button("🗑️ Delete", key=f"del_{doc.id}", use_container_width=True):
                        if st.session_state.get(f"confirm_del_{doc.id}"):
                            db.delete(doc)
                            db.commit()
                            st.rerun()
                        else:
                            st.session_state[f"confirm_del_{doc.id}"] = True
                            st.warning(f"Click Delete again to confirm removing '{doc.title}'.")

            # Inline PDF Viewer Panel
            view_id = st.session_state.get("viewing_pdf_id")
            if view_id:
                selected_doc = None
                for d in docs:
                    if d.id == view_id:
                        selected_doc = d
                        break
                if selected_doc:
                    st.markdown("<br><hr>", unsafe_allow_html=True)
                    vc1, vc2 = st.columns([6, 1])
                    vc1.markdown(f"### 📖 Viewing Document: **{selected_doc.title}**")
                    if vc2.button("❌ Close Viewer", use_container_width=True, type="secondary"):
                        del st.session_state["viewing_pdf_id"]
                        st.rerun()
                    
                    import os
                    try:
                        # Ensure static directory exists
                        os.makedirs("static", exist_ok=True)
                        
                        # Generate safe unique filename for the logged-in user
                        username = st.session_state.get("logged_in_user", "guest")
                        safe_username = "".join(c for c in username if c.isalnum())
                        filename = f"temp_viewer_{safe_username}.pdf"
                        file_path = os.path.join("static", filename)
                        
                        # Write the PDF bytes to the static folder
                        with open(file_path, "wb") as f:
                            f.write(selected_doc.file_data)
                        
                        # Render the PDF dynamically using the same-origin static URL
                        pdf_display = (
                            f'<iframe src="static/{filename}" '
                            f'width="100%" height="850px" style="border: 1px solid #dcdee6; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);"></iframe>'
                        )
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Could not render PDF inline: {e}")

    else:
        require_role("Admin")
        with st.form("upload_doc_form", clear_on_submit=True):
            title = st.text_input("Document Title *")
            doc_year = st.selectbox(
                "Academic Year *", [f"{y}/{y+1}" for y in range(2020, 2030)], index=5
            )
            pdf_file = st.file_uploader("Select PDF *", type=["pdf"])
            if st.form_submit_button("📤 Upload"):
                if not title or not pdf_file:
                    st.error("Title and PDF file are required.")
                else:
                    with get_db() as db:
                        try:
                            db.add(
                                PolicyDocument(
                                    title=title,
                                    academic_year=doc_year,
                                    file_name=pdf_file.name,
                                    file_data=pdf_file.read(),
                                    uploaded_by=st.session_state.get("logged_in_user"),
                                )
                            )
                            db.commit()
                            st.session_state["flash_msg"] = "Document uploaded successfully!"
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error("Upload failed. Please try again.")
                            st.exception(e)


if __name__ == "__main__":
    render()
