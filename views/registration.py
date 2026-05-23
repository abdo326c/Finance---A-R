# pages/registration.py
import io
from datetime import datetime
import pandas as pd
import streamlit as st

from config import VALID_COLLEGES, DEFAULT_YEAR
from auth import require_role
from models import get_db, Student, write_audit


def render(engine):
    st.subheader("👤 New Student Registration")
    require_role("Admin", "Editor")

    mode = st.radio("Registration Type:", ["Manual Entry", "Bulk Upload (Excel)"], horizontal=True)

    if mode == "Manual Entry":
        with st.form("manual_reg", clear_on_submit=True):
            st.info(f"Valid college codes: `{', '.join(VALID_COLLEGES)}`")
            c1, c2, c3 = st.columns(3)
            n_id      = c1.number_input("Student ID *", value=None, placeholder="e.g. 26100123", step=1, format="%d")
            n_name    = c2.text_input("Full Name *")
            n_college = c3.selectbox("College *", VALID_COLLEGES)
            c4, c5, c6 = st.columns(3)
            n_program = c4.text_input("Program")
            n_price   = c5.number_input("Price / Credit Hour (EGP) *", min_value=0.0, step=100.0)
            n_email   = c6.text_input("University Email")
            c7, c8, c9 = st.columns(3)
            n_mobile  = c7.text_input("Mobile")
            n_nat_id  = c8.text_input("National ID")
            n_nat     = c9.text_input("Nationality", value="Egyptian")
            c10, c11  = st.columns(2)
            n_dob     = c10.date_input("Birth Date", min_value=datetime(1990,1,1), value=datetime(2005,1,1))
            n_admit   = c11.number_input("Admit Year", value=DEFAULT_YEAR, step=1)

            if st.form_submit_button("💾 Register Student"):
                if n_id is None or not n_name or not n_college:
                    st.error("Student ID, Name, and College are required.")
                else:
                    with get_db() as db:
                        if db.get(Student, int(n_id)):
                            st.error(f"Student ID {n_id} already exists.")
                        else:
                            try:
                                db.add(Student(
                                    id=int(n_id), name=n_name, college=n_college,
                                    program=n_program, price_per_hr=n_price,
                                    email=n_email, mobile=n_mobile,
                                    national_id=n_nat_id, nationality=n_nat,
                                    admit_year=int(n_admit), birth_date=n_dob,
                                ))
                                write_audit(db, st.session_state["logged_in_user"],
                                            "REGISTER_STUDENT", f"student_id={n_id}", n_name)
                                db.commit()
                                st.cache_data.clear()
                                st.session_state["flash_msg"] = f"Student '{n_name}' registered!"
                                st.rerun()
                            except Exception:
                                db.rollback()
                                st.error("Registration failed. The ID may already be in use.")

    else:  # Bulk
        tpl = {"ID":26100123,"Name":"Ahmed Ali","College":"ENG","Program":"Computer Eng",
               "Price Per Hr":4600.0,"Email":"ahmed@nu.edu.eg","Mobile":"01000000000",
               "National ID":"29901010000000","Nationality":"Egyptian",
               "Admit Year":DEFAULT_YEAR,"Birth Date":"2005-01-01"}
        buf = io.BytesIO()
        pd.DataFrame([tpl]).to_excel(buf, index=False)
        st.download_button("📥 Download Template", buf.getvalue(), file_name="Template_Students.xlsx")

        upl = st.file_uploader("Upload Students Excel", type=["xlsx"])
        if upl and st.button("🚀 Process"):
            df_s = pd.read_excel(upl)
            df_s.columns = [str(c).strip() for c in df_s.columns]
            total = len(df_s)
            prog  = st.progress(0)
            ph    = st.empty()

            with get_db() as db:
                existing = {s[0] for s in db.query(Student.id).all()}
                new_students, failed, count = [], [], 0
                for i, row in df_s.iterrows():
                    sid     = int(row.get("ID",0)) if pd.notnull(row.get("ID")) else 0
                    orig    = row.to_dict()
                    college = str(row.get("College","")).strip().upper()
                    if sid <= 0 or sid in existing:
                        orig["Error Reason"] = "Invalid or duplicate ID"
                        failed.append(orig)
                    elif college not in VALID_COLLEGES:
                        orig["Error Reason"] = f"Invalid college '{college}'"
                        failed.append(orig)
                    else:
                        bd = pd.to_datetime(row.get("Birth Date"), errors="coerce")
                        new_students.append(Student(
                            id=sid, name=str(row.get("Name","Unknown")),
                            college=college, program=str(row.get("Program","")),
                            price_per_hr=float(row.get("Price Per Hr",0.0)),
                            email=str(row.get("Email","")), mobile=str(row.get("Mobile","")),
                            national_id=str(row.get("National ID","")),
                            nationality=str(row.get("Nationality","Egyptian")),
                            admit_year=int(row.get("Admit Year", DEFAULT_YEAR)),
                            birth_date=bd.date() if pd.notna(bd) else None,
                        ))
                        count += 1
                    prog.progress((i+1)/total)
                    ph.text(f"Processed {i+1}/{total}…")

                if new_students:
                    try:
                        db.add_all(new_students)
                        write_audit(db, st.session_state["logged_in_user"],
                                    "BULK_REGISTER", "bulk", f"{count} students")
                        db.commit()
                        st.cache_data.clear()
                        st.success(f"✅ Registered {count} students.")
                    except Exception:
                        db.rollback()
                        st.error("Database error. Some records may not have been saved.")
                elif not failed:
                    st.warning("No valid data found in the file.")

            ph.empty()
            if failed:
                st.error(f"⚠️ {len(failed)} rows skipped.")
                st.dataframe(pd.DataFrame(failed), use_container_width=True)
                buf_err = io.BytesIO()
                pd.DataFrame(failed).to_excel(buf_err, index=False)
                st.download_button("⬇️ Download Errors", buf_err.getvalue(),
                                   file_name="Failed_Registrations.xlsx")
